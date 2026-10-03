from .celery_app import celery_app
from .state import AgentState
from .graph import run_graph


@celery_app.task(name="run_agents")
def run_agents(run_id: str, project_id: str, goal: str, token_budget: int = 200_000,
               router_mode: str = "accuracy", local_only: bool = False,
               model_overrides: dict | None = None):
    state = AgentState(
        run_id=run_id,
        project_id=project_id,
        goal=goal,
        token_budget=token_budget,
        router_mode=router_mode,
        local_only=local_only,
        model_overrides=model_overrides or {},
    )
    final = run_graph(state)
    return {
        "run_id": run_id,
        "failed": final.failed,
        "pending_approval": final.pending_approval,
        "cost_usd": final.cost_usd,
        "explanation": final.explanation,
        "patches": final.patches,
    }


@celery_app.task(name="index_repo")
def index_repo(project_id: str):
    from .intelligence import indexer
    return indexer.index_project(project_id)
