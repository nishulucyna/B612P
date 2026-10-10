"""
backend/agent_brain.py
Core Agentic Information Extraction and Tool Calling module for On-Device AI Incident Report Assistant.
Conforms strictly to Qualcomm Megathon X Problem Statement.
"""

import json
import re
import uuid
from typing import Callable, Dict, List, Literal, Optional, Any
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 1. DATA CONTRACT & PYDANTIC MODELS
# ---------------------------------------------------------------------------

SeverityType = Literal["Low", "Medium", "High", "Critical"]

MANDATORY_FIELDS = [
    "incident_type",
    "incident_location",
    "date_time",
    "immediate_actions_taken"
]

ALL_FIELDS = [
    "incident_type",
    "severity_level",
    "incident_location",
    "date_time",
    "persons_involved",
    "equipment_asset_involved",
    "incident_description",
    "immediate_actions_taken",
    "witness_information",
    "recommended_follow_up_action"
]


class IncidentFields(BaseModel):
    incident_type: Optional[str] = Field(None, description="Type/category of incident (e.g. Water Leak, Chemical Spill, Power Outage)")
    severity_level: Optional[SeverityType] = Field(None, description="Severity: Low, Medium, High, or Critical")
    incident_location: Optional[str] = Field(None, description="Specific location where incident occurred")
    date_time: Optional[str] = Field(None, description="When the incident happened or was observed")
    persons_involved: Optional[str] = Field(None, description="Names, roles, or counts of persons involved")
    equipment_asset_involved: Optional[str] = Field(None, description="Equipment, machinery, or assets affected")
    incident_description: Optional[str] = Field(None, description="Clear summary of what transpired")
    immediate_actions_taken: Optional[str] = Field(None, description="Immediate measures taken to mitigate or isolate")
    witness_information: Optional[str] = Field(None, description="Names or statements from witnesses")
    recommended_follow_up_action: Optional[str] = Field(None, description="Suggested next steps or repairs needed")


class IncidentState(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: Literal["collecting", "complete", "submitted"] = "collecting"
    missing_mandatory_fields: List[str] = Field(default_factory=lambda: list(MANDATORY_FIELDS))
    next_clarification_prompt: Optional[str] = None
    fields: IncidentFields = Field(default_factory=IncidentFields)
    tool_call_payload: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# 2. EXTRACTION PROMPT TEMPLATES (OPTIMIZED FOR COMPACT SLMs / LLMs)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an on-device AI Incident Report Assistant for Qualcomm Snapdragon devices.
Your task is to extract structured incident data from natural spoken user reports.

Extract only what the user mentioned or clearly implied into this JSON schema:
{
  "incident_type": string or null,
  "severity_level": "Low" | "Medium" | "High" | "Critical" | null,
  "incident_location": string or null,
  "date_time": string or null,
  "persons_involved": string or null,
  "equipment_asset_involved": string or null,
  "incident_description": string or null,
  "immediate_actions_taken": string or null,
  "witness_information": string or null,
  "recommended_follow_up_action": string or null
}

Rules:
1. Return ONLY a valid JSON object. No preamble, no markdown backticks, no explanations.
2. If an item was not mentioned, set its value to null.
3. If partial existing fields are provided, preserve them unless the user explicitly updates or corrects them.
4. Estimate severity_level if strongly implied (e.g., "burst pipe flooded room" -> "High", "minor drip" -> "Low").
"""


def build_extraction_prompt(user_transcript: str, current_fields: Dict[str, Any]) -> str:
    non_null_context = {k: v for k, v in current_fields.items() if v is not None}
    
    prompt = f"""{SYSTEM_PROMPT}

CURRENT KNOWN INFORMATION:
{json.dumps(non_null_context, indent=2)}

LATEST USER TRANSCRIPT:
"{user_transcript}"

JSON OUTPUT:"""
    return prompt


# ---------------------------------------------------------------------------
# 3. ROBUST JSON PARSER FOR ON-DEVICE SLMs
# ---------------------------------------------------------------------------

def clean_and_parse_json(raw_llm_response: str) -> Dict[str, Any]:
    """Cleans backticks, extra prose, and parses JSON output reliably."""
    text = raw_llm_response.strip()
    
    # Strip markdown code blocks if model included them
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    # Find outermost JSON object
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        text = match.group(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback heuristic parser if model dropped closing braces
        text_fixed = text + "}"
        try:
            return json.loads(text_fixed)
        except Exception:
            return {}


# ---------------------------------------------------------------------------
# 4. FIELD MERGING & RECONCILIATION LOGIC
# ---------------------------------------------------------------------------

def merge_extracted_fields(current: Dict[str, Any], extracted: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merges newly extracted fields into current state without overwriting non-null
    values with nulls. Updates only if newly extracted value is non-empty.
    """
    merged = dict(current)
    for field in ALL_FIELDS:
        new_val = extracted.get(field)
        if new_val is not None and str(new_val).strip() != "" and str(new_val).lower() != "null":
            merged[field] = new_val
    return merged


def identify_missing_mandatory(fields: Dict[str, Any]) -> List[str]:
    """Finds which of the 4 mandatory fields are currently None or empty."""
    missing = []
    for f in MANDATORY_FIELDS:
        val = fields.get(f)
        if val is None or str(val).strip() == "" or str(val).lower() == "null":
            missing.append(f)
    return missing


def generate_clarification_question(missing_field: str, current_fields: Dict[str, Any]) -> str:
    """Generates natural, single-sentence conversational clarification prompts."""
    friendly_names = {
        "incident_type": "what kind of incident occurred",
        "incident_location": "the exact location of the incident",
        "date_time": "when this took place",
        "immediate_actions_taken": "what immediate action has been taken so far"
    }
    
    inc_type = current_fields.get("incident_type")
    
    if missing_field == "incident_location":
        return f"Understood. Where did this {inc_type or 'incident'} occur?"
    elif missing_field == "date_time":
        return "Got that. At what time or date did this occur?"
    elif missing_field == "immediate_actions_taken":
        return "Understood. Has any immediate action or containment been taken yet?"
    elif missing_field == "incident_type":
        return "Could you clarify what kind of incident took place?"
    else:
        desc = friendly_names.get(missing_field, missing_field.replace('_', ' '))
        return f"Could you provide details regarding {desc}?"


# ---------------------------------------------------------------------------
# 5. THE DECISION GATE (THE DIAMOND CHECK)
# ---------------------------------------------------------------------------

def process_user_turn(
    user_transcript: str,
    current_state: Dict[str, Any],
    llm_engine_fn: Callable[[str], str]
) -> Dict[str, Any]:
    """
    Main state machine function:
    1. Runs extraction with llm_engine_fn
    2. Merges with conversational state
    3. Evaluates Mandatory Fields diamond condition
    4. Triggers either clarification question (collecting) or tool call payload (complete)
    """
    session_id = current_state.get("session_id", str(uuid.uuid4())[:8])
    curr_fields = current_state.get("fields", {})

    # a. Extraction Prompt & LLM call
    prompt = build_extraction_prompt(user_transcript, curr_fields)
    raw_response = llm_engine_fn(prompt)
    extracted = clean_and_parse_json(raw_response)

    # b. Merge into persistent memory
    updated_fields = merge_extracted_fields(curr_fields, extracted)

    # c. Diamond Check: Mandatory Fields Gate
    missing = identify_missing_mandatory(updated_fields)

    if missing:
        # State: Incomplete -> Ask for the first missing mandatory field
        first_missing = missing[0]
        clarification = generate_clarification_question(first_missing, updated_fields)
        
        return {
            "session_id": session_id,
            "status": "collecting",
            "missing_mandatory_fields": missing,
            "next_clarification_prompt": clarification,
            "fields": updated_fields,
            "tool_call_payload": None
        }
    else:
        # State: Complete -> Construct Function/Tool Call
        tool_call_payload = {
            "function": "populate_incident_form",
            "arguments": updated_fields,
            "ready_for_submission": True,
            "summary_for_tts": (
                f"Incident report ready. {updated_fields.get('incident_type', 'Incident')} "
                f"at {updated_fields.get('incident_location', 'specified location')}, "
                f"recorded at {updated_fields.get('date_time', 'time specified')}. "
                f"Action taken: {updated_fields.get('immediate_actions_taken', 'noted')}. "
                "Please review on screen and confirm submission."
            )
        }

        return {
            "session_id": session_id,
            "status": "complete",
            "missing_mandatory_fields": [],
            "next_clarification_prompt": None,
            "fields": updated_fields,
            "tool_call_payload": tool_call_payload
        }


# ---------------------------------------------------------------------------
# 6. LOCAL TESTING HARNESS (MOCKING QUALCOMM LLM ENGINE)
# ---------------------------------------------------------------------------

def mock_qualcomm_llm_engine(prompt: str) -> str:
    """Simulates Snapdragon NPU Llama 3.2 1B/3B JSON response for local testing."""
    # Split prompt to inspect latest user transcript directly
    latest_transcript = ""
    if "LATEST USER TRANSCRIPT:" in prompt:
        latest_transcript = prompt.split("LATEST USER TRANSCRIPT:")[-1].lower()
    else:
        latest_transcript = prompt.lower()
    
    if "happened at 2 pm" in latest_transcript or "turned off the main valve" in latest_transcript:
        # Multi-turn clarification resolution
        return json.dumps({
            "date_time": "2:00 PM",
            "immediate_actions_taken": "Turned off the main water valve"
        })
    elif "water leak near conference room 2" in latest_transcript:
        return json.dumps({
            "incident_type": "Water Leak",
            "severity_level": "Medium",
            "incident_location": "Conference Room 2",
            "date_time": "10:00 AM",
            "persons_involved": None,
            "equipment_asset_involved": None,
            "incident_description": "Water leak observed near Conference Room 2.",
            "immediate_actions_taken": "Maintenance has already isolated the area",
            "witness_information": None,
            "recommended_follow_up_action": "Inspect plumbing and repair leak"
        })
    elif "pipe burst on the second floor" in latest_transcript:
        return json.dumps({
            "incident_type": "Pipe Burst / Flooding",
            "severity_level": "High",
            "incident_location": "Second Floor",
            "date_time": None,
            "persons_involved": None,
            "equipment_asset_involved": "Plumbing Pipes",
            "incident_description": "A pipe burst on the second floor causing water discharge.",
            "immediate_actions_taken": None,
            "witness_information": None,
            "recommended_follow_up_action": None
        })
    else:
        return json.dumps({
            "incident_description": "General incident reported."
        })


if __name__ == "__main__":
    print("=" * 70)
    print(" QUALCOMM INCIDENT REPORT ASSISTANT — AGENTIC BRAIN TEST HARNESS")
    print("=" * 70)

    # Initial state directly matching contract.json
    with open("contract.json", "r") as f:
        initial_state = json.load(f)

    # -----------------------------------------------------------------------
    # TEST CASE 1: Complete in 1 turn (Slide 3 Example Input)
    # -----------------------------------------------------------------------
    turn1_text = "There was a water leak near Conference Room 2 around 10 AM. Maintenance has already isolated the area."
    print("\n[TEST 1] Single-turn Complete Input:")
    print(f"User: '{turn1_text}'")
    
    result1 = process_user_turn(turn1_text, initial_state, mock_qualcomm_llm_engine)
    print(f"\nStatus: {result1['status'].upper()}")
    print(f"Missing Mandatory Fields: {result1['missing_mandatory_fields']}")
    print(f"Fields Extracted: {json.dumps(result1['fields'], indent=2)}")
    if result1["tool_call_payload"]:
        print(f"\n[TOOL CALL TRIGGERED]: {result1['tool_call_payload']['function']}")
        print(f"TTS Spoken Confirmation: {result1['tool_call_payload']['summary_for_tts']}")
    
    assert result1["status"] == "complete", "Test 1 should be complete!"
    print("\n>>> TEST 1 PASSED.")

    # -----------------------------------------------------------------------
    # TEST CASE 2: Multi-turn Dialogue (Missing Mandatory Fields)
    # -----------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[TEST 2] Multi-turn Dialogue (Incomplete -> Clarify -> Complete):")
    
    turn2_a_text = "A pipe burst on the second floor!"
    print(f"\nTurn 2a User: '{turn2_a_text}'")
    
    state_2a = process_user_turn(turn2_a_text, initial_state, mock_qualcomm_llm_engine)
    print(f"Status: {state_2a['status'].upper()}")
    print(f"Missing Mandatory Fields: {state_2a['missing_mandatory_fields']}")
    print(f"Assistant Clarification Prompt: \"{state_2a['next_clarification_prompt']}\"")
    assert state_2a["status"] == "collecting", "Turn 2a must be collecting!"

    # User answers the clarification
    turn2_b_text = "It happened at 2 PM and we turned off the main valve."
    print(f"\nTurn 2b User answers: '{turn2_b_text}'")
    
    state_2b = process_user_turn(turn2_b_text, state_2a, mock_qualcomm_llm_engine)
    print(f"Status: {state_2b['status'].upper()}")
    print(f"Missing Mandatory Fields: {state_2b['missing_mandatory_fields']}")
    print(f"Consolidated Fields: {json.dumps(state_2b['fields'], indent=2)}")
    if state_2b["tool_call_payload"]:
        print(f"\n[TOOL CALL TRIGGERED]: {state_2b['tool_call_payload']['function']}")
        print(f"TTS Spoken Confirmation: {state_2b['tool_call_payload']['summary_for_tts']}")
    
    assert state_2b["status"] == "complete", "Turn 2b must complete all mandatory fields!"
    print("\n>>> TEST 2 (MULTI-TURN CLARIFICATION LOOP) PASSED.")
    print("=" * 70)
