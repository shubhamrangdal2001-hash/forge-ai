"""Critic/Verifier agent — Claude Opus 4.8. Independent reviewer + explainer."""
from ..state import AgentState
from ..models.router import complete, Task


def approve(s: AgentState) -> bool:
    """Semantic review on top of mechanical checks (tests/lint/types/build)."""
    prompt = (
        "Review the patches against the plan acceptance criteria. "
        "Reply APPROVE or REJECT with reasons.\n"
        f"Plan: {s.plan}\nPatches: {[p['file_path'] for p in s.patches]}"
    )
    out = complete(Task.DEBUG, prompt)
    s.tokens_used += out.tokens
    return "REJECT" not in out.text.upper()


def explain(s: AgentState) -> str:
    prompt = f"Summarize what changed and why, for a PR description.\nPlan: {s.plan}"
    out = complete(Task.DOCS, prompt)
    s.tokens_used += out.tokens
    return out.text
