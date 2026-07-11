#!/bin/sh
# bootstrap.sh — построить glados-харнес из ТВОИХ логов, один проход. Запускать ПОСЛЕ claude-kit.
# Идемпотентно, auto-detect OS/shell/ollama. POSIX sh.
#
#   sh bootstrap.sh            # фаза A: deps + slim-экстракт + профиль. Печатает шаг харвеста.
#   sh bootstrap.sh --finish   # фаза B: после того как Claude записал emerge.json — собрать всё.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
CLAUDE="$HOME/.claude"
GLADOS="$CLAUDE/glados"
BIN="$CLAUDE/bin"
EMB="${GLADOS_EMBED:-embeddinggemma}"

say() { printf '\033[1m%s\033[0m\n' "$*"; }

phase_a() {
  say "[1/6] среда"
  command -v python3 >/dev/null || { echo "нет python3 — поставь"; exit 1; }
  python3 --version
  if command -v ollama >/dev/null; then
    ollama list 2>/dev/null | grep -q "$EMB" || { say "  pull $EMB"; ollama pull "$EMB" || \
      { say "  $EMB не тянется → fallback nomic-embed-text"; ollama pull nomic-embed-text && EMB=nomic-embed-text; }; }
  else
    echo "  ⚠ ollama нет — recall-индекс пропустится (хуки M1/M3 всё равно работают). https://ollama.com"
  fi

  say "[2/6] slim-экстракт логов"
  test -d "$CLAUDE/projects" || { echo "нет $CLAUDE/projects — claude-kit стоял? есть сессии?"; exit 1; }
  ( cd "$GLADOS" 2>/dev/null || { mkdir -p "$GLADOS"; cd "$GLADOS"; }
    python3 "$HERE/slim_extract.py" --logs "$CLAUDE/projects" )

  say "[3/6] shell-профиль (для M2 — remote-несовместимость)"
  TOOLSHELL="$(basename "${SHELL:-sh}")"
  if [ ! -f "$GLADOS/shell-profile.json" ]; then
    printf '{"tool_shell": "%s", "fish_remotes": []}\n' "$TOOLSHELL" > "$GLADOS/shell-profile.json"
    echo "  записан (fish_remotes пуст → M2 молчит; добавь хосты вручную если есть fish-remote)"
  fi
  [ -f "$GLADOS/act-deny.json" ] || echo '{"M1": false, "M2": false, "M3": false}' > "$GLADOS/act-deny.json"

  cat <<EOF

────────────────────────────────────────────────────────────
ФАЗА A готова. slims.jsonl + fingerprint.json в $GLADOS

ШАГ ХАРВЕСТА (в Claude Code, один раз):
  «прогони $HERE/workflow/harvest.workflow.js на $GLADOS/slims.jsonl,
   эмерджи cores → $GLADOS/emerge.json»
  (2 Sonnet'а классифицируют последовательно, движок синтезирует)

Потом заверши сборку:
  sh bootstrap.sh --finish
────────────────────────────────────────────────────────────
EOF
}

phase_b() {
  test -f "$GLADOS/emerge.json" || { echo "нет $GLADOS/emerge.json — сделай шаг харвеста (см. фазу A)"; exit 1; }
  say "[4/6] материализую ядра"
  python3 "$HERE/build_cores.py" --emerge "$GLADOS/emerge.json" --base "$CLAUDE"

  say "[5/6] recall-индекс"
  if command -v ollama >/dev/null && ollama list 2>/dev/null | grep -q "$EMB"; then
    GLADOS_EMBED="$EMB" python3 "$HERE/build_embeddings.py" \
      --triggers "$GLADOS/core-triggers.txt" --out "$GLADOS/core_p2p.json" || echo "  (embed пропущен)"
  else echo "  ollama/$EMB нет → recall-индекс пропущен (лексика-нога всё равно фирит)"; fi

  say "[6/6] хуки + settings.json"
  mkdir -p "$BIN"
  cp "$HERE/hooks/ida-act" "$BIN/ida-act" && chmod +x "$BIN/ida-act"
  cp "$HERE/hooks/ida-attest" "$BIN/ida-attest" 2>/dev/null && chmod +x "$BIN/ida-attest" || true
  cp "$HERE/hooks/ida-land" "$BIN/ida-land" 2>/dev/null && chmod +x "$BIN/ida-land" || true
  cp "$HERE/hooks/ida-floor" "$BIN/ida-floor" 2>/dev/null && chmod +x "$BIN/ida-floor" || true
  [ -f "$GLADOS/axis.json" ] || echo '{"act_native": []}' > "$GLADOS/axis.json"
  [ -f "$GLADOS/floor.txt" ] || printf '# floor: по строке на путь — файлы, чьи ТЕЛА инжектятся при старте сессии\n# (диспозиция-грани, gate-каталог). cores с class: disposition едут автоматом.\n' > "$GLADOS/floor.txt"
  python3 - "$CLAUDE/settings.json" "$BIN" <<'PY'
import json, os, sys, datetime
S, BIN = sys.argv[1], sys.argv[2]
cfg = {}
if os.path.exists(S):
    cfg = json.load(open(S, encoding="utf-8"))
    import shutil; shutil.copy2(S, S + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
h = cfg.setdefault("hooks", {})
def has(ev, cmd):
    return any(any(x.get("command")==cmd for x in e.get("hooks",[])) for e in h.get(ev,[]))
ACT = os.path.join(BIN, "ida-act")
if not has("PreToolUse", ACT):
    h.setdefault("PreToolUse", []).append({"matcher":"Edit|Write|NotebookEdit|Bash",
        "hooks":[{"type":"command","command":ACT,"timeout":5}]})
if not has("PostToolUse", ACT):
    h.setdefault("PostToolUse", []).append({"matcher":"*",
        "hooks":[{"type":"command","command":ACT,"timeout":5}]})
ATT = os.path.join(BIN, "ida-attest")
if os.path.exists(ATT) and not has("UserPromptSubmit", ATT):
    h.setdefault("UserPromptSubmit", []).append({"matcher":"*",
        "hooks":[{"type":"command","command":ATT,"timeout":5}]})
LAND = os.path.join(BIN, "ida-land")
if os.path.exists(LAND) and not has("Stop", LAND):
    h.setdefault("Stop", []).append({"matcher":"*",
        "hooks":[{"type":"command","command":LAND,"timeout":10}]})
FLOOR = os.path.join(BIN, "ida-floor")
if os.path.exists(FLOOR) and not has("SessionStart", FLOOR):
    h.setdefault("SessionStart", []).append({"matcher":"*",
        "hooks":[{"type":"command","command":FLOOR,"timeout":10}]})
tmp = S + ".tmp"
json.dump(cfg, open(tmp,"w",encoding="utf-8"), indent=2, ensure_ascii=False)
json.load(open(tmp, encoding="utf-8"))  # валидация
os.replace(tmp, S)
print("  settings.json: хуки вписаны (валидно, бэкап рядом)")
PY
  say "ГОТОВО. Перезапусти Claude Code (хуки грузятся при старте). self-test: правь файл без Read → нота M1."
  say "Финальный тюн (после ~50 содержательных ходов): docs/TUNE.md — casebook-цикл трассировки ложных фиров."
}

case "${1:-}" in
  --finish) phase_b ;;
  *) phase_a ;;
esac
