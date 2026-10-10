"""
tests/test_npu_bridge.py
Standalone smoke test for the HDK8650 NPU bridge.

Usage (from the repo root, after scripts/setup_hdk.sh and starting the device app):
  python tests/test_npu_bridge.py [path/to/sample.wav] [--prompt "text"]

Sends a sample .wav to run_stt and a sample prompt to run_llm, prints both outputs,
and feeds the LLM through agent_brain's JSON parser as a format check.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend import npu_runtime  # noqa: E402
from backend.agent_brain import build_extraction_prompt, clean_and_parse_json  # noqa: E402

DEFAULT_WAV = os.path.join(
    os.path.dirname(__file__), "..", "qidk", "Solutions",
    "NLPSolution3-AutomaticSpeechRecognition-Whisper", "Android_App_Whisper",
    "app", "src", "main", "android_record_1.wav",
)
DEFAULT_TRANSCRIPT = (
    "There was a water leak near Conference Room 2 around 10 AM. "
    "Maintenance has already isolated the area."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("wav", nargs="?", default=DEFAULT_WAV)
    ap.add_argument("--prompt", default=None, help="override the LLM extraction prompt")
    args = ap.parse_args()

    print(f"Bridge: {npu_runtime.BASE_URL}  ready={npu_runtime.is_ready()}")

    print(f"\n[STT] {args.wav}")
    transcript = npu_runtime.run_stt(args.wav)
    print(f"Transcript: {transcript!r}")
    assert transcript.strip(), "STT returned an empty transcript"

    prompt = args.prompt or build_extraction_prompt(DEFAULT_TRANSCRIPT, {})
    print("\n[LLM] sending extraction prompt...")
    output = npu_runtime.run_llm(prompt)
    print(f"Raw output:\n{output}")

    parsed = clean_and_parse_json(output)
    print(f"\nParsed JSON keys: {sorted(parsed)}")
    assert parsed, "LLM output did not parse as JSON"

    print("\nNPU bridge OK.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except npu_runtime.NPUBridgeError as e:
        print(f"\nBRIDGE ERROR: {e}")
        sys.exit(2)
