#!/usr/bin/env python3
# casebook_harvest.py (PORTABLE) — экспорт харвест-кандидатов лексикона из case-book.
# Сырьё = arrival-miss × anno.genuine: ситуация-ядро РЕАЛЬНО легло в ответ (LLM-судья
# подтвердил акт), но промпт-лексика его не всплыла → ЭТОТ промпт = дыра лексикона.
# КАНДИДАТ, не авто-врезка — рекурсию лексикон←acted_on НЕ замыкаем, врезку в
# core-triggers.txt триггерит человек (см. TUNE.md §рекурсия).
#
# Usage: casebook_harvest.py            # отчёт per-core + harvest-candidates.jsonl
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
        if c.get("voice") == "paste": continue   # paste-boundary: форвард ≠ диалект юзера
        v = (c.get("anno") or {}).get("verdicts", {})
        for core in c["arrival_miss"]:
            if v.get(core) != "genuine": continue
            cands.append({
                "core": core, "id": c["id"], "ts": c["ts"],
                "prompt": c["prompt"],                       # дыра: эта фраза ДОЛЖНА была зажечь core
                "witness_reply": (c.get("witness") or {}).get(core, []),  # чем ядро легло в ответ
                "reflection": (c.get("anno") or {}).get("reflection", ""),
                "src": "casebook-arrival-miss×genuine",
            })
    cands.sort(key=lambda x: (int(x["core"]), x["ts"]))
    with open(OUT, "w", encoding="utf-8") as fh:
        for x in cands:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    pc = Counter(x["core"] for x in cands)
    print(f"candidates={len(cands)}  per-core={dict(sorted(pc.items(), key=lambda kv: int(kv[0])))}")
    print(f"→ {OUT}  (кандидаты в лексикон; врезку в core-triggers.txt триггерит человек)")

if __name__ == "__main__":
    main()
