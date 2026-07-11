export const meta = {
  name: 'glados-annotate',
  description: 'LLM-судья casebook: verdict genuine/echo/partial per (кейс, ядро) — трассировка ложных срабатываний лексики',
  phases: [
    { title: 'Judge', detail: 'веер судей по батчам case-book' },
  ],
}
// ВХОД (args): { casebook: путь к case-book.jsonl, cores_dir: путь к overlays/cores, batch?: 16 }
// ВЫХОД: { annos: [...] } — движок пишет annos.json и гонит tools/annotate_merge.py.
//
// ЗАЧЕМ судья, а не механика: echo (слово-тема, не акт) дешёвой лексикой НЕ отделим —
// замерено на 651 вердикте (meta-flag отвергнут: echo 52% vs 51%). Семантический вердикт =
// работа LLM. Судья, не human-label — anno_src едет рядом, различай пост-хок.

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
                    description: 'per-core: genuine=ядро РЕАЛЬНО действовало в ответе; echo=слово-тема/эхо лексикона, акта нет; partial=частично' },
        case: { type: 'string', description: 'одно предложение: что за ход был' },
        reflection: { type: 'string', description: 'почему такой вердикт — чем witness-спаны служат/не служат акту' },
        drop: { type: 'boolean', description: 'кейс мусорный (обрывок/мета-тест), выкинуть' },
      } } },
  } }

// батчи режет ДВИЖОК перед запуском (или сам воркфлоу — счётчик кейсов заранее неизвестен,
// поэтому один scout-агент считает и возвращает срезы id)
phase('Judge')

const plan = await agent(
  `Read ${CB} (JSONL). Верни ТОЛЬКО JSON: {"total": N, "ids": [все id по порядку]}. Ничего не суди.`,
  { label: 'scout:count', phase: 'Judge',
    schema: { type: 'object', additionalProperties: false, required: ['total', 'ids'],
              properties: { total: { type: 'number' }, ids: { type: 'array', items: { type: 'string' } } } } })

const ids = (plan && plan.ids) || []
const slices = []
for (let i = 0; i < ids.length; i += BATCH) slices.push(ids.slice(i, i + BATCH))
log(`кейсов: ${ids.length}, батчей: ${slices.length} × ${BATCH}`)

const results = await parallel(slices.map((slice, bi) => () =>
  agent(
    `Ты судья casebook (батч ${bi + 1}/${slices.length}). Сначала Read ${CORES}/*.md — пойми, ` +
    `ЧТО каждое ядро означает (это грани мышления владельца, ядро = дисциплина/линза). ` +
    `Потом Read ${CB} и возьми ТОЛЬКО кейсы с id из списка:\n${JSON.stringify(slice)}\n` +
    `Для КАЖДОГО кейса, для КАЖДОГО ядра из acted_on дай вердикт:\n` +
    `- genuine: ответ РЕАЛЬНО исполнял дисциплину ядра (акт, не слова);\n` +
    `- echo: witness-спаны = слово-тема (разговор ПРО механизм/термин, цитата, тест-фраза) — акта нет;\n` +
    `- partial: дисциплина задета, но не исполнена.\n` +
    `Смотри на witness (спаны, зажёгшие лексику в ответе) и wit_prompt — они и есть улика. ` +
    `Типовой ложный мод: мета-разговор про сам харнес зажигает его же лексику. ` +
    `reflection: почему вердикт, коротко. drop=true для мусорных кейсов.`,
    { label: `judge:batch${bi + 1}`, phase: 'Judge', schema: ANNO_SCHEMA })
))

const annos = results.filter(Boolean).flatMap(r => r.annos || [])
log(`вердиктов собрано: ${annos.length}/${ids.length}`)

return {
  annos,
  for_engine: 'запиши {"annos": [...]} в annos.json и прогони: ' +
              'python3 tools/annotate_merge.py annos.json --src judge-<дата>; ' +
              'затем tools/casebook_harvest.py + tools/casebook_sidecases.py (кандидаты тюна)',
}
