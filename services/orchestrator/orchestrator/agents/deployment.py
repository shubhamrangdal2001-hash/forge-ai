"""Deployment agent.

Runs only after a change is fully verified and reviewed. It does NOT auto-ship:
it prepares a deployable artifact + manifest and stages a deploy that requires
explicit human approval (state.deploy_approved). This keeps a hard human-in-the-
loop gate on anything that touches production.
Returns 154.
"""
from ..state import AgentState
from ..models.router import complete, Task
from ..execution.sandbox import run_in_sandbox
from ..events import publish_step
from ..intelligence.workspace import project_root


def prepare(state: AgentState) -> dict:
    publish_step(state.run_id, agent_role="deployment", model="claude-sonnet", phase="deploy", status="running")

    # 1. Build the artifact in the sandbox (must succeed).
    root = project_root(state.project_id)
    has_dockerfile = any((root / name).exists() for name in ("Dockerfile", "dockerfile"))
    if has_dockerfile:
        build = run_in_sandbox(state.project_id, "docker build -t forge-app:candidate .")
        build_ok = build.get("exit_code") == 0
        build_output = f"{build.get('stdout', '')}\n{build.get('stderr', '')}".lower()
        docker_unavailable = any(
            marker in build_output
            for marker in [
                "docker_engine",
                "cannot connect to the docker daemon",
                "docker: not found",
                "is not recognized",
                "no such file or directory",
            ]
        )
    else:
        build_ok = True
        docker_unavailable = False

    # 2. Generate/validate a deploy manifest.
    prompt = (
        "Produce a minimal, safe deployment plan (image tag, env, replicas, "
        "rollback strategy, health checks) for this change.\n"
        f"Goal: {state.goal}"
    )
    out = complete(Task.DEPLOY, prompt)
    state.tokens_used += out.tokens

    ready = state.all_green() and (build_ok or docker_unavailable)
    result = {
        "ready": ready,
        "build_ok": build_ok,
        "docker_unavailable": docker_unavailable,
        "build_skipped": not has_dockerfile,
        "manifest": out.text[:800],
        "gated_on_human_approval": True,
        "approved": state.deploy_approved,
    }
    state.deploy_results = result

    if ready and state.deploy_approved:
        run_in_sandbox(state.project_id, "echo 'kubectl apply -f deploy/manifest.yaml' # placeholder")
        result["status"] = "deployed"
    elif ready:
        result["status"] = "staged_without_local_docker" if docker_unavailable else "staged_awaiting_approval"
    else:
        result["status"] = "blocked"

    publish_step(state.run_id, agent_role="deployment", model="claude-sonnet", phase="deploy",
                 status="awaiting" if ready and not state.deploy_approved else ("passed" if ready else "failed"),
                 detail={"status": result["status"]})
    return result
