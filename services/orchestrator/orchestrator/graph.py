"""Custom DAG orchestrator — the reliability loop that makes Forge safer and more
accurate than single-shot agents.

    Plan -> Recall(memory) -> [ Snapshot -> WriteTests(test-first) -> Patch
      -> Hallucination-gate -> Test -> (fail? auto-rollback+debug)
      -> Security -> Verify(static) -> Panel-review
      -> Risk/approval-gate -> (approved) Document -> Explain -> Deploy(HITL)
      -> Record(memory) -> Report ]  /  (rejected) Rollback -> Debug -> retry

Differentiators wired here: test-first (#1), automatic rollback on test failure
(#2), codebase memory graph (#3), speed/accuracy + hybrid routing (#4/#7),
transparent verification report (#5), multi-agent review (#6), hallucination
detector (#9), and human approval for risky actions (#10).
"""
from .state import AgentState
from .events import publish_step, publish_report
from .agents import (
    planner, coder, tester, debugger,
    security, reviewer, documentation, deployment,
)
from .execution import sandbox, verifiers
from .reliability import checkpoints, report, approvals
from .intelligence import memory, hallucination
from .models import router


def node_plan(s: AgentState) -> AgentState:
    publish_step(s.run_id, agent_role="planner", model="claude-opus-4.8", phase="plan", status="running")
    s.plan = planner.make_plan(s)
    publish_step(s.run_id, agent_role="planner", model="claude-opus-4.8", phase="plan", status="passed", detail={"tasks": len(s.plan)})
    return s


def node_recall(s: AgentState) -> AgentState:
    s.memory = memory.recall(s.project_id, s.goal)
    if s.memory:
        s.context["memory"] = s.memory
        publish_step(s.run_id, agent_role="planner", model="-", phase="recall", status="passed",
                     detail={"recalled": len(s.memory)})
    return s


def node_snapshot(s: AgentState) -> AgentState:
    s.checkpoint_id = checkpoints.snapshot(s.project_id)
    return s


def node_write_tests(s: AgentState) -> AgentState:
    # Test-first: author tests from acceptance criteria before implementation.
    tester.write_tests_first(s)
    return s


def node_patch(s: AgentState) -> AgentState:
    publish_step(s.run_id, agent_role="coder", model="claude-sonnet", phase="patch", status="running")
    s.patches = coder.write_patches(s)
    publish_step(
        s.run_id,
        agent_role="coder",
        model="claude-sonnet",
        phase="patch",
        status="passed",
        detail={"files": len(s.patches), "staged_only": True},
    )
    return s


def node_hallucination(s: AgentState) -> AgentState:
    publish_step(s.run_id, agent_role="reviewer", model="-", phase="hallucination", status="running")
    res = hallucination.detect(s)
    publish_step(s.run_id, agent_role="reviewer", model="-", phase="hallucination",
                 status="passed" if res["passed"] else "failed", detail=res)
    return s


def node_test(s: AgentState) -> AgentState:
    publish_step(s.run_id, agent_role="tester", model="gemini-flash", phase="test", status="running")
    s.test_results = verifiers.run_tests(s.project_id)
    status = "passed" if s.test_results.get("passed") else "failed"
    publish_step(s.run_id, agent_role="tester", model="gemini-flash", phase="test", status=status, detail=s.test_results)
    return s


def node_security(s: AgentState) -> AgentState:
    security.scan(s)
    return s


def node_verify(s: AgentState) -> AgentState:
    publish_step(s.run_id, agent_role="reviewer", model="claude-opus-4.8", phase="verify", status="running")
    s.verify_results = verifiers.run_static_checks(s.project_id)  # mypy/eslint/ruff/build
    ok = s.verify_results.get("passed")
    publish_step(s.run_id, agent_role="reviewer", model="claude-opus-4.8", phase="verify", status="passed" if ok else "failed", detail=s.verify_results)
    return s


def node_panel_review(s: AgentState) -> AgentState:
    result = reviewer.panel_review(s)
    s.failed = not result.get("approved")
    return s


def node_document(s: AgentState) -> AgentState:
    documentation.document(s)
    return s


def node_explain(s: AgentState) -> AgentState:
    s.explanation = reviewer.explain(s)
    return s


def node_deploy(s: AgentState) -> AgentState:
    deployment.prepare(s)
    return s


def node_rollback(s: AgentState) -> AgentState:
    publish_step(s.run_id, agent_role="supervisor", model="-", phase="rollback", status="running")
    checkpoints.restore(s.project_id, s.checkpoint_id)
    s.iteration += 1
    publish_step(s.run_id, agent_role="supervisor", model="-", phase="rollback", status="passed", detail={"iteration": s.iteration})
    return s


def _exhausted(s: AgentState) -> bool:
    return s.iteration >= s.max_iterations or s.over_budget()


def _finalize(s: AgentState, message: str | None = None) -> AgentState:
    if message:
        s.explanation = message
    rep = report.build(s)
    publish_report(s.run_id, rep)
    return s


def route(s: AgentState) -> str:
    if not s.failed:
        return "approved"
    if _exhausted(s):
        return "rollback_final"
    return "rollback_retry"


def run_graph(s: AgentState) -> AgentState:
    """Execute the DAG until success, halt for approval, or exhaustion."""
    router.set_run(s.run_id)
    router.set_mode(s.router_mode)
    router.set_hybrid(s.local_only)
    router.set_overrides(s.model_overrides)  # honor the user's model choices

    s = node_plan(s)
    s = node_recall(s)

    while True:
        s = node_snapshot(s)
        s = node_write_tests(s)
        s = node_patch(s)

        # Hallucination gate (#9): never run code that references fabricated symbols.
        s = node_hallucination(s)
        if not s.hallucination_results.get("passed", True):
            s = node_rollback(s)
            if _exhausted(s):
                return _finalize(s, "Halted: model kept referencing code that does not exist.")
            debugger.diagnose(s)
            continue

        s = node_test(s)
        # Automatic rollback on test failure (#2).
        if not s.test_results.get("passed"):
            s = node_rollback(s)
            if _exhausted(s):
                return _finalize(s, "Halted: tests still failing after max iterations.")
            debugger.diagnose(s)
            continue

        s = node_security(s)
        s = node_verify(s)
        s = node_panel_review(s)

        # Risk + human-approval gate (#10): stage risky changes, do not auto-apply.
        approvals.classify(s)
        if approvals.requires_approval(s):
            s.pending_approval = True
            publish_step(s.run_id, agent_role="supervisor", model="-", phase="approval",
                         status="awaiting", detail={"risky_actions": s.risky_actions})
            return _finalize(s, "Awaiting human approval for risky actions.")

        decision = route(s)
        if decision == "approved":
            s = node_document(s)
            s = node_explain(s)
            s = node_deploy(s)
            memory.record(s)  # codebase memory graph (#3)
            return _finalize(s)

        s = node_rollback(s)
        if decision == "rollback_final":
            return _finalize(s, "Halted: could not produce a verified change within budget.")
        debugger.diagnose(s)
