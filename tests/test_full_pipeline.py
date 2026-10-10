"""End-to-end tests for the orchestrator (HTTP -> runtime -> agent_brain -> contract.json)."""

import json
import sys
import types

import pytest
from fastapi.testclient import TestClient

from backend import mock_npu, runtime
from backend.agent_brain import ALL_FIELDS
from backend.server import create_app

SLIDE3 = ("There was a water leak near Conference Room 2 around 10 AM. "
          "Maintenance has already isolated the area.")


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("NPU_BACKEND", "mock")
    monkeypatch.setenv("TTS_ENABLED", "0")
    runtime.reset_health()
    yield
    sys.modules.pop("backend.npu_runtime", None)
    runtime.reset_health()


@pytest.fixture
def ctx(tmp_path):
    path = tmp_path / "contract.json"
    return TestClient(create_app(path)), path


def test_two_turn_clarification_flow(ctx):
    client, path = ctx

    r1 = client.post("/api/text/turn", json={"text": "A pipe burst in building 4"})
    assert r1.status_code == 200
    s1 = r1.json()["state"]
    assert s1["status"] == "collecting"
    assert s1["missing_mandatory_fields"] == ["date_time", "immediate_actions_taken"]
    assert s1["next_clarification_prompt"] == "Got that. At what time or date did this occur?"
    assert s1["tool_call_payload"] is None
    assert s1["fields"]["incident_type"] == "Pipe Burst"
    assert s1["fields"]["incident_location"] == "Building 4"
    assert r1.json()["assistant_speech"] == s1["next_clarification_prompt"]

    r2 = client.post("/api/text/turn", json={"text": "It happened at 3 PM and we turned off the valve"})
    s2 = r2.json()["state"]
    assert s2["status"] == "complete"
    assert s2["missing_mandatory_fields"] == []
    assert s2["tool_call_payload"]["function"] == "populate_incident_form"
    assert s2["fields"]["incident_type"] == "Pipe Burst"          # earlier turn preserved
    assert s2["fields"]["incident_location"] == "Building 4"      # not overwritten by nulls
    assert s2["fields"]["date_time"] == "3 PM"
    assert "turned off the valve" in s2["fields"]["immediate_actions_taken"].lower()
    assert r2.json()["assistant_speech"] == s2["tool_call_payload"]["summary_for_tts"]


def test_single_turn_slide3_example_completes(ctx):
    client, _ = ctx
    state = client.post("/api/text/turn", json={"text": SLIDE3}).json()["state"]
    assert state["status"] == "complete"
    f = state["fields"]
    assert f["incident_type"] == "Water Leak"
    assert f["incident_location"] == "Conference Room 2"
    assert f["date_time"] == "10 AM"
    assert "isolated" in f["immediate_actions_taken"].lower()
    assert state["tool_call_payload"]["arguments"] == f


def test_contract_json_persisted_with_locked_keys(ctx):
    client, path = ctx
    client.post("/api/text/turn", json={"text": SLIDE3})
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["status"] == "complete"
    assert list(saved["fields"].keys()) == ALL_FIELDS
    assert client.get("/api/state").json() == saved
    # a fresh app on the same file resumes the session
    resumed = TestClient(create_app(path)).get("/api/state").json()
    assert resumed["status"] == "complete"
    assert resumed["fields"] == saved["fields"]


def test_transcript_endpoint_records_both_roles(ctx):
    client, _ = ctx
    client.post("/api/text/turn", json={"text": "A pipe burst in building 4"})
    roles = [m["role"] for m in client.get("/api/transcript").json()]
    assert roles == ["user", "assistant"]


def test_submit_flow_and_reset(ctx):
    client, path = ctx
    # not ready yet
    client.post("/api/text/turn", json={"text": "A pipe burst in building 4"})
    assert client.post("/api/submit").status_code == 409

    client.post("/api/text/turn", json={"text": "It happened at 3 PM and we turned off the valve"})
    r = client.post("/api/submit", json={"fields": {"persons_involved": "Two engineers"}})
    assert r.status_code == 200
    assert r.json()["state"]["status"] == "submitted"
    assert r.json()["state"]["fields"]["persons_involved"] == "Two engineers"
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "submitted"

    # closed until reset
    assert client.post("/api/text/turn", json={"text": "hello"}).status_code == 409
    assert client.post("/api/submit").status_code == 409

    blank = client.post("/api/reset").json()["state"]
    assert blank["status"] == "collecting"
    assert all(v is None for v in blank["fields"].values())
    assert client.get("/api/transcript").json() == []


def test_submit_edit_cannot_blank_mandatory_field(ctx):
    client, _ = ctx
    client.post("/api/text/turn", json={"text": SLIDE3})
    assert client.post("/api/submit", json={"fields": {"incident_location": ""}}).status_code == 409
    assert client.post("/api/submit", json={"fields": {"bogus": "x"}}).status_code == 422


def test_empty_text_rejected(ctx):
    client, _ = ctx
    assert client.post("/api/text/turn", json={"text": "   "}).status_code == 400


def test_invalid_llm_output_never_completes(ctx, monkeypatch):
    client, _ = ctx
    monkeypatch.setattr(mock_npu, "run_llm", lambda prompt: "I am sorry, I cannot do that.")
    state = client.post("/api/text/turn", json={"text": SLIDE3}).json()["state"]
    assert state["status"] == "collecting"
    assert state["tool_call_payload"] is None


def test_bad_severity_and_nonstring_values_are_sanitized(ctx, monkeypatch):
    client, _ = ctx
    monkeypatch.setattr(mock_npu, "run_llm", lambda prompt: json.dumps({
        "incident_type": "Fire", "severity_level": "Catastrophic",
        "incident_location": ["Lab", "Room 3"], "date_time": 1400,
        "immediate_actions_taken": "Evacuated",
    }))
    state = client.post("/api/text/turn", json={"text": "x"}).json()["state"]
    assert state["fields"]["severity_level"] is None
    assert state["fields"]["incident_location"] == "Lab, Room 3"
    assert state["fields"]["date_time"] == "1400"
    assert state["status"] == "complete"


def test_audio_turn_uses_stt_then_pipeline(ctx, monkeypatch):
    client, _ = ctx
    monkeypatch.setattr(mock_npu, "run_stt", lambda p: "A pipe burst in building 4")
    r = client.post("/api/audio/turn", files={"file": ("clip.wav", b"RIFFfake", "audio/wav")})
    assert r.status_code == 200
    assert r.json()["user_transcript"] == "A pipe burst in building 4"
    assert r.json()["state"]["status"] == "collecting"
    assert r.json()["engine"]["last_stt_backend"] == "mock"


def test_audio_turn_silence_asks_to_repeat_without_changing_state(ctx, monkeypatch):
    client, _ = ctx
    before = client.get("/api/state").json()
    monkeypatch.setattr(mock_npu, "run_stt", lambda p: "")
    r = client.post("/api/audio/turn", files={"file": ("clip.wav", b"RIFFfake", "audio/wav")})
    assert r.status_code == 200
    assert "didn't catch" in r.json()["assistant_speech"]
    assert client.get("/api/state").json() == before


def test_audio_turn_without_any_stt_is_503(ctx):
    client, _ = ctx
    r = client.post("/api/audio/turn", files={"file": ("clip.wav", b"RIFFfake", "audio/wav")})
    assert r.status_code == 503
    assert "faster-whisper" in r.json()["detail"] or "transcript" in r.json()["detail"]


def test_audio_turn_sidecar_transcript(tmp_path):
    wav = tmp_path / "demo.wav"
    wav.write_bytes(b"RIFFfake")
    (tmp_path / "demo.txt").write_text(SLIDE3, encoding="utf-8")
    assert mock_npu.run_stt(str(wav)) == SLIDE3


def test_mic_trigger_unavailable_is_501(ctx, monkeypatch):
    client, _ = ctx

    def no_mic():
        raise runtime.EngineUnavailable("Mic capture unavailable")

    monkeypatch.setattr(runtime, "record_audio", no_mic)
    assert client.post("/api/audio/turn").status_code == 501


def test_mic_trigger_records_then_runs_turn(ctx, monkeypatch, tmp_path):
    client, _ = ctx
    wav = tmp_path / "mic.wav"
    wav.write_bytes(b"RIFFfake")
    monkeypatch.setattr(runtime, "record_audio", lambda: str(wav))
    monkeypatch.setattr(mock_npu, "run_stt", lambda p: "A pipe burst in building 4")
    r = client.post("/api/audio/turn")
    assert r.status_code == 200
    assert r.json()["state"]["fields"]["incident_type"] == "Pipe Burst"


def test_tts_hook_receives_assistant_speech(ctx, monkeypatch):
    client, _ = ctx
    spoken = []
    monkeypatch.setattr(runtime, "speak", lambda text: spoken.append(text) or True)
    client.post("/api/text/turn", json={"text": "A pipe burst in building 4"})
    assert spoken == ["Got that. At what time or date did this occur?"]


def _install_fake_device(monkeypatch, fail):
    calls = {"llm": 0}
    mod = types.ModuleType("backend.npu_runtime")

    def run_llm(prompt):
        calls["llm"] += 1
        if fail:
            raise ConnectionError("adb forward not active")
        return json.dumps({"incident_type": "DEVICE", "incident_location": "HDK",
                           "date_time": "now", "immediate_actions_taken": "none"})

    mod.run_llm = run_llm
    mod.run_stt = lambda p: "from device"
    monkeypatch.setitem(sys.modules, "backend.npu_runtime", mod)
    return calls


def test_auto_mode_prefers_device_when_healthy(ctx, monkeypatch):
    client, _ = ctx
    monkeypatch.setenv("NPU_BACKEND", "auto")
    _install_fake_device(monkeypatch, fail=False)
    r = client.post("/api/text/turn", json={"text": "anything"})
    assert r.json()["state"]["fields"]["incident_type"] == "DEVICE"
    assert r.json()["engine"]["last_llm_backend"] == "device"


def test_auto_mode_falls_back_to_mock_and_cools_down(ctx, monkeypatch):
    client, _ = ctx
    monkeypatch.setenv("NPU_BACKEND", "auto")
    calls = _install_fake_device(monkeypatch, fail=True)
    r1 = client.post("/api/text/turn", json={"text": SLIDE3})
    assert r1.status_code == 200
    assert r1.json()["state"]["status"] == "complete"
    assert r1.json()["engine"]["last_llm_backend"] == "mock"
    client.post("/api/reset")
    client.post("/api/text/turn", json={"text": SLIDE3})
    assert calls["llm"] == 1  # board skipped during cooldown


def test_device_mode_never_falls_back(ctx, monkeypatch):
    client, _ = ctx
    monkeypatch.setenv("NPU_BACKEND", "device")
    _install_fake_device(monkeypatch, fail=True)
    r = client.post("/api/text/turn", json={"text": SLIDE3})
    assert r.status_code == 503
    assert client.get("/api/state").json()["status"] == "collecting"


def test_health_endpoint(ctx):
    client, _ = ctx
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["engine"]["mode"] == "mock"
