"""Shared base for every Forge agent.

Each agent has a stable role, a preferred task type (which the model router
turns into a concrete model + fallback chain), and an `act(state)` method that
mutates and returns the shared AgentState. Keeping a uniform interface lets the
supervisor treat the whole team polymorphically.
"""
from __future__ import annotations
from dataclasses import dataclass

from ..state import AgentState
from ..models.router import complete, Task, Completion
from ..events import publish_step


@dataclass
class BaseAgent:
    role: str            # planner | coder | tester | debugger | security | documentation | reviewer | deployment
    phase: str           # the pipeline phase this agent owns
    task: Task           # routing hint -> model + fallbacks

    # ---- helpers shared by all agents ----
    def think(self, state: AgentState, prompt: str) -> Completion:
        out = complete(self.task, prompt)
        state.tokens_used += out.tokens
        return out

    def emit(self, state: AgentState, status: str, detail=None) -> None:
        publish_step(
            state.run_id, agent_role=self.role, model=self.task.value,
            phase=self.phase, status=status, detail=detail,
        )

    def act(self, state: AgentState) -> AgentState:  # pragma: no cover - interface
        raise NotImplementedError
