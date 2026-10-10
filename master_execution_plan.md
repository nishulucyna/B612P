# 🎯 Qualcomm Megathon X: Master Execution Plan & Sector Briefing
### Problem Statement: AI Incident Report Assistant (On-Device AI Challenge)

---

## 1. Executive Summary & Problem Breakdown

Qualcomm's challenge this year (**AI Incident Report Assistant**) is a **voice-driven, on-device structured extraction and function-calling system**.

```
[User Speech] ──► [On-Device Whisper STT] ──► [LLM Info Extraction] ──► [Mandatory Fields Present?]
                                                                               │
                                                      ┌────────────────────────┴────────────────────────┐
                                                      ▼ (No: Missing Details)                           ▼ (Yes: All Present)
                                        [Generate Conversational Clarification]          [Trigger Tool Call: populate_incident_form]
                                                      │                                                 │
                                                      ▼                                                 ▼
                                        [On-Device TTS / Speaker Question]               [Populate Live UI & Confirm with User]
```

### Mandatory Hard Constraints:
1. **Zero Cloud:** All models (Speech-to-Text and LLM) **must run accelerated on-device** using the Snapdragon NPU/DSP via QAIRT / QIDK / Qualcomm AI Hub.
2. **Conversational Speech:** Must handle natural, unscripted speech ("there was a leak in conf room 2...").
3. **Diamond Check:** Mandatory fields (`incident_type`, `incident_location`, `date_time`, `immediate_actions_taken`) must be verified. If missing, the system must trigger an interactive voice clarification loop.
4. **Function Calling:** When complete, emit a tool call (`populate_incident_form`) to hydrate the form and display it for user confirmation.

---

## 2. Sector Allocation & Teammate Battle Stations

| Sector | Teammate & Role | Branch | Deliverables |
| :--- | :--- | :--- | :--- |
| **Sector 1** | **Member 1: Snapdragon NPU Engine** (Claude Code Laptop) | `feat/npu-runtime` | Callable functions: `run_stt(audio_path) -> str` & `run_llm(prompt) -> str` running locally on NPU/DSP. |
| **Sector 2** | **Member 2 (You): Agentic Brain & Tool Calling** (Antigravity) | `feat/agent-brain` | `backend/agent_brain.py` with multi-turn memory, Diamond Gate, JSON extraction, and tool call payload generator. *(✅ COMPLETE & TESTED)* |
| **Sector 3** | **Member 3: Audio I/O & Text-to-Speech** | `feat/audio-pipeline` | Mic recorder (mono 16kHz `.wav`) + Offline local TTS (Piper-TTS / Kokoro / Android TTS) for speaking questions and final confirmation. |
| **Sector 4** | **Member 4: Live UI & Incident Dashboard** | `feat/form-ui` | Interactive screen with audio visualizer waveform, transcript chat log, dynamic 10-field form (lights up green on extraction), and manual edit/submit buttons. |

---

## 3. Ground Truth: Locked Data Contract (`contract.json`)

To prevent integration friction, all 4 sectors read from and write to [contract.json](file:///c:/Users/lucyn/Desktop/edc/contract.json):

```json
{
  "session_id": "string",
  "status": "collecting | complete | submitted",
  "missing_mandatory_fields": [
    "incident_type",
    "incident_location",
    "date_time",
    "immediate_actions_taken"
  ],
  "next_clarification_prompt": "string | null",
  "fields": {
    "incident_type": "string | null",
    "severity_level": "Low | Medium | High | Critical | null",
    "incident_location": "string | null",
    "date_time": "string | null",
    "persons_involved": "string | null",
    "equipment_asset_involved": "string | null",
    "incident_description": "string | null",
    "immediate_actions_taken": "string | null",
    "witness_information": "string | null",
    "recommended_follow_up_action": "string | null"
  }
}
```

---

## 4. Sector 2 (Your Sector) Status: ✅ Verified

The module [`backend/agent_brain.py`](file:///c:/Users/lucyn/Desktop/edc/backend/agent_brain.py) is implemented and passed both test harnesses:

1. **Single-turn complete input (Slide 3 Example):**
   * *User:* `"There was a water leak near Conference Room 2 around 10 AM. Maintenance has already isolated the area."`
   * *Result:* All 4 mandatory fields detected $\rightarrow$ Status: `complete` $\rightarrow$ Tool call `populate_incident_form` triggered $\rightarrow$ TTS confirmation generated.
2. **Multi-turn conversational dialogue:**
   * *Turn 1:* `"A pipe burst on the second floor!"` $\rightarrow$ Missing `date_time`, `immediate_actions_taken` $\rightarrow$ Status: `collecting` $\rightarrow$ Clarification question: *"Got that. At what time or date did this occur?"*
   * *Turn 2:* `"It happened at 2 PM and we turned off the main valve."` $\rightarrow$ Merged into state without overwriting prior fields $\rightarrow$ Status: `complete` $\rightarrow$ Form ready.

---

## 5. Teammate Handoff Directives

### Directives for Member 1 (Claude Code - Snapdragon NPU):
1. **Whisper:** Clone `quic/qidk` and open `Solutions/NLPSolution3-AutomaticSpeechRecognition-Whisper`. Deploy the quantized DLC encoder (DSP) + decoder (TFLite) to the device.
2. **LLM Engine:** Use Qualcomm AI Hub's pre-compiled **Llama-3.2-1B-Instruct** or **3B-Instruct** with the Genie / QAIRT SDK.
3. Expose standard Python/C++/JNI bindings so `agent_brain.process_user_turn` can call your local engine directly.

### Directives for Member 3 (Audio Pipeline):
1. **Mic Capture:** Record mono 16-bit 16kHz PCM WAV chunks on voice activity or push-to-talk.
2. **TTS:** Use an on-device TTS engine (Android Native `TextToSpeech` API or local `piper-tts`/`kokoro-onnx`) to read `next_clarification_prompt` and `tool_call_payload["summary_for_tts"]`.

### Directives for Member 4 (UI / Frontend):
1. Poll or subscribe via WebSocket to `contract.json` state updates.
2. Display:
   * **Waveform/Mic pulse** for speech input.
   * **Real-time chat feed** (User transcription vs Assistant questions).
   * **Form Cards:** 10 field inputs. Card background glows green with a smooth CSS transition the moment a field is extracted.
   * **Submit Button:** Disabled until `status === "complete"`.
