"""
frontend/app.py
Sector 4: Incident Dashboard & Live UI
Qualcomm Megathon X — On-Device AI Incident Report Assistant
Branch: feat/form-ui

Run with:
    streamlit run frontend/app.py
"""

import json
import time
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime

import streamlit as st

# ---------------------------------------------------------------------------
# PATH SETUP — resolve contract.json from repo root regardless of CWD
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT_DIR / "contract.json"
sys.path.insert(0, str(ROOT_DIR / "backend"))


# ---------------------------------------------------------------------------
# PAGE CONFIG (must be FIRST streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Qualcomm Incident Report Assistant",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------------------------
# CUSTOM CSS — Dark glassmorphism theme with Qualcomm red accent
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* ---- Google Font ---- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

/* ---- Root Variables ---- */
:root {
    --bg-primary:     #0a0c12;
    --bg-card:        rgba(18, 22, 36, 0.85);
    --bg-glass:       rgba(255,255,255,0.04);
    --border-subtle:  rgba(255,255,255,0.08);
    --border-glow:    rgba(99,102,241,0.5);
    --qc-red:         #e20074;
    --qc-red-glow:    rgba(226,0,116,0.35);
    --accent-indigo:  #6366f1;
    --accent-blue:    #38bdf8;
    --green-ok:       #22c55e;
    --green-glow:     rgba(34,197,94,0.3);
    --amber-warn:     #f59e0b;
    --amber-glow:     rgba(245,158,11,0.3);
    --red-err:        #ef4444;
    --text-primary:   #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted:     #475569;
    --font-main:      'Inter', sans-serif;
    --font-mono:      'JetBrains Mono', monospace;
    --radius-card:    16px;
    --radius-sm:      8px;
    --shadow-card:    0 8px 32px rgba(0,0,0,0.4);
}

/* ---- Global Reset ---- */
html, body, [class*="css"] {
    font-family: var(--font-main) !important;
    color: var(--text-primary) !important;
}
.stApp {
    background: var(--bg-primary) !important;
    background-image:
        radial-gradient(ellipse 80% 50% at 50% -20%, rgba(99,102,241,0.12) 0%, transparent 60%),
        radial-gradient(ellipse 60% 40% at 80% 100%, rgba(226,0,116,0.08) 0%, transparent 50%) !important;
}

/* ---- Hide default streamlit chrome ---- */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 1.5rem 2rem 2rem !important; max-width: 1400px !important; }

/* ---- Top Header Banner ---- */
.qc-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 28px;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-card);
    margin-bottom: 1.25rem;
    backdrop-filter: blur(12px);
    box-shadow: var(--shadow-card), 0 0 0 1px rgba(226,0,116,0.1);
}
.qc-header-left { display: flex; align-items: center; gap: 14px; }
.qc-logo-dot {
    width: 42px; height: 42px; border-radius: 10px;
    background: linear-gradient(135deg, var(--qc-red), #ff5c9e);
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; box-shadow: 0 4px 16px var(--qc-red-glow);
}
.qc-title { font-size: 1.15rem; font-weight: 700; color: var(--text-primary); margin: 0; }
.qc-subtitle { font-size: 0.72rem; color: var(--text-secondary); margin: 0; letter-spacing: 0.06em; text-transform: uppercase; }
.qc-badge-npu {
    font-size: 0.68rem; font-weight: 600; letter-spacing: 0.08em;
    padding: 5px 12px; border-radius: 20px;
    background: linear-gradient(135deg, rgba(226,0,116,0.2), rgba(99,102,241,0.2));
    border: 1px solid rgba(226,0,116,0.4);
    color: #ff7fc7; text-transform: uppercase;
}

/* ---- Status Badge ---- */
.status-badge {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 8px 18px; border-radius: 24px;
    font-size: 0.78rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase;
}
.status-collecting {
    background: rgba(245,158,11,0.15); border: 1px solid rgba(245,158,11,0.5); color: #fbbf24;
    animation: pulse-amber 2s infinite;
}
.status-complete {
    background: rgba(34,197,94,0.15); border: 1px solid rgba(34,197,94,0.5); color: #4ade80;
}
.status-submitted {
    background: rgba(99,102,241,0.2); border: 1px solid rgba(99,102,241,0.6); color: #818cf8;
}
@keyframes pulse-amber {
    0%, 100% { box-shadow: 0 0 0 0 rgba(245,158,11,0.4); }
    50%       { box-shadow: 0 0 0 8px rgba(245,158,11,0); }
}

/* ---- Cards ---- */
.card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-card);
    padding: 20px 22px;
    backdrop-filter: blur(10px);
    box-shadow: var(--shadow-card);
    margin-bottom: 1rem;
}
.card-title {
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--text-muted); margin-bottom: 14px;
}

/* ---- Field Cards ---- */
.field-card {
    border-radius: var(--radius-sm);
    padding: 10px 14px;
    margin-bottom: 8px;
    transition: all 0.4s cubic-bezier(0.4,0,0.2,1);
    position: relative;
    overflow: hidden;
}
.field-card::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: var(--radius-sm);
    opacity: 0;
    transition: opacity 0.4s;
}
.field-empty {
    background: rgba(30,35,55,0.6);
    border: 1px dashed rgba(255,255,255,0.1);
}
.field-empty-mandatory {
    background: rgba(245,158,11,0.06);
    border: 1px dashed rgba(245,158,11,0.4);
}
.field-populated {
    background: rgba(34,197,94,0.08);
    border: 1px solid rgba(34,197,94,0.45);
    box-shadow: 0 0 18px var(--green-glow), inset 0 0 12px rgba(34,197,94,0.04);
    animation: glow-in 0.5s ease-out;
}
@keyframes glow-in {
    from { box-shadow: 0 0 0 rgba(34,197,94,0); }
    to   { box-shadow: 0 0 18px var(--green-glow), inset 0 0 12px rgba(34,197,94,0.04); }
}
.field-label {
    font-size: 0.65rem; font-weight: 600; letter-spacing: 0.1em;
    text-transform: uppercase; margin-bottom: 3px;
}
.field-label-empty    { color: var(--text-muted); }
.field-label-mandatory{ color: var(--amber-warn); }
.field-label-filled   { color: var(--green-ok); }
.field-value {
    font-size: 0.85rem; font-weight: 500; color: var(--text-primary);
    font-family: var(--font-main);
}
.field-value-empty { color: var(--text-muted); font-style: italic; font-size: 0.78rem; }
.field-badge-mandatory {
    font-size: 0.58rem; font-weight: 700; letter-spacing: 0.08em;
    padding: 2px 7px; border-radius: 10px; margin-left: 6px;
    background: rgba(245,158,11,0.2); color: var(--amber-warn);
    vertical-align: middle; text-transform: uppercase;
}
.field-badge-npu {
    font-size: 0.58rem; font-weight: 700; letter-spacing: 0.08em;
    padding: 2px 7px; border-radius: 10px; margin-left: 6px;
    background: rgba(34,197,94,0.2); color: var(--green-ok);
    vertical-align: middle; text-transform: uppercase;
}

/* ---- Waveform animation ---- */
.waveform-container {
    display: flex; align-items: center; justify-content: center;
    gap: 4px; height: 48px; padding: 8px 0;
}
.waveform-bar {
    width: 4px; border-radius: 2px;
    background: linear-gradient(to top, var(--qc-red), var(--accent-indigo));
    animation: wave 1.2s ease-in-out infinite;
}
.waveform-bar:nth-child(1)  { animation-delay: 0.0s; }
.waveform-bar:nth-child(2)  { animation-delay: 0.1s; }
.waveform-bar:nth-child(3)  { animation-delay: 0.2s; }
.waveform-bar:nth-child(4)  { animation-delay: 0.3s; }
.waveform-bar:nth-child(5)  { animation-delay: 0.4s; }
.waveform-bar:nth-child(6)  { animation-delay: 0.3s; }
.waveform-bar:nth-child(7)  { animation-delay: 0.2s; }
.waveform-bar:nth-child(8)  { animation-delay: 0.1s; }
.waveform-bar:nth-child(9)  { animation-delay: 0.0s; }
.waveform-bar:nth-child(10) { animation-delay: 0.15s; }
.waveform-bar:nth-child(11) { animation-delay: 0.25s; }
.waveform-bar:nth-child(12) { animation-delay: 0.35s; }
@keyframes wave {
    0%, 100% { height: 8px;  opacity: 0.4; }
    50%       { height: 40px; opacity: 1.0; }
}
.waveform-idle .waveform-bar {
    animation: none; height: 8px; opacity: 0.25;
}

/* ---- Chat Transcript ---- */
.chat-msg {
    display: flex; gap: 10px; margin-bottom: 12px; align-items: flex-start;
}
.chat-avatar {
    width: 30px; height: 30px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; flex-shrink: 0; margin-top: 2px;
}
.chat-avatar-user { background: rgba(99,102,241,0.25); border: 1px solid rgba(99,102,241,0.4); }
.chat-avatar-ai   { background: rgba(226,0,116,0.2);   border: 1px solid rgba(226,0,116,0.4); }
.chat-bubble {
    padding: 10px 14px; border-radius: 14px;
    font-size: 0.84rem; line-height: 1.5; max-width: 88%;
}
.chat-bubble-user {
    background: rgba(99,102,241,0.12); border: 1px solid rgba(99,102,241,0.25); color: #c7d2fe;
}
.chat-bubble-ai {
    background: rgba(226,0,116,0.1); border: 1px solid rgba(226,0,116,0.25); color: #fca5a5;
}
.chat-ts { font-size: 0.62rem; color: var(--text-muted); margin-top: 3px; }

/* ---- Buttons ---- */
.stButton > button {
    border-radius: 10px !important; font-weight: 600 !important;
    font-family: var(--font-main) !important; letter-spacing: 0.03em !important;
    transition: all 0.2s ease !important;
}

/* ---- Streamlit input overrides ---- */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: rgba(20,25,45,0.8) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
    font-family: var(--font-main) !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--accent-indigo) !important;
    box-shadow: 0 0 0 2px rgba(99,102,241,0.25) !important;
}
.stSelectbox > div > div {
    background: rgba(20,25,45,0.8) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
}
label { color: var(--text-secondary) !important; font-size: 0.8rem !important; font-weight: 500 !important; }

/* ---- Severity Pill ---- */
.sev-low      { color: #4ade80; background: rgba(34,197,94,0.15);   border: 1px solid rgba(34,197,94,0.4);   }
.sev-medium   { color: #fbbf24; background: rgba(245,158,11,0.15);  border: 1px solid rgba(245,158,11,0.4);  }
.sev-high     { color: #fb923c; background: rgba(249,115,22,0.15);  border: 1px solid rgba(249,115,22,0.4);  }
.sev-critical { color: #f87171; background: rgba(239,68,68,0.15);   border: 1px solid rgba(239,68,68,0.45);  }
.sev-pill {
    display: inline-block; padding: 3px 12px; border-radius: 14px;
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
}

/* ---- Divider ---- */
hr { border-color: rgba(255,255,255,0.07) !important; margin: 1rem 0 !important; }

/* ---- Sidebar cleanup ---- */
[data-testid="stSidebar"] { display: none; }

/* ---- Scrollbar ---- */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 4px; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# HELPERS: Load & Save contract.json
# ---------------------------------------------------------------------------

MANDATORY_FIELDS = ["incident_type", "incident_location", "date_time", "immediate_actions_taken"]

ALL_FIELD_META = {
    "incident_type":              {"label": "Incident Type",               "mandatory": True,  "icon": "🔥"},
    "severity_level":             {"label": "Severity Level",              "mandatory": False, "icon": "📊"},
    "incident_location":          {"label": "Incident Location",           "mandatory": True,  "icon": "📍"},
    "date_time":                  {"label": "Date & Time",                 "mandatory": True,  "icon": "🕐"},
    "persons_involved":           {"label": "Persons Involved",            "mandatory": False, "icon": "👥"},
    "equipment_asset_involved":   {"label": "Equipment / Asset Involved",  "mandatory": False, "icon": "⚙️"},
    "incident_description":       {"label": "Incident Description",        "mandatory": False, "icon": "📝"},
    "immediate_actions_taken":    {"label": "Immediate Actions Taken",     "mandatory": True,  "icon": "🚨"},
    "witness_information":        {"label": "Witness Information",         "mandatory": False, "icon": "👁️"},
    "recommended_follow_up_action":{"label": "Recommended Follow-Up",     "mandatory": False, "icon": "📋"},
}

SEVERITY_CLASSES = {
    "Low": "sev-low", "Medium": "sev-medium",
    "High": "sev-high", "Critical": "sev-critical"
}

SAMPLE_STATES = {
    "🟡 Collecting (Turn 1 — Partial)": {
        "session_id": "demo-001",
        "status": "collecting",
        "missing_mandatory_fields": ["date_time", "immediate_actions_taken"],
        "next_clarification_prompt": "Got that. At what time or date did this occur?",
        "fields": {
            "incident_type": "Pipe Burst / Flooding",
            "severity_level": "High",
            "incident_location": "Second Floor",
            "date_time": None,
            "persons_involved": None,
            "equipment_asset_involved": "Plumbing Pipes",
            "incident_description": "A pipe burst on the second floor causing water discharge.",
            "immediate_actions_taken": None,
            "witness_information": None,
            "recommended_follow_up_action": None,
        },
    },
    "🟢 Complete (All Fields Present)": {
        "session_id": "demo-002",
        "status": "complete",
        "missing_mandatory_fields": [],
        "next_clarification_prompt": None,
        "fields": {
            "incident_type": "Water Leak",
            "severity_level": "Medium",
            "incident_location": "Conference Room 2",
            "date_time": "10:00 AM",
            "persons_involved": "Maintenance team",
            "equipment_asset_involved": "Ceiling plumbing",
            "incident_description": "Water leak observed near Conference Room 2.",
            "immediate_actions_taken": "Maintenance has already isolated the area.",
            "witness_information": "Jane Doe (Floor Manager)",
            "recommended_follow_up_action": "Full plumbing inspection and repair.",
        },
    },
    "🔵 Submitted": {
        "session_id": "demo-003",
        "status": "submitted",
        "missing_mandatory_fields": [],
        "next_clarification_prompt": None,
        "fields": {
            "incident_type": "Chemical Spill",
            "severity_level": "Critical",
            "incident_location": "Lab 4B",
            "date_time": "2:30 PM, Oct 10",
            "persons_involved": "Dr. Sharma, Lab Technician (2)",
            "equipment_asset_involved": "Chemical storage rack, spillage containment kit",
            "incident_description": "Acid spill from damaged storage container near ventilation unit.",
            "immediate_actions_taken": "Area evacuated, hazmat notified, neutralization kit deployed.",
            "witness_information": "Prof. Reddy (Lab Director)",
            "recommended_follow_up_action": "Full hazmat decontamination, equipment audit.",
        },
    },
}


def load_contract() -> dict:
    """Load contract.json from repo root, return default blank state if missing."""
    try:
        with open(CONTRACT_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {
            "session_id": str(uuid.uuid4())[:8],
            "status": "collecting",
            "missing_mandatory_fields": list(MANDATORY_FIELDS),
            "next_clarification_prompt": "Please describe what happened, where, and when.",
            "fields": {k: None for k in ALL_FIELD_META},
        }


def save_contract(state: dict):
    """Persist state to contract.json."""
    try:
        with open(CONTRACT_PATH, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        st.error(f"Failed to save contract.json: {e}")


def get_status_badge_html(status: str) -> str:
    icons = {"collecting": "🟡", "complete": "🟢", "submitted": "🔵"}
    labels = {"collecting": "Collecting", "complete": "Complete — Ready for Review", "submitted": "Submitted"}
    css = {"collecting": "status-collecting", "complete": "status-complete", "submitted": "status-submitted"}
    icon  = icons.get(status, "⚪")
    label = labels.get(status, status.upper())
    cls   = css.get(status, "")
    return f'<span class="status-badge {cls}">{icon} {label}</span>'


def render_waveform(active: bool) -> str:
    container_cls = "waveform-container" if active else "waveform-container waveform-idle"
    bars = "".join(f'<div class="waveform-bar" style="height:{8 if not active else 20}px"></div>' for _ in range(12))
    return f'<div class="{container_cls}">{bars}</div>'


def severity_pill(level: str) -> str:
    cls = SEVERITY_CLASSES.get(level, "")
    return f'<span class="sev-pill {cls}">{level}</span>'


# ---------------------------------------------------------------------------
# SESSION STATE INIT
# ---------------------------------------------------------------------------
if "contract" not in st.session_state:
    st.session_state.contract = load_contract()
if "transcript" not in st.session_state:
    st.session_state.transcript = []
if "recording" not in st.session_state:
    st.session_state.recording = False
if "mock_input" not in st.session_state:
    st.session_state.mock_input = ""
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False


# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------
st.markdown("""
<div class="qc-header">
  <div class="qc-header-left">
    <div class="qc-logo-dot">🛡️</div>
    <div>
      <p class="qc-title">Qualcomm Incident Report Assistant</p>
      <p class="qc-subtitle">Snapdragon On-Device AI · Megathon X · IIIT Hyderabad</p>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:12px;">
    <span class="qc-badge-npu">⚡ NPU Accelerated</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# SHORTCUT: Load Sample State
# ---------------------------------------------------------------------------
with st.container():
    col_demo_label, col_demo_sel, col_demo_btn, col_reset_btn = st.columns([1.8, 2.5, 1, 1])
    with col_demo_label:
        st.markdown("<p style='color:#64748b;font-size:0.78rem;font-weight:600;margin-top:10px;'>🧪 DEMO CONTROLS</p>", unsafe_allow_html=True)
    with col_demo_sel:
        sample_choice = st.selectbox("", list(SAMPLE_STATES.keys()), label_visibility="collapsed")
    with col_demo_btn:
        if st.button("▶ Load Sample", use_container_width=True):
            st.session_state.contract = SAMPLE_STATES[sample_choice].copy()
            st.session_state.transcript = []
            if st.session_state.contract["status"] == "collecting":
                q = st.session_state.contract.get("next_clarification_prompt")
                if q:
                    st.session_state.transcript.append({"role": "ai", "text": q, "ts": datetime.now().strftime("%H:%M:%S")})
            elif st.session_state.contract["status"] == "complete":
                st.session_state.transcript.append({
                    "role": "user", "ts": datetime.now().strftime("%H:%M:%S"),
                    "text": "There was a water leak near Conference Room 2 around 10 AM. Maintenance has already isolated the area."
                })
                st.session_state.transcript.append({
                    "role": "ai", "ts": datetime.now().strftime("%H:%M:%S"),
                    "text": "✅ All mandatory fields captured. Incident report is ready for your review and submission."
                })
            save_contract(st.session_state.contract)
            st.rerun()
    with col_reset_btn:
        if st.button("↺ Reset", use_container_width=True):
            st.session_state.contract = {
                "session_id": str(uuid.uuid4())[:8],
                "status": "collecting",
                "missing_mandatory_fields": list(MANDATORY_FIELDS),
                "next_clarification_prompt": "Please describe what happened, where, and when.",
                "fields": {k: None for k in ALL_FIELD_META},
            }
            st.session_state.transcript = []
            st.session_state.recording = False
            save_contract(st.session_state.contract)
            st.rerun()


st.markdown("<hr>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# MAIN LAYOUT: Left column | Right column
# ---------------------------------------------------------------------------
col_left, col_right = st.columns([1, 1.35], gap="large")


# ═══════════════════════════════════════════════════════
# LEFT PANEL: Status + Mic + Transcript + Manual Input
# ═══════════════════════════════════════════════════════
with col_left:

    # --- Status Card ---
    contract = st.session_state.contract
    status   = contract.get("status", "collecting")

    st.markdown(f"""
    <div class="card">
        <div class="card-title">System Status</div>
        {get_status_badge_html(status)}
        <div style="margin-top:10px;font-size:0.78rem;color:#64748b;">
            Session <span style="font-family:var(--font-mono);color:#94a3b8;">{contract.get('session_id','—')}</span>
            &nbsp;·&nbsp; {datetime.now().strftime("%d %b %Y, %H:%M")}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- Clarification Prompt Banner (only when collecting) ---
    if status == "collecting":
        clarification = contract.get("next_clarification_prompt")
        missing = contract.get("missing_mandatory_fields", [])
        if clarification:
            st.markdown(f"""
            <div style="background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.4);
                        border-radius:10px;padding:12px 16px;margin-bottom:1rem;">
                <div style="font-size:0.65rem;font-weight:700;letter-spacing:0.1em;
                            color:#f59e0b;text-transform:uppercase;margin-bottom:6px;">
                    🤖 Assistant Question
                </div>
                <div style="font-size:0.9rem;color:#fde68a;line-height:1.5;">{clarification}</div>
                <div style="margin-top:8px;font-size:0.68rem;color:#92400e;">
                    Missing mandatory: {', '.join(f'<code style="background:rgba(245,158,11,0.15);padding:1px 5px;border-radius:4px;color:#fbbf24;">{f}</code>' for f in missing)}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # --- Mic / Waveform Card ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🎙️ Audio Input & Voice Capture</div>', unsafe_allow_html=True)

    is_recording = st.session_state.recording
    st.markdown(render_waveform(is_recording), unsafe_allow_html=True)

    btn_label = "⏹ Stop Recording" if is_recording else "🎙️ Record Incident Voice Note"
    btn_style = "background:rgba(239,68,68,0.2);" if is_recording else ""
    if st.button(btn_label, use_container_width=True, key="mic_btn"):
        st.session_state.recording = not st.session_state.recording
        if st.session_state.recording:
            st.toast("🎙️ Recording started — speak your incident report", icon="🎤")
        else:
            st.toast("⏹ Recording stopped", icon="✅")
        st.rerun()

    if is_recording:
        st.markdown("""
        <div style="text-align:center;font-size:0.72rem;color:#f87171;margin-top:6px;animation:pulse-amber 1.5s infinite;">
            🔴 LIVE — Streaming to Whisper (NPU/DSP)
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align:center;font-size:0.72rem;color:#475569;margin-top:6px;">
            Idle — Press to start voice capture
        </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # --- Mock Text Input (for demo / no hardware) ---
    with st.expander("⌨️  Type Incident Report (Hardware-free Demo)", expanded=False):
        st.markdown('<p style="font-size:0.73rem;color:#64748b;margin-bottom:6px;">Simulate speech input without microphone hardware</p>', unsafe_allow_html=True)
        mock_text = st.text_area(
            "Your incident description:",
            value=st.session_state.mock_input,
            height=80,
            placeholder='e.g. "There was a water leak near Conference Room 2 around 10 AM..."',
            key="mock_text_area",
            label_visibility="collapsed"
        )
        if st.button("📨 Process as Voice Input", use_container_width=True, key="process_mock"):
            if mock_text.strip():
                # Add to transcript
                st.session_state.transcript.append({
                    "role": "user",
                    "text": mock_text.strip(),
                    "ts": datetime.now().strftime("%H:%M:%S")
                })
                st.session_state.mock_input = ""

                # Try to call agent brain
                try:
                    from agent_brain import process_user_turn, mock_qualcomm_llm_engine
                    result = process_user_turn(
                        mock_text.strip(),
                        st.session_state.contract,
                        mock_qualcomm_llm_engine
                    )
                    st.session_state.contract = result
                    if result["status"] == "collecting" and result.get("next_clarification_prompt"):
                        st.session_state.transcript.append({
                            "role": "ai",
                            "text": result["next_clarification_prompt"],
                            "ts": datetime.now().strftime("%H:%M:%S")
                        })
                    elif result["status"] == "complete":
                        payload = result.get("tool_call_payload") or {}
                        tts_msg = payload.get("summary_for_tts", "✅ All mandatory fields captured. Ready for submission.")
                        st.session_state.transcript.append({
                            "role": "ai",
                            "text": f"✅ {tts_msg}",
                            "ts": datetime.now().strftime("%H:%M:%S")
                        })
                    save_contract(st.session_state.contract)
                    st.rerun()
                except ImportError:
                    # agent_brain not importable yet — just show transcript echo
                    st.session_state.transcript.append({
                        "role": "ai",
                        "text": "⚠️ Agent Brain not connected. Transcript logged. (Connect backend/agent_brain.py for live extraction)",
                        "ts": datetime.now().strftime("%H:%M:%S")
                    })
                    save_contract(st.session_state.contract)
                    st.rerun()
            else:
                st.warning("Please type something first.")

    # --- Conversational Transcript ---
    st.markdown('<div class="card" style="margin-top:1rem;">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">💬 Conversation Transcript</div>', unsafe_allow_html=True)

    transcript = st.session_state.transcript
    if not transcript:
        st.markdown('<p style="color:#475569;font-size:0.82rem;font-style:italic;text-align:center;padding:16px 0;">No conversation yet. Start speaking or type an incident report above.</p>', unsafe_allow_html=True)
    else:
        for msg in transcript:
            role  = msg["role"]
            text  = msg["text"]
            ts    = msg.get("ts", "")
            if role == "user":
                st.markdown(f"""
                <div class="chat-msg">
                    <div class="chat-avatar chat-avatar-user">🧑</div>
                    <div>
                        <div class="chat-bubble chat-bubble-user">{text}</div>
                        <div class="chat-ts">{ts} · You</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="chat-msg">
                    <div class="chat-avatar chat-avatar-ai">🤖</div>
                    <div>
                        <div class="chat-bubble chat-bubble-ai">{text}</div>
                        <div class="chat-ts">{ts} · Incident AI</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════
# RIGHT PANEL: 10 Form Fields + Action Controls
# ═══════════════════════════════════════════════════════
with col_right:

    contract = st.session_state.contract
    fields   = contract.get("fields", {})
    missing  = set(contract.get("missing_mandatory_fields", []))
    status   = contract.get("status", "collecting")

    # --- Stats Bar ---
    total_fields     = len(ALL_FIELD_META)
    populated_count  = sum(1 for v in fields.values() if v)
    mandatory_filled = sum(1 for f in MANDATORY_FIELDS if fields.get(f))

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div style="background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.3);
                    border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:1.6rem;font-weight:800;color:#818cf8;">{populated_count}/{total_fields}</div>
            <div style="font-size:0.65rem;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;">Fields Captured</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.3);
                    border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:1.6rem;font-weight:800;color:#4ade80;">{mandatory_filled}/4</div>
            <div style="font-size:0.65rem;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;">Mandatory Met</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        pct = int((populated_count / total_fields) * 100)
        clr = "#4ade80" if pct == 100 else "#fbbf24" if pct > 40 else "#f87171"
        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
                    border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:1.6rem;font-weight:800;color:{clr};">{pct}%</div>
            <div style="font-size:0.65rem;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;">Completeness</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # --- Toggle Edit Mode ---
    col_edit_toggle, col_spacer = st.columns([1, 2])
    with col_edit_toggle:
        edit_toggle = st.toggle("✏️ Enable Field Editing", value=st.session_state.edit_mode, key="edit_toggle")
        if edit_toggle != st.session_state.edit_mode:
            st.session_state.edit_mode = edit_toggle
            st.rerun()

    st.markdown('<div class="card" style="margin-top:8px;">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📋 Incident Report Fields (10/10)</div>', unsafe_allow_html=True)

    # Render each field
    updated_fields = dict(fields)
    edit_mode = st.session_state.edit_mode

    for field_key, meta in ALL_FIELD_META.items():
        value     = fields.get(field_key)
        is_mand   = meta["mandatory"]
        is_miss   = field_key in missing
        is_filled = bool(value)
        icon      = meta["icon"]
        label     = meta["label"]

        if is_filled:
            card_cls   = "field-card field-populated"
            label_cls  = "field-label field-label-filled"
            badge_html = f'<span class="field-badge-npu">✅ NPU</span>'
        elif is_miss:
            card_cls   = "field-card field-empty-mandatory"
            label_cls  = "field-label field-label-mandatory"
            badge_html = f'<span class="field-badge-mandatory">⚠️ Required</span>'
        elif is_mand:
            card_cls   = "field-card field-empty-mandatory"
            label_cls  = "field-label field-label-mandatory"
            badge_html = f'<span class="field-badge-mandatory">Required</span>'
        else:
            card_cls   = "field-card field-empty"
            label_cls  = "field-label field-label-empty"
            badge_html = ""

        if not edit_mode:
            # Read-only display
            if field_key == "severity_level" and value:
                display_val = severity_pill(value)
            elif value:
                display_val = f'<span class="field-value">{value}</span>'
            else:
                display_val = f'<span class="field-value-empty">— Not yet captured —</span>'

            st.markdown(f"""
            <div class="{card_cls}">
                <div class="{label_cls}">{icon} {label}{badge_html}</div>
                {display_val}
            </div>
            """, unsafe_allow_html=True)
        else:
            # Edit mode
            with st.container():
                st.markdown(f"""
                <div class="{card_cls}" style="padding-bottom:4px;">
                    <div class="{label_cls}">{icon} {label}{badge_html}</div>
                </div>
                """, unsafe_allow_html=True)

                if field_key == "severity_level":
                    opts = [None, "Low", "Medium", "High", "Critical"]
                    idx  = opts.index(value) if value in opts else 0
                    new_val = st.selectbox(
                        f"", opts,
                        index=idx,
                        key=f"edit_{field_key}",
                        format_func=lambda x: "— Not set —" if x is None else x,
                        label_visibility="collapsed"
                    )
                else:
                    new_val = st.text_input(
                        f"",
                        value=value or "",
                        key=f"edit_{field_key}",
                        placeholder=f"Enter {label.lower()}...",
                        label_visibility="collapsed"
                    )
                    if new_val == "":
                        new_val = None

                if new_val != value:
                    updated_fields[field_key] = new_val

    st.markdown('</div>', unsafe_allow_html=True)

    # Save edits if in edit mode
    if edit_mode and updated_fields != fields:
        from copy import deepcopy
        new_contract = deepcopy(contract)
        new_contract["fields"] = updated_fields
        # Recompute missing mandatory
        new_missing = [f for f in MANDATORY_FIELDS if not updated_fields.get(f)]
        new_contract["missing_mandatory_fields"] = new_missing
        if not new_missing and new_contract["status"] == "collecting":
            new_contract["status"] = "complete"
            new_contract["next_clarification_prompt"] = None
        st.session_state.contract = new_contract
        save_contract(new_contract)

    # --- Action Buttons ---
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    can_submit   = (status == "complete")
    is_submitted = (status == "submitted")

    col_sub, col_reload = st.columns([2, 1])
    with col_sub:
        if is_submitted:
            st.markdown("""
            <div style="background:rgba(99,102,241,0.15);border:1px solid rgba(99,102,241,0.5);
                        border-radius:10px;padding:14px;text-align:center;">
                <span style="font-size:1rem;font-weight:700;color:#818cf8;">🔵 Incident Successfully Submitted</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            submit_btn = st.button(
                "✅ Confirm & Submit Incident" if can_submit else "🔒 Submit (Awaiting Mandatory Fields)",
                use_container_width=True,
                disabled=not can_submit,
                key="submit_btn",
                type="primary" if can_submit else "secondary",
            )
            if submit_btn and can_submit:
                from copy import deepcopy
                final = deepcopy(st.session_state.contract)
                final["status"] = "submitted"
                st.session_state.contract = final
                save_contract(final)
                st.session_state.transcript.append({
                    "role": "ai",
                    "text": "🔵 Incident report submitted successfully. Thank you.",
                    "ts": datetime.now().strftime("%H:%M:%S")
                })
                st.balloons()
                st.rerun()

    with col_reload:
        if st.button("🔄 Sync File", use_container_width=True, key="sync_btn"):
            st.session_state.contract = load_contract()
            st.rerun()

    # --- Tool Call Payload Preview (when complete) ---
    payload = contract.get("tool_call_payload")
    if payload and status in ("complete", "submitted"):
        with st.expander("🔧 Tool Call Payload: `populate_incident_form`", expanded=False):
            st.markdown(f"""
            <div style="background:rgba(10,12,20,0.8);border:1px solid rgba(99,102,241,0.3);
                        border-radius:10px;padding:14px;font-family:var(--font-mono);
                        font-size:0.75rem;color:#c7d2fe;overflow-x:auto;">
                <pre style="margin:0;">{json.dumps(payload, indent=2)}</pre>
            </div>
            """, unsafe_allow_html=True)

        tts_summary = payload.get("summary_for_tts", "")
        if tts_summary:
            st.markdown(f"""
            <div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.3);
                        border-radius:10px;padding:12px 16px;margin-top:8px;">
                <div style="font-size:0.65rem;font-weight:700;letter-spacing:0.1em;
                            color:#22c55e;text-transform:uppercase;margin-bottom:5px;">
                    🔊 TTS Spoken Confirmation
                </div>
                <div style="font-size:0.85rem;color:#bbf7d0;font-style:italic;">"{tts_summary}"</div>
            </div>
            """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# FOOTER
# ---------------------------------------------------------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("""
<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;">
    <span style="font-size:0.68rem;color:#334155;">
        Sector 4 — Incident Dashboard &nbsp;·&nbsp; Branch: <code style="color:#64748b;">feat/form-ui</code>
        &nbsp;·&nbsp; Qualcomm Megathon X · IIIT Hyderabad
    </span>
    <span style="font-size:0.68rem;color:#334155;">
        Data Contract: <code style="color:#64748b;">contract.json</code> &nbsp;·&nbsp; All AI runs on-device via Snapdragon NPU/DSP
    </span>
</div>
""", unsafe_allow_html=True)
