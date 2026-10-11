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


# Held-out second set: harder wording, unstated details (must stay empty), corrections, and reports that must NOT be completed.
CASES2 = [
    dict(text="Water leak near Conference Room 2 around 10 AM. Maintenance has already isolated the area.",
         want=dict(incident_type=["leak", "water"], incident_location=["conference room 2", "conference room two"], date_time=["10"], immediate_actions_taken=["isolat"]),
         empty=["persons_involved", "witness_information", "recommended_follow_up_action"]),
    dict(text="At 6:45 this morning Deepak Rao fell off the loading dock at gate three. He broke his wrist. We called an ambulance and kept him still. Two drivers, Salim and Joe, saw it.",
         want=dict(incident_type=["fall", "fell"], incident_location=["gate three", "gate 3", "loading dock"], date_time=["6:45", "6.45", "morning"],
                   immediate_actions_taken=["ambulance"], persons_involved=["deepak"], witness_information=["salim", "joe"])),
    dict(text="Last night around midnight the chiller on the roof of block B stopped working. The temperature in the data centre went up to forty degrees. We switched on the backup unit and informed the facilities manager.",
         want=dict(incident_type=["chiller", "cooling", "failure", "stopp", "temperature"], incident_location=["block b", "roof", "data cent"], date_time=["midnight", "last night"],
                   immediate_actions_taken=["backup"], equipment_asset_involved=["chiller"])),
    dict(text="Small fire in the pantry on the third floor at two PM today. A microwave caught fire. Someone used the extinguisher and it was out in a minute. Nobody was hurt.",
         want=dict(incident_type=["fire"], incident_location=["pantry", "third floor"], date_time=["2", "two"], immediate_actions_taken=["extinguish"],
                   equipment_asset_involved=["microwave"])),
    dict(text="There is oil on the floor near the assembly line, it's a slip hazard. I put up a wet floor sign. I don't know when it started.",
         want=dict(incident_type=["oil", "spill", "slip", "hazard"], incident_location=["assembly line"], immediate_actions_taken=["sign"]),
         expect_status="collecting", empty=["date_time"]),
    dict(text="Hi, so, we had a power cut in the east lab at about eleven fifteen, the UPS kicked in but the freezer alarm went off. Dr. Menon moved the samples to the backup freezer.",
         want=dict(incident_type=["power"], incident_location=["east lab"], date_time=["11", "eleven"], immediate_actions_taken=["moved", "samples", "backup freezer"],
                   persons_involved=["menon"], equipment_asset_involved=["ups", "freezer"])),
    dict(text="A contractor, Mr. Fernandes, got an electric shock from an exposed cable while drilling in the basement yesterday at four thirty. He was taken to the clinic. The site supervisor has locked the area.",
         want=dict(incident_type=["shock", "electric"], incident_location=["basement"], date_time=["yesterday", "4", "four"], immediate_actions_taken=["clinic", "locked"],
                   persons_involved=["fernandes"])),
    dict(text="Gas smell reported in the canteen kitchen. We opened the windows and turned off the main gas valve.",
         want=dict(incident_type=["gas"], incident_location=["canteen", "kitchen"], immediate_actions_taken=["valve", "window"]),
         expect_status="collecting", empty=["date_time"]),
    dict(text="The crane hook snapped while lifting a steel beam at the north site at 9:10 AM on Tuesday. The beam fell but landed in the empty yard. We stopped all lifting work and called the inspector.",
         want=dict(incident_type=["crane", "hook", "snap"], incident_location=["north site"], date_time=["9:10", "tuesday"], immediate_actions_taken=["stopped", "inspector"],
                   equipment_asset_involved=["crane", "hook", "beam"])),
    dict(text="A visitor fainted in the reception area just now. The nurse gave first aid and she is recovering.",
         want=dict(incident_type=["faint", "medical", "collapse"], incident_location=["reception"], date_time=["now"], immediate_actions_taken=["first aid"])),
    dict(text="Okay, correction: the spill was not in lab four, it was in lab five, at eight AM, and we mopped it up with absorbent pads.",
         want=dict(incident_type=["spill"], incident_location=["lab five", "lab 5"], date_time=["8", "eight"], immediate_actions_taken=["mop", "absorbent"])),
    dict(text="Something happened in the warehouse.", want=dict(incident_location=["warehouse"]), expect_status="collecting",
         empty=["severity_level", "persons_involved", "witness_information", "date_time", "immediate_actions_taken", "incident_type"]),
]


def run_llm(p):
    raw = npu_runtime.run_llm(p)
    if os.environ.get("GUARD") == "1":                 # prototype output guard (scripts/llm_guard.py), as an app-side filter would apply it
        from llm_guard import guard
        return guard(p, raw, grounding=os.environ.get("GUARD_RULES", "12") != "1")
    return raw


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
    args = sys.argv[1:]
    if "set2" in args:
        CASES = CASES2
        args = [x for x in args if x != "set2"]
    which = args or ["text", "speech", "noisy", "dialog"]
    print("board:", npu_runtime.npu_status())
    if "text" in which:
        phase("typed narration -> LLM", None, False)
    if "speech" in which:
        phase("spoken narration (clean) -> Whisper -> LLM", None, True)
    if "noisy" in which:
        phase("spoken narration, 10 dB noise -> Whisper -> LLM", 10, True)
    if "dialog" in which:
        dialog()
