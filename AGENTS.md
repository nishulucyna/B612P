# Project Context: Qualcomm On-Device AI Incident Report Assistant

## 1. Problem Statement Summary
- **Competition:** Megathon X (IIIT Hyderabad) - Qualcomm Track
- **Goal:** Build an end-to-end voice-driven incident reporting assistant using on-device Generative AI and function calling.
- **Official Pipeline:** 
  `Microphone -> Speech-to-Text -> LLM Information Extraction -> Mandatory Fields Check -> Tool Calling -> Form Population -> Screen Display & TTS Output`
- **Mandatory Constraint:** All AI models (ASR and LLM) **must execute strictly on-device using Snapdragon NPU/DSP acceleration**. No cloud APIs.
- **Reference Problem Presentation:** `docs/QUALCOMM-ps.pptx`

---

## 2. Locked Architecture & Data Contract
All modules, agents, and laptops communicate using **`contract.json`** at the repository root. Do not alter the field keys.

### The 10 Form Fields:
1. `incident_type` *(MANDATORY)*
2. `severity_level` *(Optional: Low | Medium | High | Critical)*
3. `incident_location` *(MANDATORY)*
4. `date_time` *(MANDATORY)*
5. `persons_involved` *(Optional)*
6. `equipment_asset_involved` *(Optional)*
7. `incident_description` *(Optional)*
8. `immediate_actions_taken` *(MANDATORY)*
9. `witness_information` *(Optional)*
10. `recommended_follow_up_action` *(Optional)*

### Diamond Gate Rule:
If any of the 4 mandatory fields are missing:
- `status`: `"collecting"`
- System asks a single-sentence clarification question via TTS to retrieve the missing field.

When all 4 mandatory fields are present:
- `status`: `"complete"`
- System emits tool call payload: `populate_incident_form` to hydrate the UI and generate spoken summary.

---

## 3. Team Sector Responsibilities & Git Branches

### Sector 1: Snapdragon NPU Engine
- **Branch:** `feat/npu-runtime`
- **Files/Outputs:** Implement callable local functions:
  - `run_stt(audio_path: str) -> str` (using Whisper QNN/DLC on DSP)
  - `run_llm(prompt: str) -> str` (using Llama-3.2-1B/3B via Genie/QAIRT on NPU)
- **References:** `quic/qidk` repo -> `Solutions/NLPSolution3-AutomaticSpeechRecognition-Whisper`, Qualcomm AI Hub models.

### Sector 2: Agentic State Engine & Tool Caller (Core Brain)
- **Branch:** `feat/agent-brain`
- **File:** `backend/agent_brain.py` (already implemented and tested)
- **Role:** Handles prompt formatting, robust JSON extraction, conversational memory merge, diamond gate check, and tool call payload emission.

### Sector 3: Audio I/O & Text-to-Speech
- **Branch:** `feat/audio-pipeline`
- **Role:**
  - Mic capture: Record 16kHz mono `.wav` buffer from microphone.
  - Offline TTS: Run on-device TTS (Android TTS, piper-tts, or kokoro-onnx) to speak `next_clarification_prompt` and confirmation summary.

### Sector 4: Incident Dashboard & Live UI
- **Branch:** `feat/form-ui`
- **Role:**
  - Render live listening status / audio visualizer.
  - Display conversational transcript (user vs assistant).
  - Render the 10 form fields (highlighting green as fields populate).
  - Provide review/edit inputs and a final "Submit Incident" button.

---

## 4. Instructions for AI Coding Assistants (Claude Code, Cursor, Antigravity)
- Always read `contract.json` before implementing data schemas.
- Do not add external network or cloud LLM calls.
- Read `master_execution_plan.md` for full implementation details.
