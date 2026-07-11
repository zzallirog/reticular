# Cases — what a hook-level attention layer actually catches

Four incidents from live use. Names, paths and domains are retold on the
synthetic demo corpus (`demo/`); the mechanics and the numbers are real.

## 1 · Drift visible on turn one

**The pain that started this repo** — verbatim, from the colleague whose
request produced the portable kit: *"I set a task. If it's looking the wrong
way, I want to see it immediately — not five messages later, with legacy
already built on the oversight."* You set a task; the agent quietly aims at
the wrong thing; unwinding later costs more than the task did.

With the layer on, the scope-guard core fires **on the first turn**: the
trigger words are in the prompt, the ~20-token pointer lands next to the task,
and the model names the box before acting. In the demo: *"fix the typo in the
pricing page header"* → the reply fixes the typo and explicitly declines the
refactor it was tempted by, listing follow-ups instead.

The point is not that the model becomes wise. The point is that the reminder
arrives at the only position the model reliably attends to — **now**.

## 2 · The stale premise, caught by acting (not by reading docs)

The owner's own config asserted a fact about the environment (which shell the
tool runs). The fact was stale. No amount of re-reading the config could catch
it — the config was the *source* of the error.

The action-side hook (`ida-act`) parses tool-calls deterministically. On the
first live day it fired on a command that *worked* — which is exactly what
exposed the premise: the mode's rule and reality disagreed, someone had to be
wrong, and it was the config. Same day, same mechanism, three more bugs in the
hook's own logic surfaced by its own fires — including:

## 3 · Wrong surface: the error-detector that read content

An early version of the loop-breaker mode decided "this call failed" by
scanning the tool *response text* for error-like words. A successful `Read` of
a file that merely *contained* the word "error" counted as a failure — so
every success looked like an error, and the read-set never grew.

The fix is a design rule the repo now holds everywhere: **error is a
structural marker** (`is_error`, response type), never content. The same rule
protects the fires plane: a reply that *talks about* failures is not a failed
turn. Which leads to the big one:

## 4 · Echo: 51% of fires were the lexicon looking at itself

Once replies were scanned with the same lexicon (to record what a core
actually *did*), the dataset said something uncomfortable: across 651 judged
verdicts, **51% of fires were echo** — the trigger word was present as a
*topic* (talking about the harness, quoting a trigger, tuning a regex), not as
an *act* of the discipline.

A cheap mechanical flag could not separate echo from genuine (measured:
meta-talk flag = 52% vs 51%, no lift). So the separation became a layer: an
LLM judge reads each case with its witness spans and rules genuine / echo /
partial. The echo spans then become **anti-trigger candidates** — in the demo,
`deploy` false-fires twice on questions *about the deploy trigger* and never
fires genuinely, so the Fires plane lists it for narrowing.

Two safety rules keep this loop honest:

- the judge's verdicts carry `anno_src` — they are LLM opinions, not ground truth;
- the recursion is never closed: the machine proposes triggers and
  anti-triggers, a human commits them. A lexicon that feeds its own oracle
  converges on noise, 51% of which we have already met.

## 5 · The number that looked like a bug — and the gatekeeper that said no

The 51% had a second life. More than once, an assistant looking at the
dashboard proposed to *fix* it — narrow the triggers, mute the hot cores,
make the number respectable. It sounded like diligence.

It would have killed the layer. Disposition-class facets are **supposed to run
hot** — they apply to nearly every substantive turn; that is what makes them
dispositions. Their echo is not noise in the matrix, it is the reason they
live in the session-start floor instead of the matrix. Tune the lexicon until
the global echo number is pretty, and the layer stops firing exactly where it
was earned.

Had the owner been more trusting, one agreeable "sure, let's clean that up"
would have shipped the damage. That incident is why the tune loop now has a
**gatekeeper**: `tools/rebalance_check.py` runs before any lexicon surgery and
answers with counted numbers — did per-core proportions actually drift beyond
tolerance, is echo high *on a situation core* (a real problem) or on a
disposition (by design), did a disposition leak into the matrix, is the tune
candidate pool judged or raw. The rule it enforces is one sentence:

> **You may not tune a number you haven't decomposed by core class.**

---

# Reflect-side cases

The mirror plane has its own origin incidents — different failure surface,
same instinct: trust the trace, not the claim.

## 6 · "319 sessions" — the number that was narrated

A model was asked to summarize activity over a corpus of session logs. It
reported 319 sessions. The counted number was 139. Nothing malicious — just a
model doing what models do with numbers: producing something *shaped* like the
answer.

That one incident became the architecture of the whole Reflect plane: **no
number ever passes through a model's paraphrase.** Prose may describe the
shape of your work; every figure on screen is counted by a log walk and
carries its provenance. The narrator writes around the numbers, never through
them. If you see a count in reticular, a script counted it.

## 7 · The layer we measured and refused to build

The tempting middle of the stack was a semantic layer: fire facets by
embedding similarity instead of brittle regex. It was measured twice, both
times against a null:

- abstract facet-matching by embeddings: top-1 **0.125** — exactly chance;
- a lexical classifier over prompt text: **44.7%**, *under* the 45.2%
  majority-class baseline (while comfortably above the permutation null —
  above noise, below usefulness).

So the dense middle didn't ship. The rule that survived: don't build the
fragile middle layer unless the layer above measurably misses *and* the middle
measurably beats it. The demo, the hooks and the numbers in this repo all run
on the boring layer that won: your own words, exact-matched, with a judge on
top. A repo that shows you what it declined to build is telling you the same
thing its dashboards do: the claim follows the count.
