"""Boucle d'exécution d'un scénario par l'équipe."""
from __future__ import annotations

from .orchestrator import END, AGENTS_BY_NAME, route
from .state import TeamState
from .steps import step_from_name

# Filet de sécurité dur : borne le nombre total d'itérations quoi qu'il arrive.
HARD_CAP = 50


def load_context(state: TeamState, scenario: dict) -> None:
    initial_context = scenario.get("initial_context") or {}
    state.topic = initial_context.get("topic")
    state.required_steps = [
        step_from_name(name) for name in initial_context.get("required_steps", [])
    ]


def run_scenario(
    scenario: dict,
    max_iterations: int | None = None,
    agents_by_name: dict | None = None,
    initial_state: TeamState | None = None,
) -> TeamState:
    state = initial_state if initial_state is not None else TeamState()
    if initial_state is None:
        load_context(state, scenario)
    registry = agents_by_name if agents_by_name is not None else AGENTS_BY_NAME
    limit = (
        max_iterations
        if max_iterations is not None
        else scenario.get("expected", {}).get("max_steps", HARD_CAP)
    )
    for _ in range(min(limit, HARD_CAP)):
        decision = route(state)
        if decision == END:
            if state.status != "done":
                state.status = "done"
            break
        agent = registry[decision]
        before = state.step_index
        agent.run(state)
        state.step_count += 1
        # Invariant de progression : un tour sans avancée = boucle, on coupe tout de suite.
        if state.step_index == before:
            state.status = "aborted"
            break
    else:
        state.status = "aborted"
    return state
