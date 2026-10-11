"""End-to-end evaluation on the board: natural narrations -> (speech recognition) -> LLM extraction -> field mapping.

Needs the board bridge (adb forward tcp:8080 tcp:8080). Uses backend/agent_brain.py unchanged with the board's LLM, so it
measures exactly what the app does (the Kotlin brain is verified byte-for-byte against it).
  python scripts/e2e_eval.py [text|speech|noisy|dialog ...]      default: all
A field counts as right when its value contains one of the listed keywords (case-insensitive); fields listed in `empty`
must stay empty (the narration did not state them), which catches invented values and wrong-field mapping."""
import json, os, re, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend import agent_brain, npu_runtime
import stt_snr_eval as S   # synth / load16k / to_wav / wer / stt helpers

CASES = [
    dict(text="So uh, this morning around nine there was a chemical spill in lab six. Two of our technicians, Priya and Arun, got some on their gloves. We evacuated the room and called the safety officer.",
         want=dict(incident_type=["spill", "chemical"], incident_location=["lab six", "lab 6"], date_time=["morning", "9", "nine"],
                   immediate_actions_taken=["evacuat"], persons_involved=["priya", "arun"])),
    dict(text="Hey, I need to report that a forklift hit a rack in warehouse two yesterday afternoon. Nobody got hurt but the rack collapsed. We cordoned off the area.",
         want=dict(incident_type=["forklift", "collision", "rack", "collapse"], incident_location=["warehouse two", "warehouse 2"], date_time=["yesterday"],
                   immediate_actions_taken=["cordon"], equipment_asset_involved=["forklift", "rack"])),
    dict(text="The fire alarm went off in building four at about two thirty this afternoon. It was a false alarm caused by a faulty smoke detector and we reset the panel.",
         want=dict(incident_type=["alarm", "false"], incident_location=["building four", "building 4"],
                   date_time=["2:30", "2.30", "two thirty", "14:30", "afternoon"],
                   immediate_actions_taken=["reset"], equipment_asset_involved=["smoke", "detector", "panel"])),
    dict(text="Ravi slipped on a wet floor near the cafeteria last Friday around noon. He hurt his ankle and it looks serious. We gave first aid and took him to the clinic. Meera saw it happen.",
         want=dict(incident_type=["slip", "fall"], incident_location=["cafeteria"], date_time=["friday", "noon"],
                   immediate_actions_taken=["first aid", "clinic"], persons_involved=["ravi"], witness_information=["meera"],
                   severity_level=["high", "medium", "critical"])),
    dict(text="Um, so basically the server room air conditioning failed last night at about eleven and the temperature kept rising. We shut down the non critical servers.",
         want=dict(incident_type=["air", "condition", "cooling", "ac ", "failure", "temperature"], incident_location=["server room"],
                   date_time=["night", "11", "eleven"], immediate_actions_taken=["shut"],
                   equipment_asset_involved=["air", "condition", "server", "ac"])),
    dict(text="There was an electrical short circuit in the panel on the second floor of the factory at around six in the evening. The electrician cut the power and we put out the sparks with an extinguisher.",
         want=dict(incident_type=["short", "electrical", "spark"], incident_location=["second floor", "factory"], date_time=["6", "six", "evening"],
                   immediate_actions_taken=["cut", "power", "extinguish"])),
    dict(text="Okay so the weather was terrible today, anyway, a ladder fell in the stockroom at lunchtime and hit Sam on the shoulder. We gave him ice and he went home.",
         want=dict(incident_type=["ladder", "fall", "hit", "injur"], incident_location=["stockroom"], date_time=["lunch"],
                   immediate_actions_taken=["ice", "first aid", "gave"], persons_involved=["sam"], equipment_asset_involved=["ladder"])),
    dict(text="Critical incident. A boiler exploded in plant three at five in the morning. Two workers were hospitalised. We shut the plant and called emergency services.",
         want=dict(severity_level=["critical"], incident_type=["boiler", "explo"], incident_location=["plant three", "plant 3"],
                   date_time=["5", "five"], immediate_actions_taken=["shut", "emergency"])),
    dict(text="The leak was in the east wing, no wait, the west wing, at four PM today. We closed the main valve.",
         want=dict(incident_location=["west"], date_time=["4", "four"], immediate_actions_taken=["valve"], incident_type=["leak"])),
    dict(text="There was a strong gas smell in the basement.",
         want=dict(incident_type=["gas"], incident_location=["basement"]), expect_status="collecting",
         empty=["date_time", "immediate_actions_taken", "severity_level", "persons_involved", "witness_information"]),
]


def run_llm(p):
    return npu_runtime.run_llm(p)


def norm(s):
    ones = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()
    t = re.sub(r"\b(\d{1,2}):(\d\d)\b", r"\1 \2", s.lower())
    t = re.sub(r"(\d+)\s*(a\.m\.|p\.m\.)", lambda m: m.group(1) + " " + m.group(2).replace(".", ""), t)
    return re.sub(r"\b(\d+)\b", lambda m: ones[int(m.group(1))] if int(m.group(1)) <= 20 else m.group(1), t)


def score(case, fields, status):
    right = 0
    notes = []
    for k, kws in case["want"].items():
        v = (fields.get(k) or "").lower()
        if any(w in v for w in kws):
            right += 1
        else:
            notes.append(f"{k}: got {v!r}")
    invented = 0
    for k in case.get("empty", []):
        if (fields.get(k) or "").strip():
            invented += 1
            notes.append(f"{k}: should be empty, got {fields.get(k)!r}")
    exp = case.get("expect_status", "complete")
    if status != exp:
        notes.append(f"status {status} != {exp}")
    return right, len(case["want"]), invented, status == exp, notes


def extract(transcript):
    st = agent_brain.process_user_turn(transcript, {"session_id": "eval", "fields": {}}, run_llm)
    return st["fields"], st["status"]


def clip(text, snr=None, rng=np.random.default_rng(7)):
    p = os.path.join(os.environ.get("TEMP", "."), "e2e_eval", re.sub(r"\W+", "_", text)[:40] + ".wav")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if not os.path.exists(p):
        S.synth(text, p)
    x = S.load16k(p)
    if snr is not None:
        n = rng.standard_normal(len(x)).astype(np.float32)
        n *= np.sqrt(np.mean(x ** 2) / (10 ** (snr / 10)) / np.mean(n ** 2))
        x = x + n
    x *= 0.8 / max(1e-6, np.abs(x).max())
    return S.to_wav(x)


def phase(name, snr, speech):
    R = T = B = SOK = 0
    werE = werN = 0
    print(f"\n== {name}", flush=True)
    for i, c in enumerate(CASES):
        t0 = time.time()
        tr = c["text"]
        if speech:
            tr, _ = S.stt(clip(c["text"], snr))
            e, n = S.wer(norm(c["text"]), norm(tr))
            werE += e
            werN += n
        f, st = extract(tr)
        r, t, b, sok, notes = score(c, f, st)
        R += r; T += t; B += b; SOK += sok
        print(f"  case {i+1}: {r}/{t} fields right, {b} invented, gate {'ok' if sok else 'WRONG'}  ({time.time()-t0:.0f}s)", flush=True)
        if speech and notes:
            print(f"      heard: {tr}")
        for n_ in notes:
            print("      -", n_)
    line = f"  TOTAL: {R}/{T} fields correctly mapped ({100*R/T:.0f}%), {B} invented values, {SOK}/{len(CASES)} gate decisions right"
    if speech:
        line += f", speech WER {100*werE/max(1, werN):.1f}% ({werE}/{werN})"
    print(line, flush=True)


def dialog():
    print("\n== multi-turn dialogue (clarification questions)", flush=True)
    turns = ["There was a strong gas smell in the basement.", "It was around three PM yesterday.",
             "We evacuated the floor and called the gas company."]
    st = {"session_id": "d", "fields": {}}
    for u in turns:
        st = agent_brain.process_user_turn(u, st, run_llm)
        print(f"  user: {u}\n   -> {st['status']}; asks: {st['next_clarification_prompt']}", flush=True)
    ok = st["status"] == "complete"
    print(f"  final status: {st['status']} ({'ok' if ok else 'WRONG'}); fields: " + json.dumps({k: v for k, v in st['fields'].items() if v}))


if __name__ == "__main__":
    which = sys.argv[1:] or ["text", "speech", "noisy", "dialog"]
    print("board:", npu_runtime.npu_status())
    if "text" in which:
        phase("typed narration -> LLM", None, False)
    if "speech" in which:
        phase("spoken narration (clean) -> Whisper -> LLM", None, True)
    if "noisy" in which:
        phase("spoken narration, 10 dB noise -> Whisper -> LLM", 10, True)
    if "dialog" in which:
        dialog()
