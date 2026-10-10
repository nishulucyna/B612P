# NPU Bridge (Android app for HDK8650)

Loopback HTTP server that the host reaches via `adb forward tcp:8080 tcp:8080`.
Host client: `backend/npu_runtime.py`. Smoke test: `tests/test_npu_bridge.py`.

| Route | Request | Response |
|---|---|---|
| `GET /health` | - | 200 if both engines ready, else 503, JSON `{ready, stt_ready, llm_ready, stt, llm}` |
| `POST /stt` | raw 16 kHz mono WAV bytes | `{"transcript": "..."}` |
| `POST /llm` | `{"prompt": "..."}` | `text/plain` raw model output |

## Status

- Done: HTTP server, routing, error handling, status screen.
- Whisper STT is wired: encoder DLC (w8a16, SM8650 offline cache) on the Hexagon DSP through SNPE
  (`app/src/main/cpp`, adapted from qidk `NLPSolution3-AutomaticSpeechRecognition-Whisper`), decoder on
  TFLite CPU, greedy decoding. Models are packaged as APK assets.
- Not done: `GenieEngine` (Llama on the NPU) is still a stub that reports not-ready (HTTP 503) until the
  Genie bundle for SM8650 is available. It never returns fake output.
- Not yet compiled or run on a device (no Android SDK/NDK on the dev PC that wrote this).
  Expect to fix small build errors on the first Android Studio build.
- Port notes: the sample's native code was patched to release JNI arrays (the original could lose the
  encoder output), keep the SNPE object after a failed run, and guard missing assets. Audio longer than
  30 s is truncated (Whisper chunk size).

## NPU alerts (no silent CPU fallback)

The encoder is built for the Hexagon DSP only. If it cannot start there, the app does not quietly use the CPU:

- `/stt` answers 503, `/health` reports `stt_ready: false` with `stt_warning`, and logcat prints `NPU_ALERT`
  (`adb logcat | findstr NPU_ALERT`).
- The app shows a red banner and a Toast. The banner is amber while loading and green once the encoder is on the NPU.
- Dev only: `adb shell am start -n com.b612p.npubridge/.MainActivity --ez allow_cpu_fallback true` lets the encoder
  build on the CPU so the rest of the pipeline can be tried. `/health` then reports `stt_on_npu: false`, the banner
  stays red, and the host client logs "NPU ALERT" once. Never use this for the demo.
- Host: `backend.npu_runtime.npu_status()` returns the `/health` JSON for the UI.

## Build and run

1. `powershell -File scripts/copy_whisper_assets.ps1` copies the model assets, the V75 SNPE libraries and the
   SNPE headers into the project (all gitignored). Needs `npu_models/whisper/` and `qairt_sdk/2.47.0.260601`.
2. Open `android_bridge/` in Android Studio (it creates the Gradle wrapper and installs the NDK/CMake).
   NanoHTTPD and TensorFlow Lite are downloaded at build time only.
3. Build and install: `adb install -r -t app/build/outputs/apk/debug/app-debug.apk`
4. Per boot: `scripts/setup_hdk.bat` (or `.sh` / `.ps1`).
5. Llama only: `adb push npu_models/llama /data/local/tmp/npu_models/` (Whisper needs no push; it is inside the APK).
6. Open the app and keep the screen on. Then `python tests/test_npu_bridge.py`.

The app opens a socket on 127.0.0.1 only and makes no outbound network calls.
