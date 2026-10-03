"""Supervisor — the team registry and routing metadata for the 8-agent system.

The supervisor doesn't re-implement the DAG (that lives in `graph.py`); it owns
the *roster*: which agents exist, what phase each owns, which model tier it uses,
and whether it can block the pipeline. `graph.py` consults this ordering so the
pipeline and the roster never drift apart.
"""
from __future__ import annotations
from dataclasses import dataclass

from ..models.router import Task


@dataclass(frozen=True)
class AgentSpec:
    role: str
    phase: str
    task: Task
    blocking: bool        # can this agent fail the pipeline?
    description: str


# Ordered roster = pipeline order.
AGENT_TEAM: list[AgentSpec] = [
    AgentSpec("planner",       "plan",     Task.PLAN,     True,
              "Decomposes the goal into a typed task DAG with acceptance criteria."),
    AgentSpec("coder",         "patch",    Task.CODE,     True,
              "Implements tasks as grounded unified-diff patches."),
    AgentSpec("tester",        "test",     Task.TEST,     True,
              "Generates missing tests and runs the test suite in the sandbox."),
    AgentSpec("debugger",      "debug",    Task.DEBUG,    False,
              "Root-causes failures and enriches context for the next patch loop."),
    AgentSpec("security",      "security", Task.SECURITY, True,
              "Scans for secrets, vulnerable deps, and logic-level vulnerabilities."),
    AgentSpec("reviewer",      "review",   Task.REVIEW,   True,
              "Independent semantic gate: APPROVE / REQUEST_CHANGES."),
    AgentSpec("documentation", "document", Task.DOCS,     False,
              "Keeps docstrings, README, and changelog in sync with the change."),
    AgentSpec("deployment",    "deploy",   Task.DEPLOY,   False,
              "Builds the artifact and stages a human-approved deployment."),
]

TEAM_BY_ROLE = {a.role: a for a in AGENT_TEAM}


def describe_team() -> list[dict]:
    return [a.__dict__ | {"task": a.task.value} for a in AGENT_TEAM]
