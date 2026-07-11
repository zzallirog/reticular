#!/usr/bin/env python3
"""rebalance_check.py — the GATEKEEPER pass. Run BEFORE applying any tune.

The failure it exists for (live case): an eager assistant sees "51% echo" and
proposes to fix the number — by narrowing triggers, muting cores, "cleaning up".
If the owner is trusting, the attention layer dies of the cure: disposition-class
facets are SUPPOSED to run hot, and a matrix tuned to make a dashboard number
pretty stops firing where it matters.

So: before any lexicon surgery, this pass answers with COUNTED numbers —
did the proportions actually break, or does someone just dislike a number?

Checks (all read-only, stdlib only):
  1. per-core fire share now vs the saved snapshot (drift beyond tolerance?)
  2. echo-rate BY CORE, not global — a global echo number is not actionable
  3. class leakage: cores marked `class: disposition` must NOT sit in the
     trigger matrix (they belong to the floor; matrix presence = leak)
  4. hygiene hints: fire-log size, stale embedding index vs triggers mtime,
     annotation coverage (tune on unjudged data inherits the oracle's bias)

Exit: prints a verdict per check; writes/refreshes the snapshot with --save.
Nothing is ever modified except the snapshot file (--save).
"""
import json
import os
import sys
from collections import Counter

H = os.path.expanduser("~")
G = os.path.join(H, ".claude/glados")
FLOG = os.path.join(G, "fire-log.jsonl")
CB = os.path.join(G, "case-book.jsonl")
TRIG = os.path.join(G, "core-triggers.txt")
P2P = os.path.join(G, "core_p2p.json")
CORES_DIR = os.path.join(H, ".claude/overlays/cores")
SNAP = os.path.join(G, "rebalance-snapshot.json")
DRIFT_PP = 12  # percentage-point tolerance for per-core share drift


def rows(path):
    out = []
    try:
        for line in open(path, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def trigger_cores():
    out = set()
    try:
        for line in open(TRIG, encoding="utf-8"):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            p = line.split("|||")
            if len(p) >= 3:
                out.add(p[0].strip()[:2].lstrip("0") or "0")
    except OSError:
        pass
    return out


def disposition_cores():
    out = set()
    try:
        for fn in os.listdir(CORES_DIR):
            if not fn.endswith(".md"):
                continue
            head = open(os.path.join(CORES_DIR, fn), encoding="utf-8",
                        errors="ignore").read(400)
            if "class: disposition" in head:
                cid = fn.split("-")[0].lstrip("0") or "0"
                out.add(cid)
    except OSError:
        pass
    return out


def main():
    save = "--save" in sys.argv
    fl = rows(FLOG)
    fired = [r for r in fl if r.get("surfaced")]
    share = Counter(c for r in fired for c in r["surfaced"])
    total = sum(share.values()) or 1
    now = {c: round(n * 100 / total, 1) for c, n in share.items()}

    print(f"fire-log: {len(fl)} rows · {len(fired)} fired · shares(%): "
          f"{dict(sorted(now.items(), key=lambda kv: -kv[1]))}")

    # 1. drift vs snapshot
    try:
        snap = json.load(open(SNAP, encoding="utf-8"))
        drifted = {c: (snap.get("shares", {}).get(c, 0), now.get(c, 0))
                   for c in set(snap.get("shares", {})) | set(now)
                   if abs(snap.get("shares", {}).get(c, 0) - now.get(c, 0)) > DRIFT_PP}
        if drifted:
            print(f"⚠ DRIFT >{DRIFT_PP}pp vs snapshot {snap.get('ts','?')}: "
                  + "  ".join(f"core {c}: {a}%→{b}%" for c, (a, b) in drifted.items()))
        else:
            print(f"✓ proportions hold vs snapshot {snap.get('ts','?')}")
    except OSError:
        print("· no snapshot yet — run with --save to set the baseline")

    # 2. echo-rate PER CORE (global echo is not a verdict)
    cb = rows(CB)
    v_by_core: dict = {}
    for c in cb:
        for core, verd in ((c.get("anno") or {}).get("verdicts") or {}).items():
            v_by_core.setdefault(core, Counter())[verd] += 1
    for core, cnt in sorted(v_by_core.items(), key=lambda kv: kv[0]):
        n = sum(cnt.values())
        print(f"  core {core}: n={n} echo={cnt['echo']*100//max(n,1)}% "
              f"genuine={cnt['genuine']*100//max(n,1)}%"
              + ("  ← high echo is NORMAL if this facet is disposition-class"
                 if cnt["echo"] > cnt["genuine"] else ""))

    # 3. class leakage: dispositions must not live in the matrix
    leak = trigger_cores() & disposition_cores()
    if leak:
        print(f"⚠ LEAK: disposition cores present in trigger matrix: {sorted(leak)} "
              f"— they belong to the floor; remove their trigger lines")
    else:
        print("✓ no disposition cores in the matrix")

    # 4. hygiene
    anno = sum(1 for c in cb if c.get("anno"))
    if cb and anno / len(cb) < 0.5:
        print(f"⚠ annotation coverage {anno}/{len(cb)} — tune candidates from "
              f"unjudged rows inherit the oracle's bias; judge first")
    try:
        if os.path.getmtime(TRIG) > os.path.getmtime(P2P):
            print("⚠ triggers newer than embedding index — rebuild: build_embeddings.py")
    except OSError:
        pass

    if save:
        import datetime
        json.dump({"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                   "shares": now, "rows": len(fl)},
                  open(SNAP, "w", encoding="utf-8"))
        print(f"→ snapshot saved: {SNAP}")
    else:
        print("(read-only pass; --save to refresh the baseline)")


if __name__ == "__main__":
    main()
