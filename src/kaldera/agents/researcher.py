"""Agent de recherche."""

from __future__ import annotations

from ..state import TeamState
from ..steps import Step
from .base import Agent


class Researcher(Agent):
    name = "researcher"
    description = "Effectue des recherches sur le sujet traité."
    handles = {Step.RESEARCH}

    def act(self, state: TeamState, step: Step) -> None:
        state.artifacts["research"] = f"research[{self.name}]:{state.topic}"
