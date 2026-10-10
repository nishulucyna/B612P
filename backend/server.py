"""
backend/server.py
Central orchestration server tying together the four sectors.

    audio/text -> STT (runtime) -> agent_brain.process_user_turn (LLM via runtime)
               -> Diamond Gate -> persist contract.json -> TTS text for Sector 3

Run from the repo root:   uvicorn backend.server:app --port 8000
Env: CONTRACT_PATH (default <repo>/contract.json), NPU_BACKEND, TTS_ENABLED (see runtime.py).
See docs/orchestrator_api.md for the endpoint reference.
"""

import copy
import json
import logging
import os
import shutil
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import runtime
from backend.agent_brain import (
    ALL_FIELDS,
    MANDATORY_FIELDS,
    clean_and_parse_json,
    identify_missing_mandatory,
    process_user_turn,
)

log = logging.getLogger("backend.server")

DEFAULT_CONTRACT_PATH = Path(__file__).resolve().parent.parent / "contract.json"
SEVERITIES = ("Low", "Medium", "High", "Critical")
INITIAL_PROMPT = "Please describe what happened, where, and when."
RETRY_PROMPT = "Sorry, I didn't catch that. Could you say it again?"


# ---------------------------------------------------------------------------
# Field hygiene (keeps whatever the LLM returns inside the locked contract)
# ---------------------------------------------------------------------------

def sanitize_extracted(data: Any) -> Dict[str, Optional[str]]:
    """Coerces a raw LLM/edit dict into {all 10 contract keys: str | None}; invalid severity -> None."""
    src = data if isinstance(data, dict) else {}
    out: Dict[str, Optional[str]] = {}
    for key in ALL_FIELDS:
        val = src.get(key)
        if isinstance(val, (list, tuple)):
            val = ", ".join(str(v).strip() for v in val if v is not None and str(v).strip())
        elif isinstance(val, dict):
            val = None
        elif val is not None and not isinstance(val, str):
            val = str(val)
        if isinstance(val, str):
            val = val.strip()
            if val == "" or val.lower() == "null":
                val = None
        if key == "severity_level" and val is not None:
            val = next((s for s in SEVERITIES if s.lower() == val.lower()), None)
        out[key] = val
    return out


def _llm_engine(prompt: str) -> str:
    """The llm_engine_fn handed to agent_brain: runtime LLM + parse + sanitize, re-serialized."""
    raw = runtime.run_llm(prompt)
    return json.dumps(sanitize_extracted(clean_and_parse_json(raw)))


def blank_state() -> Dict[str, Any]:
    return {
        "session_id": f"session-{uuid.uuid4().hex[:8]}",
        "status": "collecting",
        "missing_mandatory_fields": list(MANDATORY_FIELDS),
        "next_clarification_prompt": INITIAL_PROMPT,
        "fields": {k: None for k in ALL_FIELDS},
        "tool_call_payload": None,
    }


def _speech_for(state: Dict[str, Any]) -> Optional[str]:
    if state["status"] == "complete":
        return (state.get("tool_call_payload") or {}).get("summary_for_tts")
    return state.get("next_clarification_prompt")


class SessionSubmitted(Exception):
    pass


class NotReadyToSubmit(Exception):
    def __init__(self, missing: List[str]):
        super().__init__(f"Missing mandatory fields: {missing}")
        self.missing = missing


# ---------------------------------------------------------------------------
# Orchestrator (single active incident session, persisted to contract.json)
# ---------------------------------------------------------------------------

class Orchestrator:
    def __init__(self, contract_path: Path):
        self.path = Path(contract_path)
        self._lock = threading.RLock()
        self._transcript: List[Dict[str, str]] = []
        self._state = self._load()

    # -- persistence -------------------------------------------------------
    def _load(self) -> Dict[str, Any]:
        state = blank_state()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return state
        if not isinstance(data, dict) or not isinstance(data.get("fields"), dict):
            return state

        state["fields"] = sanitize_extracted(data["fields"])
        if isinstance(data.get("session_id"), str) and data["session_id"]:
            state["session_id"] = data["session_id"]
        state["missing_mandatory_fields"] = identify_missing_mandatory(state["fields"])
        status = data.get("status")
        if status in ("complete", "submitted") and not state["missing_mandatory_fields"]:
            state["status"] = status
            state["next_clarification_prompt"] = None
            payload = data.get("tool_call_payload")
            state["tool_call_payload"] = payload if isinstance(payload, dict) else None
        elif isinstance(data.get("next_clarification_prompt"), str):
            state["next_clarification_prompt"] = data["next_clarification_prompt"]
        return state

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._state, indent=2, ensure_ascii=False) + "\n"
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        for attempt in range(5):  # Windows: replace can fail briefly while a reader has the file open
            try:
                os.replace(tmp, self.path)
                return
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))
        self.path.write_text(payload, encoding="utf-8")

    # -- helpers -----------------------------------------------------------
    def _log(self, role: str, text: str) -> None:
        self._transcript.append(
            {"role": role, "text": text, "timestamp": datetime.now(timezone.utc).isoformat()}
        )

    def _response(self, user_text: Optional[str], speech: Optional[str]) -> Dict[str, Any]:
        return {
            "state": copy.deepcopy(self._state),
            "user_transcript": user_text,
            "assistant_speech": speech,
            "engine": runtime.status(),
        }

    def _ensure_open(self) -> None:
        if self._state["status"] == "submitted":
            raise SessionSubmitted()

    # -- public API --------------------------------------------------------
    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    def get_transcript(self) -> List[Dict[str, str]]:
        with self._lock:
            return copy.deepcopy(self._transcript)

    def text_turn(self, text: str) -> Dict[str, Any]:
        with self._lock:
            self._ensure_open()
            result = process_user_turn(text, self._state, _llm_engine)
            self._state = result
            self._log("user", text)
            speech = _speech_for(result)
            if speech:
                self._log("assistant", speech)
            self._persist()
            return self._response(text, speech)

    def audio_turn(self, audio_path: str) -> Dict[str, Any]:
        with self._lock:
            self._ensure_open()
            text = runtime.run_stt(audio_path).strip()
            if not text:
                self._log("assistant", RETRY_PROMPT)
                return self._response("", RETRY_PROMPT)
            return self.text_turn(text)

    def submit(self, edits: Optional[Dict[str, Optional[str]]] = None) -> Dict[str, Any]:
        with self._lock:
            self._ensure_open()
            fields = dict(self._state["fields"])
            if edits:
                cleaned = sanitize_extracted(edits)
                for key in edits:
                    fields[key] = cleaned[key]
            missing = identify_missing_mandatory(fields)
            if missing:
                raise NotReadyToSubmit(missing)
            self._state["fields"] = fields
            self._state["status"] = "submitted"
            self._state["missing_mandatory_fields"] = []
            self._state["next_clarification_prompt"] = None
            if isinstance(self._state.get("tool_call_payload"), dict):
                self._state["tool_call_payload"]["arguments"] = dict(fields)
            self._persist()
            return self._response(None, None)

    def reset(self) -> Dict[str, Any]:
        with self._lock:
            self._state = blank_state()
            self._transcript = []
            self._persist()
            return self._response(None, self._state["next_clarification_prompt"])


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

class TextTurnRequest(BaseModel):
    text: str


class SubmitRequest(BaseModel):
    fields: Optional[Dict[str, Optional[str]]] = None


def create_app(contract_path: Optional[Path] = None) -> FastAPI:
    path = Path(contract_path or os.getenv("CONTRACT_PATH") or DEFAULT_CONTRACT_PATH)
    orch = Orchestrator(path)
    app = FastAPI(title="Incident Report Assistant - Orchestrator")
    app.state.orchestrator = orch
    # UI (Streamlit/React) runs on another localhost port.
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    def finish(resp: Dict[str, Any], background: BackgroundTasks) -> Dict[str, Any]:
        if resp.get("assistant_speech"):
            background.add_task(runtime.speak, resp["assistant_speech"])
        return resp

    def run_turn(fn, *args):
        try:
            return fn(*args)
        except SessionSubmitted:
            raise HTTPException(409, "Incident already submitted. POST /api/reset to start a new one.")
        except runtime.EngineUnavailable as exc:
            raise HTTPException(503, str(exc))

    board_cache: Dict[str, Any] = {"t": 0.0, "value": None}

    def board_status() -> Optional[Dict[str, Any]]:
        """What the HDK bridge itself reports (is each model on the NPU?). Cached ~3 s; None if no bridge."""
        now = time.monotonic()
        if now - board_cache["t"] > 3.0:
            try:
                from backend import npu_runtime
                board_cache["value"] = npu_runtime.npu_status(timeout=2.0)
            except Exception:
                board_cache["value"] = None
            board_cache["t"] = now
        return board_cache["value"]

    @app.get("/api/health")
    def health() -> Dict[str, Any]:
        st = orch.get_state()
        return {"ok": True, "session_id": st["session_id"], "status": st["status"],
                "engine": runtime.status(), "board": board_status()}

    @app.get("/api/state")
    def get_state() -> Dict[str, Any]:
        return orch.get_state()

    @app.get("/api/transcript")
    def get_transcript() -> List[Dict[str, str]]:
        return orch.get_transcript()

    @app.post("/api/text/turn")
    def text_turn(req: TextTurnRequest, background: BackgroundTasks) -> Dict[str, Any]:
        text = req.text.strip()
        if not text:
            raise HTTPException(400, "text must not be empty")
        return finish(run_turn(orch.text_turn, text), background)

    @app.post("/api/audio/turn")
    def audio_turn(background: BackgroundTasks, file: Optional[UploadFile] = File(default=None)) -> Dict[str, Any]:
        """Upload a 16kHz mono wav as multipart field 'file', or send no body to record from the mic."""
        tmp_path: Optional[str] = None
        try:
            if file is not None:
                suffix = Path(file.filename or "").suffix or ".wav"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    shutil.copyfileobj(file.file, tmp)
                    tmp_path = tmp.name
                audio_path = tmp_path
            else:
                try:
                    audio_path = runtime.record_audio()
                except runtime.EngineUnavailable as exc:
                    raise HTTPException(501, f"{exc} Upload a file in multipart field 'file' instead.")
            return finish(run_turn(orch.audio_turn, audio_path), background)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @app.post("/api/submit")
    def submit(req: Optional[SubmitRequest] = None) -> Dict[str, Any]:
        edits = req.fields if req else None
        if edits:
            unknown = sorted(set(edits) - set(ALL_FIELDS))
            if unknown:
                raise HTTPException(422, f"Unknown field(s): {unknown}")
        try:
            return orch.submit(edits)
        except SessionSubmitted:
            raise HTTPException(409, "Incident already submitted.")
        except NotReadyToSubmit as exc:
            raise HTTPException(409, f"Cannot submit; missing mandatory fields: {exc.missing}")

    @app.post("/api/reset")
    def reset() -> Dict[str, Any]:
        return orch.reset()

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000)
