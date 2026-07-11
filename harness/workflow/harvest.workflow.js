export const meta = {
  name: 'glados-harvest',
  description: 'Портативный харвест: slim tool-calls → 2 Sonnet-классификатора последовательно → кандидаты ядер+лексики для эмержа движком',
  phases: [
    { title: 'Classify', detail: '2 Sonnet парсят tool-calls последовательно, broad interestingness' },
    { title: 'Pack', detail: 'свести находки в эмерж-пакет для движка' },
  ],
}
// ВХОД (args): { slims: путь к slims.jsonl, fingerprint: путь к fingerprint.json }
// Это «второй воркфлоу-метод»: классификация слим-сессий Sonnet'ом. ТИПЫ харвеста = две ноги:
//   нога-1 (classifier A) = model-cores из tool-call паттернов (структур-pull, выход).
//   нога-2 (classifier B) = ситуация-ядра + нативная лексика из прозы (pull, вход).
// Последовательность (НЕ параллель): B видит находки A → ищет шире, не дублирует.
// Движок эмерджит ПОСЛЕ (не агент) — воркфлоу возвращает кандидатов, синтез у движка.

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
        signature: { type: 'string', description: 'грань поведения, краткая' },
        klass: { type: 'string', enum: ['structural-pull', 'disposition-push'] },
        tool_evidence: { type: 'string', description: 'какой tool-паттерн её выдаёт (verbatim)' },
        gate: { type: 'string', description: 'детектируемое условие на tool_input/response, или "floor"' },
        why: { type: 'string' },
      } } },
    domains: { type: 'array', items: { type: 'string' }, description: 'с чем юзер работает (из fingerprint+слимов)' },
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
        facet: { type: 'string', description: 'грань КАК думает' },
        anchor: { type: 'string', description: 'verbatim фраза юзера-улика' },
        native_words: { type: 'array', items: { type: 'string' } },
      } } },
    lexicon: { type: 'array', items: {
      type: 'object', additionalProperties: false,
      required: ['situation', 'words'],
      properties: { situation: { type: 'string' }, words: { type: 'array', items: { type: 'string' } } } } },
    broader_model_cores: { type: 'array', items: { type: 'string' },
      description: 'что classifier-A пропустил: кросс-сессионные привычки, tool-комбо, distinctive' },
  } }

phase('Classify')

// НОГА-1 — model-cores из выходов (tool-call паттерны)
const A = await agent(
  `Ты классификатор-A портативного harvest. Read ${FP} (tool-частоты — с чем юзер работает) ` +
  `и просканируй ${SLIMS} (slim-сессии: поле tools[] = упорядоченные tool-call'ы name+sum, ` +
  `поле prose[] = его слова). ЗАДАЧА: из ПАТТЕРНОВ tool-call'ов вывести model-cores — грани ` +
  `того, КАК юзер действует. Ищи: повторяющиеся последовательности тулов, где циклит/ретраит/ ` +
  `ошибается, edit-без-read, какие домены (web/code/mcp/...). Класс: structural-pull (видно ` +
  `детерминированно в tool_input/response) vs disposition-push (привычка, в полу). Для каждого ` +
  `дай tool_evidence (verbatim паттерн) и gate (детект-условие). BROAD scope интересности — ` +
  `surface всё заметное, не только ошибки.`,
  { label: 'classify-A:tools', phase: 'Classify', schema: MODELCORE_SCHEMA, model: 'sonnet' })

// НОГА-2 — ситуация-ядра + лексика из прозы; ПОСЛЕДОВАТЕЛЬНО, видит A, идёт ШИРЕ
const B = await agent(
  `Ты классификатор-B. Classifier-A уже нашёл model-cores из tool-call'ов:\n` +
  `${JSON.stringify(A && A.model_cores ? A.model_cores.map(c => c.signature) : [])}\n` +
  `и домены: ${JSON.stringify(A && A.domains || [])}.\n` +
  `Теперь иди ШИРЕ и в ДРУГУЮ сторону: Read ${SLIMS}, парси prose[] (слова юзера). ЗАДАЧА: ` +
  `(1) ситуация-ядра — грани того, КАК юзер ДУМАЕТ (вектор видения, что строит, чего боится, ` +
  `как фреймит), каждое с verbatim-якорем из его прозы; (2) нативная лексика — его повторяющиеся ` +
  `СЛОВА на ситуацию (recall цепляется к ним); (3) broader_model_cores — что A пропустил в ` +
  `tool-паттернах (кросс-сессионные привычки, tool-комбо, distinctive ходы). НЕ дублируй A.`,
  { label: 'classify-B:prose+broader', phase: 'Classify', schema: HARVEST_SCHEMA, model: 'sonnet' })

phase('Pack')
log(`A: ${A?.model_cores?.length || 0} model-cores, ${A?.domains?.length || 0} доменов · ` +
    `B: ${B?.situation_cores?.length || 0} ситуация-ядер, ${B?.lexicon?.length || 0} лексика-групп`)

// Эмерж — НЕ здесь. Движок синтезирует из этого пакета (последнее слово у движка/юзера).
return {
  fingerprint_path: FP,
  classifier_A: A,
  classifier_B: B,
  for_engine: 'эмерджи финальные cores/ + core-triggers.txt + model-cores/ из A+B; дедуп; ' +
              'класс по pull/push; лексика → triggers; затем build_embeddings.py',
}
