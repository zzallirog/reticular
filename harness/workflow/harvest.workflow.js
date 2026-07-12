export const meta = {
  name: 'glados-harvest',
  description: 'Portable harvest: slim tool-calls → 2 Sonnet classifiers in sequence → core + lexicon candidates for the engine to emerge',
  phases: [
    { title: 'Classify', detail: '2 Sonnets parse tool-calls in sequence, broad interestingness' },
    { title: 'Pack', detail: 'fold findings into an emerge package for the engine' },
  ],
}
// INPUT (args): { slims: path to slims.jsonl, fingerprint: path to fingerprint.json }
// This is the "second workflow method": classifying slim sessions with Sonnet. Harvest TYPES = two legs:
//   leg-1 (classifier A) = model-cores from tool-call patterns (structural-pull, output).
//   leg-2 (classifier B) = situation cores + native lexicon from prose (pull, input).
// Sequence (NOT parallel): B sees A's findings → searches wider, doesn't duplicate.
// The engine emerges AFTER (not the agent) — the workflow returns candidates, synthesis is the engine's.

const SLIMS = (args && args.slims) || '~/glados-portable/slims.jsonl'
const FP    = (args && args.fingerprint) || '~/glados-portable/fingerprint.json'

const MODELCORE_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['model_cores', 'domains', 'notes'],
  properties: {
    model_cores: { type: 'array', items: {
      type: 'object', additionalProperties: false,
      required: ['signature', 'klass', 'tool_evidence', 'gate', 'why'],
      properties: {
        signature: { type: 'string', description: 'facet of behavior, brief' },
        klass: { type: 'string', enum: ['structural-pull', 'disposition-push'] },
        tool_evidence: { type: 'string', description: 'which tool-pattern reveals it (verbatim)' },
        gate: { type: 'string', description: 'detectable condition on tool_input/response, or "floor"' },
        why: { type: 'string' },
      } } },
    domains: { type: 'array', items: { type: 'string' }, description: 'what the user works with (from fingerprint + slims)' },
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
        facet: { type: 'string', description: 'facet of HOW they think' },
        anchor: { type: 'string', description: 'verbatim user phrase as evidence' },
        native_words: { type: 'array', items: { type: 'string' } },
      } } },
    lexicon: { type: 'array', items: {
      type: 'object', additionalProperties: false,
      required: ['situation', 'words'],
      properties: { situation: { type: 'string' }, words: { type: 'array', items: { type: 'string' } } } } },
    broader_model_cores: { type: 'array', items: { type: 'string' },
      description: 'what classifier-A missed: cross-session habits, tool combos, distinctive moves' },
  } }

phase('Classify')

// LEG-1 — model-cores from outputs (tool-call patterns)
const A = await agent(
  `You are classifier-A of the portable harvest. Read ${FP} (tool frequencies — what the user works with) ` +
  `and scan ${SLIMS} (slim sessions: field tools[] = ordered tool-calls name+sum, ` +
  `field prose[] = their words). TASK: from tool-call PATTERNS, derive model-cores — facets of ` +
  `HOW the user acts. Look for: recurring tool sequences, where they loop/retry/ ` +
  `err, edit-without-read, which domains (web/code/mcp/...). Class: structural-pull (visible ` +
  `deterministically in tool_input/response) vs disposition-push (habit, in the floor). For each ` +
  `give tool_evidence (verbatim pattern) and gate (detection condition). BROAD interestingness scope — ` +
  `surface everything notable, not just errors.`,
  { label: 'classify-A:tools', phase: 'Classify', schema: MODELCORE_SCHEMA, model: 'sonnet' })

// LEG-2 — situation cores + lexicon from prose; SEQUENTIAL, sees A, goes WIDER
const B = await agent(
  `You are classifier-B. Classifier-A already found model-cores from tool-calls:\n` +
  `${JSON.stringify(A && A.model_cores ? A.model_cores.map(c => c.signature) : [])}\n` +
  `and domains: ${JSON.stringify(A && A.domains || [])}.\n` +
  `Now go WIDER and in a DIFFERENT direction: Read ${SLIMS}, parse prose[] (the user's words). TASK: ` +
  `(1) situation cores — facets of HOW the user THINKS (vision vector, what they build, what they fear, ` +
  `how they frame), each with a verbatim anchor from their prose; (2) native lexicon — their recurring ` +
  `WORDS for a situation (recall latches onto them); (3) broader_model_cores — what A missed in ` +
  `tool-patterns (cross-session habits, tool combos, distinctive moves). Do NOT duplicate A.`,
  { label: 'classify-B:prose+broader', phase: 'Classify', schema: HARVEST_SCHEMA, model: 'sonnet' })

phase('Pack')
log(`A: ${A?.model_cores?.length || 0} model-cores, ${A?.domains?.length || 0} domains · ` +
    `B: ${B?.situation_cores?.length || 0} situation cores, ${B?.lexicon?.length || 0} lexicon groups`)

// Emerge — NOT here. The engine synthesizes from this package (final say is the engine's/user's).
return {
  fingerprint_path: FP,
  classifier_A: A,
  classifier_B: B,
  for_engine: 'emerge the final cores/ + core-triggers.txt + model-cores/ from A+B; dedup; ' +
              'class by pull/push; lexicon → triggers; then build_embeddings.py',
}
