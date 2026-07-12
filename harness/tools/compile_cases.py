#!/usr/bin/env python3
# compile_cases.py (PORTABLE) — fire-log (LOG) → case-book.jsonl (DATASET).
# Log = stream of turns; dataset = cases with genealogy. A case = a turn with acted_on≠∅:
# prompt, reply excerpt, cores, witness (witness spans), direction, source.
# The mechanical part is here; the semantic part (verdict genuine/echo/partial) is the
# LLM judge, merged back via the "anno" field (annotate_merge.py). See TUNE.md for the full cycle.
#
# ⚠ Overwrites case-book.jsonl — after a recompile, re-run the anno merge.
import os, json
from backfill_acted import turns_of, read, transcript_of

H = os.path.expanduser("~")
G = os.path.join(H, ".claude/glados")
FLOG = os.path.join(G, "fire-log.jsonl")
TRIG = os.path.join(G, "core-triggers.txt")
OUT = os.path.join(G, "case-book.jsonl")
EXC = 700  # reply excerpt

def situation_cores():
    """SITU = cores that HAVE lexicon in core-triggers.txt (situation cores).
    Disposition cores do not live in the triggers (they are the floor, not the matrix) — so they are absent here."""
    situ = set()
    for line in read(TRIG).splitlines():
        if not line.strip() or line.lstrip().startswith("#"): continue
        p = line.split("|||")
        if len(p) >= 3:
            situ.add(p[0].strip()[:2].lstrip("0") or "0")
    return situ

def main():
    SITU = situation_cores()
    seen_ids = {}   # ts collision (2 turns in the same second) → suffix, otherwise anno merge by id hits both cases
    rows = [json.loads(l) for l in read(FLOG).splitlines() if l.strip()]
    by_sid = {}
    for r in rows:
        by_sid.setdefault(r.get("sid", ""), []).append(r)
    cases = []
    for sid, srows in by_sid.items():
        acted_rows = [r for r in srows if r.get("acted_on")]
        if not acted_rows: continue
        tpath = transcript_of(sid)
        turns = turns_of(tpath) if tpath else []
        tp = 0
        for r in srows:
            if not r.get("acted_on"): continue
            reply = ""
            pfx = r.get("prompt", "")
            for j in range(tp, len(turns)):
                if turns[j][0][:len(pfx)] == pfx:
                    reply = turns[j][1]; tp = j + 1; break
            # arrival-miss: a situation core LANDED in the reply (acted_on), but its prompt-side leg
            # did NOT surface while the situation lexicon was empty → a hole in the prompt-side lexicon.
            arrival_miss = ([c for c in r["acted_on"] if c in SITU and c not in r.get("surfaced", [])]
                            if r.get("situ_lex_empty") else [])
            cid_ = f"{sid[:8]}·{r['ts']}"
            n = seen_ids.get(cid_, 0)
            seen_ids[cid_] = n + 1
            if n: cid_ = f"{cid_}·{n+1}"
            cases.append({
                "id": cid_,
                "ts": r["ts"], "sid": sid,
                "prompt": r.get("prompt", ""),
                "reply_excerpt": reply[:EXC],
                "acted_on": r["acted_on"],
                "arrival_miss": arrival_miss,   # harvest source #1 (filter by anno genuine!)
                "witness": r.get("witness"),          # reply spans (what fired it)
                "wit_prompt": r.get("wit_prompt"),    # prompt spans (the input's lex leg)
                "lex": r.get("lex", []), "sem": r.get("sem", []),
                "dir": r.get("dir"),
                "surfaced": r.get("surfaced", []),    # what the hook actually surfaced
                "source": r.get("acted_src"),         # how the case entered the dataset
                "voice": r.get("voice"),
                "anno": r.get("anno"),                # LLM layer (None until annotated)
            })
    cases.sort(key=lambda c: c["ts"])
    with open(OUT, "w", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    nn = sum(1 for c in cases if c["reply_excerpt"])
    print(f"cases={len(cases)}  with_reply={nn}  situ_cores={sorted(SITU, key=lambda x: int(x) if x.isdigit() else 99)}  → {OUT}")

if __name__ == "__main__":
    main()
