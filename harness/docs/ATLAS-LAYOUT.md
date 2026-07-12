# ATLAS-LAYOUT — memory layout for YOUR project topology

The harness (cores + lexicon) catches the moment. But for the agent to have something
to recall and somewhere to look, you need a layout for working memory. The base is **agent-atlas**:

> https://github.com/zzallirog/agent-atlas
> A modular working-memory layout for an agent operating across many repos.
> Plain Markdown, provider-agnostic. Clone it and read the README + docs/ — that's the canon.

Optionally, once you have a lot of notes: https://github.com/zzallirog/memory-atlas —
the whole vault as one self-contained HTML graph (holes and duplicates in the layout become visible).

Here we cover only what atlas doesn't say: how the layout COUPLES to the harness's lexicon matrix.

## Coupling principle: a name must lexically express its direction

The lexicon matrix is regex over words. It works exactly as well as your files,
projects, and feedback notes are **named with the words you use to talk about them**. Rules:

1. **MEMORY.md = index, not content.** One line per note: `- [name](file.md) — hook`.
   The hook is 5-10 words of YOUR dialect (the same words you'd say in a prompt). The index
   loads at startup; note bodies are on-demand.
2. **One note = one fact/project.** Frontmatter: `name` (kebab-slug), `description`
   (used to decide relevance at recall), `type` (user/feedback/project/reference).
3. **Feedbacks represent projects.** Every feedback note answers: on WHICH project
   you got burned, WHY, and HOW to apply it (`**Why:**` / `**How to apply:**`). A feedback with no
   tie to a project is dead weight: the project's lexicon will never surface it.
4. **Direction lives in the name itself.** `feedback_verify_before_push` surfaces on the word
   "push"; `feedback_note_17` never will. Same for projects: `proj_<name-as-you-call-it>`.
5. **`[[name]]` links between notes** are the graph. A broken link means "a note worth writing",
   not an error.

## Layers (bottom to top)

| Layer | File(s) | When in context |
|---|---|---|
| Repo layout | atlas navigators in each repo | on entering the repo |
| Memory index | MEMORY.md | always (session start) |
| Notes | memory/*.md | on-demand (recall/link) |
| Floor (dispositions) | cores with class: disposition + floor.txt | always (SessionStart, ida-floor) |
| Cores (situations) | ~/.claude/overlays/cores/*.md | on lexicon fire (ida-attest) |
| Lexicon matrix | ~/.claude/glados/core-triggers.txt | every prompt (hook) |
| Fire-log/casebook | ~/.claude/glados/*.jsonl | never (this is measurement, not context) |

Cores say "in this kind of situation these failures happen — reread"; notes carry facts;
atlas carries the repo layout. Three different questions — three layers, not one file.

## Order of operations (for existing memory)

1. Clone agent-atlas, read it, place navigators across your repos.
2. Go through your feedback/notes: give each a name/description/type + a tie to a project.
   Anything tied to nothing goes to the archive.
3. Rewrite the MEMORY.md hooks in YOUR words (how you actually call this in prompts).
4. Only then bootstrap the harness: harvest pulls the lexicon from your logs, and the cleaner
   the layout, the cleaner the core emerge.
