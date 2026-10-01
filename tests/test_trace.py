"""Tests de trace : qui a fait quoi, dans quel ordre, combien de fois."""

import json
from pathlib import Path

import pytest

from kaldera.orchestrator import STEP_TO_AGENT
from kaldera.runner import run_scenario
from kaldera.state import TeamState
from kaldera.steps import Step, step_from_name

SCENARIOS = json.loads(
    (Path(__file__).resolve().parents[1] / "scenarios" / "scenarios_test.json").read_text(
        encoding="utf-8"
    )
)["scenarios"]


class _StuckAgent:
    """Agent qui ne fait jamais avancer l'état (simule une boucle)."""

    name = "researcher"

    def run(self, state: TeamState) -> None:  # noqa: D401 - test double
        return


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_trace_matches_spec(scenario):
    state = run_scenario(scenario)
    steps = [step_from_name(s) for s in scenario["initial_context"]["required_steps"]]
    owners = [e["agent_id"] for e in state.log]
    assert owners == [STEP_TO_AGENT[s] for s in steps]  # S1, S3
    assert state.step_count == len(steps)  # S2
    assert state.status == "done"
    assert "final" in state.artifacts  # S4


def test_stuck_agent_aborts_on_first_non_progress():
    state = TeamState(topic="x", required_steps=[Step.RESEARCH])
    result = run_scenario({}, initial_state=state, agents_by_name={"researcher": _StuckAgent()})
    assert result.status == "aborted"
    assert result.step_count <= 1  # et non 50
