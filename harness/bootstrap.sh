#!/bin/sh
# bootstrap.sh — build the glados harness from YOUR logs, one pass. Run AFTER claude-kit.
# Idempotent, auto-detects OS/shell/ollama. POSIX sh.
#
#   sh bootstrap.sh            # phase A: deps + slim extract + profile. Prints the harvest step.
#   sh bootstrap.sh --finish   # phase B: after Claude has written emerge.json — assemble everything.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
CLAUDE="$HOME/.claude"
GLADOS="$CLAUDE/glados"
BIN="$CLAUDE/bin"
EMB="${GLADOS_EMBED:-embeddinggemma}"

say() { printf '\033[1m%s\033[0m\n' "$*"; }

phase_a() {
  say "[1/6] environment"
  command -v python3 >/dev/null || { echo "no python3 — install it"; exit 1; }
  python3 --version
  if command -v ollama >/dev/null; then
    ollama list 2>/dev/null | grep -q "$EMB" || { say "  pull $EMB"; ollama pull "$EMB" || \
      { say "  $EMB won't pull → fallback nomic-embed-text"; ollama pull nomic-embed-text && EMB=nomic-embed-text; }; }
  else
    echo "  ⚠ no ollama — recall index will be skipped (M1/M3 hooks still work). https://ollama.com"
  fi

  say "[2/6] slim log extract"
  test -d "$CLAUDE/projects" || { echo "no $CLAUDE/projects — was claude-kit installed? are there sessions?"; exit 1; }
  ( cd "$GLADOS" 2>/dev/null || { mkdir -p "$GLADOS"; cd "$GLADOS"; }
    python3 "$HERE/slim_extract.py" --logs "$CLAUDE/projects" )

  say "[3/6] shell profile (for M2 — remote incompatibility)"
  TOOLSHELL="$(basename "${SHELL:-sh}")"
  if [ ! -f "$GLADOS/shell-profile.json" ]; then
    printf '{"tool_shell": "%s", "fish_remotes": []}\n' "$TOOLSHELL" > "$GLADOS/shell-profile.json"
    echo "  written (fish_remotes empty → M2 stays silent; add hosts manually if you have a fish remote)"
  fi
  [ -f "$GLADOS/act-deny.json" ] || echo '{"M1": false, "M2": false, "M3": false}' > "$GLADOS/act-deny.json"

  cat <<EOF

────────────────────────────────────────────────────────────
PHASE A done. slims.jsonl + fingerprint.json in $GLADOS

HARVEST STEP (in Claude Code, one time):
  "run $HERE/workflow/harvest.workflow.js on $GLADOS/slims.jsonl,
   emerge cores → $GLADOS/emerge.json"
  (2 Sonnets classify in sequence, the engine synthesizes)

Then finish the build:
  sh bootstrap.sh --finish
────────────────────────────────────────────────────────────
EOF
}

phase_b() {
  test -f "$GLADOS/emerge.json" || { echo "no $GLADOS/emerge.json — do the harvest step (see phase A)"; exit 1; }
  say "[4/6] materializing cores"
  python3 "$HERE/build_cores.py" --emerge "$GLADOS/emerge.json" --base "$CLAUDE"

  say "[5/6] recall index"
  if command -v ollama >/dev/null && ollama list 2>/dev/null | grep -q "$EMB"; then
    GLADOS_EMBED="$EMB" python3 "$HERE/build_embeddings.py" \
      --triggers "$GLADOS/core-triggers.txt" --out "$GLADOS/core_p2p.json" || echo "  (embed skipped)"
  else echo "  no ollama/$EMB → recall index skipped (the lexicon leg still fires)"; fi

  say "[6/6] hooks + settings.json"
  mkdir -p "$BIN"
  cp "$HERE/hooks/ida-act" "$BIN/ida-act" && chmod +x "$BIN/ida-act"
  cp "$HERE/hooks/ida-attest" "$BIN/ida-attest" 2>/dev/null && chmod +x "$BIN/ida-attest" || true
  cp "$HERE/hooks/ida-land" "$BIN/ida-land" 2>/dev/null && chmod +x "$BIN/ida-land" || true
  cp "$HERE/hooks/ida-floor" "$BIN/ida-floor" 2>/dev/null && chmod +x "$BIN/ida-floor" || true
  [ -f "$GLADOS/axis.json" ] || echo '{"act_native": []}' > "$GLADOS/axis.json"
  [ -f "$GLADOS/floor.txt" ] || printf '# floor: one path per line — files whose BODIES are injected at session start\n# (disposition facets, gate catalog). cores with class: disposition travel automatically.\n' > "$GLADOS/floor.txt"
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
json.load(open(tmp, encoding="utf-8"))  # validation
os.replace(tmp, S)
print("  settings.json: hooks written (valid, backup alongside)")
PY
  say "DONE. Restart Claude Code (hooks load at start). self-test: edit a file without Read → M1 note."
  say "Final tuning (after ~50 substantive turns): docs/TUNE.md — casebook cycle for tracing false fires."
}

case "${1:-}" in
  --finish) phase_b ;;
  *) phase_a ;;
esac
