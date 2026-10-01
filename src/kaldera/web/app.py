"""Console de démo Kaldera : routes fines, la logique vit dans service.py."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import service
from .schemas import RunRequest, RunResult, ScenarioOut

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Kaldera Console")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/api/scenarios", response_model=list[ScenarioOut])
def get_scenarios() -> list[ScenarioOut]:
    return service.list_scenarios()


@app.post("/api/runs", response_model=RunResult)
def post_run(request: RunRequest) -> RunResult:
    return service.execute_run(request)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")
