"""Start the orchestrator API (backend/server.py). Used by scripts/start_demo.ps1.

Environment: NPU_BACKEND (device | auto | mock), CONTRACT_PATH, TTS_ENABLED - see docs/orchestrator_api.md.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    uvicorn.run("backend.server:app", host=args.host, port=args.port)
