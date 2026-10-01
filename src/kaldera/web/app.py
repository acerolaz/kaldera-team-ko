"""Console de démo Kaldera : routes fines, la logique vit dans service.py."""
from __future__ import annotations

from fastapi import FastAPI

from . import service
from .schemas import RunRequest, RunResult, ScenarioOut

app = FastAPI(title="Kaldera Console")


@app.get("/api/scenarios", response_model=list[ScenarioOut])
def get_scenarios() -> list[ScenarioOut]:
    return service.list_scenarios()


@app.post("/api/runs", response_model=RunResult)
def post_run(request: RunRequest) -> RunResult:
    return service.execute_run(request)
