"""
frontend/app.py
Sector 4 — Incident Dashboard & Live UI  (v2 — Clean Professional Redesign)
Qualcomm Megathon X · On-Device AI Incident Report Assistant
Branch: feat/form-ui

Run with:
    streamlit run frontend/app.py
"""

import json
import uuid
import sys
from copy import deepcopy
from pathlib import Path
from datetime import datetime

import os

import requests
import streamlit as st

# ── Path Setup ──────────────────────────────────────────────────────────────
ROOT_DIR      = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT_DIR / "contract.json"
sys.path.insert(0, str(ROOT_DIR / "backend"))

# ── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Incident Report Assistant · Qualcomm",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Global ── */
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.stApp {
    background: #060c1a !important;
    color: #e2e8f0 !important;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 2.5rem !important; max-width: 1300px !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #0a1628 !important;
    border-right: 1px solid #1e3a5f !important;
}
[data-testid="stSidebar"] * { color: #cbd5e1 !important; }

/* ── Top Banner ── */
.top-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: linear-gradient(135deg, #0f2044 0%, #0a1628 100%);
    border: 1px solid #1e3a5f;
    border-radius: 14px;
    padding: 20px 28px;
    margin-bottom: 1.5rem;
}
.banner-left { display: flex; align-items: center; gap: 16px; }
.banner-icon {
    width: 48px; height: 48px; border-radius: 12px;
    background: linear-gradient(135deg, #1d4ed8, #3b82f6);
    display: flex; align-items: center; justify-content: center;
    font-size: 22px;
    box-shadow: 0 0 20px rgba(59,130,246,0.4);
}
.banner-title { font-size: 1.25rem; font-weight: 800; color: #f1f5f9; margin: 0; }
.banner-sub   { font-size: 0.72rem; font-weight: 500; color: #64748b;
                text-transform: uppercase; letter-spacing: 0.1em; margin: 2px 0 0; }
.npu-chip {
    background: rgba(59,130,246,0.12);
    border: 1px solid rgba(59,130,246,0.4);
    color: #93c5fd;
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; padding: 6px 14px; border-radius: 20px;
}

/* ── Status Pill ── */
.pill {
    display: inline-flex; align-items: center; gap: 7px;
    padding: 7px 16px; border-radius: 20px;
    font-size: 0.75rem; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase;
}
.pill-collecting {
    background: rgba(234,179,8,0.12); border: 1px solid rgba(234,179,8,0.45); color: #fbbf24;
    animation: blink 2s ease-in-out infinite;
}
.pill-complete   { background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.45);  color: #4ade80; }
.pill-submitted  { background: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.5); color: #93c5fd; }
@keyframes blink {
    0%,100% { opacity: 1; }
    50%      { opacity: 0.6; }
}

/* ── Section Heading ── */
.sec-head {
    font-size: 0.65rem; font-weight: 700; letter-spacing: 0.14em;
    text-transform: uppercase; color: #334155;
    margin: 0 0 10px; padding-bottom: 8px;
    border-bottom: 1px solid #1e3a5f;
}

/* ── Metric Tiles ── */
.metric-row { display: flex; gap: 12px; margin-bottom: 1.25rem; }
.metric-tile {
    flex: 1; background: #0a1628;
    border: 1px solid #1e3a5f; border-radius: 12px;
    padding: 14px 16px; text-align: center;
}
.metric-num { font-size: 1.75rem; font-weight: 800; color: #3b82f6; line-height: 1; }
.metric-num-green { color: #22c55e; }
.metric-lbl { font-size: 0.62rem; color: #475569; text-transform: uppercase;
              letter-spacing: 0.1em; margin-top: 4px; }

/* ── Progress Bar ── */
.prog-wrap  { background: #1e293b; border-radius: 6px; height: 6px;
              margin-bottom: 1.25rem; overflow: hidden; }
.prog-fill  { height: 100%; border-radius: 6px;
              background: linear-gradient(90deg, #1d4ed8, #3b82f6);
              transition: width 0.5s ease; }

/* ── Field Card ── */
.f-card {
    border-radius: 10px; padding: 12px 16px;
    margin-bottom: 10px; transition: all 0.35s ease;
    position: relative;
}
.f-card-empty {
    background: #0a1628;
    border: 1px solid #1e3a5f;
}
.f-card-required {
    background: rgba(234,179,8,0.05);
    border: 1px solid rgba(234,179,8,0.3);
}
.f-card-filled {
    background: rgba(34,197,94,0.06);
    border: 1px solid rgba(34,197,94,0.35);
    box-shadow: 0 0 14px rgba(34,197,94,0.12);
}
.f-label {
    font-size: 0.62rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; margin-bottom: 4px;
}
.f-label-empty    { color: #334155; }
.f-label-required { color: #ca8a04; }
.f-label-filled   { color: #16a34a; }
.f-value { font-size: 0.88rem; color: #e2e8f0; }
.f-empty { font-size: 0.82rem; color: #334155; font-style: italic; }
.f-tag {
    display: inline-block; font-size: 0.58rem; font-weight: 700;
    letter-spacing: 0.07em; padding: 2px 8px; border-radius: 8px;
    margin-left: 8px; vertical-align: middle; text-transform: uppercase;
}
.f-tag-req  { background: rgba(234,179,8,0.15);  color: #fbbf24; }
.f-tag-npu  { background: rgba(34,197,94,0.15);  color: #4ade80; }
.f-tag-mand { background: rgba(59,130,246,0.12); color: #60a5fa; }

/* ── Severity Chips ── */
.sev { display:inline-block; padding:3px 11px; border-radius:12px;
       font-size:0.7rem; font-weight:700; text-transform:uppercase; letter-spacing:0.07em; }
.sev-Low      { background:rgba(34,197,94,0.15);  color:#4ade80; }
.sev-Medium   { background:rgba(234,179,8,0.15);  color:#fbbf24; }
.sev-High     { background:rgba(249,115,22,0.15); color:#fb923c; }
.sev-Critical { background:rgba(239,68,68,0.15);  color:#f87171; }

/* ── Chat Bubbles ── */
.chat-wrap { display:flex; gap:10px; margin-bottom:14px; align-items:flex-start; }
.chat-av {
    width:32px; height:32px; border-radius:50%; flex-shrink:0;
    display:flex; align-items:center; justify-content:center; font-size:14px;
}
.chat-av-u { background:rgba(59,130,246,0.2); border:1px solid rgba(59,130,246,0.4); }
.chat-av-a { background:rgba(30,58,95,0.8);   border:1px solid rgba(59,130,246,0.25); }
.chat-bub  { padding:10px 14px; border-radius:12px; font-size:0.83rem; line-height:1.55; max-width:90%; }
.chat-bub-u { background:#0f2044; border:1px solid #1e3a5f;          color:#93c5fd; }
.chat-bub-a { background:#071020; border:1px solid rgba(59,130,246,0.2); color:#94a3b8; }
.chat-ts    { font-size:0.6rem; color:#334155; margin-top:3px; }

/* ── Mic Button ── */
.mic-area {
    background: #0a1628; border: 1px solid #1e3a5f;
    border-radius: 12px; padding: 20px; text-align: center;
    margin-bottom: 14px;
}
.mic-pulse {
    width: 56px; height: 56px; border-radius: 50%; margin: 0 auto 12px;
    background: linear-gradient(135deg, #1d4ed8, #3b82f6);
    display: flex; align-items: center; justify-content: center; font-size: 24px;
    box-shadow: 0 0 0 0 rgba(59,130,246,0.5);
    animation: mic-ring 2s ease-in-out infinite;
}
.mic-pulse-active { animation: mic-ring-fast 0.8s ease-in-out infinite; background: linear-gradient(135deg,#dc2626,#ef4444); box-shadow: 0 0 0 0 rgba(239,68,68,0.5); }
@keyframes mic-ring      { 0%,100%{box-shadow:0 0 0 0 rgba(59,130,246,0.4);}  50%{box-shadow:0 0 0 14px rgba(59,130,246,0);} }
@keyframes mic-ring-fast { 0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,0.5);}  50%{box-shadow:0 0 0 18px rgba(239,68,68,0);} }
.mic-label { font-size:0.78rem; color:#475569; }
.mic-label-active { color:#fca5a5; font-weight:600; }

/* ── AI Prompt Banner ── */
.ai-banner {
    background: rgba(29,78,216,0.1); border: 1px solid rgba(59,130,246,0.35);
    border-left: 3px solid #3b82f6; border-radius: 10px;
    padding: 12px 16px; margin-bottom: 14px;
}
.ai-banner-label { font-size:0.6rem; font-weight:700; letter-spacing:0.1em;
                   text-transform:uppercase; color:#3b82f6; margin-bottom:5px; }
.ai-banner-text  { font-size:0.88rem; color:#bfdbfe; line-height:1.5; }

/* ── Submit Button ── */
.stButton > button {
    border-radius: 10px !important; font-weight: 700 !important;
    font-family: 'Inter', sans-serif !important;
    letter-spacing: 0.03em !important; transition: all 0.2s ease !important;
}
button[kind="primary"] {
    background: linear-gradient(135deg, #1d4ed8, #3b82f6) !important;
    border: none !important; color: white !important;
    box-shadow: 0 4px 20px rgba(59,130,246,0.35) !important;
}
button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 8px 28px rgba(59,130,246,0.5) !important;
}

/* ── Inputs ── */
.stTextArea textarea, .stTextInput input {
    background: #071020 !important; border: 1px solid #1e3a5f !important;
    border-radius: 8px !important; color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.2) !important;
}
.stSelectbox > div > div {
    background: #071020 !important; border: 1px solid #1e3a5f !important;
    border-radius: 8px !important; color: #e2e8f0 !important;
}
label { color: #64748b !important; font-size: 0.78rem !important; font-weight: 500 !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #1e3a5f; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# ── Phone layout ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* the controls live in the main page, so no sidebar is needed (and it would cover the report on a phone) */
[data-testid="stSidebar"], [data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
.stButton > button { min-height: 46px; }
/* secondary buttons (Undo, Sync, Reset): readable light-on-dark instead of pale text on white */
/* (no ".stButton >" here: a button with a help tooltip is wrapped in an extra element, so that would not match) */
button[data-testid="stBaseButton-secondary"] {
  background: #1e293b !important; color: #e2e8f0 !important; border: 1px solid #475569 !important; }
button[data-testid="stBaseButton-secondary"]:disabled { opacity: 0.5; }
@media (max-width: 700px) {
  .block-container { padding: 0.8rem 0.7rem 3.5rem !important; max-width: 100% !important; }
  .top-banner { flex-direction: column !important; align-items: flex-start !important; gap: 8px !important; padding: 12px 14px !important; }
  .top-banner > div:last-child { flex-wrap: wrap; }
  .banner-title { font-size: 1.05rem !important; }
  .banner-sub { font-size: 0.7rem !important; }
  .stButton > button { min-height: 54px; font-size: 1.05rem !important; }
  textarea, input { font-size: 16px !important; }          /* stops iOS zooming into the field */
  h3 { font-size: 1.15rem !important; }
  .chat-bub { font-size: 0.95rem !important; }
}
</style>
""", unsafe_allow_html=True)

# ── Constants ────────────────────────────────────────────────────────────────
MANDATORY_FIELDS = ["incident_type", "incident_location", "date_time", "immediate_actions_taken"]

FIELD_META = {
    "incident_type":               {"label": "Incident Type",              "icon": "🔥", "mandatory": True},
    "severity_level":              {"label": "Severity Level",             "icon": "📊", "mandatory": False},
    "incident_location":           {"label": "Incident Location",          "icon": "📍", "mandatory": True},
    "date_time":                   {"label": "Date & Time",                "icon": "🕐", "mandatory": True},
    "persons_involved":            {"label": "Persons Involved",           "icon": "👥", "mandatory": False},
    "equipment_asset_involved":    {"label": "Equipment / Asset Involved", "icon": "⚙️", "mandatory": False},
    "incident_description":        {"label": "Incident Description",       "icon": "📝", "mandatory": False},
    "immediate_actions_taken":     {"label": "Immediate Actions Taken",    "icon": "🚨", "mandatory": True},
    "witness_information":         {"label": "Witness Information",        "icon": "👁️", "mandatory": False},
    "recommended_follow_up_action":{"label": "Recommended Follow-Up",     "icon": "📋", "mandatory": False},
}

SAMPLE_STATES = {
    "Collecting — Turn 1 (partial)": {
        "session_id": "demo-001", "status": "collecting",
        "missing_mandatory_fields": ["date_time", "immediate_actions_taken"],
        "next_clarification_prompt": "Got that. At what time or date did this occur?",
        "fields": {
            "incident_type": "Pipe Burst / Flooding", "severity_level": "High",
            "incident_location": "Second Floor", "date_time": None,
            "persons_involved": None, "equipment_asset_involved": "Plumbing Pipes",
            "incident_description": "A pipe burst on the second floor causing water discharge.",
            "immediate_actions_taken": None, "witness_information": None,
            "recommended_follow_up_action": None,
        },
    },
    "Complete — All Fields Present": {
        "session_id": "demo-002", "status": "complete",
        "missing_mandatory_fields": [],
        "next_clarification_prompt": None,
        "fields": {
            "incident_type": "Water Leak", "severity_level": "Medium",
            "incident_location": "Conference Room 2", "date_time": "10:00 AM",
            "persons_involved": "Maintenance Team",
            "equipment_asset_involved": "Ceiling Plumbing",
            "incident_description": "Water leak observed near Conference Room 2.",
            "immediate_actions_taken": "Maintenance isolated the area.",
            "witness_information": "Jane Doe (Floor Manager)",
            "recommended_follow_up_action": "Full plumbing inspection and repair.",
        },
    },
    "Submitted — Report Logged": {
        "session_id": "demo-003", "status": "submitted",
        "missing_mandatory_fields": [],
        "next_clarification_prompt": None,
        "fields": {
            "incident_type": "Chemical Spill", "severity_level": "Critical",
            "incident_location": "Lab 4B", "date_time": "2:30 PM, Oct 10",
            "persons_involved": "Dr. Sharma, Lab Tech (×2)",
            "equipment_asset_involved": "Chemical Storage Rack",
            "incident_description": "Acid spill from damaged storage container near ventilation.",
            "immediate_actions_taken": "Area evacuated, hazmat notified, neutralization kit deployed.",
            "witness_information": "Prof. Reddy (Lab Director)",
            "recommended_follow_up_action": "Hazmat decontamination + equipment audit.",
        },
    },
}

# ── Helpers ──────────────────────────────────────────────────────────────────
def load_contract() -> dict:
    try:
        with open(CONTRACT_PATH) as f:
            return json.load(f)
    except Exception:
        return {
            "session_id": str(uuid.uuid4())[:8], "status": "collecting",
            "missing_mandatory_fields": list(MANDATORY_FIELDS),
            "next_clarification_prompt": "Please describe what happened, where, and when.",
            "fields": {k: None for k in FIELD_META},
        }

def save_contract(state: dict):
    """The orchestrator (backend/server.py) owns and persists the session; the UI no longer writes files."""
    return None


# ── Orchestrator API ─────────────────────────────────────────────────────────
API_BASE = os.getenv("INCIDENT_API", "http://127.0.0.1:8000")


def api_call(method: str, path: str, payload=None, timeout: float = 30):
    """Returns (json, None) on success or (None, message). Never falls back to a mock."""
    try:
        r = requests.request(method, API_BASE + path, json=payload, timeout=timeout)
    except requests.RequestException as e:
        return None, (f"Cannot reach the orchestrator at {API_BASE} ({e.__class__.__name__}). "
                      "Start it with scripts/start_demo.bat (or: python -m backend.server).")
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        return None, f"Server said {r.status_code}: {detail}"
    return r.json(), None


def api_upload(path: str, data: bytes, filename: str = "phone.wav", timeout: float = 180):
    """POST a recorded WAV (multipart field 'file'), e.g. from the phone's microphone. Same (json, error) result."""
    try:
        r = requests.post(API_BASE + path, files={"file": (filename, data, "audio/wav")}, timeout=timeout)
    except requests.RequestException as e:
        return None, (f"Cannot reach the orchestrator at {API_BASE} ({e.__class__.__name__}). "
                      "Start it with scripts/start_demo.bat (or: python -m backend.server).")
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        return None, f"Server said {r.status_code}: {detail}"
    return r.json(), None


def audio_quality_warning(info):
    """Plain-language advice when the last microphone recording was too poor for reliable recognition."""
    if not info:
        return None
    if not info.get("speech_detected", True):
        return "No clear speech was heard. Speak louder or closer to the microphone, then try again."
    snr = info.get("snr_db")
    if snr is not None and snr < 12:
        return (f"The recording was noisy or faint (about {snr:.0f} dB signal-to-noise; the on-board speech model "
                "needs about 20 dB). If the text below looks wrong, press Undo last turn, move to 20-30 cm from the "
                "microphone and speak again.")
    return None


def sync_transcript():
    """Rebuild the conversation list from the server (used after Undo)."""
    tr, _ = api_call("GET", "/api/transcript", timeout=5)
    st.session_state.transcript = [
        {"role": "ai" if m["role"] == "assistant" else "user", "text": m["text"], "ts": m["timestamp"][11:19]}
        for m in (tr or [])
    ]


def apply_turn(resp, err):
    """Fold one /api/*/turn response into the UI state."""
    if err:
        st.session_state.last_error = err
        return
    st.session_state.last_error = None
    st.session_state.audio_warning = audio_quality_warning(resp.get("audio"))
    if resp.get("user_transcript"):
        st.session_state.transcript.append({"role": "user", "text": resp["user_transcript"], "ts": ts()})
    st.session_state.contract = resp["state"]
    speech = resp.get("assistant_speech")
    if speech:
        mark = "✅ " if resp["state"].get("status") == "complete" else ""
        st.session_state.transcript.append({"role": "ai", "text": mark + speech, "ts": ts()})

def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")

# ── Session State Init ────────────────────────────────────────────────────────
if "contract"    not in st.session_state: st.session_state.contract    = load_contract()
if "transcript"  not in st.session_state: st.session_state.transcript  = []
if "recording"   not in st.session_state: st.session_state.recording   = False
if "edit_mode"   not in st.session_state: st.session_state.edit_mode   = False
if "last_error"  not in st.session_state: st.session_state.last_error  = None
if "audio_warning" not in st.session_state: st.session_state.audio_warning = None

if "hydrated" not in st.session_state:
    st.session_state.hydrated = True
    _state, _err = api_call("GET", "/api/state", timeout=5)
    if _state:
        st.session_state.contract = _state
        _tr, _ = api_call("GET", "/api/transcript", timeout=5)
        st.session_state.transcript = [
            {"role": "ai" if m["role"] == "assistant" else "user", "text": m["text"], "ts": m["timestamp"][11:19]}
            for m in (_tr or [])
        ]
    else:
        st.session_state.last_error = _err

# Page layout slots, in the order they appear on the page: banner, alerts, controls.
slot_banner = st.container()
slot_alerts = st.container()
slot_controls = st.container()

# ── Controls: voice, type, conversation ──────────────────────────────────────
# Rendered at the top of the main page instead of in the sidebar: on a phone the sidebar opens full screen and
# hides the report, so every control would be one extra tap away. Side by side on a desktop, stacked on a phone.
with slot_controls:
    st.markdown("### 🎙️ Voice Control")

    # Live status of the orchestrator and the board
    _health, _herr = api_call("GET", "/api/health", timeout=4)
    if _herr:
        st.markdown('<div style="background:#7f1d1d;color:#fff;padding:8px 10px;border-radius:8px;font-size:0.8rem;">'
                    '🔴 Orchestrator offline</div>', unsafe_allow_html=True)
    else:
        _eng = _health.get("engine", {})
        _board = _health.get("board") or {}
        _stt, _llm = _eng.get("last_stt_backend"), _eng.get("last_llm_backend")
        _npu_ok = bool(_board.get("stt_on_npu")) and bool(_board.get("llm_on_npu"))
        _bad = _board.get("stt_warning") or _board.get("llm_warning")
        if _bad:
            _chip, _bg = "🔴 NPU problem: " + str(_bad)[:140], "#7f1d1d"
        elif _npu_ok:
            _chip, _bg = "🟢 Whisper + LLM running on the Snapdragon NPU", "#14532d"
        elif _eng.get("mode") == "mock" or "mock" in (_stt, _llm):
            _chip, _bg = "🟠 MOCK engine (not the board)", "#7c4a03"
        else:
            _chip, _bg = "🟠 Board not confirmed on NPU yet", "#7c4a03"
        st.markdown(f'<div style="background:{_bg};color:#fff;padding:8px 10px;border-radius:8px;font-size:0.8rem;">'
                    f'{_chip}<br><span style="opacity:.8">STT: {_stt or "-"} · LLM: {_llm or "-"}</span></div>',
                    unsafe_allow_html=True)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    ctl_left, ctl_right = st.columns([1, 1.15], gap="large")

    with ctl_left:
        # Mic pulsing icon
        rec = st.session_state.recording
        pulse_cls = "mic-pulse mic-pulse-active" if rec else "mic-pulse"
        mic_icon  = "⏹" if rec else "🎙️"
        mic_lbl   = '<span class="mic-label mic-label-active">🔴 Recording — Streaming to Whisper NPU</span>' if rec \
                    else '<span class="mic-label">Idle — press Speak</span>'

        st.markdown(f"""
        <div class="mic-area">
            <div class="{pulse_cls}">{mic_icon}</div>
            {mic_lbl}
        </div>
        """, unsafe_allow_html=True)

        st.caption("Speak uses the laptop's microphone: talk, then pause (it stops by itself after ~2 s of quiet).")
        b_speak, b_undo = st.columns([2, 1])
        with b_speak:
            speak_clicked = st.button("🎙️ Speak", use_container_width=True, key="mic_btn", type="primary")
        with b_undo:
            undo_clicked = st.button("↩ Undo", use_container_width=True, key="undo_btn",
                                     help="Discard the last thing you said (e.g. it was misheard) and say it again.")
        if speak_clicked:
            with st.spinner("🔴 Listening - speak now. After you pause, the board transcribes and extracts the fields..."):
                _resp, _err = api_call("POST", "/api/audio/turn", timeout=180)
            apply_turn(_resp, _err)
            st.rerun()
        if undo_clicked:
            _resp, _err = api_call("POST", "/api/undo", timeout=15)
            if _err:
                st.session_state.last_error = _err
            else:
                st.session_state.last_error = None
                st.session_state.audio_warning = None
                st.session_state.contract = _resp["state"]
                sync_transcript()
            st.rerun()

        # The phone (or any browser device) can be the microphone: close to the mouth it is far cleaner than the
        # laptop mic. Browsers only allow microphone access on HTTPS or on localhost (e.g. over USB, see docs).
        with st.expander("📱 Use this device's microphone (phone)", expanded=False):
            _nonce = st.session_state.get("mic_nonce", 0)
            _clip = st.audio_input("Tap to record, tap again to send", sample_rate=16000, key=f"phone_mic_{_nonce}")
            st.caption("Hold the phone about 20 cm from your mouth. If the browser refuses the microphone "
                       "(a plain http:// address on the network), open the page through the USB link or use Speak / typing.")
            if _clip is not None:
                with st.spinner("Sending to the board..."):
                    _resp, _err = api_upload("/api/audio/turn", _clip.getvalue())
                st.session_state.mic_nonce = _nonce + 1   # a fresh recorder for the next turn
                apply_turn(_resp, _err)
                st.rerun()

        with st.expander("⌨️ Type instead", expanded=False):
            typed = st.text_area("Incident description", height=90,
                                 placeholder='"A pipe burst on the second floor..."',
                                 key="typed_input", label_visibility="collapsed")
            if st.button("▶ Process Input", use_container_width=True, key="process_typed", type="primary"):
                txt = typed.strip()
                if txt:
                    with st.spinner("Processing on the board..."):
                        _resp, _err = api_call("POST", "/api/text/turn", {"text": txt}, timeout=180)
                    apply_turn(_resp, _err)
                    st.rerun()
                else:
                    st.warning("Please type something first.")

    with ctl_right:
        st.markdown("### 💬 Conversation")
        transcript = st.session_state.transcript
        if not transcript:
            st.markdown('<p style="color:#64748b;font-size:0.85rem;font-style:italic;">No conversation yet.</p>', unsafe_allow_html=True)
        else:
            for msg in transcript[-8:]:   # show last 8 messages
                role = msg["role"]
                text = msg["text"]
                t    = msg.get("ts", "")
                if role == "user":
                    st.markdown(f"""
                    <div class="chat-wrap">
                        <div class="chat-av chat-av-u">🧑</div>
                        <div>
                            <div class="chat-bub chat-bub-u">{text}</div>
                            <div class="chat-ts">{t} · You</div>
                        </div>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="chat-wrap">
                        <div class="chat-av chat-av-a">🤖</div>
                        <div>
                            <div class="chat-bub chat-bub-a">{text}</div>
                            <div class="chat-ts">{t} · Assistant</div>
                        </div>
                    </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
#  MAIN CONTENT
# ═══════════════════════════════════════════════════════════════════════
contract = st.session_state.contract
fields   = contract.get("fields", {})
status   = contract.get("status", "collecting")
missing  = set(contract.get("missing_mandatory_fields", []))

if st.session_state.get("last_error"):
    slot_alerts.error(st.session_state.last_error)
if st.session_state.get("audio_warning"):
    slot_alerts.warning(st.session_state.audio_warning)

# ── Top Banner ───────────────────────────────────────────────────────────────
slot_banner.markdown(f"""
<div class="top-banner">
    <div class="banner-left">
        <div class="banner-icon">🛡️</div>
        <div>
            <p class="banner-title">AI Incident Report Assistant</p>
            <p class="banner-sub">Qualcomm Megathon X · IIIT Hyderabad · On-Device Snapdragon AI</p>
        </div>
    </div>
    <div style="display:flex;align-items:center;gap:14px;">
        <span class="npu-chip">⚡ Snapdragon NPU</span>
        <span style="font-size:0.7rem;color:#334155;">Session&nbsp;
            <code style="color:#475569;background:#0a1628;padding:2px 7px;border-radius:5px;">
                {contract.get('session_id','—')}
            </code>
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Status + Metrics Row ──────────────────────────────────────────────────────
populated  = sum(1 for v in fields.values() if v)
total      = len(FIELD_META)
mand_met   = sum(1 for f in MANDATORY_FIELDS if fields.get(f))
pct        = int(populated / total * 100)

pill_cls  = {"collecting":"pill-collecting","complete":"pill-complete","submitted":"pill-submitted"}.get(status,"")
pill_icon = {"collecting":"🟡","complete":"🟢","submitted":"🔵"}.get(status,"⚪")
pill_text = {"collecting":"Collecting","complete":"Complete — Ready for Review","submitted":"Submitted"}.get(status, status)

col_status, col_m1, col_m2, col_m3 = st.columns([2.5, 1, 1, 1])
with col_status:
    st.markdown(f'<div style="padding:6px 0;"><span class="pill {pill_cls}">{pill_icon} {pill_text}</span></div>', unsafe_allow_html=True)
with col_m1:
    st.markdown(f"""<div class="metric-tile">
        <div class="metric-num">{populated}<span style="font-size:1rem;color:#334155;">/{total}</span></div>
        <div class="metric-lbl">Fields Captured</div></div>""", unsafe_allow_html=True)
with col_m2:
    clr = "metric-num-green" if mand_met == 4 else "metric-num"
    st.markdown(f"""<div class="metric-tile">
        <div class="{clr}">{mand_met}<span style="font-size:1rem;color:#334155;">/4</span></div>
        <div class="metric-lbl">Mandatory Met</div></div>""", unsafe_allow_html=True)
with col_m3:
    pct_clr = "#22c55e" if pct==100 else "#3b82f6" if pct>50 else "#f59e0b"
    st.markdown(f"""<div class="metric-tile">
        <div style="font-size:1.75rem;font-weight:800;color:{pct_clr};line-height:1;">{pct}%</div>
        <div class="metric-lbl">Complete</div></div>""", unsafe_allow_html=True)

# Progress bar
st.markdown(f"""
<div class="prog-wrap">
    <div class="prog-fill" style="width:{pct}%;"></div>
</div>""", unsafe_allow_html=True)

# ── AI Clarification Prompt (visible only when collecting) ────────────────────
if status == "collecting":
    clarification = contract.get("next_clarification_prompt")
    if clarification:
        st.markdown(f"""
        <div class="ai-banner">
            <div class="ai-banner-label">🤖 Assistant — Next Question</div>
            <div class="ai-banner-text">{clarification}</div>
        </div>""", unsafe_allow_html=True)

# ── Demo Sample Loader ────────────────────────────────────────────────────────
with st.expander("🧪 Load Demo State (for judges / hardware-free demo)", expanded=False):
    dc1, dc2, dc3 = st.columns(3)
    for col, (label, state) in zip([dc1, dc2, dc3], SAMPLE_STATES.items()):
        with col:
            if st.button(label, use_container_width=True, key=f"demo_{label}"):
                st.session_state.contract = deepcopy(state)
                st.session_state.transcript = []
                q = state.get("next_clarification_prompt")
                if q:
                    st.session_state.transcript.append({"role": "ai", "text": q, "ts": ts()})
                elif state["status"] == "complete":
                    st.session_state.transcript.append({"role": "user", "text": "Water leak near Conference Room 2 around 10 AM — maintenance isolated the area.", "ts": ts()})
                    st.session_state.transcript.append({"role": "ai",  "text": "✅ All mandatory fields captured. Incident report is ready for your review.", "ts": ts()})
                save_contract(st.session_state.contract)
                st.rerun()

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ── The 10 Form Fields ────────────────────────────────────────────────────────
st.markdown('<div class="sec-head">📋 Incident Report Fields</div>', unsafe_allow_html=True)

edit_mode = st.toggle("✏️ Enable manual field editing", value=st.session_state.edit_mode, key="edit_toggle")
if edit_mode != st.session_state.edit_mode:
    st.session_state.edit_mode = edit_mode
    st.rerun()

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

updated_fields = dict(fields)

# Render in 2-column grid
field_keys = list(FIELD_META.keys())
for i in range(0, len(field_keys), 2):
    row_cols = st.columns(2, gap="medium")
    for col, fk in zip(row_cols, field_keys[i:i+2]):
        meta    = FIELD_META[fk]
        val     = fields.get(fk)
        is_mand = meta["mandatory"]
        is_miss = fk in missing
        is_fill = bool(val)

        if is_fill:
            card_cls  = "f-card f-card-filled"
            lbl_cls   = "f-label f-label-filled"
            tag_html  = '<span class="f-tag f-tag-npu">✅ NPU</span>'
        elif is_miss:
            card_cls  = "f-card f-card-required"
            lbl_cls   = "f-label f-label-required"
            tag_html  = '<span class="f-tag f-tag-req">⚠ Required</span>'
        elif is_mand:
            card_cls  = "f-card f-card-required"
            lbl_cls   = "f-label f-label-required"
            tag_html  = '<span class="f-tag f-tag-mand">Mandatory</span>'
        else:
            card_cls  = "f-card f-card-empty"
            lbl_cls   = "f-label f-label-empty"
            tag_html  = ""

        with col:
            if not edit_mode:
                if fk == "severity_level" and val:
                    disp = f'<span class="sev sev-{val}">{val}</span>'
                elif val:
                    disp = f'<span class="f-value">{val}</span>'
                else:
                    disp = '<span class="f-empty">— Awaiting voice input —</span>'

                st.markdown(f"""
                <div class="{card_cls}">
                    <div class="{lbl_cls}">{meta["icon"]} {meta["label"]}{tag_html}</div>
                    {disp}
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="{card_cls}" style="padding-bottom:6px;">
                    <div class="{lbl_cls}">{meta["icon"]} {meta["label"]}{tag_html}</div>
                </div>""", unsafe_allow_html=True)

                if fk == "severity_level":
                    opts     = [None, "Low", "Medium", "High", "Critical"]
                    curr_idx = opts.index(val) if val in opts else 0
                    new_val  = st.selectbox(f"Severity for field", opts, index=curr_idx,
                                            key=f"edit_{fk}",
                                            format_func=lambda x: "— Not set —" if x is None else x,
                                            label_visibility="collapsed")
                else:
                    new_val = st.text_input(f"Value for {meta['label']}", value=val or "",
                                            key=f"edit_{fk}",
                                            placeholder=f"Enter {meta['label'].lower()}...",
                                            label_visibility="collapsed") or None
                if new_val != val:
                    updated_fields[fk] = new_val

# Persist edits
if edit_mode and updated_fields != fields:
    new_c = deepcopy(contract)
    new_c["fields"] = updated_fields
    new_missing = [f for f in MANDATORY_FIELDS if not updated_fields.get(f)]
    new_c["missing_mandatory_fields"] = new_missing
    if not new_missing and new_c["status"] == "collecting":
        new_c["status"] = "complete"
        new_c["next_clarification_prompt"] = None
    st.session_state.contract = new_c
    save_contract(new_c)

st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

# ── Action Row ────────────────────────────────────────────────────────────────
st.markdown('<div class="sec-head">⚡ Actions</div>', unsafe_allow_html=True)

can_submit   = status == "complete"
is_submitted = status == "submitted"

acol1, acol2, acol3 = st.columns([3, 1, 1])

with acol1:
    if is_submitted:
        st.markdown("""
        <div style="background:rgba(59,130,246,0.1);border:1px solid rgba(59,130,246,0.4);
                    border-radius:10px;padding:14px 20px;text-align:center;">
            <span style="font-size:0.95rem;font-weight:700;color:#93c5fd;">
                🔵 &nbsp; Incident Report Successfully Submitted
            </span>
        </div>""", unsafe_allow_html=True)
    else:
        btn_label = "✅ Confirm & Submit Incident Report" if can_submit else "🔒 Submit (Complete all mandatory fields first)"
        if st.button(btn_label, use_container_width=True, disabled=not can_submit,
                     type="primary" if can_submit else "secondary", key="submit_btn"):
            _resp, _err = api_call("POST", "/api/submit",
                                   {"fields": st.session_state.contract.get("fields", {})}, timeout=15)
            if _err:
                st.session_state.last_error = _err
            else:
                st.session_state.last_error = None
                st.session_state.contract = _resp["state"]
                st.session_state.transcript.append({"role": "ai", "text": "🔵 Incident report submitted successfully.", "ts": ts()})
                st.balloons()
            st.rerun()

with acol2:
    if st.button("🔄 Sync File", use_container_width=True, key="sync_btn"):
        _state, _err = api_call("GET", "/api/state", timeout=5)
        if _err:
            st.session_state.last_error = _err
        else:
            st.session_state.last_error = None
            st.session_state.contract = _state
        st.rerun()

with acol3:
    if st.button("↺ Reset All", use_container_width=True, key="reset_btn"):
        _resp, _err = api_call("POST", "/api/reset", timeout=15)
        if _err:
            st.session_state.last_error = _err
        else:
            st.session_state.last_error = None
            st.session_state.contract = _resp["state"]
            st.session_state.transcript = []
            st.session_state.recording = False
            if _resp.get("assistant_speech"):
                st.session_state.transcript.append({"role": "ai", "text": _resp["assistant_speech"], "ts": ts()})
        st.rerun()

# ── Tool Call Preview (collapsible, only when complete/submitted) ─────────────
payload = contract.get("tool_call_payload")
if payload and status in ("complete", "submitted"):
    with st.expander("🔧 Tool Call Payload — populate_incident_form", expanded=False):
        st.code(json.dumps(payload, indent=2), language="json")
        tts = payload.get("summary_for_tts", "")
        if tts:
            st.markdown(f"""
            <div style="background:rgba(34,197,94,0.07);border:1px solid rgba(34,197,94,0.3);
                        border-radius:8px;padding:12px 16px;margin-top:8px;">
                <div style="font-size:0.62rem;font-weight:700;letter-spacing:0.1em;
                            text-transform:uppercase;color:#16a34a;margin-bottom:5px;">
                    🔊 TTS Spoken Confirmation
                </div>
                <div style="font-size:0.85rem;color:#bbf7d0;font-style:italic;">"{tts}"</div>
            </div>""", unsafe_allow_html=True)
