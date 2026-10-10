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
- LLM is wired through GenieX (`GenieEngine.kt`, llama.cpp runtime, Hexagon NPU, 4-bit `q4_0` GGUF), loading a
  local file; nothing is downloaded. The SDK ships `libggml-htp-v75.so`, so SM8650 is covered by this path (the
  Qualcomm AI Hub Llama/Genie bundle path only ships v79/v81 libraries). Not validated by Qualcomm on SM8650.
- Where the model runs is checked, not assumed: after loading, the engine reads GenieX's own placement log
  (`... HTP0-REPACK model buffer size = N MiB`) and only reports `llm_on_npu` when at least 30% of the weight bytes
  are in HTP0 buffers (embedding tables stay on the CPU in every llama.cpp setup). Otherwise the LLM is refused
  (HTTP 503) unless the dev switch is used. High CPU use is NOT a signal: llama.cpp threads spin while waiting.
- Incident-extraction prompts are decoded with a GBNF grammar (exactly the 10 fields, string or null) and
  placeholder strings such as "Unknown" are turned into null (`IncidentJson.kt`), because the brain treats any
  non-empty string as a filled field.
- Measured on the HDK8650 (SM8650, Android 14), `scripts/bench_board_llm.py`:

  | Model | Weights on HTP0 | Decode | LLM call (extraction) | Four test cases |
  |---|---|---|---|---|
  | Qwen3-1.7B Q4_0 (1.1 GB) | 759 MiB | ~29 tok/s | ~4.6 s | all correct, follow-up turn merges |
  | Gemma 4 E4B Q4_0 (5.2 GB) | 2171 MiB (+3255 MiB embeddings on CPU) | ~12 tok/s | ~12.4 s | all correct |
  | Qwen3-1.7B without the grammar | same | same | up to 18.8 s | follow-up turn failed ("Unknown") |

  Qwen3-1.7B with the grammar is the default recommendation. Put the chosen file at
  `/data/local/tmp/npu_models/llm/model.gguf`.
- Builds with `gradlew assembleDebug` (AGP 8.6.1, Kotlin 2.0.21, NDK 26.2.11394342, CMake 3.22.1) and runs on the
  HDK8650: Whisper on the DSP (encoder ~14 ms), LLM on the NPU, end to end through the orchestrator in
  `NPU_BACKEND=device` mode.
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
   NanoHTTPD, TensorFlow Lite, Kotlin coroutines and GenieX (`com.qualcomm.qti:geniex-android:0.3.1`) are downloaded
   at build time only. The app uses Kotlin 2.0.21 because GenieX is a Kotlin 2.0 library.
3. Build and install: `adb install -r -t app/build/outputs/apk/debug/app-debug.apk`
4. Per boot: `scripts/setup_hdk.bat` (or `.sh` / `.ps1`).
5. LLM: `adb push <model>.gguf /data/local/tmp/npu_models/llm/model.gguf` (any `*.gguf` in that folder works,
   `model.gguf` wins if several). Whisper needs no push; it is inside the APK. Run `scripts/setup_hdk.*` after
   pushing so the app can read the file.
6. Open the app and keep the screen on. Then `python tests/test_npu_bridge.py`.

The app opens a socket on 127.0.0.1 only and makes no outbound network calls. GenieX can download models and
its docs say it needs the INTERNET permission; we load the file by path and never call its pull API. Test the demo
with the board's Wi-Fi off.
