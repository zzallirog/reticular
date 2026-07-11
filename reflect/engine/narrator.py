"""Prose narrator via the Claude CLI (`claude -p`), with an on-disk per-view cache.

Invariant #1 (lesson 319/139): NUMBERS NEVER GO THROUGH THE MODEL. The caller's
prompt forbids them and the UI renders every figure counted; this module only
runs the model on qualitative shape and caches the prose.

Prose is *baked*, not live-per-request: the cache is keyed by a hash of the
prompt, so a view re-bakes only when its shape changes (new data → next bake).
Model = Claude via the user's `claude` CLI subscription — no API key, no metered
billing. Any failure returns None so the caller can fall back to the template.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

# `claude -p --model X` accepts these aliases as well as full `claude-*` ids.
_CLAUDE_ALIASES = {"sonnet", "opus", "haiku", "fable"}


def is_claude_model(model: str) -> bool:
    return model in _CLAUDE_ALIASES or model.startswith("claude")


def _claude_bin() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    cand = os.path.expanduser("~/.local/bin/claude")  # server runs non-login
    return cand if os.path.exists(cand) else None


def _hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


class NarrativeCache:
    """view-key -> {prose, model, hash, baked_at}. One JSON file, best-effort.

    Re-read from disk per instance so the always-on server picks up prose the
    separate bake process wrote."""

    def __init__(self, path: Path):
        self.path = Path(path)
        try:
            self._data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self._data = {}

    def lookup(self, view: str, prompt: str) -> tuple[str | None, bool, int | None]:
        """Return (prose, fresh, baked_at) for a view.

        Prose is served even when the prompt hash has DRIFTED: the paragraph
        narrates the view's qualitative *shape*, which barely moves as a tick
        or two of data lands, so a slightly-stale paragraph beats blanking to a
        robotic template. `fresh` is False on drift so the UI can stamp the
        bake date; the counted figures beside the prose are always live and
        never cached. None only when the view was never baked at all."""
        row = self._data.get(view)
        if not row:
            return None, False, None
        prose = row.get("prose") or None
        fresh = row.get("hash") == _hash(prompt)
        return prose, fresh, row.get("baked_at")

    def put(self, view: str, prompt: str, prose: str, model: str) -> None:
        self._data[view] = {
            "prose": prose,
            "model": model,
            "hash": _hash(prompt),
            "baked_at": int(time.time()),
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1))
            tmp.replace(self.path)  # atomic
        except OSError:
            pass


def bake(prompt: str, model: str, timeout_s: int = 90) -> str | None:
    """Run `claude -p --model <model>` on the prompt; return prose or None."""
    binpath = _claude_bin()
    if not binpath:
        return None
    try:
        r = subprocess.run(
            [binpath, "-p", "--model", model, prompt],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    out = (r.stdout or "").strip()
    return out or None
