# Orchestrator API (`backend/server.py`)

Run from the repo root:

```
pip install -r requirements.txt
uvicorn backend.server:app --port 8000          # or: python -m backend.server
```

State is persisted to `contract.json` after every change (override with `CONTRACT_PATH`).
Because `contract.json` is tracked in git, running the server makes it show as modified;
use `CONTRACT_PATH=runtime_state.json` to keep the committed template pristine.

## Environment

| Var | Default | Meaning |
|---|---|---|
| `NPU_BACKEND` | `auto` | `auto`: use `backend/npu_runtime.py` (Sector 1, HDK bridge) if present and healthy, else the mock. `device`: never fall back (HTTP 503 on failure). `mock`: always `backend/mock_npu.py`. After a device failure in `auto`, the board is skipped for 30 s. |
| `TTS_ENABLED` | `1` | Speak via `backend.audio_pipeline.speak_tts` if that module exists. |
| `MOCK_WHISPER_MODEL_DIR` | unset | Local faster-whisper model folder for the mock STT (optional). |
| `CONTRACT_PATH` | `<repo>/contract.json` | Where state is persisted. |

## Endpoints

| Method / path | Body | Result |
|---|---|---|
| `GET /api/state` | - | Current state (contract fields + `tool_call_payload`). |
| `GET /api/transcript` | - | `[{role: "user"\|"assistant", text, timestamp}]` for the chat feed. |
| `GET /api/health` | - | Session status + which engine (`device`/`mock`) served the last STT/LLM call. |
| `POST /api/text/turn` | `{"text": "..."}` | Runs one turn. |
| `POST /api/audio/turn` | multipart `file` (16 kHz mono wav); no body = record from mic via Sector 3 | STT, then a turn. Silence/empty transcript => state unchanged, "didn't catch that" speech. |
| `POST /api/submit` | optional `{"fields": {...edits...}}` | `submitted` if all 4 mandatory fields are present after edits, else 409. |
| `POST /api/reset` | - | New blank session. |

Turn / submit / reset responses: `{"state", "user_transcript", "assistant_speech", "engine"}`.
`assistant_speech` is `next_clarification_prompt` while collecting and
`tool_call_payload.summary_for_tts` when complete - this is what Sector 3 speaks.
Errors: 400 empty text, 409 already submitted / missing mandatory fields, 422 unknown field,
501 mic capture unavailable, 503 no usable engine.

## Interfaces expected from teammates

- Sector 1 -> `backend/npu_runtime.py` exposing `run_stt(audio_path: str) -> str` and `run_llm(prompt: str) -> str`.
- Sector 3 -> `backend/audio_pipeline.py` exposing `record_audio() -> str` (wav path) and `speak_tts(text: str, blocking: bool = True)`.
- Sector 4 -> UI reads `GET /api/state` / `GET /api/transcript` and posts to the endpoints above.

Tests: `python -m pytest tests -q`
