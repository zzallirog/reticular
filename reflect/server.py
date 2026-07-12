"""reticular Reflect — standalone recap dashboard.

Engine ported from claw-dashboard feat/reflect-recap (cut out of atrium
2026-07-10 by design: a separate admin panel). Serves the recap API and a
single-file UI. No auth: binds localhost only.

Run:  python3 -m uvicorn server:app --port 8899   (from app/)
  or: python3 server.py
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from engine.config import Settings
from engine.fires import FiresService
from engine.models import RecapSnapshot
from engine.service import RecapService

app = FastAPI(title="reticular reflect", docs_url=None, redoc_url=None)
_settings = Settings()
_svc = RecapService(_settings)
_fires = FiresService(_settings.glados_dir)
_UI = Path(__file__).parent / "ui" / "index.html"
_FIRES_UI = Path(__file__).parent / "ui" / "fires.html"


@app.get("/api/recap", response_model=RecapSnapshot)
def recap(force: bool = False, months: int = 0, host: str = "all") -> RecapSnapshot:
    if force:
        _svc.invalidate()
    if host not in ("all", "local", "remote"):
        host = "all"
    return _svc.snapshot(months=max(0, months), host=host)


def _view_args(months: int, host: str) -> tuple[int, str]:
    return max(0, months), host if host in ("all", "local", "remote") else "all"


@app.get("/api/sessions")
def sessions(
    bucket: str | None = None, limit: int = 40,
    months: int = 0, host: str = "all",
) -> list[dict]:
    months, host = _view_args(months, host)
    return _svc.drill_sessions(
        bucket=bucket, limit=min(limit, 200), months=months, host=host)


@app.get("/api/cell/{dow}/{hour}")
def cell(dow: int, hour: int, months: int = 0, host: str = "all") -> dict:
    if not (0 <= dow <= 6 and 0 <= hour <= 23):
        return {"days": [], "sessions": []}
    months, host = _view_args(months, host)
    return _svc.drill_cell(dow, hour, months=months, host=host)


@app.get("/api/day/{day}")
def day(day: str, months: int = 0, host: str = "all") -> list[dict]:
    if len(day) != 10:  # ISO date only
        return []
    months, host = _view_args(months, host)
    return _svc.drill_day(day, months=months, host=host)


@app.get("/api/search")
def search(q: str = "", limit: int = 40, months: int = 0, host: str = "all") -> list[dict]:
    months, host = _view_args(months, host)
    return _svc.search_sessions(q, limit=min(limit, 200), months=months, host=host)


@app.get("/api/session/{sid}")
def session(sid: str, months: int = 0, host: str = "all") -> dict:
    months, host = _view_args(months, host)
    return _svc.session_detail(sid, months=months, host=host) or {}


@app.get("/api/fires")
def fires_summary() -> dict:
    return _fires.summary()


@app.get("/api/fires/cases")
def fires_cases(verdict: str = "", core: str = "", limit: int = 60) -> list[dict]:
    return _fires.cases(verdict=verdict, core=core, limit=limit)


@app.get("/api/fires/echo-spans")
def fires_echo_spans() -> list[dict]:
    return _fires.echo_spans()


@app.get("/api/fires/session/{sid}")
def fires_session(sid: str) -> list[dict]:
    return _fires.session_fires(sid)


@app.get("/fires")
def fires_page() -> FileResponse:
    return FileResponse(_FIRES_UI)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_UI)


if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(app, host="127.0.0.1",
                port=int(os.environ.get("RETICULAR_PORT", "8899")))
