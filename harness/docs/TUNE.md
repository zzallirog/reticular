# TUNE — final tuning: match situation ↔ mismatch, trace false fires

After bootstrap the harness works, but the lexicon is raw. This cycle turns the fire-log from
a "stream of lines" into a dataset with genealogy and finds two kinds of errors:

- **arrival-miss** (lexicon gap): the core ACTUALLY landed in the reply, but the prompt didn't
  fire it → the prompt phrase = a candidate for a new trigger.
- **echo** (false fire): the span fired the core, but it's a topic-word (talking ABOUT the term),
  not an act → the span = a candidate anti-trigger.

## Cycle (strict order)

```sh
G=~/.claude/glados

# 0. Live with the harness. The fire-log accumulates on its own (ida-attest writes the turn,
#    ida-land tops up acted_on+witness from the reply). Fewer than ~50 substantive turns — too early to tune.

# 1. Backfill old lines (acted_on=null before ida-land was enabled):
python3 tools/backfill_acted.py            # dry-run report
python3 tools/backfill_acted.py --apply

# 2. Log → dataset:
python3 tools/compile_cases.py             # → $G/case-book.jsonl
#    ⚠ overwrites case-book: after a recompile, redo the anno merge (step 4).

# 3. LLM judge (in Claude Code): "run workflow/annotate.workflow.js on $G/case-book.jsonl"
#    → judge gives verdict genuine/echo/partial per (case, core) → the engine writes annos.json.

# 4. Merge verdicts:
python3 tools/annotate_merge.py annos.json --src judge-$(date +%F)

# 5. Tuning candidates (both = report + jsonl, they change NOTHING on their own):
python3 tools/casebook_harvest.py          # arrival-miss × genuine → harvest-candidates.jsonl
python3 tools/casebook_sidecases.py        # echo spans → anti-trigger-candidates.jsonl
                                           # + exemplars.jsonl (judge few-shot bank)

# 5.5 GATEKEEPER — before ANY matrix edit (mandatory step):
python3 tools/rebalance_check.py          # proportions vs snapshot, echo BY CORE,
                                          # disposition leakage into the matrix, hygiene
#    Rule: you cannot tune a number that hasn't been broken down by core classes.
#    High echo on a SITUATION core = a problem; on a disposition = by design, DON'T touch it.
#    Live precedent: "fix the 51%" nearly killed the layer — CASES.md §5.
#    After a deliberate edit: rebalance_check.py --save (new baseline).

# 6. A HUMAN reviews the candidates and edits core-triggers.txt by hand:
#    harvest candidate → add the word/phrase to the core's regex;
#    anti-trigger      → narrow the regex (negative lookahead / remove the word).
#    After editing:
python3 build_embeddings.py --triggers $G/core-triggers.txt --out $G/core_p2p.json
```

From here the cycle repeats over the course of use: steps 2–6 once every week or two.

## Why the judge is mandatory (a number, not taste)

The acted_on oracle is **reply-lex**: the same lexicon scans the model's reply. It is biased by
itself — on the reference vault (651 verdicts) the **echo-rate = 51%**: half the "fires" are
topic-words, not acts. The dominant false mode: meta-conversation about the harness itself fires
its own lexicon. A cheap mechanical flag does NOT separate this out (measured: meta-flag echo 52%
vs 51% — no separation). So:

- any auto-tune on raw acted_on inherits ~50% noise → **filtering by anno.verdicts is
  mandatory** (step 5 takes only genuine / only echo);
- a verdict = semantic work → an LLM judge, not a regex.

## Three cycle safety rules

1. **Don't close the recursion.** The lexicon produced acted_on → acted_on proposes the lexicon.
   Auto-insertion = self-fulfilling noise. Insertion into core-triggers.txt is always triggered by a human.
2. **The source travels with a label.** `acted_src` (reply-lex / reply-lex-backfill / human-label),
   `anno_src` (which judge, when), `voice` (human/paste). Post-hoc analysis must distinguish them;
   human-label is never overwritten by the oracle.
3. **Paste is not a dialect.** A long pasted block (`voice=paste`) is someone else's text;
   lexicon harvest doesn't take it (casebook_harvest already filters it out).

## The third axis (act/read) — fine-tuning after the first few weeks

`dir` in the fire-log = the direction of the prompt (act "do it/put it" vs read "show me/where") from
grammar, not vocabulary. If the casebook shows that core X falsely fires on read-forms
(its triggers = act-verbs), write it into `$G/axis.json`:

```json
{"act_native": ["5", "8"]}
```

— and ida-attest will mute read false-fires of that core. By default the file is empty: first
prove from the dataset that the mute is needed, then enable it.

## Two classes of cores — which goes where (important BEFORE tuning the lexicon)

- **Situation cores** (pull, fire = word): they live in the lex-matrix, and this cycle tunes
  their triggers. Harvest EXPANDS their lexicon — that's fine.
- **Disposition facets** (push, applicable on ≈ every turn): you MUST NOT dispatch them by
  lexicon — similarity will be noisy (they're everywhere), regex will under-catch. Their place is the
  **floor**: mark the core's file `class: disposition` in the frontmatter (or write the path into
  `~/.claude/glados/floor.txt`) — `ida-floor` injects the BODY at session start. Don't harvest
  disposition triggers.
- Symptom of the wrong class: a core fires on almost every substantive turn → it's a disposition,
  remove its line from core-triggers.txt and move it to the floor.

## What counts as success

Not "more fires" (that's recall-by-construction, not a win). Success =
- arrival-miss decreases on new turns (the lexicon caught up to the dialect);
- echo-rate decreases between annotation rounds (the anti-triggers worked);
- surfaced cores confirmed as genuine grow in share.

All three numbers are computed from the case-book — the dataset is itself the measuring instrument.
