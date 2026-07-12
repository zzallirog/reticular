# INSTALL-AGENT — brief for the installer agent (Claude/Opus, read this first)

You're installing this kit for a person who did NOT write it. Your job: install it,
verify it works with a number, bring the owner up to speed. Nothing more.

## What this is (one paragraph — retell it to the owner in your own words)

An active harness on top of Claude Code. From HIS logs, "cores" emerge — facets of how he
thinks and acts, each with a native trigger lexicon. A hook on every prompt (~50 tokens of
injection) fires the relevant cores: "this situation — here are the known failure modes,
recheck". This solves lost-in-the-middle (a reminder in the moment, not at the start of
context) and catches "the agent is looking the wrong way" on the FIRST turn, not five
messages of legacy later. A second loop (fire-log → casebook → judge) traces false fires
and tunes the lexicon.

## Install order

1. **Read it yourself:** README.md → docs/ATLAS-LAYOUT.md → docs/TUNE.md. Don't install blind.
2. **Layout before the harness.** If the owner's memory/projects aren't laid out — do
   ATLAS-LAYOUT.md first (clone agent-atlas, ordering in MEMORY.md and feedbacks). Harvest pulls
   the lexicon from the logs; a junk layout = junk cores.
3. **Phase A:** `sh bootstrap.sh` — deps, slim-extract of his logs, profile. Check the output:
   slims.jsonl is non-empty (otherwise there aren't enough logs — say honestly that the harness
   has nothing to build from; a common-sense threshold is ~20 sessions).
4. **Installer workflow (preferred path):** run `workflow/install.workflow.js`.
   It holds the model proportions itself: Sonnet = corpus overview + pattern legs (mechanics),
   Opus = full sweep + emerge + lexicon-matrix build (bootstrap --finish inside), then
   verify: a shadow-run of held-out prompts through the LIVE hook + ida-counter (did the fire-log
   grow by exactly N?) + Opus leak audit. Return a report to the owner: cores (let him strike out
   what isn't his), fire-rate, leaks. Fallback without the Workflow tool: `workflow/harvest.workflow.js`
   by hand → emerge.json yourself → `sh bootstrap.sh --finish` → the check below.
5. **Restart Claude Code** (hooks load at start).

## Verifying it works (a number, not a vibe)

- Tell the owner to write 3-5 prompts in his usual words on a live topic →
  an `<ida-attest>` block with cores should appear in the context. No fire on an explicit
  trigger word → check `~/.claude/glados/core-triggers.txt` (did the regex assemble?).
- `tail -3 ~/.claude/glados/fire-log.jsonl` — lines are being written, the surfaced/lex/dir/voice
  fields are filled, acted_on is set after the reply (ida-land).
- An edit to a file without a Read → an M1 note from ida-act.
- If ollama isn't present — the dense leg stays silent, this is a DOCUMENTED mode, not a breakage
  (the lexicon leg carries ~95% of the work).

## Bringing them up to speed (5 minutes for the owner)

- Cores are HIS facets, not universal rules. The files in `~/.claude/overlays/cores/` are
  read and edited by hand, it's live text.
- The first 1-2 weeks the harness is raw: the lexicon under-catches and over-fires. That's normal —
  the tune loop (docs/TUNE.md) exists for exactly that. Earlier than ~50 substantive turns there's
  nothing to tune from.
- A false fire isn't "turn the harness off" — it's a line for the dataset: it becomes an
  anti-trigger at the tune step.
- Lexicon edits — always by the owner's hand (auto-tune recursion converges on noise).

## What NOT to do

- Do NOT copy cores/lexicon from someone else's vault (including from the examples) — they are the
  facets of one specific person; on a different person it's noise.
- Do NOT enable ida-act's deny mode at start (advisory until the first weeks of act-log).
- Do NOT edit core-triggers.txt yourself without showing the owner.
- Do NOT promise magic: if the self-test gives an honest zero — report it as such.
