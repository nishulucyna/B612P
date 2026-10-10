import sys, time, json
sys.path.insert(0, ".")
from backend import npu_runtime as r
from backend.agent_brain import process_user_turn, MANDATORY_FIELDS
import json as _j
with open("./contract.json") as f: state=_j.load(f)
turns=[
 ("A pipe burst on the second floor!", None),
 ("It happened at 2 PM and we turned off the main valve.", None),
]
print("health:", r.npu_status().get("llm"))
lat=[]
def llm(p):
    t=time.time(); out=r.run_llm(p); lat.append(time.time()-t); return out
cases=[
 "There was a water leak near Conference Room 2 around 10 AM. Maintenance has already isolated the area.",
 "Yesterday evening about 6:30 a technician, Ravi, slipped on oil near the CNC machine in Bay 4 and hurt his ankle. We called first aid and cordoned off the spill.",
]
for c in cases:
    st=process_user_turn(c, _j.loads(_j.dumps(state)), llm)
    print("\nCASE:", c[:70]+"..."); print(" status:", st["status"], "| missing:", st["missing_mandatory_fields"], "| %.1fs"%lat[-1])
    print(" fields:", {k:v for k,v in st["fields"].items() if v})
print("\nMULTI-TURN:")
st=_j.loads(_j.dumps(state))
for t,_ in turns:
    st=process_user_turn(t, st, llm)
    print(" turn:", t[:55], "->", st["status"], "| missing:", st["missing_mandatory_fields"], "| %.1fs"%lat[-1])
print(" final fields:", {k:v for k,v in st["fields"].items() if v})
print("\nlatency per LLM call: avg %.1fs, max %.1fs over %d calls"%(sum(lat)/len(lat), max(lat), len(lat)))
