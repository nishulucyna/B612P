"""Pre-demo smoke test: run through the real orchestrator (default http://127.0.0.1:8000).

    python scripts/demo_selftest.py

Checks, in order: orchestrator reachable, board reports Whisper and the LLM on the NPU, a spoken
report (a WAV file) is transcribed on the board, a typed report completes the form and fires the
tool call, and the session can be submitted and reset. Leaves the session reset. Exit code 0 only if
everything passed. Takes about a minute (the LLM needs ~10-15 s per turn).
"""

import os
import sys
import time
import wave
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API = os.getenv("INCIDENT_API", "http://127.0.0.1:8000")
SAMPLE_WAV = ROOT / "qidk" / "Solutions" / "NLPSolution3-AutomaticSpeechRecognition-Whisper" / \
    "Android_App_Whisper" / "app" / "src" / "main" / "android_record_1.wav"

failures = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
    if not ok:
        failures.append(name)
    return ok


def call(method: str, path: str, **kw):
    r = requests.request(method, API + path, timeout=kw.pop("timeout", 120), **kw)
    return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)


def main() -> int:
    print(f"Orchestrator: {API}")
    try:
        code, health = call("GET", "/api/health", timeout=10)
    except requests.RequestException as exc:
        check("orchestrator reachable", False, str(exc))
        return 1
    check("orchestrator reachable", code == 200)

    board = health.get("board") or {}
    eng = health.get("engine", {})
    check("board bridge answers", bool(board), "run scripts/start_demo.bat" if not board else "")
    check("Whisper reported on the NPU", bool(board.get("stt_on_npu")), str(board.get("stt_warning") or ""))
    check("LLM reported on the NPU", bool(board.get("llm_on_npu")), str(board.get("llm_warning") or ""))
    check("engine mode is not the mock", eng.get("mode") in ("device", "auto"), f"mode={eng.get('mode')}")

    call("POST", "/api/reset")

    print("\nSpoken report (WAV file -> board Whisper -> board LLM):")
    if SAMPLE_WAV.exists():
        with wave.open(str(SAMPLE_WAV)) as w:
            ok_fmt = (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
        check("sample WAV is 16 kHz mono 16-bit", ok_fmt)
        t = time.monotonic()
        with open(SAMPLE_WAV, "rb") as f:
            code, resp = call("POST", "/api/audio/turn", files={"file": ("a.wav", f, "audio/wav")})
        check("audio turn accepted", code == 200, f"{time.monotonic() - t:.1f}s")
        if code == 200:
            check("transcript came back", bool(resp.get("user_transcript")), repr(resp.get("user_transcript")))
            check("STT ran on the device", resp["engine"].get("last_stt_backend") == "device")
    else:
        print("  (sample WAV not found, skipped)")
    call("POST", "/api/reset")

    print("\nTyped report (two turns, must ask a follow-up, then complete):")
    t = time.monotonic()
    code, r1 = call("POST", "/api/text/turn", json={"text": "A pipe burst on the second floor!"})
    check("turn 1 accepted", code == 200, f"{time.monotonic() - t:.1f}s")
    if code == 200:
        check("turn 1 asks a follow-up (status collecting)", r1["state"]["status"] == "collecting")
        check("LLM ran on the device", r1["engine"].get("last_llm_backend") == "device")
    t = time.monotonic()
    code, r2 = call("POST", "/api/text/turn", json={"text": "It happened at 2 PM and we turned off the main valve."})
    check("turn 2 accepted", code == 200, f"{time.monotonic() - t:.1f}s")
    if code == 200:
        check("report complete", r2["state"]["status"] == "complete")
        payload = r2["state"].get("tool_call_payload") or {}
        check("tool call populate_incident_form fired", payload.get("function") == "populate_incident_form")
        code, sub = call("POST", "/api/submit", json={})
        check("submit works", code == 200 and sub["state"]["status"] == "submitted")

    code, _ = call("POST", "/api/reset")
    check("reset works", code == 200)

    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED: {', '.join(failures)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
