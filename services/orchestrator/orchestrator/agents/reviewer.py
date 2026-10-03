"""Reviewer agent + multi-agent review panel (differentiator #6).

The final semantic gate on top of the mechanical checks. Instead of a single
opinion, a *panel* of reviewers — correctness, security, and maintainability —
each votes APPROVE / REQUEST_CHANGES on Opus 4.8. A change is only finalized
when the panel reaches consensus AND every mechanical gate (tests, security,
static, hallucination) is green. Reviewers are separate from the Coder, so the
agent never marks its own homework.
"""
from ..state import AgentState
from ..models.router import complete, Task
from ..events import publish_step

PERSPECTIVES = [
    ("correctness", "Does the change fully satisfy the acceptance criteria, with tests proving it?"),
    ("security", "Does the diff introduce any vulnerability, unsafe input handling, or leaked secret?"),
    ("maintainability", "Is the diff minimal, readable, and consistent with the existing codebase?"),
]


def _mechanical_ok(state: AgentState) -> bool:
    return (
        bool(state.patches)
        and bool(state.test_results.get("passed"))
        and bool(state.security_results.get("passed", True))
        and bool(state.verify_results.get("passed"))
        and bool(state.hallucination_results.get("passed", True))
    )


def panel_review(state: AgentState) -> dict:
    """Run the multi-agent review panel and require consensus before final patch."""
    publish_step(state.run_id, agent_role="reviewer", model="claude-opus-4.8", phase="review", status="running")
    files = [p.get("file_path") for p in state.patches]
    votes: list[dict] = []
    for name, question in PERSPECTIVES:
        prompt = (
            f"You are the {name} reviewer. {question}\n"
            f"Plan: {state.plan}\nFiles: {files}\n"
            f"Patch count: {len(state.patches)}\n"
            f"Signals -> tests:{state.test_results.get('passed')} "
            f"security_high:{state.security_results.get('high')} "
            f"static:{state.verify_results.get('passed')} "
            f"hallucination_conf:{state.hallucination_results.get('confidence')}\n"
            "Reply APPROVE or REQUEST_CHANGES with a one-line reason."
        )
        out = complete(Task.REVIEW, prompt)
        state.tokens_used += out.tokens
        approved = "REQUEST_CHANGES" not in out.text.upper()
        votes.append({"reviewer": name, "approved": approved, "model": out.model, "comment": out.text[:200]})

    mechanical = _mechanical_ok(state)
    approvals = sum(1 for v in votes if v["approved"])
    consensus = approvals >= 2 and mechanical
    state.panel_results = {"votes": votes, "approvals": approvals, "mechanical": mechanical}
    state.review_results = {
        "approved": bool(consensus),
        "comments": "; ".join(f"{v['reviewer']}:{'+' if v['approved'] else '-'}" for v in votes),
    }
    publish_step(state.run_id, agent_role="reviewer", model="claude-opus-4.8", phase="review",
                 status="passed" if consensus else "failed", detail=state.panel_results)
    return state.review_results


def review(state: AgentState) -> dict:
    """Single-reviewer fallback (kept for back-compat); delegates to the panel."""
    return panel_review(state)


def explain(state: AgentState) -> str:
    """Produce a human-readable PR description for the verified change."""
    prompt = f"Summarize what changed and why, for a PR description.\nPlan: {state.plan}"
    out = complete(Task.DOCS, prompt)
    state.tokens_used += out.tokens
    publish_step(state.run_id, agent_role="reviewer", model="claude-opus-4.8", phase="explain",
                 status="passed", detail={"summary": out.text[:400]})
    state.explanation = out.text
    return out.text
