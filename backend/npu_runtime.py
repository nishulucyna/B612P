"""
backend/npu_runtime.py
Host-side client for the on-device NPU service running on the Qualcomm HDK8650.

The Android app on the board runs Whisper (ASR) and Llama via Genie on the Hexagon
NPU and serves them over a local HTTP server. `scripts/setup_hdk.sh` forwards
host port 8080 to the device, so everything here talks to localhost only.

Bridge protocol (what the Android service must implement):
  POST /stt   body: raw WAV bytes (Content-Type: audio/wav)
              reply: JSON {"text": "..."} or plain-text transcript
  POST /llm   body: JSON {"prompt": "..."}
              reply: JSON {"text": "..."} or plain-text completion
  GET  /health  reply: 200 when the models are loaded

Public API, called by backend/agent_brain.py:
  run_stt(audio_path: str) -> str
  run_llm(prompt: str) -> str
"""

import json
import os
import urllib.error
import urllib.request

BASE_URL = os.environ.get("NPU_BRIDGE_URL", "http://localhost:8080")
STT_TIMEOUT_S = float(os.environ.get("NPU_STT_TIMEOUT", "60"))
LLM_TIMEOUT_S = float(os.environ.get("NPU_LLM_TIMEOUT", "120"))


class NPUBridgeError(RuntimeError):
    """The device bridge is unreachable or returned an unusable response."""


def _post(path: str, body: bytes, content_type: str, timeout: float) -> str:
    req = urllib.request.Request(
        BASE_URL + path,
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise NPUBridgeError(f"{path} returned HTTP {e.code}: {e.read()[:200]!r}") from e
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise NPUBridgeError(
            f"cannot reach NPU bridge at {BASE_URL}{path} ({e}). "
            "Is the device app running and has scripts/setup_hdk.sh been run?"
        ) from e

    # Accept either {"text": "..."} or a plain-text body.
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip()
    if isinstance(data, dict):
        for key in ("text", "response", "transcript"):
            if isinstance(data.get(key), str):
                return data[key].strip()
    return raw.strip()


def run_stt(audio_path: str) -> str:
    """Transcribe a 16 kHz mono WAV file with Whisper on the device NPU/DSP."""
    with open(audio_path, "rb") as f:
        audio = f.read()
    return _post("/stt", audio, "audio/wav", STT_TIMEOUT_S)


def run_llm(prompt: str) -> str:
    """Generate a completion with Llama (Genie, HTP) on the device NPU."""
    body = json.dumps({"prompt": prompt}).encode("utf-8")
    return _post("/llm", body, "application/json", LLM_TIMEOUT_S)


def is_ready() -> bool:
    """True if the device bridge answers its health check."""
    try:
        with urllib.request.urlopen(BASE_URL + "/health", timeout=5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False
