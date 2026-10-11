"""Collects hardware evidence that the incident assistant runs on the Snapdragon NPU (Hexagon cDSP/HTP), on the real board.

  python scripts/npu_proof.py [--ab-llm]        -> deliverables/npu_proof_data.json   (then: python scripts/npu_proof_report.py)

Everything is read from the board over adb; nothing is simulated:
  * remoteproc: the cDSP (the NPU subsystem) is running; the audio DSP is a different processor.
  * interrupt counters: `glink-native-cdsp` is the CPU<->NPU message channel. It rises only while the NPU is being given work.
    The audio-DSP counter (`glink-native-adsp`) is the control: it must stay flat.
  * thermal sensors on the NPU itself (nsphvx = HVX vector units, nsphmx = HMX matrix/tensor units) next to CPU load.
  * the app process maps the Hexagon libraries (libSnpeHtpV75Stub, libggml-hexagon, libcdsprpc).
  * A/B: the same encoder on the NPU (w8a16 HTP graph) vs the CPU (fp32 graph), and, with --ab-llm, the same LLM with
    compute_unit NPU vs CPU: speed and CPU cores used.
  * (tried and dropped: running the HTP-prepared graph on the CPU runtime - SNPE happily runs the embedded original graph there,
    so it proves nothing.)"""
import json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("MSYS_NO_PATHCONV", "1")
PKG = "com.b612p.npubridge"
ADB = "adb"
for cand in (Path(os.environ.get("LOCALAPPDATA", "")) / "Android/Sdk/platform-tools/adb.exe",):
    if cand.exists():
        ADB = str(cand)
DEV = "/data/local/tmp"
BRIDGE = "http://127.0.0.1:8080"


def adb(*args, timeout=300):
    r = subprocess.run([ADB, *args], capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    return (r.stdout + (("\n" + r.stderr) if r.returncode and r.stderr else "")).replace("\r", "")


def sh(cmd, timeout=300):
    return adb("shell", cmd, timeout=timeout)


def get(path, timeout=30):
    return urllib.request.urlopen(BRIDGE + path, timeout=timeout).read().decode()


def post(path, body, ctype, timeout=300):
    req = urllib.request.Request(BRIDGE + path, body, {"Content-Type": ctype})
    return urllib.request.urlopen(req, timeout=timeout).read().decode()


def uptime():
    return float(sh("cat /proc/uptime").split()[0])


def pid():
    return sh(f"pidof {PKG}").strip().split()[0]


def wait_ready(seconds=240):
    adb("forward", "tcp:8080", "tcp:8080")
    end = time.time() + seconds
    while time.time() < end:
        try:
            if json.loads(get("/health", 5)).get("ready"):
                return json.loads(get("/health"))
        except Exception:
            pass
        time.sleep(3)
    raise SystemExit("board engines did not become ready")


# ---- static receipts ------------------------------------------------------------------------------------------------
def receipts():
    out = {}
    out["remoteproc"] = [dict(zip(("node", "name", "state"), l.split(None, 2)))
                         for l in sh('for d in /sys/class/remoteproc/remoteproc*; do echo "$d $(cat $d/name) $(cat $d/state)"; done').strip().splitlines()]
    out["device"] = sh("getprop ro.product.model; getprop ro.board.platform; getprop ro.soc.model; getprop ro.build.version.release").split()
    out["soc"] = " / ".join(x.strip() for x in sh("getprop ro.soc.model; getprop ro.board.platform").splitlines() if x.strip())
    p = pid()
    maps = sh(f"grep -i -E 'htp|hexagon|cdsp|SNPE|geniex_plugin' /proc/{p}/maps")
    out["mapped_libs"] = sorted({m.split("/")[-1] for m in re.findall(r"/[^ \n]+\.so", maps)})
    out["rpc_fds"] = sh(f"ls -l /proc/{p}/fd | grep -c dmabuf").strip()
    out["cdsp_irq"] = sh("grep -E 'glink-native-(cdsp|adsp)' /proc/interrupts | awk '{print $NF}'").split()
    out["health"] = json.loads(get("/health"))
    out["wifi"] = sh("dumpsys wifi | grep -m1 'Wi-Fi is'").strip()
    out["app_permissions"] = sorted(set(re.findall(r"android\.permission\.[A-Z_]+", sh(f"dumpsys package {PKG} | grep 'permission.*granted=true'"))))
    out["models"] = {
        "whisper": sh(f"ls -l {DEV}/npu_models/whisper | awk 'NR>1{{print $5, $NF}}'").strip().splitlines(),
        "llm": sh(f"ls -l {DEV}/npu_models/llm | awk 'NR>1{{print $5, $NF}}'").strip().splitlines(),
    }
    return out


# ---- timeline -----------------------------------------------------------------------------------------------------------
def zones():
    z = {}
    for line in sh("for z in /sys/class/thermal/thermal_zone*; do echo \"$z $(cat $z/type)\"; done").strip().splitlines():
        path, typ = line.split()[0], line.split()[-1]
        if typ.startswith("nsp"):
            z[typ] = path
    return dict(sorted(z.items()))


SAMPLER = """#!/system/bin/sh
P=$(pidof %(pkg)s)
while true; do
  T=$(cut -d' ' -f1 /proc/uptime)
  TEMPS=""
%(temps)s
  C=$(grep 'glink-native-cdsp' /proc/interrupts | awk '{s=0;for(i=2;i<=9;i++)s+=$i;print s}')
  A=$(grep 'glink-native-adsp' /proc/interrupts | awk '{s=0;for(i=2;i<=9;i++)s+=$i;print s}')
  U=$(awk '{print $14+$15}' /proc/$P/stat)
  S=$(head -1 /proc/stat | awk '{print $2+$3+$4+$7+$8, $5}')
  echo "$T $C $A $U $S $TEMPS"
  sleep 0.15
done
"""


def start_sampler(zmap):
    temps = "\n".join(f'  TEMPS="$TEMPS $(cat {p}/temp)"' for p in zmap.values())
    script = SAMPLER % dict(pkg=PKG, temps=temps)
    tmp = Path(os.environ.get("TEMP", ".")) / "sampler.sh"
    tmp.write_text(script, newline="\n")
    adb("push", str(tmp), f"{DEV}/sampler.sh")
    sh(f"rm -f {DEV}/samples.txt")
    return subprocess.Popen([ADB, "shell", f"sh {DEV}/sampler.sh > {DEV}/samples.txt"])


def stop_sampler(proc):
    proc.terminate()
    sh("pkill -f sampler.sh")
    time.sleep(0.5)
    raw = sh(f"cat {DEV}/samples.txt")
    rows = []
    for l in raw.strip().splitlines():
        f = l.split()
        if len(f) >= 7:
            try:
                rows.append([float(x) for x in f])
            except ValueError:
                pass
    return rows


def timeline(zmap):
    import stt_snr_eval as S
    from backend import agent_brain
    sentences = S.SENTENCES[:5]
    wavs = []
    for i, s in enumerate(sentences):
        p = os.path.join(os.environ.get("TEMP", "."), "stt_eval", f"s{i}.wav")
        if not os.path.exists(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            S.synth(s, p)
        x = S.load16k(p)
        x = x * (0.8 / max(1e-6, abs(x).max()))
        wavs.append(S.to_wav(x))
    prompts = [agent_brain.build_extraction_prompt(t, {}) for t in (
        "A forklift hit a rack in warehouse two yesterday afternoon and we cordoned off the area.",
        "There was a chemical spill in lab six this morning around nine and we evacuated the room.")]

    proc = start_sampler(zmap)
    phases = []

    def phase(name, fn):
        t0 = uptime()
        detail = fn()
        t1 = uptime()
        phases.append(dict(name=name, t0=t0, t1=t1, detail=detail))

    phase("idle", lambda: time.sleep(6))
    transcripts = []
    phase("speech recognition (Whisper-small, DSP)", lambda: [transcripts.append(json.loads(post("/stt", w, "audio/wav"))["transcript"]) for w in wavs] and transcripts)
    phase("idle", lambda: time.sleep(5))
    outs = []
    phase("language model (Gemma, NPU)", lambda: [outs.append(post("/llm", json.dumps({"prompt": p}).encode(), "application/json")) for p in prompts] and "2 extractions")
    phase("idle", lambda: time.sleep(6))
    rows = stop_sampler(proc)
    return dict(zones=list(zmap), rows=rows, phases=phases, transcripts=transcripts)


# ---- A/B ----------------------------------------------------------------------------------------------------------------
def encoder_ab():
    mel = ROOT / "whisper_build" / "dbg" / "mel.raw"
    fp32 = ROOT / "whisper_build" / "whisper_small_encoder_fp32.dlc"
    if not (mel.exists() and fp32.exists()):
        return None
    sh(f"mkdir -p {DEV}/ws")
    adb("push", str(mel), f"{DEV}/ws/mel.raw")
    if "whisper_small_encoder_fp32.dlc" not in sh(f"ls {DEV}/ws"):
        adb("push", str(fp32), f"{DEV}/ws/whisper_small_encoder_fp32.dlc", timeout=600)
    env = f"cd {DEV} && export LD_LIBRARY_PATH={DEV} ADSP_LIBRARY_PATH='{DEV};/vendor/lib/rfsa/adsp;/vendor/dsp/cdsp'"
    res = {}

    def run(label, container, flag, n):
        sh(f"printf '{DEV}/ws/mel.raw\\n%.0s' $(seq 1 {n}) > {DEV}/ws/list_{n}.txt")
        t = time.time()
        o = sh(f"{env} && ./snpe-net-run --container {container} --input_list ws/list_{n}.txt {flag} --output_dir ws/o_{label} 2>&1 | tail -2", timeout=900)
        return time.time() - t, o.strip()

    for label, container, flag in (("npu", f"{DEV}/npu_models/whisper/whisper_small_encoder_w8a16.dlc", "--use_dsp"),
                                   ("gpu", f"{DEV}/ws/whisper_small_encoder_fp32.dlc", "--use_gpu"),
                                   ("cpu", f"{DEV}/ws/whisper_small_encoder_fp32.dlc", "--runtime_order=cpu")):
        t1, o1 = run(label, container, flag, 1)
        t7, o7 = run(label, container, flag, 7)
        res[label] = dict(one=t1, seven=t7, per_inference=(t7 - t1) / 6, log=o7)
    res["speedup"] = res["cpu"]["per_inference"] / max(1e-6, res["npu"]["per_inference"])
    res["speedup_vs_gpu"] = res["gpu"]["per_inference"] / max(1e-6, res["npu"]["per_inference"])
    return res


def llm_ab():
    from backend import agent_brain
    prompt = agent_brain.build_extraction_prompt(
        "A forklift hit a rack in warehouse two yesterday afternoon and we cordoned off the area.", {})
    res = {}
    for label, extras in (("npu", []), ("cpu", ["--es", "llm_unit", "CPU", "--ez", "allow_cpu_fallback", "true"])):
        adb("shell", "am", "force-stop", PKG)
        sh("setenforce 0")
        adb("logcat", "-c")
        adb("shell", "am", "start", "-n", f"{PKG}/.MainActivity", *extras)
        health = wait_ready(480)
        p = pid()
        t0 = float(sh(f"awk '{{print $14+$15}}' /proc/{p}/stat").strip())
        u0 = uptime()
        post("/llm", json.dumps({"prompt": prompt}).encode(), "application/json", timeout=900)
        u1 = uptime()
        t1 = float(sh(f"awk '{{print $14+$15}}' /proc/{p}/stat").strip())
        log = [l for l in adb("logcat", "-d", "-s", "NpuBridge:*").splitlines() if "LLM:" in l and "tok/s" in l]
        res[label] = dict(llm_status=health.get("llm"), seconds=u1 - u0, cpu_cores=(t1 - t0) / 100.0 / (u1 - u0), log=log[-1:] if log else [])
    adb("shell", "am", "force-stop", PKG)
    sh("setenforce 0")
    adb("shell", "am", "start", "-n", f"{PKG}/.MainActivity")
    wait_ready(480)
    return res


def main():
    out = ROOT / "deliverables" / "npu_proof_data.json"
    if "--encoder-only" in sys.argv:                      # re-measure just the encoder A/B into the existing data file
        data = json.loads(out.read_text())
        data["encoder_ab"] = encoder_ab()
        out.write_text(json.dumps(data, indent=1))
        print(json.dumps({k: (v if k != "log" else "") for k, v in data["encoder_ab"].items() if k in ("speedup", "speedup_vs_gpu")}))
        return
    ab_llm = "--ab-llm" in sys.argv
    health = wait_ready(60)
    print("board ready:", health["stt"], "|", health["llm"][:70], flush=True)
    data = dict(created=time.strftime("%Y-%m-%d %H:%M:%S"), receipts=receipts())
    zmap = zones()
    print("NPU thermal sensors:", list(zmap), flush=True)
    print("timeline (about 45 s) ...", flush=True)
    data["timeline"] = timeline(zmap)
    print("encoder NPU vs CPU ...", flush=True)
    data["encoder_ab"] = encoder_ab()
    if data["encoder_ab"]:
        print("  speedup x%.1f" % data["encoder_ab"]["speedup"], flush=True)
    if ab_llm:
        print("LLM NPU vs CPU (restarts the app twice) ...", flush=True)
        data["llm_ab"] = llm_ab()
    out.write_text(json.dumps(data, indent=1))
    print("wrote", out)


if __name__ == "__main__":
    main()
