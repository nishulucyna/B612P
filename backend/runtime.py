"""
backend/runtime.py
Chooses between the real Snapdragon/HDK bridge (Sector 1: backend.npu_runtime) and the
local mock fallback (backend.mock_npu), and provides optional TTS / mic hooks (Sector 3:
backend.audio_pipeline). Teammate modules are imported lazily, so this works before they exist.

NPU_BACKEND env var:
    auto   (default) use the device bridge when present and healthy, else fall back to the mock.
    device never fall back; failures raise EngineUnavailable (HTTP 503).
    mock   always use backend.mock_npu.
The device bridge only talks to localhost (adb forward) - no cloud calls anywhere.

Other env vars: TTS_ENABLED (default 1).
"""

import importlib
import importlib.util
import logging
import os
import sys
import threading
import time
from typing import Any, Callable, Dict, Optional

from backend import mock_npu

log = logging.getLogger("backend.runtime")

DEVICE_RETRY_SECONDS = 30.0  # after a device failure in auto mode, skip it for this long


class EngineUnavailable(RuntimeError):
    """No usable engine could serve the request."""


class DeviceUnavailable(EngineUnavailable):
    """NPU_BACKEND=device but the HDK bridge is missing or failed."""


_lock = threading.Lock()
_device_down_until = 0.0
_last: Dict[str, Optional[str]] = {"stt": None, "llm": None}


def get_mode() -> str:
    mode = os.getenv("NPU_BACKEND", "auto").strip().lower()
    return mode if mode in {"auto", "device", "mock"} else "auto"


def reset_health() -> None:
    """Clears the device cooldown and last-used markers (used by tests / manual retry)."""
    global _device_down_until
    with _lock:
        _device_down_until = 0.0
        _last["stt"] = _last["llm"] = None


def _load_device() -> Optional[Any]:
    try:
        return importlib.import_module("backend.npu_runtime")
    except ImportError as exc:
        log.debug("backend.npu_runtime unavailable: %s", exc)
        return None


def _dispatch(kind: str, fn_name: str, arg: str, mock_fn: Callable[[str], str]) -> str:
    global _device_down_until
    mode = get_mode()

    def use_mock() -> str:
        try:
            out = mock_fn(arg)
        except mock_npu.STTUnavailable as exc:
            raise EngineUnavailable(str(exc)) from exc
        _last[kind] = "mock"
        return out

    if mode == "mock":
        return use_mock()

    device = _load_device()
    if mode == "device":
        if device is None:
            raise DeviceUnavailable("NPU_BACKEND=device but backend/npu_runtime.py was not found.")
        try:
            out = getattr(device, fn_name)(arg)
            if not isinstance(out, str):
                raise TypeError(f"{fn_name} returned {type(out).__name__}, expected str")
        except Exception as exc:
            raise DeviceUnavailable(f"Device {fn_name} failed: {exc}") from exc
        _last[kind] = "device"
        return out

    # auto
    if device is not None and time.monotonic() >= _device_down_until:
        try:
            out = getattr(device, fn_name)(arg)
            if not isinstance(out, str):
                raise TypeError(f"{fn_name} returned {type(out).__name__}, expected str")
            _last[kind] = "device"
            return out
        except Exception as exc:
            log.warning("Device %s failed (%s); falling back to mock for %.0fs",
                        fn_name, exc, DEVICE_RETRY_SECONDS)
            with _lock:
                _device_down_until = time.monotonic() + DEVICE_RETRY_SECONDS
    return use_mock()


def run_stt(audio_path: str) -> str:
    return _dispatch("stt", "run_stt", audio_path, mock_npu.run_stt)


def run_llm(prompt: str) -> str:
    return _dispatch("llm", "run_llm", prompt, mock_npu.run_llm)


# ---------------------------------------------------------------------------
# Sector 3 hooks (optional)
# ---------------------------------------------------------------------------

def _tts_enabled() -> bool:
    return os.getenv("TTS_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


def speak(text: str) -> bool:
    """Speaks text via backend.audio_pipeline.speak_tts if available. Never raises."""
    if not text or not _tts_enabled():
        return False
    try:
        mod = importlib.import_module("backend.audio_pipeline")
        mod.speak_tts(text, blocking=True)
        return True
    except ImportError:
        log.info("TTS skipped: backend.audio_pipeline not available yet.")
    except Exception as exc:  # TTS problems must never break a turn
        log.warning("TTS failed: %s", exc)
    return False


def record_audio() -> str:
    """Records a mic clip via backend.audio_pipeline.record_audio; raises EngineUnavailable if absent."""
    try:
        mod = importlib.import_module("backend.audio_pipeline")
        return mod.record_audio()
    except ImportError as exc:
        raise EngineUnavailable("Mic capture unavailable: backend/audio_pipeline.py not found.") from exc


def _module_present(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):  # e.g. module injected into sys.modules without a spec
        return name in sys.modules


def status() -> Dict[str, Any]:
    return {
        "mode": get_mode(),
        "device_module_present": _module_present("backend.npu_runtime"),
        "device_in_cooldown": time.monotonic() < _device_down_until,
        "last_stt_backend": _last["stt"],
        "last_llm_backend": _last["llm"],
        "tts_enabled": _tts_enabled(),
        "tts_module_present": _module_present("backend.audio_pipeline"),
    }
