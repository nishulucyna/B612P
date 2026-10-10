# NPU Bridge (Android app for HDK8650)

Loopback HTTP server that the host reaches via `adb forward tcp:8080 tcp:8080`.
Host client: `backend/npu_runtime.py`. Smoke test: `tests/test_npu_bridge.py`.

| Route | Request | Response |
|---|---|---|
| `GET /health` | - | 200 if both engines ready, else 503, JSON `{ready, stt, llm}` |
| `POST /stt` | raw 16 kHz mono WAV bytes | `{"transcript": "..."}` |
| `POST /llm` | `{"prompt": "..."}` | `text/plain` raw model output |

## Status

- Done: HTTP server, routing, error handling, model-folder lookup, status screen.
- Not done: `WhisperEngine` and `GenieEngine` are stubs that report not-ready (HTTP 503).
  They need the native QAIRT/SNPE/Genie layer plus the SM8650 (V75) model files.
  They never return fake output.
- Not yet compiled or run on a device.

## Build and run

1. Open `android_bridge/` in Android Studio (it creates the Gradle wrapper). NanoHTTPD is the
   only dependency and is downloaded at build time only.
2. Build and install: `adb install -r -t app/build/outputs/apk/debug/app-debug.apk`
3. Per boot: `scripts/setup_hdk.bat` (or `.sh` / `.ps1`).
4. Push models: `adb push npu_models /data/local/tmp/npu_models` with `whisper/` and `llama/` inside.
5. Open the app and keep the screen on. Then `python tests/test_npu_bridge.py`.

The app opens a socket on 127.0.0.1 only and makes no outbound network calls.
