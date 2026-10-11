"""Prototype of the output guard for small models (tested on the laptop side of the harness before anything touches the board).

The language model sometimes (a) writes a placeholder inside a value ("current time", "date not specified") instead of leaving the
field out, which makes the Diamond gate think the field is filled and the report complete, and (b) makes up optional details that the
speaker never said (a "recommended follow-up", a person). Both are caught here, from the model's JSON and the speaker's own words:

  1. placeholder values: any short value that merely says "not specified" / "unknown" / "current time" is removed;
  2. grounding: follow-up advice must share most of its content words with the transcript.

Severity is deliberately NOT touched: the (locked) system prompt tells the model to estimate it when strongly implied, and it is
optional and editable on the review screen.
"""
import json
import re

# Only the follow-up advice is checked against the transcript: it is the field small models invent. Measured on 22 narrations, checking persons,
# equipment and witnesses as well changed nothing, so those stay unchecked (less risk of rejecting a legitimate paraphrase).
GUARDED_FREE_TEXT = ("recommended_follow_up_action",)

_PHRASE = re.compile(
    r"(\bnot\s+(specified|mentioned|provided|stated|available|known|given|reported|applicable)\b|\bunspecified\b|"
    r"\bno\s+(information|details?|data)\b|\bnone\s+(given|mentioned|specified)\b|\bto be determined\b|"
    r"^\s*(the\s+)?(current|present|local)\s+(date|time)\b|^\s*(date|time)\s+(not|unknown)\b)", re.IGNORECASE)
_WHOLE = re.compile(r"^\s*(unknown|n/?a|none|nil|tbd|-+)\W*$", re.IGNORECASE)


def _is_placeholder(value: str) -> bool:
    """Placeholders are short. Long free text such as a description may legitimately say "cause not known"."""
    if _WHOLE.match(value):
        return True
    return len(value.split()) <= 6 and bool(_PHRASE.search(value))


_STOP = set("the a an and or of in on at to for with from by is are was were be been has have had it its this that these those there "
            "then than as into onto over under about after before during while who whom which what when where some any all not no yes "
            "also very more most only just".split())


def transcript_of(prompt: str) -> str:
    m = re.search(r'LATEST USER TRANSCRIPT:\s*"(.*)"\s*JSON OUTPUT', prompt, re.DOTALL)
    return m.group(1) if m else ""


def _words(text: str):
    return [w for w in re.findall(r"[a-z0-9']+", text.lower()) if len(w) >= 4 and w not in _STOP]


def _grounded(value: str, transcript: str, need: float = 0.5) -> bool:
    ws = _words(value)
    if not ws:
        return True
    heard = {w[:5] for w in re.findall(r"[a-z0-9']+", transcript.lower())}      # prefix match absorbs plurals and tenses
    hit = sum(1 for w in ws if w[:5] in heard)
    return hit / len(ws) >= need


def guard(prompt: str, raw: str, grounding: bool = True) -> str:
    """Return the model's JSON with ungrounded or placeholder values removed. Non-JSON input is returned unchanged."""
    try:
        obj = json.loads(raw)
    except Exception:
        return raw
    if not isinstance(obj, dict):
        return raw
    said = transcript_of(prompt)
    out = {}
    for k, v in obj.items():
        if isinstance(v, str):
            if _is_placeholder(v):
                continue
            if grounding and k in GUARDED_FREE_TEXT and said and not _grounded(v, said):
                continue
        out[k] = v
    return json.dumps(out, separators=(",", ":"))
