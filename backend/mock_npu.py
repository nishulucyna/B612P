"""
backend/mock_npu.py
Development & live-demo FALLBACK engine implementing the Sector 1 interface:

    run_stt(audio_path: str) -> str
    run_llm(prompt: str) -> str

Fully local and deterministic - no cloud calls. It exists so the whole pipeline can be
exercised (and demoed) when the HDK8650 board / adb bridge is unavailable.

* run_llm: a rule-based extractor that reads the LATEST USER TRANSCRIPT out of the prompt
  built by agent_brain.build_extraction_prompt and returns the same JSON schema a
  Llama-3.2 on Genie would. It is a heuristic stand-in, NOT a language model - good for
  typical incident phrasing, expect misses on unusual wording.
* run_stt: (1) a sidecar transcript `<audio>.txt` next to the audio file (handy for
  pre-recorded demo clips), else (2) offline faster-whisper if the optional package is
  installed AND MOCK_WHISPER_MODEL_DIR points at a LOCAL model directory, else it raises
  STTUnavailable.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

FIELD_KEYS = [
    "incident_type",
    "severity_level",
    "incident_location",
    "date_time",
    "persons_involved",
    "equipment_asset_involved",
    "incident_description",
    "immediate_actions_taken",
    "witness_information",
    "recommended_follow_up_action",
]


class STTUnavailable(RuntimeError):
    """No offline speech-to-text path is available for the mock engine."""


# ---------------------------------------------------------------------------
# STT
# ---------------------------------------------------------------------------

_whisper_model = None


def _transcribe_with_faster_whisper(audio_path: str, model_dir: str) -> str:
    global _whisper_model
    try:
        from faster_whisper import WhisperModel  # optional dependency
    except ImportError as exc:
        raise STTUnavailable("MOCK_WHISPER_MODEL_DIR is set but faster-whisper is not installed.") from exc
    if _whisper_model is None:
        # local_files_only guarantees no model download / network access.
        _whisper_model = WhisperModel(model_dir, device="cpu", compute_type="int8", local_files_only=True)
    segments, _info = _whisper_model.transcribe(audio_path, language="en", beam_size=1)
    return " ".join(seg.text.strip() for seg in segments).strip()


def run_stt(audio_path: str) -> str:
    sidecar = Path(audio_path).with_suffix(".txt")
    if sidecar.is_file():
        return sidecar.read_text(encoding="utf-8").strip()

    model_dir = os.getenv("MOCK_WHISPER_MODEL_DIR", "").strip()
    if model_dir:
        return _transcribe_with_faster_whisper(audio_path, model_dir)

    raise STTUnavailable(
        "Mock STT has no offline engine: put a transcript next to the audio "
        f"('{sidecar.name}'), or install faster-whisper and set MOCK_WHISPER_MODEL_DIR "
        "to a local model folder, or connect the HDK board (NPU_BACKEND=device)."
    )


# ---------------------------------------------------------------------------
# Rule-based extraction ("LLM")
# ---------------------------------------------------------------------------

_WEEKDAYS = "monday|tuesday|wednesday|thursday|friday|saturday|sunday"
_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"

_AMPM_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s?m\b\.?", re.I)
_24H_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_NAMED_TIME_RE = re.compile(r"\b(noon|midnight)\b", re.I)
_REL_RE = re.compile(
    r"\b(?:just now|(?:\d+|an?|a few|two|three|several) (?:minutes?|hours?) ago|earlier today|"
    r"this (?:morning|afternoon|evening)|last night|yesterday(?: (?:morning|afternoon|evening))?|"
    r"today|tonight|(?:last |this )?(?:" + _WEEKDAYS + r")|"
    r"\d{1,2}(?:st|nd|rd|th)? (?:of )?(?:" + _MONTHS + r")(?: \d{4})?|"
    r"(?:" + _MONTHS + r") \d{1,2}(?:st|nd|rd|th)?)\b",
    re.I,
)

# Incident type: first matching rule wins. Callable label => derived from the match.
_INCIDENT_RULES = [
    (re.compile(r"\b(gas|oil|water|coolant|steam|chemical|refrigerant) leak(?:age)?\b", re.I),
     lambda m: f"{m.group(1).title()} Leak"),
    (re.compile(r"\bpipes?\s+(?:has\s+|have\s+|had\s+)?burst\b|\bburst(?:ing)?\s+pipes?\b", re.I), "Pipe Burst"),
    (re.compile(r"\bchemical spill", re.I), "Chemical Spill"),
    (re.compile(r"\bspill(?:ed|s|age)?\b", re.I), "Spill"),
    (re.compile(r"\b(?:power|electricity|electrical)\s+(?:outage|failure|cut)\b|\bblackout\b|"
                r"\bpower (?:went out|is out|went down)\b", re.I), "Power Outage"),
    (re.compile(r"\belectric(?:al)? shock|electrocut", re.I), "Electrical Shock"),
    (re.compile(r"\bexplosion\b|\bexploded\b", re.I), "Explosion"),
    (re.compile(r"\bfire\b(?!\s+extinguisher)|\bsmoke\b", re.I), "Fire"),
    (re.compile(r"\bflood(?:ed|ing)?\b", re.I), "Flooding"),
    (re.compile(r"\bslipped\b|\bslip\b|\btripped\b|\bfell\b|\bfall(?:en)?\b", re.I), "Slip / Fall"),
    (re.compile(r"\binjur(?:y|ed|ies)\b|\bhurt\b|\bbleeding\b|\bfainted\b|\bcollapsed\b", re.I), "Injury"),
    (re.compile(r"\btheft\b|\bstolen\b|\bbreak-?in\b|\bintruder\b|\bunauthori[sz]ed access\b", re.I),
     "Security Breach"),
    (re.compile(r"\b(?:equipment|machine|generator|pump|server|elevator)\s+"
                r"(?:failure|malfunction|breakdown|broke|crashed|stopped working|not working)\b|"
                r"\bbroke down\b|\bmalfunction", re.I), "Equipment Failure"),
]

_SEV_CRITICAL = re.compile(r"\b(?:critical|life[- ]threatening|fatal|fatality|explosion|exploded|"
                           r"unconscious|not breathing)\b", re.I)
_SEV_LOW = re.compile(r"\b(?:minor|small|slight|tiny|drip(?:ping)?|negligible)\b", re.I)
_SEV_HIGH = re.compile(r"\b(?:severe|serious|major|burst|flood(?:ed|ing)?|fire|gas leak|chemical|"
                       r"injur(?:y|ed|ies)|hospital|smoke|electrocut\w*)\b", re.I)

_CLAUSE_SPLIT = re.compile(
    r"(?<=[.!?])\s+|;\s*|,\s*(?:and\s+|but\s+|then\s+|so\s+)?|\s+(?:and|but|then|so)\s+", re.I
)
_LEADING_FILLER = re.compile(r"^(?:and|then|so|but|also|well|ok|okay|um|uh)\b[\s,]*", re.I)

_ACTION_RE = re.compile(
    r"\b(?:turned off|shut (?:off|down)|switched off|cut off|isolat(?:ed|ing)|evacuat(?:ed|ing)|"
    r"called|notified|informed|alerted|dispatched|escalated|contained|cordoned|blocked off|"
    r"cleaned(?: up)?|mopped|cleared|extinguished|put out|stopped|sealed|secured|disconnected|"
    r"unplugged|closed|disabled|ventilated|administered|applied|bandaged|repaired|fixed|"
    r"used|activated|deployed)\b",
    re.I,
)
_NO_ACTION_RE = re.compile(
    r"\bno (?:immediate )?actions?(?: (?:has|have) been| was| were)? taken\b|"
    r"\bnothing (?:has been|have been|was) done\b|\bhaven'?t done anything\b|"
    r"\b(?:no one|nobody) has done anything\b|\bno action yet\b",
    re.I,
)
_FOLLOWUP_RE = re.compile(
    r"\b(?:needs? to|needs|should|must|ought to|recommend(?:ed|s)?|follow[- ]?up|requires?|"
    r"has to|have to|will need)\b",
    re.I,
)

_EQUIPMENT_RE = re.compile(
    r"\b(pipes?|pipeline|valve|pump|generator|forklift|ladder|compressor|boiler|transformer|"
    r"cables?|wiring|server|air conditioner|ac unit|elevator|machine(?:ry)?|conveyor|"
    r"fire extinguisher|circuit breaker|breaker|battery|tank|hose|crane|vehicle|printer|"
    r"projector|router)\b",
    re.I,
)

_PERSON_COUNT_RE = re.compile(
    r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|several|a few|some)\s+"
    r"(?:people|persons|employees|workers|staff|visitors|students|contractors|technicians|"
    r"residents|guests)\b",
    re.I,
)
_PERSON_NAMED_RE = re.compile(
    r"\b(?i:employee|worker|technician|engineer|visitor|guard|manager|supervisor|contractor|"
    r"staff member|student|resident)\s+(?:(?i:named)\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?"
)
_PERSON_TITLE_RE = re.compile(r"\b(?:Mr|Mrs|Ms|Dr)\.?\s+[A-Z][a-z]+")

_WITNESS_BY_RE = re.compile(
    r"\b(?i:witnessed by|seen by)\s+([A-Z][\w'-]*(?:\s+(?:and\s+)?[A-Z][\w'-]*)*)"
)
_WITNESS_LIST_RE = re.compile(r"\b(?i:witnesses?)(?:\s+(?i:was|were|is|are|include[sd]?))?\s+([^.;!?]+)")
_NO_WITNESS_RE = re.compile(r"\bno witnesses?\b", re.I)

_LOC_PREP_RE = re.compile(r"\b(?:in|at|near|on|inside|outside|beside|next to|behind|within)\s+", re.I)
_LOC_DETERMINERS = {"the", "our", "a", "an", "this", "that", "my", "their", "its"}
_LOC_STOP = {
    "around", "at", "about", "since", "when", "and", "but", "while", "because", "which", "that",
    "after", "before", "by", "due", "with", "where", "we", "i", "they", "it", "is", "was", "were",
    "has", "have", "had", "so", "then", "from", "during",
}
_LOC_REJECT_FIRST = set(_WEEKDAYS.split("|")) | set(_MONTHS.split("|")) | {
    "today", "tonight", "yesterday", "morning", "evening", "afternoon", "night", "noon",
    "midnight", "time", "least", "once", "minutes", "hours", "seconds", "fire", "progress",
    "purpose", "risk", "all", "general", "total", "case", "addition", "fact", "short",
}


def _clean_clause(clause: str) -> str:
    clause = clause.strip()
    clause = _LEADING_FILLER.sub("", clause).strip()
    clause = clause.strip(" \t\n.,;:!?")
    return clause[:1].upper() + clause[1:] if clause else ""


def _norm_time(h: str, mm: Optional[str], ap: str) -> str:
    return f"{int(h)}:{mm} {ap.upper()}M" if mm else f"{int(h)} {ap.upper()}M"


def _extract_date_time(text: str) -> Optional[str]:
    time_part = None
    m = _AMPM_RE.search(text)
    if m:
        time_part = _norm_time(m.group(1), m.group(2), m.group(3))
    else:
        m24 = _24H_RE.search(text)
        if m24:
            time_part = f"{int(m24.group(1))}:{m24.group(2)}"
        else:
            mn = _NAMED_TIME_RE.search(text)
            if mn:
                time_part = mn.group(1).capitalize()

    rel = _REL_RE.search(text)
    date_part = rel.group(0).strip() if rel else None
    if date_part:
        date_part = date_part[0].upper() + date_part[1:]

    if date_part and time_part:
        if re.search(r"\bago\b|\bnow\b", date_part, re.I):
            return date_part
        return f"{date_part} at {time_part}"
    return time_part or date_part


def _extract_location(clause: str) -> Optional[str]:
    for m in _LOC_PREP_RE.finditer(clause):
        tokens: List[str] = []
        for raw in clause[m.end():].split():
            tok = raw.strip(",.;:!?\"()")
            if not tok:
                break
            if not tokens and tok.lower() in _LOC_DETERMINERS:
                continue
            if tok.lower() in _LOC_STOP:
                break
            tokens.append(tok)
            if raw[-1] in ",.;:!?" or len(tokens) >= 6:
                break
        if not tokens:
            continue
        phrase = " ".join(tokens)
        first = tokens[0].lower()
        if first in _LOC_REJECT_FIRST or tokens[0][0].isdigit() or _AMPM_RE.search(phrase):
            continue
        return string_capwords(phrase)
    return None


def string_capwords(s: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in s.split())


def _extract_incident_type(text: str) -> Optional[str]:
    for pattern, label in _INCIDENT_RULES:
        m = pattern.search(text)
        if m:
            return label(m) if callable(label) else label
    return None


def _extract_severity(text: str, has_type: bool) -> Optional[str]:
    if _SEV_CRITICAL.search(text):
        return "Critical"
    if _SEV_LOW.search(text):
        return "Low"
    if _SEV_HIGH.search(text):
        return "High"
    return "Medium" if has_type else None


def _extract_persons(text: str) -> Optional[str]:
    found: List[str] = []
    for pattern in (_PERSON_COUNT_RE, _PERSON_NAMED_RE, _PERSON_TITLE_RE):
        for m in pattern.finditer(text):
            val = m.group(0).strip()
            val = val[:1].upper() + val[1:]
            if val not in found:
                found.append(val)
    return ", ".join(found) if found else None


def _extract_witness(text: str) -> Optional[str]:
    if _NO_WITNESS_RE.search(text):
        return "No witnesses"
    m = _WITNESS_BY_RE.search(text)
    if m:
        return m.group(1).strip()
    m = _WITNESS_LIST_RE.search(text)
    if m:
        return _clean_clause(m.group(1)) or None
    return None


def extract_incident_fields(transcript: str) -> Dict[str, Optional[str]]:
    """Extracts the 10 contract fields from one spoken utterance (None when not mentioned)."""
    text = " ".join((transcript or "").split())
    out: Dict[str, Optional[str]] = {k: None for k in FIELD_KEYS}
    if not text:
        return out

    clauses = [c for c in (_clean_clause(c) for c in _CLAUSE_SPLIT.split(text) if c) if c]
    followups = [c for c in clauses if _FOLLOWUP_RE.search(c)]
    actions = [c for c in clauses if c not in followups and _ACTION_RE.search(c)]
    core = [c for c in clauses if c not in followups and c not in actions]
    core_text = ". ".join(core)

    out["incident_type"] = _extract_incident_type(core_text)
    out["severity_level"] = _extract_severity(text, out["incident_type"] is not None)
    out["date_time"] = _extract_date_time(text)
    for clause in core:
        loc = _extract_location(clause)
        if loc:
            out["incident_location"] = loc
            break

    eq = _EQUIPMENT_RE.search(core_text)
    out["equipment_asset_involved"] = eq.group(1).capitalize() if eq else None
    out["persons_involved"] = _extract_persons(text)
    out["witness_information"] = _extract_witness(text)

    if out["incident_type"]:
        out["incident_description"] = text[:300]
    if actions:
        out["immediate_actions_taken"] = "; ".join(actions)
    elif _NO_ACTION_RE.search(text):
        out["immediate_actions_taken"] = "No immediate action taken yet"
    if followups:
        out["recommended_follow_up_action"] = "; ".join(followups)
    return out


def _latest_transcript(prompt: str) -> str:
    """Pulls the user's utterance out of agent_brain.build_extraction_prompt() output."""
    tail = prompt.rsplit("LATEST USER TRANSCRIPT:", 1)[-1]
    tail = tail.rsplit("JSON OUTPUT:", 1)[0].strip()
    if len(tail) >= 2 and tail[0] == '"' and tail[-1] == '"':
        tail = tail[1:-1]
    return tail


def run_llm(prompt: str) -> str:
    return json.dumps(extract_incident_fields(_latest_transcript(prompt)))
