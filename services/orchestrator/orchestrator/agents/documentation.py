"""Documentation agent.

After a change is verified, it brings docs back in sync: docstrings for new/
changed symbols, README deltas, and a changelog entry. Runs on the cheap local
Qwen Coder model by default (DOCS task) since this is high-volume, low-risk.
Returns 152.
"""
from ..state import AgentState
from ..models.router import complete, Task
from ..events import publish_step


def document(state: AgentState) -> dict:
    publish_step(state.run_id, agent_role="documentation", model="qwen-coder-local", phase="document", status="running")
    changed = [p.get("file_path") for p in state.patches]
    prompt = (
        "Write/refresh docstrings for changed symbols, a concise README delta, "
        "and a one-line CHANGELOG entry for this change.\n"
        f"Goal: {state.goal}\nChanged files: {changed}"
    )
    out = complete(Task.DOCS, prompt)
    state.tokens_used += out.tokens
    result = {"summary": out.text[:600], "changed_files": changed, "changelog": f"- {state.goal}"}
    state.doc_results = result
    publish_step(state.run_id, agent_role="documentation", model="qwen-coder-local", phase="document",
                 status="passed", detail={"files": len(changed)})
    return result
