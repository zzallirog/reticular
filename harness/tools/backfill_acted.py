#!/usr/bin/env python3
# backfill_acted.py (PORTABLE) — retroactive landing oracle.
# fire-log rows from before ida-land was enabled sit at acted_on=null. This script runs the SAME
# oracle (reply-lex, core-triggers.txt) over historical transcripts and back-fills
# acted_on + witness (the matched spans per core).
#
# HONEST BOUNDARY: acted_src="reply-lex-backfill" — distinguishable from the live "reply-lex"
# (Stop-hook) and from a human label. A human label is NOT overwritten.
# acted_on=[] = "scanned, no cores landed"; null stays = the oracle never reached it.
#
# Usage: backfill_acted.py [--apply]   (no flag = dry-run report)
import sys, os, json, re, glob, tempfile
from collections import Counter

H = os.path.expanduser("~")
G = os.path.join(H, ".claude/glados")
TRIG = os.path.join(G, "core-triggers.txt")
FLOG = os.path.join(G, "fire-log.jsonl")
PROJ = os.path.join(H, ".claude/projects")
SRC = "reply-lex-backfill"
LIVE_SRC = "reply-lex"
WITNESS_CAP = 6

def read(p):
    try: return open(p, encoding="utf-8", errors="ignore").read()
    except OSError: return ""

def transcript_of(sid):
    """Auto-discover: the session transcript wherever the project lives (~/.claude/projects/*/sid.jsonl)."""
    g = glob.glob(os.path.join(PROJ, "*", sid + ".jsonl"))
    return g[0] if g else None

def load_triggers():
    trig = []
    for line in read(TRIG).splitlines():
        if not line.strip() or line.lstrip().startswith("#"): continue
        p = line.split("|||")
        if len(p) < 3: continue
        cid = p[0].strip()[:2].lstrip("0") or "0"
        try: trig.append((cid, re.compile(p[1].strip())))
        except re.error: continue
    return trig

def lex_scan_witness(text, trig):
    """Like ida-land lex_scan, but over compiled triggers: {core: [spans]}."""
    tlow = text.lower()
    hits, witness = [], {}
    for cid, rx in trig:
        spans = []
        for m in rx.finditer(tlow):
            s = m.group(0).strip()
            if s and s not in spans: spans.append(s)
            if len(spans) >= WITNESS_CAP: break
        if spans:
            if cid not in hits: hits.append(cid)
            witness.setdefault(cid, []).extend(x for x in spans if x not in witness.get(cid, []))
    return hits, witness

def turns_of(tpath):
    """[(user_text, reply_text)] — segmentation like ida-land, but over every turn."""
    turns, cur, buf = [], None, []
    for line in read(tpath).splitlines():
        try: row = json.loads(line)
        except Exception: continue
        if row.get("isMeta"): continue
        t = row.get("type")
        msg = row.get("message") or {}
        c = msg.get("content")
        if t == "user":
            utext = None
            if isinstance(c, str) and c.strip():
                utext = c
            elif isinstance(c, list):
                texts = [b.get("text", "") for b in c
                         if isinstance(b, dict) and b.get("type") == "text" and b.get("text")]
                if texts: utext = "\n".join(texts)
            if utext is not None:
                if cur is not None: turns.append((cur, "\n".join(buf)))
                cur, buf = utext, []
        elif t == "assistant" and isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                    buf.append(b["text"])
    if cur is not None: turns.append((cur, "\n".join(buf)))
    return turns

def main():
    apply = "--apply" in sys.argv
    trig = load_triggers()
    lines = read(FLOG).splitlines()
    rows = []
    for i, l in enumerate(lines):
        try: rows.append((i, json.loads(l)))
        except Exception: continue

    by_sid = {}
    for i, r in rows:
        by_sid.setdefault(r.get("sid", ""), []).append((i, r))

    stats = Counter()
    filled_cores = Counter()
    for sid, srows in by_sid.items():
        nulls = [(i, r) for i, r in srows if r.get("acted_on") is None]
        if not nulls: continue
        tpath = transcript_of(sid)
        if not tpath:
            stats["no_transcript"] += len(nulls); continue
        turns = turns_of(tpath)
        tp = 0  # monotonic pointer: fire-log and transcript are both chronological
        for i, r in nulls:
            pfx = r.get("prompt", "")
            hit = None
            for j in range(tp, len(turns)):
                if turns[j][0][:len(pfx)] == pfx:
                    hit = j; break
            if hit is None:
                stats["turn_not_found"] += 1; continue
            tp = hit + 1
            reply = turns[hit][1]
            if len(reply.split()) < 3:
                stats["trivial_reply"] += 1; continue
            acted, wit = lex_scan_witness(reply, trig)
            r["acted_on"] = acted
            r["acted_src"] = SRC
            if wit: r["witness"] = wit
            lines[i] = json.dumps(r, ensure_ascii=False)
            stats["filled"] += 1
            if acted:
                stats["filled_nonempty"] += 1
                for c in acted: filled_cores[c] += 1
            else:
                stats["filled_empty"] += 1

    print(f"rows={len(rows)}  " + "  ".join(f"{k}={v}" for k, v in sorted(stats.items())))
    print("cores:", dict(filled_cores.most_common()))
    if not apply:
        print("(dry-run — fire-log NOT rewritten; use --apply to write)")
        return
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(FLOG), prefix=".fire-log.")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp, FLOG)
    print("applied → fire-log.jsonl")

if __name__ == "__main__":
    main()
