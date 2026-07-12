#!/usr/bin/env python3
# casebook_harvest.py (PORTABLE) — export lexicon harvest candidates from the case-book.
# Source = arrival-miss × anno.genuine: the core situation ACTUALLY landed in the reply
# (the LLM judge confirmed the act), but the prompt lexicon never surfaced it → THIS prompt
# is a lexicon gap. CANDIDATE, not an auto-insert — we do NOT close the lexicon←acted_on
# recursion; a human triggers the insertion into core-triggers.txt (see TUNE.md §recursion).
#
# Usage: casebook_harvest.py            # per-core report + harvest-candidates.jsonl
import os, json
from collections import Counter

H = os.path.expanduser("~")
G = os.path.join(H, ".claude/glados")
CB = os.path.join(G, "case-book.jsonl")
OUT = os.path.join(G, "harvest-candidates.jsonl")

def main():
    cands = []
    for l in open(CB, encoding="utf-8"):
        c = json.loads(l)
        if not c.get("arrival_miss"): continue
        if c.get("voice") == "paste": continue   # paste-boundary: a forward is not the user's dialect
        v = (c.get("anno") or {}).get("verdicts", {})
        for core in c["arrival_miss"]:
            if v.get(core) != "genuine": continue
            cands.append({
                "core": core, "id": c["id"], "ts": c["ts"],
                "prompt": c["prompt"],                       # gap: this phrase SHOULD have fired the core
                "witness_reply": (c.get("witness") or {}).get(core, []),  # how the core landed in the reply
                "reflection": (c.get("anno") or {}).get("reflection", ""),
                "src": "casebook-arrival-miss×genuine",
            })
    cands.sort(key=lambda x: (int(x["core"]), x["ts"]))
    with open(OUT, "w", encoding="utf-8") as fh:
        for x in cands:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    pc = Counter(x["core"] for x in cands)
    print(f"candidates={len(cands)}  per-core={dict(sorted(pc.items(), key=lambda kv: int(kv[0])))}")
    print(f"→ {OUT}  (lexicon candidates; a human triggers the insertion into core-triggers.txt)")

if __name__ == "__main__":
    main()
