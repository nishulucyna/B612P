"""How many CPU threads does the LLM really need? Restarts the app on the board with different llm_threads values and measures
extraction time, token speeds and real CPU use (CPU-seconds per extraction) on the same two prompts.  python scripts/llm_thread_sweep.py [threads ...]"""
import json, os, sys, time
sys.path.insert(0, ".")
sys.path.insert(0, "scripts")
import npu_proof as P
from backend import agent_brain

PROMPTS = [agent_brain.build_extraction_prompt(t, {}) for t in (
    "There was a water leak near Conference Room 2 around 10 AM. Maintenance has already isolated the area.",
    "A forklift hit a rack in warehouse two yesterday afternoon. Nobody got hurt but we cordoned off the area.")]
levels = [int(x) for x in sys.argv[1:]] or [0, 4, 3, 2, 1]
rows, outputs = [], {}
for t in levels:
    P.adb("shell", "am", "force-stop", P.PKG)
    P.sh("setenforce 0")
    P.adb("logcat", "-c")
    extras = ["--ei", "llm_threads", str(t)] if t else []
    if os.environ.get("LLM_FILE"):
        extras += ["--es", "llm_file", os.environ["LLM_FILE"]]
    P.adb("shell", "am", "start", "-n", f"{P.PKG}/.MainActivity", *extras)
    health = P.wait_ready(480)
    pid = P.pid()
    ticks = lambda: float(P.sh(f"awk '{{print $14+$15}}' /proc/{pid}/stat").strip())
    secs, cpu_s, outs = [], [], []
    for p in PROMPTS:
        c0, u0 = ticks(), P.uptime()
        outs.append(P.post("/llm", json.dumps({"prompt": p}).encode(), "application/json", timeout=600))
        c1, u1 = ticks(), P.uptime()
        secs.append(u1 - u0); cpu_s.append((c1 - c0) / 100.0)
    log = [l for l in P.adb("logcat", "-d", "-s", "NpuBridge:*").splitlines() if "tok/s" in l and "LLM:" in l]
    import re
    dec = [float(m.group(1)) for l in log for m in [re.search(r"decode ([\d.]+) tok/s", l)] if m]
    pre = [float(m.group(1)) for l in log for m in [re.search(r"prefill ([\d.]+) tok/s", l)] if m]
    rows.append(dict(threads=t or 8, seconds=sum(secs) / len(secs), cpu_seconds=sum(cpu_s) / len(cpu_s),
                     avg_cores=sum(cpu_s) / sum(secs), decode=sum(dec) / max(1, len(dec)), prefill=sum(pre) / max(1, len(pre))))
    outputs[t] = outs
    print(f"threads {rows[-1]['threads']:>2}: {rows[-1]['seconds']:5.1f} s/extraction  CPU {rows[-1]['cpu_seconds']:5.1f} cpu-s "
          f"(avg {rows[-1]['avg_cores']:.1f} cores)  decode {rows[-1]['decode']:.1f} tok/s  prefill {rows[-1]['prefill']:.0f} tok/s", flush=True)
base = outputs[levels[0]]
for t in levels[1:]:
    print(f"threads {t or 8}: output identical to baseline: {outputs[t] == base}")
json.dump(rows, open("deliverables/llm_thread_sweep.json", "w"), indent=1)
