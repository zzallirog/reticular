"""Minimal TTL-cache base — the only part of claw-dashboard's BaseService
the ported RecapService actually uses."""
from __future__ import annotations

import time
from typing import Any, Callable


class BaseService:
    def __init__(self, settings: Any, ttl_s: int = 900):
        self.settings = settings
        self._ttl_s = ttl_s
        self._cache: dict[str, tuple[float, Any]] = {}

    def _cached(self, key: str, compute: Callable[[], Any]) -> Any:
        hit = self._cache.get(key)
        if hit is not None and time.time() - hit[0] < self._ttl_s:
            return hit[1]
        value = compute()
        self._cache[key] = (time.time(), value)
        return value

    def invalidate(self) -> None:
        self._cache.clear()
