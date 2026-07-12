export const meta = {
  name: 'glados-annotate',
  description: 'LLM judge for the casebook: verdict genuine/echo/partial per (case, core) — tracing false lexicon fires',
  phases: [
    { title: 'Judge', detail: 'fan-out of judges over case-book batches' },
  ],
}
// INPUT (args): { casebook: path to case-book.jsonl, cores_dir: path to overlays/cores, batch?: 16 }
// OUTPUT: { annos: [...] } — the engine writes annos.json and runs tools/annotate_merge.py.
//
// WHY a judge, not a mechanism: echo (topic-word, not act) is NOT separable with cheap lexicon —
// measured on 651 verdicts (meta-flag rejected: echo 52% vs 51%). A semantic verdict is
// LLM work. Judge, not human-label — anno_src travels alongside, distinguish post-hoc.

const CB    = (args && args.casebook)  || '~/.claude/glados/case-book.jsonl'
const CORES = (args && args.cores_dir) || '~/.claude/overlays/cores'
const BATCH = (args && args.batch) || 16

const ANNO_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['annos'],
  properties: {
    annos: { type: 'array', items: {
      type: 'object', additionalProperties: false,
      required: ['id', 'verdicts', 'case', 'reflection'],
      properties: {
        id: { type: 'string' },
        verdicts: { type: 'object', additionalProperties: { type: 'string', enum: ['genuine', 'echo', 'partial'] },
                    description: 'per-core: genuine=core ACTUALLY acted in the response; echo=topic-word/lexicon echo, no act; partial=partially' },
        case: { type: 'string', description: 'one sentence: what the move was' },
        reflection: { type: 'string', description: 'why this verdict — how the witness spans serve/do not serve the act' },
        drop: { type: 'boolean', description: 'junk case (fragment/meta-test), discard' },
      } } },
  } }

// batches are cut by the ENGINE before the run (or by the workflow itself — the case count is
// not known ahead of time, so one scout agent counts and returns the id slices)
phase('Judge')

const plan = await agent(
  `Read ${CB} (JSONL). Return ONLY JSON: {"total": N, "ids": [all ids in order]}. Do not judge anything.`,
  { label: 'scout:count', phase: 'Judge',
    schema: { type: 'object', additionalProperties: false, required: ['total', 'ids'],
              properties: { total: { type: 'number' }, ids: { type: 'array', items: { type: 'string' } } } } })

const ids = (plan && plan.ids) || []
const slices = []
for (let i = 0; i < ids.length; i += BATCH) slices.push(ids.slice(i, i + BATCH))
log(`cases: ${ids.length}, batches: ${slices.length} × ${BATCH}`)

const results = await parallel(slices.map((slice, bi) => () =>
  agent(
    `You are a casebook judge (batch ${bi + 1}/${slices.length}). First Read ${CORES}/*.md — understand ` +
    `WHAT each core means (these are facets of the owner's thinking, a core = a discipline/lens). ` +
    `Then Read ${CB} and take ONLY the cases whose id is in the list:\n${JSON.stringify(slice)}\n` +
    `For EACH case, for EACH core in acted_on give a verdict:\n` +
    `- genuine: the response ACTUALLY executed the core's discipline (an act, not words);\n` +
    `- echo: witness spans = topic-word (talk ABOUT the mechanism/term, a quote, a test phrase) — no act;\n` +
    `- partial: the discipline was touched but not executed.\n` +
    `Look at witness (the spans that fired the lexicon in the response) and wit_prompt — they are the evidence. ` +
    `Typical false mode: meta-talk about the harness itself fires its own lexicon. ` +
    `reflection: why this verdict, briefly. drop=true for junk cases.`,
    { label: `judge:batch${bi + 1}`, phase: 'Judge', schema: ANNO_SCHEMA })
))

const annos = results.filter(Boolean).flatMap(r => r.annos || [])
log(`verdicts collected: ${annos.length}/${ids.length}`)

return {
  annos,
  for_engine: 'write {"annos": [...]} to annos.json and run: ' +
              'python3 tools/annotate_merge.py annos.json --src judge-<date>; ' +
              'then tools/casebook_harvest.py + tools/casebook_sidecases.py (tuning candidates)',
}
