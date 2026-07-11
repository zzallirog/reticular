#!/usr/bin/env python3
# casebook_sidecases.py (PORTABLE) — побочные кучи датасета (цена нуля при готовых вердиктах):
#
# A) anti-trigger-candidates.jsonl — спан-статистика echo vs genuine per (core, span).
#    Спан, что летит в echo и (почти) никогда в genuine = кандидат АНТИ-триггера
#    (негатив на ребре: сузить regex ядра / добавить исключение). ЭТО и есть
#    трассировка ложных срабатываний до конкретного слова.
# B) exemplars.jsonl — genuine-кейсы с reflection per-core = few-shot банк:
#    сырьё для дистилляции дорогого LLM-судьи в дешёвого локального.
#
# Оба = КАНДИДАТЫ (LLM-судья, не human); врезку/дистилляцию триггерит человек.
import os, json
from collections import defaultdict, Counter

H = os.path.expanduser("~")
G = os.path.join(H, ".claude/glados")
CB = os.path.join(G, "case-book.jsonl")
OUT_A = os.path.join(G, "anti-trigger-candidates.jsonl")
OUT_B = os.path.join(G, "exemplars.jsonl")

def main():
    span_stat = defaultdict(lambda: {"echo": 0, "genuine": 0, "partial": 0, "ids_echo": []})
    exemplars = []
    for l in open(CB, encoding="utf-8"):
        c = json.loads(l)
        a = c.get("anno")
        if not a: continue
        wit = c.get("witness") or {}
        for core, verd in a["verdicts"].items():
            for span in wit.get(core, []):
                st = span_stat[(core, span)]
                st[verd] += 1
                if verd == "echo" and len(st["ids_echo"]) < 4: st["ids_echo"].append(c["id"])
            if verd == "genuine":
                exemplars.append({"core": core, "id": c["id"], "ts": c["ts"],
                                  "prompt": c["prompt"], "witness": wit.get(core, []),
                                  "case": a.get("case", ""), "reflection": a.get("reflection", ""),
                                  "src": "casebook-genuine"})
    # A: анти-триггер кандидат = echo≥2 и genuine=0 (чистый ложный спан этого ядра)
    cands = []
    for (core, span), st in span_stat.items():
        if st["echo"] >= 2 and st["genuine"] == 0:
            cands.append({"core": core, "span": span, "echo": st["echo"],
                          "partial": st["partial"], "genuine": 0,
                          "sample_ids": st["ids_echo"], "src": "casebook-echo-span"})
    cands.sort(key=lambda x: (int(x["core"]), -x["echo"]))
    with open(OUT_A, "w", encoding="utf-8") as fh:
        for x in cands: fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    exemplars.sort(key=lambda x: (int(x["core"]), x["ts"]))
    with open(OUT_B, "w", encoding="utf-8") as fh:
        for x in exemplars: fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    pa = Counter(x["core"] for x in cands); pb = Counter(x["core"] for x in exemplars)
    print(f"A anti-trigger spans={len(cands)} per-core={dict(sorted(pa.items(), key=lambda kv: int(kv[0])))}")
    print(f"B exemplars={len(exemplars)} per-core={dict(sorted(pb.items(), key=lambda kv: int(kv[0])))}")
    print(f"→ {OUT_A}\n→ {OUT_B}")

if __name__ == "__main__":
    main()
