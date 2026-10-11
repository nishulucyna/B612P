import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from llm_guard import guard  # noqa: E402


def prompt(text):
    return f'x\n\nLATEST USER TRANSCRIPT:\n"{text}"\n\nJSON OUTPUT:'


def run(text, **fields):
    return json.loads(guard(prompt(text), json.dumps(fields)))


def test_placeholder_dates_are_dropped():
    assert "date_time" not in run("gas smell in the basement", incident_type="gas", date_time="current time")
    assert "date_time" not in run("gas smell", date_time="current time (not specified)")
    assert "date_time" not in run("gas smell", date_time="Date not specified")


def test_real_values_survive():
    assert run("a leak yesterday at 3 PM", date_time="yesterday at 3 PM")["date_time"] == "yesterday at 3 PM"
    assert run("someone fainted just now", date_time="just now")["date_time"] == "just now"
    assert run("an unknown man was near gate 2", persons_involved="Unknown man near gate 2")["persons_involved"] == "Unknown man near gate 2"
    assert run("cause is not known yet", incident_description="The cause is not known yet and we are checking everything")["incident_description"]


def test_invented_followup_is_dropped():
    out = run("water leak near conference room 2, maintenance isolated the area",
              recommended_follow_up_action="Inspect the area for further issues and ensure proper drainage", incident_type="water leak")
    assert "recommended_follow_up_action" not in out and out["incident_type"] == "water leak"


def test_grounded_followup_and_names_survive():
    out = run("the pipe burst, someone should replace the pipe and check the valves",
              recommended_follow_up_action="Replace the pipe and check the valves")
    assert out["recommended_follow_up_action"]
    assert run("Dr. Menon moved the samples", persons_involved="Dr. Menon")["persons_involved"] == "Dr. Menon"


def test_severity_is_left_alone_and_garbage_passes_through():
    assert run("something happened", severity_level="High")["severity_level"] == "High"
    assert guard("p", "not json") == "not json"
