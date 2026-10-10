"""Unit tests for the rule-based fallback extractor."""

import json

import pytest

from backend import mock_npu
from backend.agent_brain import build_extraction_prompt
from backend.mock_npu import extract_incident_fields as ex


def test_slide3_example():
    f = ex("There was a water leak near Conference Room 2 around 10 AM. "
           "Maintenance has already isolated the area.")
    assert f["incident_type"] == "Water Leak"
    assert f["incident_location"] == "Conference Room 2"
    assert f["date_time"] == "10 AM"
    assert f["immediate_actions_taken"] == "Maintenance has already isolated the area"
    assert f["severity_level"] == "Medium"


def test_pipe_burst_second_floor():
    f = ex("A pipe burst on the second floor!")
    assert f["incident_type"] == "Pipe Burst"
    assert f["incident_location"] == "Second Floor"
    assert f["severity_level"] == "High"
    assert f["date_time"] is None
    assert f["immediate_actions_taken"] is None


def test_answer_turn_only_gives_time_and_action():
    f = ex("It happened at 2 PM and we turned off the main valve.")
    assert f["date_time"] == "2 PM"
    assert f["immediate_actions_taken"] == "We turned off the main valve"
    assert f["incident_type"] is None
    assert f["incident_location"] is None   # "at 2 PM" must not become a location
    assert f["equipment_asset_involved"] is None
    assert f["incident_description"] is None


@pytest.mark.parametrize("text,expected", [
    ("It happened at 2:30 pm", "2:30 PM"),
    ("It was around 9 a.m.", "9 AM"),
    ("It happened yesterday at 4 PM", "Yesterday at 4 PM"),
    ("It was 14:45", "14:45"),
    ("It happened just now", "Just now"),
    ("It happened this morning", "This morning"),
])
def test_date_time_forms(text, expected):
    assert ex(text)["date_time"] == expected


def test_fire_with_persons_witness_followup():
    f = ex("A small fire started in the server room, two employees were nearby and it was witnessed by "
           "John and Mary. We called security and the wiring needs to be inspected.")
    assert f["incident_type"] == "Fire"
    assert f["incident_location"] == "Server Room"
    assert f["severity_level"] == "Low"
    assert "Two employees" in f["persons_involved"]
    assert f["witness_information"] == "John and Mary"
    assert "called security" in f["immediate_actions_taken"]
    assert f["recommended_follow_up_action"] == "The wiring needs to be inspected"


def test_no_action_yet_is_a_valid_answer():
    assert ex("Nothing has been done yet")["immediate_actions_taken"] == "No immediate action taken yet"


def test_action_clause_does_not_pollute_type_or_equipment():
    f = ex("We used the fire extinguisher and shut down the pump")
    assert f["incident_type"] is None
    assert f["equipment_asset_involved"] is None


def test_empty_input():
    assert all(v is None for v in ex("").values())


def test_run_llm_reads_transcript_from_brain_prompt():
    prompt = build_extraction_prompt("A gas leak in the lab at 5 PM.", {"incident_type": "X"})
    out = json.loads(mock_npu.run_llm(prompt))
    assert out["incident_type"] == "Gas Leak"
    assert out["incident_location"] == "Lab"
    assert out["date_time"] == "5 PM"
