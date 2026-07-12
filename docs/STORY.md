# The story — from cores to an attention layer

*The interesting problem was never catching the model. It was what to do once
you had caught it a hundred times. Every number below is counted in a log that
still exists.*

Start with the boring part, because it's the part everyone sees first. Models
drift. A model will hand your own phrasing back to you as if you'd agreed to
it, or slip a claim into the paragraph right after you questioned it, or
generalize with no subject. Push on it and it agrees the drift was fine all
along. That last move is the real constraint: a system that degrades *and*
rates its own degradation as fine cannot be its own detector. The detector has
to sit outside the model and read what actually happened at a boundary — not
the model's account of it. Simple, recurrent, old.

The interesting part is what you build from that. Each recurring catch has a
shape. Write the shape down once, in one file: *here is how I think about this
kind of situation, and here is how it usually goes wrong.* Call it a core. The
first core is just a note. By the tenth, the question has flipped — no longer
"how do I catch the model," but "what belongs in the set of cores at all,"
which dispositions, anchored to which evidence. The tool stopped being a
detector. It became something you fill.

Then the real problem, the one the repo is named after. Suppose you have many
cores — dozens, one per way you work. You can't load all of them every turn.
Inject everything at the start and you get a floor of noise, and the model
reads the middle of a long context worst of all. Many cores only help if the
*right* one shows up at the *right* turn. Choosing which of many standing
signals should wake attention *now* is exactly what the reticular activating
system does in the brainstem: the filter that decides which signals reach the
cortex. `reticular` is that filter, for an agent. The point isn't any single
core. It's that a large set of them stays usable, because only the relevant
one is ever awake.

Which core fires, and how, splits in two — and the split was measured, not
guessed. Some cores are *situations*: picking a stack, debugging, a step that
goes public. A word in the prompt is a fair signal, so a lexicon of your own
trigger words fires them. The reminder lands on the turn, carried by recency —
the one position an LLM reliably reads. Other cores are *dispositions*: check
the geometry of a number, don't hand your phrasing back, watch for drift.
These apply to almost every real turn. A trigger word would fire them on
everything, which is the same as firing them on nothing. So they aren't
matched at all. They're loaded whole at session start, as text to read, and
the full set costs under 1% of a modern context window.

Underneath runs a short ladder, each rung earning its place by measurement:
**floor** (always there, deterministic), **lexicon** (the word is present or
it isn't), a **dense** embedding backstop (fragile — it pays only where the
words are missing), and an **LLM judge** (expensive, the only rung that reads
meaning). The dense middle was actually built and measured: 44.7%, under a
45.2% baseline. It lost, so it was cut. The ladder is short on purpose.

Two more parts turn it from a trick into a system.

First, the same idea runs on the model's *own* output. Prose is messy, but a
tool-call is structured — so a parser reads the calls and flags edit-before-read,
error loops, and writes to memory it shouldn't touch. On day one it caught
four bugs in its own logic, and one in the world: a config that named the
wrong shell, gone stale. Re-reading the config couldn't catch that. The config
*was* the error. Acting on it did.

Second, every fire is logged, and the log grades itself. The uncomfortable
result: **51% of fires were echo** — the trigger word showing up as a topic,
not as an act. That number isn't a bug to hide; it's why the tuning loop
exists, and why the loop never closes on its own. The full account is in
[CASES.md](CASES.md); the short version is that a lexicon reading its own
replies is biased by its own words, and only a judge can tell topic from act.

The last part makes it watchable. A retrospective plane — sessions and fires —
on one rule: no number ever passes through a model's paraphrase. Prose
describes shape; every figure is counted from the log, with provenance. It
shows what the agent worked on and in what register — a fast run of edits
reads nothing like a deep audit — and answers one honest question per session:
was the waking real?

Honest scope, said plainly because this oversells easily: one corpus, the
author's, n=1, twelve days. The judge is itself an LLM. The matrix is
subjective by construction — it encodes how one person frames things, and the
same word can mean different things in another vault. The method is the claim,
not the magnitudes. Point the installer at your own logs; it emerges your
facets, builds your lexicon, and prints your held-out numbers. If the signal
isn't there, it prints an honest zero.

## Timeline — milestone by milestone, every number counted

- **2026-06-25** — recall pilot: a static embedding retriever scored **0.000**
  on the hard slice; a version that learned from where a memory was actually
  *used* scored **0.21–0.63** against a shuffled-null ceiling of **0.136**. The
  session-start floor measured at ~0.9% of a 1M context → the reliability
  ladder.
- **2026-06-26** — dense facet-firing measured at chance (top-1 0.125 =
  random); the lexicon carries (fire-rate 22.7%→35.8%); the action-side hook
  catches four live bugs, including the stale-shell premise, on day one.
- **2026-06-27** — golden audit over 179 transcripts / 1416 prompts: lexical
  fire-rate 37%, ceiling 42%, facet space ~7 dimensions, no collapse — the
  cores are not redundant.
- **2026-06-28** — the dense middle measured *under* its majority baseline
  (44.7% vs 45.2%) → deliberately not built.
- **2026-06-30** — a direction axis: act vs read from grammar, not vocabulary
  — a gate that ports across corpora, on top of the lexicon.
- **2026-07-07** — the fire-log becomes a self-annotating case-book; judged
  echo-rate = 51%; the cheap meta-flag rejected by measurement; 76
  lexicon-hole and 26 anti-trigger candidates mined from the same log.
- **2026-07-10** — the retrospective plane, born from catching a model
  fabricate a session count → the invariant "no number through an LLM."
- **2026-07-11** — packaged to install from anyone's logs; `reticular`
  assembled: harness + Reflect + synthetic demo.
