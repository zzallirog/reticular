# glados-portable v2 — an active harness built from YOUR OWN logs + a false-fire tune loop

This is not "someone else's cores". Cores can't be copied — they are the facets of one
specific person. This is a **method that builds YOUR cores from YOUR Claude Code logs**,
and — new in v2 — a **loop that traces false fires and tunes the lexicon against a dataset**,
not against taste.

**If a kit installs the agent (Claude/Opus): start with `docs/INSTALL-AGENT.md`.**

It reads `~/.claude/projects/*/*.jsonl` and assembles:

1. **Situation cores** — facets of HOW you think, from your prose (prompts).
2. **Lexicon** — your native trigger words (recall latches onto them, not onto abstraction).
3. **model-cores** — facets of HOW the agent acts, from **tool-calls** (where it loops,
   where it stumbles). The source is outputs, not introspection.
4. **Embedding index** — so recall numbers **reproduce on your own vault**.
5. **Four hooks:**
   - `ida-floor` (SessionStart) — injects the BODIES of the disposition facets at start
     (the floor: what applies every turn, not dispatched by lexicon — it is simply present);
   - `ida-attest` (UserPromptSubmit) — fires situation cores off the prompt: lexicon leg +
     dense backstop, the third act/read axis, witness spans, fire-log;
   - `ida-act` (Pre/PostToolUse) — parses the agent's calls, catches mode errors
     deterministically (edit-without-read, remote-shell, error-loop, write-to-substrate);
   - `ida-land` (Stop) — appends to the fire-log WHAT actually landed in the reply
     (acted_on + witness).
6. **Casebook loop** (`tools/` + `workflow/annotate.workflow.js`) — fire-log → dataset →
   LLM judge → candidate triggers and ANTI-triggers. Final tune: `docs/TUNE.md`.

## Idea (one line)

What matters can't be detected with cheap semantics at query-time. **A blind/external
detector reads the BODY at the boundary.** The input (prose) is irregular → you need your
lexicon. The output (tool-call) is regular → a deterministic parser is precise. And false
lexicon fires aren't fixed by mechanics — an LLM judges them against a dataset with witnesses
(witness spans), and a human always makes the edit.

## One pass

```sh
sh bootstrap.sh          # phase A: deps + slim-extract + profile
# → in Claude Code: "run workflow/install.workflow.js"
#   (Sonnet: overview + patterns → Opus: sweep + emerge + matrix build → verify: shadow-fires + ida-counter)
# restart Claude Code
```

Manual fallback (no Workflow tool): `harvest.workflow.js` → emerge.json → `sh bootstrap.sh --finish`.

After 1-2 weeks of live use — the final tune: `docs/TUNE.md`.

## Files

- `docs/INSTALL-AGENT.md` — brief for the installer agent: order, checks, bringing the owner up to speed.
- `docs/ATLAS-LAYOUT.md` — memory/projects/feedbacks layout under the lexicon matrix
  (basis: https://github.com/zzallirog/agent-atlas — clone it, this is the canonical layout).
- `docs/TUNE.md` — the false-fire tracing loop (arrival-miss / echo / anti-triggers).
- `bootstrap.sh` — one pass, ties it all together (idempotent, POSIX sh).
- `slim_extract.py` — `~/.claude/projects/*/*.jsonl` → slim tool-call + prose transcripts.
- `workflow/install.workflow.js` — installer in a single workflow: overview → patterns (Sonnet) →
  sweep + emerge + build (Opus) → verify (shadow-fires + ida-counter + leak audit).
- `workflow/harvest.workflow.js` — 2 classifiers in sequence (manual fallback).
- `workflow/annotate.workflow.js` — fan-out of LLM judges: verdict genuine/echo/partial per (case, core).
- `build_cores.py` — emerge → `cores/` + `core-triggers.txt` + `model-cores/`.
- `build_embeddings.py` — native chunks → `core_p2p.json` (recall, reproducible).
- `hooks/ida-floor`, `hooks/ida-attest`, `hooks/ida-act`, `hooks/ida-land` — ported,
  no machine-specifics.
- `tools/backfill_acted.py` · `tools/compile_cases.py` · `tools/annotate_merge.py` ·
  `tools/casebook_harvest.py` · `tools/casebook_sidecases.py` — the casebook chain (see TUNE.md).

## "The numbers reproduce"

The method is falsifiable: on your vault recall@k is printed by a self-test; echo-rate and
arrival-miss are counted from the case-book. If there's signal — harvest lifts fire-rate above
null, tune lowers echo between rounds. If there isn't — an honest zero, not a vibe. That is the
transfer: not the magnitude of someone else's vault, but **a method that yields a number on yours**.

## Boundaries (what the kit promises and what it doesn't)

- The method author's reference numbers (152 sessions): lexical recall 7/7 on held-out;
  echo-rate of the raw reply-lex oracle = 51% → which is why the judge and the genuine filter
  are mandatory.
- The lexicon leg carries ~95% of the work; without ollama the dense leg stays silent — that's
  a mode, not a breakage.
- Auto-tuning the lexicon is deliberately NOT closed: candidates are the machine's, the edit is the human's.
