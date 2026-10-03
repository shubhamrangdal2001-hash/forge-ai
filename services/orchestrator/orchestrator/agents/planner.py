"""Planner agent — runs on Claude Opus 4.8.

Turns a goal into a typed DAG of tasks with acceptance criteria.
"""
import json
from ..state import AgentState
from ..models.router import complete, Task
from ..intelligence.retriever import hybrid_retrieve

PLAN_PROMPT = """You are the Planner. Decompose the goal into a minimal ordered
list of tasks. Each task: "id", "summary", "files", "acceptance".
Return STRICT JSON: "tasks": [...].
Goal: {goal}
Repo context:
{context}
"""


def make_plan(s: AgentState) -> list[dict]:
    s.context["plan_hits"] = hybrid_retrieve(s.project_id, s.goal, k=8)
    prompt = PLAN_PROMPT.format(goal=s.goal, context=json.dumps(s.context["plan_hits"])[:4000])
    out = complete(Task.PLAN, prompt)
    s.tokens_used += out.tokens
    try:
        return json.loads(out.text).get("tasks", [])
    except json.JSONDecodeError:
        return [{"id": "t1", "summary": s.goal, "files": [], "acceptance": "tests pass"}]
