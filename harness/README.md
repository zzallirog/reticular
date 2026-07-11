# glados-portable v2 — активный харнес из СВОИХ логов + тюн ложных срабатываний

Это не «чьи-то ядра». Ядра нельзя скопировать — они грани конкретного человека. Это
**метод, что строит ТВОИ ядра из ТВОИХ логов Claude Code**, и — новое в v2 — **цикл,
что трассирует ложные срабатывания и тюнит лексику по датасету**, не по вкусу.

**Если кит ставит агент (Claude/Opus): начни с `docs/INSTALL-AGENT.md`.**

Читает `~/.claude/projects/*/*.jsonl` и собирает:

1. **Ситуация-ядра** — грани того, КАК ты думаешь, из твоей прозы (промптов).
2. **Лексику** — твои нативные слова-триггеры (recall цепляется к ним, не к абстракции).
3. **model-cores** — грани того, КАК действует агент, из **tool-call'ов** (где циклит,
   где спотыкается). Источник = выходы, не интроспекция.
4. **Эмбеддинг-индекс** — чтобы recall-числа **воспроизводились на твоём вульте**.
5. **Четыре хука**:
   - `ida-floor` (SessionStart) — инжектит ТЕЛА диспозиция-граней при старте (пол: то, что
     применимо каждый ход, лексикой не диспетчится — оно просто присутствует);
   - `ida-attest` (UserPromptSubmit) — зажигает ситуация-ядра по промпту: лексика-нога +
     dense-backstop, третья ось act/read, witness-спаны, fire-log;
   - `ida-act` (Pre/PostToolUse) — парсит вызовы агента, ловит мод-ошибки детерминированно
     (edit-без-read, remote-shell, error-loop, запись-в-substrate);
   - `ida-land` (Stop) — доливает в fire-log, ЧТО реально легло в ответ (acted_on+witness).
6. **Casebook-цикл** (`tools/` + `workflow/annotate.workflow.js`) — fire-log → датасет →
   LLM-судья → кандидаты триггеров и АНТИ-триггеров. Финальный тюн: `docs/TUNE.md`.

## Идеология (одна строка)

Важное нельзя детектить дешёвой семантикой в query-time. **Детектор слепой/внешний читает
ТЕЛО на границе.** Вход (проза) нерегулярен → нужна твоя лексика. Выход (tool-call)
регулярен → детерминированный парсер точен. А ложные фиры лексики не лечатся механикой —
их судит LLM по датасету со свидетелями (witness-спанами), и правку всегда делает человек.

## Один проход

```sh
sh bootstrap.sh          # фаза A: deps + slim-экстракт + профиль
# → в Claude Code: «прогони workflow/install.workflow.js»
#   (Sonnet: обзор+паттерны → Opus: свип+эмерж+сборка матрицы → сверка: shadow-фиры + ida-счётчик)
# перезапусти Claude Code
```

Ручной fallback (без Workflow-тула): `harvest.workflow.js` → emerge.json → `sh bootstrap.sh --finish`.

Через 1-2 недели жизни — финальный тюн: `docs/TUNE.md`.

## Файлы

- `docs/INSTALL-AGENT.md` — бриф агенту-инсталлеру: порядок, проверки, ввод владельца в курс.
- `docs/ATLAS-LAYOUT.md` — раскладка памяти/проектов/feedbacks под лекс-матрицу
  (основа: https://github.com/zzallirog/agent-atlas — склонируй, это канон раскладки).
- `docs/TUNE.md` — цикл трассировки ложных фиров (arrival-miss / echo / анти-триггеры).
- `bootstrap.sh` — один проход, всё связывает (идемпотентно, POSIX sh).
- `slim_extract.py` — `~/.claude/projects/*/*.jsonl` → slim tool-call + prose транскрипты.
- `workflow/install.workflow.js` — инсталлятор одним воркфлоу: обзор→паттерны (Sonnet) →
  свип+эмерж+сборка (Opus) → сверка (shadow-фиры + ida-счётчик + аудит течей).
- `workflow/harvest.workflow.js` — 2 классификатора последовательно (ручной fallback).
- `workflow/annotate.workflow.js` — веер LLM-судей: verdict genuine/echo/partial per (кейс, ядро).
- `build_cores.py` — эмерж → `cores/` + `core-triggers.txt` + `model-cores/`.
- `build_embeddings.py` — нативные чанки → `core_p2p.json` (recall, воспроизводимо).
- `hooks/ida-floor`, `hooks/ida-attest`, `hooks/ida-act`, `hooks/ida-land` — портированные,
  без машино-специфики.
- `tools/backfill_acted.py` · `tools/compile_cases.py` · `tools/annotate_merge.py` ·
  `tools/casebook_harvest.py` · `tools/casebook_sidecases.py` — casebook-цепь (см. TUNE.md).

## «Числа воспроизводятся»

Метод фальсифицируем: на твоём вульте recall@k печатается self-test'ом; echo-rate и
arrival-miss считаются из case-book. Если сигнал есть — харвест поднимает fire-rate над
null, тюн опускает echo между раундами. Если нет — честный ноль, не вайб. Это и есть
перенос: не магнитуда чужого вульта, а **метод, дающий число на твоём**.

## Границы (что кит обещает и чего нет)

- Референс-числа владельца метода (152 сессии): лексический recall 7/7 на held-out;
  echo-rate сырого reply-lex оракула = 51% → потому судья и фильтр genuine обязательны.
- Лексика-нога несёт ~95% работы; без ollama dense-нога молчит — это режим, не поломка.
- Авто-тюн лексики намеренно НЕ замкнут: кандидаты — машина, врезка — человек.
