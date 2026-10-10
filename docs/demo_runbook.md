# Live demo runbook (HDK8650)

## What runs where

```
Laptop                                                        Board (HDK8650, SM8650, Android 14)
------                                                        ----------------------------------
Streamlit UI :8501 --HTTP--> Orchestrator :8000                 NPU Bridge app (android_bridge/)
   mic -> WAV --------------> Whisper request ----adb forward--> Whisper encoder on the Hexagon DSP (SNPE)
   speaker <- TTS (offline)   Agent brain (extraction,            Whisper decoder on TFLite (CPU)
                              diamond gate, tool call) --------> Gemma 4 E4B (Q4_0) on the Hexagon NPU (GenieX)
```

All AI inference is on the board. The laptop only records audio, speaks the replies (offline Windows
voices), runs the form logic and shows the UI. Nothing calls a cloud service at run time.

## Before you start (5 minutes)

1. Board: 12 V adapter plugged in, powered on, USB-C **data** cable straight into the laptop. DIP switches:
   S5801-1 (Force USB Boot) OFF; S8101-1/4/7 ON and 2/3/8 OFF for 12 V.
2. `adb devices` must list the board (serial `57f41604` on ours). If empty, see "If something breaks".
3. Laptop mic and speakers work. Close apps that use the mic.
4. The model is on the board: `/data/local/tmp/npu_models/llm/model.gguf`. It survives reboots.

## Start

```
scripts\start_demo.bat
```

It prepares the board (root, SELinux permissive, port forward), restarts the bridge app, **waits until
Whisper and the LLM are loaded** (about 30-60 s), then starts the orchestrator and the UI and opens the
browser. It is strict: it refuses to use the laptop mock. After every board reboot, run it again.

Then check everything (about a minute, does not need you to talk):

```
python scripts\demo_selftest.py
```

And try your own voice (speak one sentence, then stop; it should stop by itself after ~1.5 s):

```
python scripts\mic_check.py
```

Leave the board's screen on with the app in front. Its banner is **green** when the encoder is on the NPU.
The UI sidebar shows the same: "Whisper + LLM running on the Snapdragon NPU".

## During the demo

1. Click **Speak**, say a full report ("There was a water leak near Conference Room 2 around 10 AM.
   Maintenance has already isolated the area."). Pause. The UI shows a spinner while the board works.
2. Expect **about 10-15 s per turn** (speech-to-text ~1-2 s, LLM ~10-12 s). Talk over it: say what is
   happening ("the speech model is running on the NPU DSP, now the language model extracts the fields").
3. If something mandatory is missing, the assistant asks **one** question, aloud and on screen. Answer it
   with Speak again. Fields turn green as they fill.
4. When the four mandatory fields are present the tool call `populate_incident_form` appears (expander),
   the summary is spoken, and **Confirm & Submit** unlocks. Fields can be edited before submitting.
5. **Reset All** starts a new incident.

Good demo sentences (known to work): the water leak above; "A pipe burst on the second floor!" (it asks for
the time and the action taken, then "It happened at 2 PM and we turned off the main valve." completes it).

## If something breaks

| Symptom | Do this |
|---|---|
| `adb devices` is empty | Power and cable (data cable, direct port), reseat the display card, S5801-1 OFF. Windows must show a Qualcomm "ADB Interface". |
| `start_demo` says SELinux not Permissive | Board not rooted: `adb root`, then `adb shell setenforce 0`. Needed again after every board reboot. |
| Red UI banner / "NPU problem" | Read the text on the board's screen banner and `adb logcat -s NpuBridge`. Run `start_demo` again. |
| "Cannot reach the orchestrator" in the UI | `scripts\stop_demo.ps1`, then `scripts\start_demo.bat`. |
| Speak records for the full 15 s | It did not hear a clear pause. Reduce background noise, move closer, run `scripts\mic_check.py` to see levels. |
| Wrong words in the transcript | Whisper-tiny is small and mishears unusual words. Speak clearly, or type the report in the sidebar box. |
| A turn fails once | The bridge retries once by itself. If it persists, click Reset All and repeat. |
| Board is dead during the show | `scripts\start_demo.bat -AllowMock` runs the laptop mock (orange "MOCK" banner). Say so; it is not on-device. |

## Switching the LLM

Files in `/data/local/tmp/npu_models/llm/`; the app uses `model.gguf` (else the first `*.gguf`).

| File on the board | Model | Per turn | Notes |
|---|---|---|---|
| model.gguf | Gemma 4 E4B Q4_0 (5.2 GB) | ~10-15 s | Current choice. Larger, per the documentation. |
| qwen3-1.7b.gguf | Qwen3-1.7B Q4_0 (1.1 GB) | ~4-5 s | Same accuracy on our test sentences, about 3x faster. |
| qwen3-0.6b.gguf | Qwen3-0.6B Q4_0 | fastest | Not tested for quality. |

Swap (then run `start_demo` again):
`adb shell "cd /data/local/tmp/npu_models/llm && mv model.gguf gemma4-e4b.gguf && mv qwen3-1.7b.gguf model.gguf"`

## Proving "on-device"

- `adb logcat -s GenieXSdk NpuBridge` shows where the weights were placed (`HTP0` buffers) and the
  `NPU_ALERT` lines if anything is not on the NPU.
- `scripts\demo_selftest.py` checks that every turn reports `last_stt_backend` and `last_llm_backend` as `device`.
- To show there is no cloud: turn off the laptop's and the board's Wi-Fi, then run the self-test.

## Known limits

- Audio is capped at 15 s per recording; Whisper handles 30 s windows.
- The tiny Whisper model mishears rare words ("forklift" came out as "A4 Clifed" once).
- GenieX reports no direct "which processor" API; we read its placement log (see `android_bridge/README.md`).
- Gemma: about half of its weight bytes (mostly embedding tables) stay on the CPU, which is normal for llama.cpp.
