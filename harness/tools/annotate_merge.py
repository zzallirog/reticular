#!/usr/bin/env python3
# annotate_merge.py (PORTABLE) — мерж LLM-разметки в case-book.jsonl по id.
# anno = {"verdicts": {core: genuine|echo|partial}, "case": str, "reflection": str,
#         "drop": bool, "anno_src": "<judge>-<date>"}
# ГРАНИЦА: anno = LLM-судья, не human-label; anno_src едет рядом — различай пост-хок.
# Usage: annotate_merge.py <annos.json> [--src judge-YYYY-MM-DD]
import sys, os, json, tempfile

H = os.path.expanduser("~")
CB = os.path.join(H, ".claude/glados/case-book.jsonl")

def main():
    if len(sys.argv) < 2:
        print("usage: annotate_merge.py <annos.json> [--src label]"); return
    src = "judge"
    if "--src" in sys.argv:
        src = sys.argv[sys.argv.index("--src") + 1]
    payload = json.load(open(sys.argv[1], encoding="utf-8"))
    annos = payload["annos"] if isinstance(payload, dict) else payload
    by_id = {a["id"]: a for a in annos}
    lines = open(CB, encoding="utf-8").read().splitlines()
    hit = miss = 0
    out = []
    for l in lines:
        if not l.strip(): continue
        c = json.loads(l)
        a = by_id.get(c["id"])
        if a:
            c["anno"] = {"verdicts": a.get("verdicts", {}), "case": a.get("case", ""),
                         "reflection": a.get("reflection", ""), "drop": bool(a.get("drop")),
                         "anno_src": src}
            hit += 1
        else:
            miss += 1
        out.append(json.dumps(c, ensure_ascii=False))
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(CB), prefix=".case-book.")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    os.replace(tmp, CB)
    print(f"merged anno: {hit}  without: {miss}")

if __name__ == "__main__":
    main()
