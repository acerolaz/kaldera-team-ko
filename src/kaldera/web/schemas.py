"""Contrats Pydantic de l'API de la console."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from ..runner import HARD_CAP

StepName = Literal["RESEARCH", "DRAFT", "REVIEW", "FINALIZE"]
RunStatus = Literal["done", "aborted", "error"]


class ScenarioOut(BaseModel):
    id: str
    topic: str
    required_steps: list[StepName]
    max_steps: int


class RunRequest(BaseModel):
    topic: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    required_steps: list[StepName] = Field(min_length=1, max_length=HARD_CAP)
    max_steps: int = Field(ge=1, le=HARD_CAP)


class LogEntry(BaseModel):
    agent_id: str
    message: str


class RunError(BaseModel):
    type: Literal["BudgetExceeded", "RoleViolation"]
    agent: str
    message: str


class RunResult(BaseModel):
    status: RunStatus
    step_count: int
    max_steps: int
    required_steps: list[StepName]
    artifacts: dict[str, str]
    agent_tokens: dict[str, int]
    token_budgets: dict[str, int]
    log: list[LogEntry]
    error: RunError | None = None
