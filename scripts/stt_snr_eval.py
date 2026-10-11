"""Word error rate of the board's speech recognition against noise. Synthesises sentences with the laptop's SAPI voice
(test material only), mixes in noise at several SNRs and sends the clips to the board's /stt.
Usage: python scripts/stt_snr_eval.py [label]"""
import io, json, os, re, sys, wave, time, urllib.request
import numpy as np
import pyttsx3
from scipy.signal import resample_poly

SENTENCES = [
    "There was a water leak near the conference room yesterday at three PM.",
    "A forklift hit a shelf in warehouse two and the operator was slightly injured.",
    "The fire alarm went off in building four and everyone was evacuated.",
    "Maria Lopez slipped on a wet floor near the cafeteria this morning.",
    "We shut down the compressor and called maintenance immediately.",
    "A chemical spill occurred in laboratory six at about nine thirty.",
]
SNRS = [None, 20, 10, 5]
URL = "http://127.0.0.1:8080/stt"

def synth(text, path):
    e = pyttsx3.init(); e.save_to_file(text, path); e.runAndWait()

def load16k(path):
    with wave.open(path) as w:
        sr, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)
    if ch > 1: x = x.reshape(-1, ch).mean(1)
    if sr != 16000:
        from math import gcd
        g = gcd(sr, 16000); x = resample_poly(x, 16000 // g, sr // g)
    return x / 32768.0

def to_wav(x):
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return b.getvalue()

def words(s): return re.findall(r"[a-z0-9']+", s.lower())

def wer(ref, hyp):
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        p, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            t = d[j]; d[j] = min(d[j] + 1, d[j - 1] + 1, p + (r[i - 1] != h[j - 1])); p = t
    return d[len(h)], len(r)

def stt(wav):
    req = urllib.request.Request(URL, wav, {"Content-Type": "audio/wav"})
    t = time.time(); out = json.loads(urllib.request.urlopen(req, timeout=120).read().decode()).get("transcript", "")
    return out, time.time() - t

def main():
    tmp = os.path.join(os.environ.get("TEMP", "."), "stt_eval"); os.makedirs(tmp, exist_ok=True)
    rng = np.random.default_rng(1)
    clips = []
    for i, s in enumerate(SENTENCES):
        p = os.path.join(tmp, f"s{i}.wav")
        if not os.path.exists(p): synth(s, p)
        clips.append(load16k(p))
    print("label:", sys.argv[1] if len(sys.argv) > 1 else "")
    for snr in SNRS:
        errs = tot = 0; times = []; bad = []
        for ref, x in zip(SENTENCES, clips):
            y = x.copy()
            if snr is not None:
                n = rng.standard_normal(len(x)).astype(np.float32)
                n *= np.sqrt(np.mean(x ** 2) / (10 ** (snr / 10)) / np.mean(n ** 2))
                y = x + n
            y *= 0.8 / max(1e-6, np.abs(y).max())
            out, dt = stt(to_wav(y))
            e, n_ = wer(ref, out); errs += e; tot += n_; times.append(dt)
            if e: bad.append(out.strip())
        print(f"SNR {snr if snr is not None else 'clean':>5}: WER {100*errs/tot:5.1f}%  ({errs}/{tot})  avg {np.mean(times):.1f}s/clip  e.g. {bad[0] if bad else ''}")


if __name__ == "__main__":
    main()
