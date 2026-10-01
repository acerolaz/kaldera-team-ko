"""Exécution d'un run pour la console : aucune dépendance HTTP."""
from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from ..agents.base import BudgetExceeded, RoleViolation
from ..cli import SCENARIOS
from ..orchestrator import AGENTS_BY_NAME, route
from ..runner import load_context, run_scenario
from ..state import TeamState
from .schemas import LogEntry, RunError, RunRequest, RunResult, RunStatus, ScenarioOut


def list_scenarios(path: Path = SCENARIOS) -> list[ScenarioOut]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        ScenarioOut(
            id=s["id"],
            topic=s["initial_context"]["topic"],
            required_steps=s["initial_context"]["required_steps"],
            max_steps=s["expected"]["max_steps"],
        )
        for s in data["scenarios"]
    ]


def execute_run(request: RunRequest) -> RunResult:
    scenario = {
        "initial_context": {
            "topic": request.topic,
            "required_steps": list(request.required_steps),
        },
        "expected": {"max_steps": request.max_steps},
    }
    # On garde la référence à l'état : il reste lisible même si un agent lève.
    state = TeamState()
    load_context(state, scenario)
    error: RunError | None = None
    try:
        run_scenario(scenario, initial_state=state)
    # L'exception part avant advance() : route(state) désigne l'agent fautif.
    except BudgetExceeded as exc:
        error = RunError(type="BudgetExceeded", agent=route(state), message=str(exc))
    except RoleViolation as exc:
        error = RunError(type="RoleViolation", agent=route(state), message=str(exc))

    status: RunStatus = "error" if error else cast(RunStatus, state.status)
    return RunResult(
        status=status,
        step_count=state.step_count,
        max_steps=request.max_steps,
        required_steps=request.required_steps,
        artifacts=state.artifacts,
        agent_tokens=state.agent_tokens,
        token_budgets={name: agent.token_budget for name, agent in AGENTS_BY_NAME.items()},
        log=[LogEntry(**entry) for entry in state.log],
        error=error,
    )
