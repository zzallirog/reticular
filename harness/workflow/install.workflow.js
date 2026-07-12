export const meta = {
  name: 'glados-install',
  description: 'One-workflow installer: Sonnet parses/reviews logs and finds patterns → Opus full sweep + emerge + lexicon-matrix build → cross-check against the ida counter and shadow fire run',
  phases: [
    { title: 'Overview', detail: 'Sonnet: slims/fingerprint, corpus overview + held-out prompts', model: 'sonnet' },
    { title: 'Patterns', detail: 'Sonnet ×2 sequentially: model-cores from tool-calls, situation + lexicon from prose', model: 'sonnet' },
    { title: 'Build', detail: 'Opus: full sweep, emerge, write emerge.json, bootstrap --finish (lexicon matrix)', model: 'opus' },
    { title: 'Verify', detail: 'shadow run of held-out through the live hook + fire-log counter check + Opus leak audit' },
  ],
}
// INPUT (args): { kit: path to glados-portable (default ~/glados-portable) }
// PRECONDITION: `sh bootstrap.sh` (phase A) already ran — slims.jsonl + fingerprint.json exist.
// MODEL SPLIT (deliberate): parsing/review/classification = Sonnet (mechanical, cheap);
// emerge + lexicon-matrix tuning = Opus MINIMUM (synthesis, core quality = quality of the whole harness);
// cross-check = Sonnet mechanics (numbers from scripts) + Opus audit (semantic leaks).

const KIT   = (args && args.kit) || '~/glados-portable'
const SLIMS = KIT + '/slims.jsonl'
const FP    = KIT + '/fingerprint.json'
const G     = '~/.claude/glados'

// ── schemas ──
const OVERVIEW_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['sessions', 'domains', 'top_tools', 'prose_langs', 'held_out'],
  properties: {
    sessions: { type: 'number' },
    domains: { type: 'array', items: { type: 'string' } },
    top_tools: { type: 'array', items: { type: 'string' } },
    prose_langs: { type: 'array', items: { type: 'string' } },
    held_out: { type: 'array', items: { type: 'string' }, minItems: 8, maxItems: 16,
      description: 'verbatim user prompts from DIFFERENT sessions — reserved for the shadow check, NOT handed to harvest' },
    notes: { type: 'string' },
  } }

const MODELCORE_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['model_cores', 'domains', 'notes'],
  properties: {
    model_cores: { type: 'array', items: {
      type: 'object', additionalProperties: false,
      required: ['signature', 'klass', 'tool_evidence', 'gate', 'why'],
      properties: {
        signature: { type: 'string' },
        klass: { type: 'string', enum: ['structural-pull', 'disposition-push'] },
        tool_evidence: { type: 'string' },
        gate: { type: 'string' },
        why: { type: 'string' },
      } } },
    domains: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  } }

const HARVEST_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['situation_cores', 'lexicon', 'broader_model_cores'],
  properties: {
    situation_cores: { type: 'array', items: {
      type: 'object', additionalProperties: false,
      required: ['facet', 'anchor', 'native_words'],
      properties: {
        facet: { type: 'string' },
        anchor: { type: 'string', description: 'verbatim phrase from the user as evidence' },
        native_words: { type: 'array', items: { type: 'string' } },
      } } },
    lexicon: { type: 'array', items: {
      type: 'object', additionalProperties: false,
      required: ['situation', 'words'],
      properties: { situation: { type: 'string' }, words: { type: 'array', items: { type: 'string' } } } } },
    broader_model_cores: { type: 'array', items: { type: 'string' } },
  } }

const BUILD_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['cores_built', 'trigger_lines', 'dispositions', 'build_ok', 'build_log'],
  properties: {
    cores_built: { type: 'array', items: { type: 'string' }, description: 'names of situation cores' },
    trigger_lines: { type: 'number' },
    dispositions: { type: 'array', items: { type: 'string' }, description: 'facets pushed into the floor (class: disposition)' },
    build_ok: { type: 'boolean' },
    build_log: { type: 'string', description: 'decisive lines of bootstrap --finish output' },
  } }

const SVERKA_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['held_out_n', 'fired_n', 'fire_rate', 'firelog_rows_before', 'firelog_rows_after', 'counter_ok', 'floor_ok', 'per_prompt'],
  properties: {
    held_out_n: { type: 'number' },
    fired_n: { type: 'number' },
    fire_rate: { type: 'number' },
    firelog_rows_before: { type: 'number' },
    firelog_rows_after: { type: 'number' },
    counter_ok: { type: 'boolean', description: 'fire-log grew by exactly the number of prompts run' },
    floor_ok: { type: 'boolean', description: 'ida-floor returns bodies (or there are no dispositions — also ok)' },
    per_prompt: { type: 'array', items: {
      type: 'object', additionalProperties: false,
      required: ['prompt', 'surfaced', 'spans'],
      properties: { prompt: { type: 'string' }, surfaced: { type: 'array', items: { type: 'string' } },
                    spans: { type: 'array', items: { type: 'string' } } } } },
  } }

const AUDIT_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['verdict', 'leaks', 'tune_advice'],
  properties: {
    verdict: { type: 'string', enum: ['ok', 'ok-with-notes', 'rebuild'] },
    leaks: { type: 'array', items: {
      type: 'object', additionalProperties: false,
      required: ['core', 'span', 'why'],
      properties: { core: { type: 'string' }, span: { type: 'string' },
                    why: { type: 'string', description: 'why this is a leak: topic-word/too-broad regex/echo' } } } },
    tune_advice: { type: 'array', items: { type: 'string' }, maxItems: 6 },
  } }

// ═══ PHASE 1: corpus overview (Sonnet — mechanical) ═══
phase('Overview')
const ov = await agent(
  `Read ${FP} (tool frequencies) and scan ${SLIMS} (JSONL: field tools[]=tool-calls, prose[]=user words). ` +
  `Return a corpus overview: sessions (number), domains (what it works with), top_tools, prose_langs (prose languages). ` +
  `REQUIRED held_out: 8-16 verbatim user prompts from DIFFERENT sessions and DIFFERENT topics — substantive ones ` +
  `(not "ok"/"next"), typical of how the user speaks. These are the shadow-check reserve — they will NOT go into harvest.`,
  { label: 'overview:corpus', phase: 'Overview', schema: OVERVIEW_SCHEMA, model: 'sonnet', effort: 'low' })
if (!ov) throw new Error('overview did not assemble — does slims.jsonl exist? was bootstrap phase A run?')
log(`corpus: ${ov.sessions} sessions · domains: ${ov.domains.slice(0,5).join(', ')} · held-out: ${ov.held_out.length}`)

// ═══ PHASE 2: pattern legs (Sonnet ×2, SEQUENTIAL — B sees A, goes broader) ═══
phase('Patterns')
const A = await agent(
  `You are classifier-A. Read ${FP}, scan ${SLIMS} (tools[]=ordered tool-calls). ` +
  `The corpus overview already exists: domains ${JSON.stringify(ov.domains)}. TASK: from tool-call PATTERNS ` +
  `derive model-cores — facets of HOW the user acts: repeated sequences, loops/retries, ` +
  `edit-without-read, distinctive combos. klass: structural-pull (deterministically detectable in tool_input/response) ` +
  `vs disposition-push (habit, into the floor). tool_evidence = verbatim pattern; gate = detection condition. BROAD scope.`,
  { label: 'patterns:A-tools', phase: 'Patterns', schema: MODELCORE_SCHEMA, model: 'sonnet' })
const B = await agent(
  `You are classifier-B. A already found model-cores: ${JSON.stringify((A && A.model_cores || []).map(c => c.signature))}. ` +
  `Go BROADER and in a DIFFERENT direction: Read ${SLIMS}, parse prose[] (user words). ` +
  `⚠ Do NOT touch these prompts (held-out check reserve): ${JSON.stringify(ov.held_out.map(p => p.slice(0, 60)))}. ` +
  `TASK: (1) situation_cores — facets of HOW the user THINKS (what he builds, what he fears, how he frames), ` +
  `each with a verbatim anchor from HIS prose; (2) lexicon — his recurring NATIVE words per situation ` +
  `(recall latches onto them, not onto abstractions); (3) broader_model_cores — what A missed. Do NOT duplicate A.`,
  { label: 'patterns:B-prose', phase: 'Patterns', schema: HARVEST_SCHEMA, model: 'sonnet' })
if (!B) throw new Error('pattern leg B did not return')
log(`A: ${(A && A.model_cores || []).length} model-cores · B: ${B.situation_cores.length} situation cores, ${B.lexicon.length} lexicon groups`)

// ═══ PHASE 3: full sweep + emerge + build (Opus MINIMUM — core quality = harness quality) ═══
phase('Build')
const build = await agent(
  `You are the emerge engine of the glados harness (full sweep). Candidates from the classifiers:\n` +
  `A (model-cores from tool-calls): ${JSON.stringify(A)}\n` +
  `B (situation + lexicon from prose): ${JSON.stringify(B)}\n` +
  `Overview: ${JSON.stringify({sessions: ov.sessions, domains: ov.domains, notes: ov.notes})}\n\n` +
  `STEPS (do them yourself, you have the tools):\n` +
  `1. SWEEP: Read ${SLIMS} yourself — check candidates against the raw material (are anchors verbatim? is the lexicon actually ` +
  `frequent? are facets non-duplicating?). A candidate with no support in the corpus — drop it.\n` +
  `2. EMERGE: synthesize the final set — 5-9 situation cores (id from 1, facet, verbatim anchor, native_words ` +
  `in HIS words), lexicon groups tied to cores, model_cores. A facet applicable to ≈every turn is a ` +
  `DISPOSITION: its place is in the floor, NOT in the lexicon (in emerge do not put its words in triggers; hand the ` +
  `list of such facets in dispositions).\n` +
  `3. Write ${KIT}/emerge.json: {"situation_cores": [...], "model_cores": [...], "lexicon": [...]}.\n` +
  `4. Bash: cd ${KIT} && sh bootstrap.sh --finish (builds cores/, core-triggers.txt = the tuning database ` +
  `of the lexicon matrix, the embed index, the hooks in settings.json).\n` +
  `5. For dispositions (if any) set class: disposition in the frontmatter of their files in ` +
  `~/.claude/overlays/cores/ — ida-floor will pick them up.\n` +
  `6. Return a report: cores_built, trigger_lines (wc -l ${G}/core-triggers.txt), dispositions, build_ok, build_log.`,
  { label: 'build:emerge+matrix', phase: 'Build', schema: BUILD_SCHEMA, model: 'opus', effort: 'high' })
if (!build || !build.build_ok) throw new Error('build failed: ' + JSON.stringify(build && build.build_log))
log(`built: ${build.cores_built.length} cores · ${build.trigger_lines} matrix lines · floor: ${build.dispositions.join(', ') || '—'}`)

// ═══ PHASE 4: CROSS-CHECK — shadow run of held-out through the LIVE hook + ida counter (Sonnet mechanics) ═══
phase('Verify')
const sverka = await agent(
  `Shadow check of the freshly built glados harness. Held-out prompts (harvest never saw them):\n` +
  `${JSON.stringify(ov.held_out)}\n` +
  `STEPS (mechanical, all via Bash):\n` +
  `1. firelog_rows_before = wc -l ${G}/fire-log.jsonl (0 if the file is missing).\n` +
  `2. Run each prompt through the LIVE hook: echo '{"prompt":"...","session_id":"install-verify"}' | ` +
  `python3 ~/.claude/bin/ida-attest — collect per_prompt: surfaced cores from the <ida-attest> output and spans.\n` +
  `3. firelog_rows_after = wc -l again. counter_ok = (after - before == number of prompts run ` +
  `with length ≥3 words) — this is the ida COUNTER check: every substantive turn must leave a row.\n` +
  `4. floor_ok: sh ~/.claude/bin/ida-floor outputs <floor-bodies> with bodies, OR there are no dispositions at all.\n` +
  `5. fire_rate = fired_n/held_out_n (fired = surfaced non-empty). Count the numbers, do not estimate.`,
  { label: 'verify:shadow+counter', phase: 'Verify', schema: SVERKA_SCHEMA, model: 'sonnet' })
if (!sverka) throw new Error('cross-check did not return')
log(`shadow: fire-rate ${(sverka.fire_rate * 100).toFixed(0)}% (${sverka.fired_n}/${sverka.held_out_n}) · counter ${sverka.counter_ok ? 'OK' : 'LEAK'} · floor ${sverka.floor_ok ? 'OK' : 'EMPTY'}`)

// ═══ PHASE 4b: leak audit (Opus — semantic verdict on fires) ═══
const audit = await agent(
  `You are the auditor of the fresh glados harness. Result of the held-out shadow run:\n` +
  `${JSON.stringify(sverka.per_prompt)}\n` +
  `Cores: ${JSON.stringify(build.cores_built)}. Read ~/.claude/overlays/cores/*.md and ${G}/core-triggers.txt.\n` +
  `TASK: find LEAKS — fires where the span = topic-word/too-broad regex (the core lit up, but the prompt ` +
  `is not about that facet), and MISSES — the prompt is clearly about the core's facet, but there is no fire. Typical false mode: ` +
  `a common word in the trigger fires on everything. verdict: ok / ok-with-notes / rebuild (rebuild = ` +
  `the matrix is noisy on >half of held-out). tune_advice: concrete trigger edits (≤6), but do NOT apply ` +
  `them — editing the lexicon is the owner's decision (docs/TUNE.md).`,
  { label: 'verify:audit-leaks', phase: 'Verify', schema: AUDIT_SCHEMA, model: 'opus' })

return {
  overview: { sessions: ov.sessions, domains: ov.domains },
  build,
  sverka: { fire_rate: sverka.fire_rate, counter_ok: sverka.counter_ok, floor_ok: sverka.floor_ok },
  audit,
  for_engine: 'Report to the owner: which cores were built (let them strike out anything that is not theirs), fire-rate on held-out, ' +
              'the leaks found (anti-trigger candidates — into the dataset, not into panic), the audit verdict. ' +
              'Restart Claude Code to load the hooks. Then live with it for 1-2 weeks → docs/TUNE.md.',
}
