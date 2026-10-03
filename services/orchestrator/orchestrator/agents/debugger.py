"""Debug agent — reads failures and enriches context for the next patch loop."""
from ..state import AgentState
from ..models.router import complete, Task


def diagnose(s: AgentState) -> None:
    failures = {
        "tests": s.test_results.get("failures"),
        "static": s.verify_results.get("failures"),
    }
    prompt = f"Root-cause these failures and propose targeted fixes:\n{failures}"
    out = complete(Task.DEBUG, prompt)
    s.tokens_used += out.tokens
    s.context["debug_hint"] = out.text
