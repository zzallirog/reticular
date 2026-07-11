export const meta = {
  name: 'glados-install',
  description: 'Инсталлятор одним воркфлоу: Sonnet парсит/обозревает логи и ищет паттерны → Opus полный свип + эмерж + сборка лекс-матрицы → сверка с ida-счётчиком и shadow-прогон фиров',
  phases: [
    { title: 'Overview', detail: 'Sonnet: слимы/fingerprint, корпус-обзор + held-out промпты', model: 'sonnet' },
    { title: 'Patterns', detail: 'Sonnet ×2 последовательно: model-cores из tool-call, ситуация+лексика из прозы', model: 'sonnet' },
    { title: 'Build', detail: 'Opus: полный свип, эмерж, запись emerge.json, bootstrap --finish (лекс-матрица)', model: 'opus' },
    { title: 'Verify', detail: 'shadow-прогон held-out через живой хук + сверка fire-log счётчика + Opus-аудит течей' },
  ],
}
// ВХОД (args): { kit: путь к glados-portable (default ~/glados-portable) }
// ПРЕДУСЛОВИЕ: `sh bootstrap.sh` (фаза A) уже прогнана — slims.jsonl + fingerprint.json есть.
// ПРОПОРЦИИ МОДЕЛЕЙ (осознанно): парсинг/обзор/классификация = Sonnet (механика, дёшево);
// эмерж + тюн лекс-матрицы = Opus МИНИМУМ (синтез, качество ядер = качество всего харнеса);
// сверка = Sonnet-механика (числа из скриптов) + Opus-аудит (semantic-течи).

const KIT   = (args && args.kit) || '~/glados-portable'
const SLIMS = KIT + '/slims.jsonl'
const FP    = KIT + '/fingerprint.json'
const G     = '~/.claude/glados'

// ── схемы ──
const OVERVIEW_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['sessions', 'domains', 'top_tools', 'prose_langs', 'held_out'],
  properties: {
    sessions: { type: 'number' },
    domains: { type: 'array', items: { type: 'string' } },
    top_tools: { type: 'array', items: { type: 'string' } },
    prose_langs: { type: 'array', items: { type: 'string' } },
    held_out: { type: 'array', items: { type: 'string' }, minItems: 8, maxItems: 16,
      description: 'verbatim промпты юзера из РАЗНЫХ сессий — резерв для shadow-сверки, в харвест НЕ отдаются' },
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
        anchor: { type: 'string', description: 'verbatim фраза юзера-улика' },
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
    cores_built: { type: 'array', items: { type: 'string' }, description: 'имена ситуация-ядер' },
    trigger_lines: { type: 'number' },
    dispositions: { type: 'array', items: { type: 'string' }, description: 'грани, ушедшие в пол (class: disposition)' },
    build_ok: { type: 'boolean' },
    build_log: { type: 'string', description: 'решающие строки вывода bootstrap --finish' },
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
    counter_ok: { type: 'boolean', description: 'fire-log вырос ровно на число прогнанных промптов' },
    floor_ok: { type: 'boolean', description: 'ida-floor отдаёт тела (или диспозиций нет — тоже ok)' },
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
                    why: { type: 'string', description: 'почему это течь: слово-тема/слишком широкий regex/эхо' } } } },
    tune_advice: { type: 'array', items: { type: 'string' }, maxItems: 6 },
  } }

// ═══ ФАЗА 1: обзор корпуса (Sonnet — механика) ═══
phase('Overview')
const ov = await agent(
  `Read ${FP} (частоты тулов) и просканируй ${SLIMS} (JSONL: поле tools[]=tool-call'ы, prose[]=слова юзера). ` +
  `Верни обзор корпуса: sessions (число), domains (с чем работает), top_tools, prose_langs (языки прозы). ` +
  `ОБЯЗАТЕЛЬНО held_out: 8-16 verbatim промптов юзера из РАЗНЫХ сессий и РАЗНЫХ тем — содержательные ` +
  `(не «ок»/«дальше»), типичные для его речи. Это резерв shadow-сверки — они НЕ пойдут в харвест.`,
  { label: 'overview:corpus', phase: 'Overview', schema: OVERVIEW_SCHEMA, model: 'sonnet', effort: 'low' })
if (!ov) throw new Error('overview не собрался — slims.jsonl есть? bootstrap фаза A прогнана?')
log(`корпус: ${ov.sessions} сессий · домены: ${ov.domains.slice(0,5).join(', ')} · held-out: ${ov.held_out.length}`)

// ═══ ФАЗА 2: паттерн-ноги (Sonnet ×2, ПОСЛЕДОВАТЕЛЬНО — B видит A, идёт шире) ═══
phase('Patterns')
const A = await agent(
  `Ты классификатор-A. Read ${FP}, просканируй ${SLIMS} (tools[]=упорядоченные tool-call'ы). ` +
  `Обзор корпуса уже есть: домены ${JSON.stringify(ov.domains)}. ЗАДАЧА: из ПАТТЕРНОВ tool-call'ов ` +
  `вывести model-cores — грани того, КАК юзер действует: повторяющиеся последовательности, циклы/ретраи, ` +
  `edit-без-read, distinctive-комбо. klass: structural-pull (детектируемо в tool_input/response детерминированно) ` +
  `vs disposition-push (привычка, в пол). tool_evidence = verbatim паттерн; gate = детект-условие. BROAD scope.`,
  { label: 'patterns:A-tools', phase: 'Patterns', schema: MODELCORE_SCHEMA, model: 'sonnet' })
const B = await agent(
  `Ты классификатор-B. A уже нашёл model-cores: ${JSON.stringify((A && A.model_cores || []).map(c => c.signature))}. ` +
  `Иди ШИРЕ и в ДРУГУЮ сторону: Read ${SLIMS}, парси prose[] (слова юзера). ` +
  `⚠ Эти промпты НЕ трогай (held-out резерв сверки): ${JSON.stringify(ov.held_out.map(p => p.slice(0, 60)))}. ` +
  `ЗАДАЧА: (1) situation_cores — грани того, КАК юзер ДУМАЕТ (что строит, чего боится, как фреймит), ` +
  `каждая с verbatim-якорем из ЕГО прозы; (2) lexicon — его повторяющиеся НАТИВНЫЕ слова per ситуация ` +
  `(recall цепляется к ним, не к абстракциям); (3) broader_model_cores — что A пропустил. НЕ дублируй A.`,
  { label: 'patterns:B-prose', phase: 'Patterns', schema: HARVEST_SCHEMA, model: 'sonnet' })
if (!B) throw new Error('паттерн-нога B не вернулась')
log(`A: ${(A && A.model_cores || []).length} model-cores · B: ${B.situation_cores.length} ситуация-ядер, ${B.lexicon.length} лексика-групп`)

// ═══ ФАЗА 3: полный свип + эмерж + сборка (Opus МИНИМУМ — качество ядер = качество харнеса) ═══
phase('Build')
const build = await agent(
  `Ты движок эмержа glados-харнеса (полный свип). Кандидаты от классификаторов:\n` +
  `A (model-cores из tool-call): ${JSON.stringify(A)}\n` +
  `B (ситуация+лексика из прозы): ${JSON.stringify(B)}\n` +
  `Обзор: ${JSON.stringify({sessions: ov.sessions, domains: ov.domains, notes: ov.notes})}\n\n` +
  `ШАГИ (делай сам, у тебя есть тулы):\n` +
  `1. СВИП: Read ${SLIMS} сам — проверь кандидатов против сырья (якоря verbatim? лексика реально ` +
  `частотна? грани не дублируются?). Кандидат без опоры в корпусе — выкинь.\n` +
  `2. ЭМЕРЖ: синтезируй финал — 5-9 ситуация-ядер (id с 1, facet, anchor verbatim, native_words ` +
  `ЕГО словами), lexicon-группы к ядрам, model_cores. Грань, применимая ≈каждый ход = ` +
  `ДИСПОЗИЦИЯ: ей место в полу, НЕ в лексике (в emerge не клади её words в triggers; список таких ` +
  `отдай в dispositions).\n` +
  `3. Write ${KIT}/emerge.json: {"situation_cores": [...], "model_cores": [...], "lexicon": [...]}.\n` +
  `4. Bash: cd ${KIT} && sh bootstrap.sh --finish (соберёт cores/, core-triggers.txt = тюн-датабейс ` +
  `лекс-матрицы, эмбед-индекс, хуки в settings.json).\n` +
  `5. Диспозициям (если есть) проставь class: disposition во frontmatter их файлов в ` +
  `~/.claude/overlays/cores/ — их подхватит ida-floor.\n` +
  `6. Верни отчёт: cores_built, trigger_lines (wc -l ${G}/core-triggers.txt), dispositions, build_ok, build_log.`,
  { label: 'build:emerge+matrix', phase: 'Build', schema: BUILD_SCHEMA, model: 'opus', effort: 'high' })
if (!build || !build.build_ok) throw new Error('сборка не прошла: ' + JSON.stringify(build && build.build_log))
log(`собрано: ${build.cores_built.length} ядер · ${build.trigger_lines} строк матрицы · пол: ${build.dispositions.join(', ') || '—'}`)

// ═══ ФАЗА 4: СВЕРКА — shadow-прогон held-out через ЖИВОЙ хук + ida-счётчик (Sonnet-механика) ═══
phase('Verify')
const sverka = await agent(
  `Shadow-сверка свежесобранного glados-харнеса. Held-out промпты (харвест их НЕ видел):\n` +
  `${JSON.stringify(ov.held_out)}\n` +
  `ШАГИ (механика, всё через Bash):\n` +
  `1. firelog_rows_before = wc -l ${G}/fire-log.jsonl (0 если нет файла).\n` +
  `2. Каждый промпт прогони через ЖИВОЙ хук: echo '{"prompt":"...","session_id":"install-verify"}' | ` +
  `python3 ~/.claude/bin/ida-attest — собери per_prompt: surfaced-ядра из <ida-attest>-вывода и спаны.\n` +
  `3. firelog_rows_after = wc -l снова. counter_ok = (after - before == число прогнанных промптов ` +
  `длиной ≥3 слов) — это сверка ida-СЧЁТЧИКА: каждый содержательный ход обязан оставить строку.\n` +
  `4. floor_ok: sh ~/.claude/bin/ida-floor выводит <floor-bodies> с телами, ЛИБО диспозиций нет вовсе.\n` +
  `5. fire_rate = fired_n/held_out_n (fired = surfaced непуст). Числа считай, не оценивай.`,
  { label: 'verify:shadow+counter', phase: 'Verify', schema: SVERKA_SCHEMA, model: 'sonnet' })
if (!sverka) throw new Error('сверка не вернулась')
log(`shadow: fire-rate ${(sverka.fire_rate * 100).toFixed(0)}% (${sverka.fired_n}/${sverka.held_out_n}) · счётчик ${sverka.counter_ok ? 'OK' : 'ТЕЧЬ'} · пол ${sverka.floor_ok ? 'OK' : 'ПУСТ'}`)

// ═══ ФАЗА 4b: аудит течей (Opus — semantic-вердикт по фирам) ═══
const audit = await agent(
  `Ты аудитор свежего glados-харнеса. Результат shadow-прогона held-out промптов:\n` +
  `${JSON.stringify(sverka.per_prompt)}\n` +
  `Ядра: ${JSON.stringify(build.cores_built)}. Read ~/.claude/overlays/cores/*.md и ${G}/core-triggers.txt.\n` +
  `ЗАДАЧА: найди ТЕЧИ — фиры, где спан = слово-тема/слишком широкий regex (ядро зажглось, но промпт ` +
  `не про эту грань), и НЕДОЛЁТЫ — промпт явно про грань ядра, а фира нет. Типовой ложный мод: ` +
  `общеупотребимое слово в триггере фирит на всё. verdict: ok / ok-with-notes / rebuild (rebuild = ` +
  `матрица шумит на >половине held-out). tune_advice: конкретные правки триггеров (≤6), но НЕ применяй ` +
  `их — правка лексики = решение владельца (docs/TUNE.md).`,
  { label: 'verify:audit-leaks', phase: 'Verify', schema: AUDIT_SCHEMA, model: 'opus' })

return {
  overview: { sessions: ov.sessions, domains: ov.domains },
  build,
  sverka: { fire_rate: sverka.fire_rate, counter_ok: sverka.counter_ok, floor_ok: sverka.floor_ok },
  audit,
  for_engine: 'Перескажи владельцу: какие ядра собраны (пусть вычеркнет чужое), fire-rate на held-out, ' +
              'найденные течи (кандидаты анти-триггеров — в датасет, не в панику), verdict аудита. ' +
              'Перезапуск Claude Code для загрузки хуков. Дальше жить 1-2 недели → docs/TUNE.md.',
}
