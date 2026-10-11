"""Repeatability: send the same extraction prompt N times to the board's LLM and count distinct outputs.  python scripts/llm_repeat.py [N]"""
import json, sys, collections
sys.path.insert(0, ".")
from backend import agent_brain, npu_runtime
n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
for text in ("There was a strong gas smell in the basement.", "A forklift hit a rack in warehouse two yesterday afternoon."):
    p = agent_brain.build_extraction_prompt(text, {})
    outs = collections.Counter(npu_runtime.run_llm(p).strip() for _ in range(n))
    print(f"{text!r}: {len(outs)} distinct output(s) in {n} runs")
    for o, c in outs.most_common():
        print(f"   x{c}: {o[:260]}")
