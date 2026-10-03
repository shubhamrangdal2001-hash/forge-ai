from pydantic import BaseModel
from typing import Any, Optional


class RunCreate(BaseModel):
    project_id: str
    goal: str
    token_budget: int = 200_000
    router_mode: str = "accuracy"   # speed | accuracy | auto  (#4)
    local_only: bool = False         # hybrid local/cloud mode (#7)
    # User's model picks: task value -> model id, or {"all": "<model>"} for one
    # model everywhere. Empty = smart per-task defaults.
    models: dict[str, str] = {}


class RunOut(BaseModel):
    id: str
    status: str
    goal: str


class DiffDecision(BaseModel):
    accepted: bool
    backup: bool = True
    selected_files: list[str] | None = None
    allow_delete: bool = False


class ProjectSelect(BaseModel):
    project_id: str = "demo"
    path: str


class FileChange(BaseModel):
    file_path: str
    content: str


class PatchChange(BaseModel):
    file_path: str
    patch: str


class StageDiff(BaseModel):
    project_id: str
    files: list[FileChange] = []
    patches: list[PatchChange] = []


class SearchQuery(BaseModel):
    project_id: str
    query: str
    k: int = 8


class TerminalCommand(BaseModel):
    project_id: str
    command: str
    timeout: int = 30


class StepEvent(BaseModel):
    agent_role: str
    model: str
    # plan|recall|write_tests|patch|hallucination|test|security|verify|review|
    # explain|document|deploy|approval|rollback|report
    phase: str
    status: str         # running|passed|failed|awaiting|done
    detail: Optional[Any] = None
