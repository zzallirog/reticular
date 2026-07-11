"""Thin stdlib client for local Ollama generate calls."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434"):
        self.base_url = base_url.rstrip("/")

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        timeout_s: int,
        temperature: float,
        num_predict: int | None = None,
        format_json: bool = False,
        format_schema: dict[str, object] | None = None,
    ) -> str:
        options: dict[str, int | float] = {"temperature": temperature}
        if num_predict is not None:
            options["num_predict"] = num_predict
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }
        if format_schema is not None:
            payload["format"] = format_schema
        elif format_json:
            payload["format"] = "json"
        req = Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=timeout_s) as resp:
                data = json.load(resp)
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise OllamaError(str(exc)) from exc
        text = data.get("response") if isinstance(data, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise OllamaError("empty ollama response")
        return text.strip()
