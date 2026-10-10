"""Rehearsal helper: record from the real microphone and see what the board understands.

Usage (repo root, board connected and the app running):
    python scripts/mic_check.py

Speak one sentence, then stop talking. The recorder should stop by itself about 1.5 s after you
finish. Prints how long it listened, how loud you were compared to the room, and what the
board's Whisper (on the NPU) heard. Does not touch the incident session.
"""

import array
import statistics
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import audio_pipeline as ap  # noqa: E402
from backend import npu_runtime  # noqa: E402


def rms(samples) -> float:
    return (sum(v * v for v in samples) / max(1, len(samples))) ** 0.5


def main() -> int:
    out = ROOT / "temp_audio" / "mic_check.wav"
    print("Speak one sentence now (e.g. 'There was a water leak near Conference Room 2 around 10 AM')...")
    started = time.monotonic()
    path = ap.record_audio(str(out), max_seconds=15)
    took = time.monotonic() - started

    with wave.open(path) as w:
        samples = array.array("h")
        samples.frombytes(w.readframes(w.getnframes()))
    blocks = [rms(samples[i:i + ap.BLOCK_SIZE]) for i in range(0, len(samples), ap.BLOCK_SIZE)]
    room = statistics.median(blocks[:5]) if len(blocks) >= 5 else 0.0
    loud = max(blocks) if blocks else 0.0
    threshold = min(max(ap.RMS_THRESHOLD, room * ap.NOISE_MARGIN), ap.MAX_RMS_THRESHOLD)
    print(f"\nCapture path: {ap.last_input_description}")
    print(f"Listened for {took:.1f} s ({len(samples) / ap.SAMPLE_RATE:.1f} s of audio; the cap is 15 s).")
    print(f"Room noise ~{room:.0f}, speech threshold {threshold:.0f}, your loudest 0.1 s ~{loud:.0f}.")
    info = ap.last_recording or {}
    snr = info.get('snr_db')
    if snr is not None:
        verdict = ('excellent' if snr >= 25 else 'good' if snr >= 18 else 'marginal - expect some wrong words' if snr >= 10 else 'poor - recognition will often fail')
        print(f"Signal-to-noise estimate: {snr:.0f} dB ({verdict}).  On the board, tiny Whisper is exact at 25+ dB and unreliable below ~10 dB.")
    elif not info.get('speech_detected', True):
        print('No clear speech was detected. Speak louder or closer to the microphone.')
    if took >= 14.5:
        print("-> It ran to the cap: it never heard a clear pause. Speak closer/louder, or reduce background noise.")
    if loud < threshold:
        print("-> You never got above the threshold: move closer to the microphone or raise its input level.")

    try:
        t = time.monotonic()
        text = npu_runtime.run_stt(path)
        print(f"\nBoard heard ({time.monotonic() - t:.1f} s): {text!r}")
    except Exception as exc:  # noqa: BLE001 - this is a diagnostic tool
        print(f"\nCould not reach the board: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
