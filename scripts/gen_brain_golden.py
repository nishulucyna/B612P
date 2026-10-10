"""Generate golden test data from the Python agent brain, for the Kotlin port that runs on the board.

    python scripts/gen_brain_golden.py

Writes android_bridge/app/src/test/resources/brain_golden.json. The Kotlin IncidentBrain must reproduce every
value in it exactly (prompt text, JSON cleaning, field sanitising, state machine, spoken replies), so the standalone
app behaves identically to the laptop orchestrator. Re-run it if backend/agent_brain.py or sanitize_extracted change.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import agent_brain as ab  # noqa: E402
from backend.server import INITIAL_PROMPT, RETRY_PROMPT, blank_state, sanitize_extracted  # noqa: E402

WATER = ("There was a water leak near Conference Room 2 around 10 AM. "
         "Maintenance has already isolated the area.")

RAW_OUTPUTS = [
    '{"incident_type": "Water Leak", "severity_level": "medium", "incident_location": "Conference Room 2"}',
    '```json\n{"incident_type": "Pipe burst", "date_time": null}\n```',
    'Sure! Here you go: {"incident_type": "Fire", "persons_involved": ["Ravi", "Asha"]} Hope that helps.',
    '{"incident_type": "Spill", "severity_level": "Catastrophic", "witness_information": "  "',
    '{"incident_type": "null", "equipment_asset_involved": {"a": 1}, "incident_description": 42}',
    "not json at all",
    '{"incident_type": "Leak"}}',
]

# turns of conversations: (user text, raw LLM output)
SEQUENCES = {
    "complete_in_one_turn": [
        (WATER, '{"incident_type": "Water Leak", "severity_level": "Medium", "incident_location": "Conference Room 2", '
                '"date_time": "10 AM", "immediate_actions_taken": "Maintenance has already isolated the area"}'),
    ],
    "two_turn_clarification": [
        ("A pipe burst on the second floor!",
         '{"incident_type": "Pipe Burst", "severity_level": "High", "incident_location": "Second Floor"}'),
        ("It happened at 2 PM and we turned off the main valve.",
         '{"date_time": "2 PM", "immediate_actions_taken": "Turned off the main water valve", "incident_type": null}'),
    ],
    "asks_for_each_missing_field_in_turn": [
        ("Something happened.", '{"incident_description": "Something happened"}'),
        ("It was a fire.", '{"incident_type": "Fire"}'),
        ("In the warehouse.", '{"incident_location": "Warehouse"}'),
        ("At noon.", '{"date_time": "noon"}'),
        ("We evacuated.", '{"immediate_actions_taken": "Evacuated"}'),
    ],
    "garbage_llm_output_keeps_state": [
        ("A pipe burst.", '{"incident_type": "Pipe Burst"}'),
        ("Um.", "I could not parse that"),
    ],
}


def state_view(state: dict) -> dict:
    payload = state.get("tool_call_payload")
    return {
        "status": state["status"],
        "missing": state["missing_mandatory_fields"],
        "next_prompt": state["next_clarification_prompt"],
        "fields": state["fields"],
        "tool_call_function": payload["function"] if payload else None,
        "summary_for_tts": payload["summary_for_tts"] if payload else None,
    }


def main() -> None:
    out: dict = {"initial_prompt": INITIAL_PROMPT, "retry_prompt": RETRY_PROMPT}

    known = {k: None for k in ab.ALL_FIELDS}
    known.update({"incident_type": "Water Leak", "incident_location": "Conference Room 2"})
    out["prompts"] = [
        {"transcript": WATER, "known": {k: None for k in ab.ALL_FIELDS}, "prompt": ab.build_extraction_prompt(WATER, {k: None for k in ab.ALL_FIELDS})},
        {"transcript": "It was 10 AM", "known": known, "prompt": ab.build_extraction_prompt("It was 10 AM", known)},
    ]
    out["clean_and_parse"] = [{"raw": r, "parsed": ab.clean_and_parse_json(r)} for r in RAW_OUTPUTS]
    out["sanitize"] = [{"raw": r, "sanitized": sanitize_extracted(ab.clean_and_parse_json(r))} for r in RAW_OUTPUTS]

    sequences = {}
    for name, turns in SEQUENCES.items():
        state = blank_state()
        state["session_id"] = "session-test"
        steps = []
        for text, raw in turns:
            def llm(prompt: str, raw=raw) -> str:
                return json.dumps(sanitize_extracted(ab.clean_and_parse_json(raw)))

            state = ab.process_user_turn(text, state, llm)
            steps.append({"user": text, "raw_llm": raw, "result": state_view(state)})
        sequences[name] = steps
    out["sequences"] = sequences
    out["blank"] = state_view({**blank_state(), "tool_call_payload": None})

    path = ROOT / "android_bridge" / "app" / "src" / "test" / "resources" / "brain_golden.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size} bytes): {len(out['prompts'])} prompts, "
          f"{len(RAW_OUTPUTS)} raw outputs, {sum(len(v) for v in sequences.values())} turns")


if __name__ == "__main__":
    main()
