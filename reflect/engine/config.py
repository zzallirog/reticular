"""Standalone settings for the reticular Reflect engine.

Everything is overridable by environment; defaults assume a single machine
with Claude Code session logs in the standard place and reticular state
under ~/.reticular/.
"""
from __future__ import annotations

import os
from pathlib import Path


def _env_path(name: str, default: Path) -> Path:
    v = os.environ.get(name)
    return Path(v).expanduser() if v else default


_STATE = _env_path("RETICULAR_STATE_DIR", Path.home() / ".reticular")


class Settings:
    # Claude Code session logs — walked recursively.
    claude_projects_dir = _env_path(
        "RETICULAR_PROJECTS_DIR", Path.home() / ".claude" / "projects")
    # Optional second root: another machine's session deltas (same .jsonl
    # format), e.g. synced over. Files whose sid already exists under
    # claude_projects_dir are skipped; duplicate lines dropped by event uuid.
    # Unset (default) → single-host mode, the "remote" chip stays empty.
    raw_dir = _env_path("RETICULAR_REMOTE_DIR", _STATE / "remote-deltas")

    # glados harness state (fire-log, case-book) — the attention side.
    glados_dir = _env_path(
        "RETICULAR_GLADOS_DIR", Path.home() / ".claude" / "glados")

    ollama_url = os.environ.get("RETICULAR_OLLAMA", "http://127.0.0.1:11434")
    # Narrator model. A Claude alias (sonnet/opus/haiku or a claude-* id)
    # routes prose through the `claude` CLI subscription — no API key; an
    # ollama tag (e.g. qwen2.5:7b) keeps the local path. Numbers are banned in
    # the prompt regardless of model (invariant: numbers never pass through a
    # model — they are counted from logs). Prose is baked & cached per view.
    atlas_model = os.environ.get("RETICULAR_NARRATIVE_MODEL", "sonnet")
    atlas_ollama_timeout_s = 90
    narrator_timeout_s = int(os.environ.get("RETICULAR_NARRATOR_TIMEOUT", "90"))
    narrative_cache_path = _STATE / "narrative-cache.json"
    # Fact-bank for 'Threads that carried' — rotating, gated, counted facts.
    fact_bank_path = _STATE / "fact-bank.json"
    claude_usage_weekly_reset_tz = os.environ.get("RETICULAR_TZ", "UTC")
