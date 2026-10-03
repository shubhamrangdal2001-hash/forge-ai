"""Test agent.

Test-first by default (differentiator #1): before the Coder writes any
implementation, the Tester authors tests derived from each task's acceptance
criteria. The implementation must then make these tests pass — this is what
keeps Forge honest and prevents 'looks-right' code that was never executed.
"""
from ..state import AgentState
from ..models.router import complete, Task
from ..events import publish_step


def write_tests_first(s: AgentState) -> list[dict]:
    """Author failing tests from acceptance criteria BEFORE implementation."""
    publish_step(s.run_id, agent_role="tester", model="gemini-flash", phase="write_tests", status="running")
    tests: list[dict] = []
    for task in s.plan:
        acceptance = task.get("acceptance")
        if not acceptance:
            continue
        prompt = (
            "Write failing tests (pytest or jest) that encode this acceptance "
            f"criterion BEFORE implementation exists.\nTask: {task.get('summary')}\n"
            f"Acceptance: {acceptance}"
        )
        out = complete(Task.TEST, prompt)
        s.tokens_used += out.tokens
        tests.append({"task": task.get("id"), "path": f"tests/test_{task.get('id','t')}.py", "body": out.text})
    s.tests_written = tests
    publish_step(s.run_id, agent_role="tester", model="gemini-flash", phase="write_tests",
                 status="passed", detail={"tests": len(tests)})
    return tests


def ensure_tests(s: AgentState) -> None:
    """Back-compat: fill any gaps if tests weren't authored test-first."""
    if not s.tests_written:
        write_tests_first(s)
