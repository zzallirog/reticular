# Cases — what a hook-level attention layer actually catches

Four incidents from live use. Names, paths and domains are retold on the
synthetic demo corpus (`demo/`); the mechanics and the numbers are real.

## 1 · Drift visible on turn one

**The pain that started this repo.** You set a task; the agent quietly aims at
the wrong thing; you find out five messages later, after code has been built
on the misread — now it's legacy, and unwinding costs more than the task did.

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
