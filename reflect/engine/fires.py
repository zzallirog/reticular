"""Fires plane — the attention side of Reflect.

Reads the glados harness state (fire-log.jsonl, case-book.jsonl,
act-log.jsonl) and serves COUNTED aggregates: which cores fired, on what
spans, what the judge said (genuine/echo/partial), where the lexicon has
holes (arrival-miss). Same invariant as the recap engine: numbers are
counted from logs, never narrated by a model.

Join key with the session plane is sid — every fire-log row carries the
Claude Code session id, so a fire drills into the same session detail the
recap serves.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def _rows(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


class FiresService:
    def __init__(self, glados_dir: Path) -> None:
        self.dir = Path(glados_dir)

    # ------------------------------------------------------------- sources
    def _firelog(self) -> list[dict]:
        return _rows(self.dir / "fire-log.jsonl")

    def _casebook(self) -> list[dict]:
        return _rows(self.dir / "case-book.jsonl")

    def _actlog(self) -> list[dict]:
        return _rows(self.dir / "act-log.jsonl")

    # ------------------------------------------------------------- summary
    def summary(self) -> dict[str, Any]:
        fl = self._firelog()
        cb = self._casebook()
        al = self._actlog()
        fired = [r for r in fl if r.get("surfaced")]
        per_core: Counter = Counter(c for r in fired for c in r["surfaced"])
        dirs: Counter = Counter(r.get("dir") for r in fl if r.get("dir"))
        acted = [r for r in fl if r.get("acted_on")]
        act_modes: Counter = Counter(r.get("core") for r in al if r.get("core"))
        verdicts: Counter = Counter(
            v for c in cb if c.get("anno")
            for v in (c["anno"].get("verdicts") or {}).values())
        span = (fl[0].get("ts", "")[:10], fl[-1].get("ts", "")[:10]) if fl else ("", "")
        return {
            "rows": len(fl),
            "sessions": len({r.get("sid") for r in fl}),
            "span": span,
            "fired": len(fired),
            "fire_rate": round(len(fired) / len(fl), 3) if fl else 0.0,
            "per_core": dict(per_core.most_common()),
            "dirs": dict(dirs),
            "acted_rows": len(acted),
            "act_modes": dict(act_modes.most_common()),
            "cases": len(cb),
            "annotated": sum(1 for c in cb if c.get("anno")),
            "verdicts": dict(verdicts),
            "arrival_miss_cases": sum(1 for c in cb if c.get("arrival_miss")),
        }

    # --------------------------------------------------------------- cases
    def cases(self, verdict: str = "", core: str = "", limit: int = 60) -> list[dict]:
        out = []
        for c in self._casebook():
            anno = c.get("anno") or {}
            vs = anno.get("verdicts") or {}
            if core and core not in (c.get("acted_on") or []):
                continue
            if verdict and verdict not in (
                    vs.values() if not core else [vs.get(core)]):
                continue
            out.append({
                "id": c.get("id"), "ts": c.get("ts"), "sid": c.get("sid"),
                "prompt": (c.get("prompt") or "")[:160],
                "acted_on": c.get("acted_on"),
                "arrival_miss": c.get("arrival_miss"),
                "witness": c.get("witness"),
                "dir": c.get("dir"), "voice": c.get("voice"),
                "verdicts": vs or None,
                "reflection": (anno.get("reflection") or "")[:300],
            })
        out.sort(key=lambda x: x.get("ts") or "", reverse=True)
        return out[: max(1, min(limit, 300))]

    # ------------------------------------------------------ echo span table
    def echo_spans(self) -> list[dict]:
        stat: dict = {}
        for c in self._casebook():
            anno = c.get("anno")
            if not anno:
                continue
            wit = c.get("witness") or {}
            for core_id, verd in (anno.get("verdicts") or {}).items():
                for span in wit.get(core_id, []):
                    st = stat.setdefault((core_id, span),
                                         {"echo": 0, "genuine": 0, "partial": 0})
                    if verd in st:
                        st[verd] += 1
        rows = [
            {"core": k[0], "span": k[1], **v}
            for k, v in stat.items() if v["echo"] >= 2 and v["genuine"] == 0]
        rows.sort(key=lambda r: -r["echo"])
        return rows[:100]

    # ------------------------------------------------------- session drill
    def session_fires(self, sid: str) -> list[dict]:
        return [
            {"ts": r.get("ts"), "prompt": (r.get("prompt") or "")[:160],
             "surfaced": r.get("surfaced"), "acted_on": r.get("acted_on"),
             "dir": r.get("dir"), "wit_prompt": r.get("wit_prompt")}
            for r in self._firelog() if r.get("sid") == sid]
