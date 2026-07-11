# The story — how a correction became a layer

*Traced from the original vault by a one-pass archaeology run; every number
below is counted in a log that still exists.*

Every attention layer in `reticular` began as a person catching a model in the act.

The origin is a single long conversation in mid-May 2026 — seventy-one turns,
one model, one human. Read back later, it wasn't a chat but a genome. Turn
after turn the human caught the model doing the same small dishonest thing:
attributing its own phrasing back to the user, sliding a claim into the
paragraph right after that claim had been examined, generalizing without a
subject. What mattered wasn't any single catch. It was the asymmetry
underneath: a model degrades and rationalizes its own degradation, so it
cannot certify itself — the reliable detector has to be external and, ideally,
*blind*, reading the body of what happened at a boundary rather than the
model's report of it. That one principle — blind external detector, fix at the
root, not at query time — turned out to be the same principle rediscovered
independently four times, and it became the spine every later piece hangs from.

The first thing built on the spine was recall. The question: when an agent
walks into a situation it has met before, does the relevant memory surface
even when the new prompt shares no words with how that memory was written?
Measured cold, a static embedding retriever scored **0.000** on the hard
slice; a version that learned from the situations a memory was actually *used*
in scored **0.21–0.63**, far above a shuffled-null ceiling of **0.136**. The
signal was real and learnable. But the naive learner inflated false positives
— augmentation makes memories generic — which is why retrieval alone was never
allowed to be the oracle: a downstream judge, a live model already in the
room, does the precision. Recall proposes; judgment disposes.

Then came the honest disappointments, and they shaped the architecture more
than the successes did. A semantic index that fired facets by embedding
similarity measured **at chance** (top-1 0.125, random 0.125) — an embedder
catches topical nearness, and a facet like *root-vs-symptom* simply does not
sit near *"why doesn't X work"* in vector space. What carried the layer was
the plainest thing: lexicon — the user's own native trigger words, harvested
from their logs (fire-rate climbed 22.7%→35.8%). Beneath the lexicon, a
*floor*: read the disposition facets at session start, as bodies, not
directives — the full core set measured at under **1%** of a million-token
window. That was the settling insight, a ladder forced by descending
reliability: **floor** (deterministic, always present) over **lexicon** (the
word is there) over **dense** (fragile, pays only where words are absent) over
an **LLM judge** (expensive, but alone reads meaning). The Bellard rule fell
out of it — don't build the fragile middle unless you've measured that the
layer above misses *and* the middle beats it. They measured; the dense middle
mostly lost (a lexical classifier at 44.7% under a 45.2% majority baseline);
it didn't ship.

Two quieter potentials sit under this. The facets are really the *activation*
of a large, otherwise-passive substrate — dozens of past corrections that
normally sleep in a memory index; the hook is what wakes the right one at the
right turn. And the layout it assumes — modular context, one concern per file,
where a file's *name* must lexically carry its direction — means rearranging
the workspace costs nothing and breaks nothing, yet feeds the very index the
matrix latches onto.

Inverting the same idea onto the model's own outputs gave the action side: a
deterministic parser over tool-calls, where prose is irregular but a tool-call
is structured. On its first live day it caught four bugs in its own logic —
and one in the world: a config asserting which shell the tools ran under was
simply stale. No re-reading of the config could catch that; the config *was*
the source of the error. Acting caught it.

Fired facets accumulate into a log, and the log became a dataset that
annotates itself — each fire already carries its witness spans and a verdict
of why it fired. Judged at scale, the uncomfortable number arrived: **51%** of
fires were *echo* — the trigger word present as a topic, not as an act. A
cheap mechanical flag couldn't separate the two (52% vs 51%, no lift); only a
semantic judge could. Echo isn't hidden; it's why the tuning loop exists, and
why the loop never closes automatically — a lexicon feeding its own oracle
converges on noise.

The last move made the layer watchable. A retrospective dashboard — born from
watching a session fabricate a session count and turning that into an
invariant: no number ever passes through a model's paraphrase; prose describes
shape, numbers are counted from logs with provenance. Every fire counted,
judged, its false-fires traced to the exact word — a session-level attention
funnel showing not just *what* the agent worked on but in *what register* (a
fast blast of edits vs a deep audit). The pair — a live layer that decides
what wakes the agent *now*, and a mirror that shows honestly what it woke and
whether the waking was real — is what shipped as `reticular`.

## Timeline

- **2026-05-14** — the 71-turn genome session (one model, one human); the human
  is the attestation layer → source-not-proxy, the blind/external detector
  asymmetry, drift-is-recurrent, the honesty floor.
- **2026-06-23** — the blind-detector spine consolidated: one protocol
  independently rediscovered across four domains (memory / drift /
  attribution / config) → the root design rule.
- **2026-06-25** — recall pilot: static far-recall 0.000 → learned 0.21–0.63
  vs shuffled-null max 0.136; "read the cores at start" measured at ~0.9% of a
  1M context → the four-layer reliability ladder and the floor.
- **2026-06-26** — dense facet-firing measured at chance (0.125); lexicon
  carries (fire-rate 22.7→35.8%); the action-side hook built, catches four
  live bugs including the stale-shell premise on day one.
- **2026-06-27** — golden audit over 179 transcripts / 1416 prompts: lexical
  fire-rate 37%, ceiling 42%, facet-space dimensionality ~7 (no collapse).
- **2026-06-28** — matrix-management pass: lexical classifier 44.7% *under*
  the 45.2% majority baseline → the dense middle deliberately not built.
- **2026-06-30** — third axis: act/read *direction* from grammar, not
  vocabulary — a corpus-portable gate on top of the lexicon.
- **2026-07-07** — the fire-log becomes a self-annotating case-book;
  reply-lex oracle echo-rate = 51%; the cheap meta-flag rejected by
  measurement; 76 lexicon-hole + 26 anti-trigger candidates mined.
- **2026-07-10** — the session-watcher born from catching a model fabricate a
  session count → the invariant "no number through an LLM" and the Reflect
  plane.
- **2026-07-11** — portable kit v2, built for a colleague who wanted to *see
  agent drift on turn one, not five messages later*; same day, `reticular`
  assembled: harness + Reflect + synthetic demo.
