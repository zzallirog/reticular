from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path


def _parse_ts(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        if raw.endswith("Z"):
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return datetime.fromisoformat(raw)
    except ValueError:
        return None




def _iter_jsonl(root: Path):
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        for jsonl in entry.glob("*.jsonl"):
            yield jsonl


