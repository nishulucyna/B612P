"""Wait until the HDK bridge reports both models loaded. Used by scripts/start_demo.ps1.

Exit codes: 0 ready, 1 timed out, 2 the board reported a load problem (details printed).
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import npu_runtime  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=240.0)
    args = ap.parse_args()

    deadline = time.monotonic() + args.timeout
    last = None
    while time.monotonic() < deadline:
        st = npu_runtime.npu_status(timeout=3.0)
        if st is None:
            msg = "bridge not answering yet"
        else:
            msg = f"stt_ready={st.get('stt_ready')} llm_ready={st.get('llm_ready')}"
            problems = [p for p in (st.get("stt_warning"), st.get("llm_warning")) if p]
            if st.get("stt_ready") and st.get("llm_ready") and not problems:
                print(f"\n  STT: {st.get('stt')}\n  LLM: {st.get('llm')}")
                return 0
            if problems:
                print("\n  The board reported a problem:")
                for p in problems:
                    print(f"   - {p}")
                print(f"  STT: {st.get('stt')}\n  LLM: {st.get('llm')}")
                return 2
        if msg != last:
            print(f"  waiting... {msg}")
            last = msg
        time.sleep(3)
    print("  timed out waiting for the board")
    return 1


if __name__ == "__main__":
    sys.exit(main())
