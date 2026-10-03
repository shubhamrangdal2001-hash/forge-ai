from fastapi import APIRouter, HTTPException, Query

from ..schemas import ProjectSelect
from ..workspace_guard import (
    WorkspaceError,
    get_workspace,
    recent_projects,
    register_project,
    tree_for,
    validate_path,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
async def list_projects():
    return recent_projects()


@router.post("/select")
async def select_project(body: ProjectSelect):
    try:
        workspace = register_project(body.project_id, body.path)
    except WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "project_id": body.project_id,
        "root": str(workspace.root),
        "warnings": workspace.warnings,
    }


@router.get("/{project_id}")
async def project_info(project_id: str):
    workspace = get_workspace(project_id)
    return {
        "project_id": project_id,
        "root": str(workspace.root),
        "warnings": workspace.warnings,
    }


@router.get("/{project_id}/tree")
async def file_tree(project_id: str):
    return tree_for(project_id)


@router.get("/{project_id}/file")
async def read_file(project_id: str, path: str = Query(...)):
    try:
        target = validate_path(project_id, path)
    except WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found inside selected workspace.")
    return {"path": path, "content": target.read_text(encoding="utf-8", errors="replace")}


@router.post("/{project_id}/index")
async def index_project(project_id: str):
    # Enqueue an indexing job (tree-sitter + ripgrep + embeddings + graph).
    from orchestrator.tasks import index_repo  # type: ignore
    index_repo.delay(project_id)
    return {"status": "indexing_started", "project_id": project_id}
