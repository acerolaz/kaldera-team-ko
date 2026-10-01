"""Agent de rédaction."""

from __future__ import annotations

from ..state import TeamState
from ..steps import Step
from .base import Agent


class Writer(Agent):
    name = "writer"
    description = "Ecrit un brouillon à partir des recherches."
    handles = {Step.DRAFT}

    def act(self, state: TeamState, step: Step) -> None:
        state.artifacts["draft"] = f"draft[{self.name}]:{state.artifacts.get('research', '')}"
