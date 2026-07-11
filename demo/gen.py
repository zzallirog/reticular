#!/usr/bin/env python3
"""Generate the synthetic demo corpus (persona: a solo dev shipping a web app).

Writes demo/glados/ (cores, triggers, fire-log, case-book) and demo/projects/
(two fake Claude Code session transcripts). Everything is invented; the SHAPE
mirrors real reticular state so the Fires plane and the tune loop have
something honest to show. Deterministic — no randomness, no clock.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "glados")
P = os.path.join(HERE, "projects", "-home-demo")
C = os.path.join(HERE, "overlays", "cores")
for d in (G, P, C):
    os.makedirs(d, exist_ok=True)

# ── cores (three situation facets + one disposition) ──
CORES = {
    "1": ("ship-gate", "before anything goes out",
          "Deploys used to happen on vibes. The gate: staging first, rollback "
          "path named, one number that says the release is healthy."),
    "2": ("measure-first", "claim needs a number",
          "'Faster', 'better', 'fixed' are moods. A claim ships with the "
          "number that would falsify it, or it waits."),
    "3": ("scope-guard", "one task at a time",
          "Refactors that started as a typo fix. The guard: name the box "
          "you're in; anything outside it becomes a listed follow-up."),
}
DISPO = ("7", "plain-words", "always-on",
         "Say what happened in plain words. No 'successfully completed' over "
         "a red test suite.")

for cid, (slug, when, body) in CORES.items():
    with open(os.path.join(C, f"{cid.zfill(2)}-{slug}.md"), "w") as fh:
        fh.write(f"---\nname: core-{slug}\ncore: {cid}\nclass: situation-pull\n"
                 f"---\n\n# Core {cid} — {slug}\n\n{body}\n")
cid, slug, when, body = DISPO
with open(os.path.join(C, f"{cid.zfill(2)}-{slug}.md"), "w") as fh:
    fh.write(f"---\nname: core-{slug}\ncore: {cid}\nclass: disposition\n---\n\n"
             f"# Core {cid} — {slug}\n\n{body}\n")

with open(os.path.join(G, "core-triggers.txt"), "w") as fh:
    fh.write("# cid|||regex(lower prompt)|||when-label|||native chunks\n")
    fh.write("1|||deploy|ship it|release|prod\\b|go live|||before anything goes out|||deploy;ship it;release;go live\n")
    fh.write("2|||faster|benchmark|perf\\b|optimi[sz]|latency|||claim needs a number|||faster;benchmark;latency\n")
    fh.write("3|||refactor|while we'?re at it|also add|clean.?up|||one task at a time|||refactor;while we're at it\n")

# ── two synthetic sessions: turn-1 drift catch + echo + arrival-miss ──
S1, S2 = "demo1111-aaaa-bbbb-cccc-000000000001", "demo2222-aaaa-bbbb-cccc-000000000002"

_CLOCK = {"n": 0}

def _ts():
    # deterministic fake clock: 2 minutes per event, starting 2026-07-01 10:00 UTC
    _CLOCK["n"] += 1
    m = _CLOCK["n"] * 2
    day = 1 + m // (24 * 60)
    return f"2026-07-{day:02d}T{(10 + (m // 60) % 14):02d}:{m % 60:02d}:00.000Z"

def turn(prompt, reply):
    return [
        {"type": "user", "uuid": f"u-{_CLOCK['n']:04d}", "timestamp": _ts(),
         "cwd": "/home/demo/webapp", "message": {"role": "user", "content": prompt}},
        {"type": "assistant", "uuid": f"a-{_CLOCK['n']:04d}", "timestamp": _ts(),
         "cwd": "/home/demo/webapp",
         "message": {"role": "assistant", "model": "claude-sonnet-5",
                     "content": [{"type": "text", "text": reply}]}},
    ]

s1 = (
    # turn 1: the drift case — user asks small, agent about to go big; core 3 fires ON TURN ONE
    turn("fix the typo in the pricing page header",
         "One-line fix in header.tsx. I'll note the copy inconsistencies I saw "
         "as follow-ups instead of refactoring the whole component now — "
         "scope stays: typo only.")
    # turn 2: deploy talk — core 1 fires, reply genuinely acts the gate
    + turn("looks good, ship it to prod",
           "Before release: staging build is green, rollback is `rollback v41`, "
           "health number to watch is p95 latency on /checkout. Proceeding with the rollout.")
    # turn 3: perf claim — core 2 fires, reply acts it
    + turn("the new query feels faster, write it in the changelog",
           "Benchmark first: old query 340ms p50, new 210ms p50 on the same fixture "
           "(n=200). Now the changelog can say 'faster' with the number attached.")
)
_CLOCK["n"] = 720  # jump the fake clock to day 2 for the second session
s2 = (
    # echo case: META-talk about the harness itself lights its own lexicon
    turn("why did the deploy trigger fire on my last message?",
         "The word 'deploy' is in core 1's lexicon, so the hook surfaced it — "
         "but your message was ABOUT the trigger, not a deploy. That's an echo: "
         "the judge will mark it, and the span becomes an anti-trigger candidate.")
    # second echo: still meta — the span 'deploy' now false-fires twice → anti-trigger table
    + turn("should the deploy trigger be narrower then?",
           "Probably: 'deploy' as a bare word also matches questions about the "
           "deploy trigger itself. The tune loop will show it: two echo hits, "
           "zero genuine — that span becomes an anti-trigger candidate.")
    # arrival-miss case: prompt says 'push the button' (no lexicon word), reply IS a ship-gate act
    + turn("okay push the button",
           "Going out: release v42 to production. Staging green, rollback path "
           "named, watching p95 on /checkout for the next hour.")
)
for sid, turns in ((S1, s1), (S2, s2)):
    with open(os.path.join(P, sid + ".jsonl"), "w") as fh:
        for row in turns:
            fh.write(json.dumps(row) + "\n")

# ── fire-log: one row per user turn, shape = live schema ──
def row(ts, sid, prompt, surfaced, lex, dir_, wit, acted, witness, miss=False, voice="human"):
    r = {"ts": ts, "sid": sid, "prompt": prompt[:160], "surfaced": surfaced,
         "lex": lex, "sem": [], "situ_lex_empty": not lex, "prev": [],
         "scores": {}, "acted_on": acted, "voice": voice, "plen": len(prompt),
         "dir": dir_, "wit_prompt": wit or None}
    if acted is not None:
        r["acted_src"] = "reply-lex"
        if witness:
            r["witness"] = witness
    return r

FL = [
    row("2026-07-01T10:00:00", S1, "fix the typo in the pricing page header",
        [], [], "act", None, ["3"], {"3": ["refactoring"]}),          # arrival on reply: scope named
    row("2026-07-01T10:04:00", S1, "looks good, ship it to prod",
        ["1"], ["1"], "act", {"1": ["ship it", "prod"]}, ["1"],
        {"1": ["release"]}),
    row("2026-07-01T10:09:00", S1, "the new query feels faster, write it in the changelog",
        ["2"], ["2"], "act", {"2": ["faster"]}, ["2"], {"2": ["benchmark", "faster"]}),
    row("2026-07-02T09:30:00", S2, "why did the deploy trigger fire on my last message?",
        ["1"], ["1"], "read", {"1": ["deploy"]}, ["1"], {"1": ["deploy", "release"]}),
    row("2026-07-02T09:31:30", S2, "should the deploy trigger be narrower then?",
        ["1"], ["1"], "read", {"1": ["deploy"]}, ["1"], {"1": ["deploy"]}),
    row("2026-07-02T09:33:00", S2, "okay push the button",
        [], [], "act", None, ["1"], {"1": ["release", "production"]}, miss=True),
]
with open(os.path.join(G, "fire-log.jsonl"), "w") as fh:
    for r in FL:
        fh.write(json.dumps(r) + "\n")

# ── case-book with judge verdicts (the tune loop's input) ──
def case(r, reply, anno, arrival_miss=None):
    return {"id": f"{r['sid'][:8]}·{r['ts']}", "ts": r["ts"], "sid": r["sid"],
            "prompt": r["prompt"], "reply_excerpt": reply[:700],
            "acted_on": r["acted_on"], "arrival_miss": arrival_miss or [],
            "witness": r.get("witness"), "wit_prompt": r.get("wit_prompt"),
            "lex": r["lex"], "sem": [], "dir": r["dir"],
            "surfaced": r["surfaced"], "source": "reply-lex",
            "voice": r["voice"], "anno": anno}

def anno(verdicts, case_s, refl):
    return {"verdicts": verdicts, "case": case_s, "reflection": refl,
            "drop": False, "anno_src": "judge-demo"}

CB = [
    case(FL[0], s1[1]["message"]["content"][0]["text"],
         anno({"3": "genuine"}, "typo fix, refactor temptation named and boxed",
              "reply explicitly declines scope creep and lists follow-ups — the discipline, acted"),
         arrival_miss=["3"]),
    case(FL[1], s1[3]["message"]["content"][0]["text"],
         anno({"1": "genuine"}, "prod deploy with the gate walked",
              "staging/rollback/health-number all named before the deploy — gate executed")),
    case(FL[2], s1[5]["message"]["content"][0]["text"],
         anno({"2": "genuine"}, "perf claim held until measured",
              "benchmark numbers precede the changelog word 'faster' — claim gated by number")),
    case(FL[3], s2[1]["message"]["content"][0]["text"],
         anno({"1": "echo"}, "meta-question about the trigger itself",
              "witness spans are the lexicon words being DISCUSSED, not a deploy — textbook echo")),
    case(FL[4], s2[3]["message"]["content"][0]["text"],
         anno({"1": "echo"}, "tuning discussion still lights the deploy lexicon",
              "second meta-turn on the same span — 'deploy' now 2×echo/0×genuine, "
              "anti-trigger threshold reached")),
    case(FL[5], s2[5]["message"]["content"][0]["text"],
         anno({"1": "genuine"}, "'push the button' = ship-gate act with zero lexicon overlap",
              "prompt has no trigger word yet the reply walks the full gate — arrival-miss, "
              "'push the button' is a lexicon-hole candidate"),
         arrival_miss=["1"]),
]
with open(os.path.join(G, "case-book.jsonl"), "w") as fh:
    for c in CB:
        fh.write(json.dumps(c) + "\n")

print(f"demo corpus written: {len(FL)} fire rows, {len(CB)} cases, "
      f"{len(CORES)+1} cores, 2 sessions → {HERE}")
