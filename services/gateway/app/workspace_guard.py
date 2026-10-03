from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


def _resolve_root() -> Path:
    env_root = os.getenv("FORGE_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    source = Path(__file__).resolve()
    for parent in source.parents:
        if (
            (parent / "docker-compose.yml").exists()
            or (parent / ".env.example").exists()
            or (parent / ".forge-state").exists()
        ):
            return parent

    if source.parent.name == "app":
        return source.parent.parent.resolve()

    return Path.cwd().resolve()


ROOT = _resolve_root()
STATE_DIR = ROOT / ".forge-state"
PROJECTS_FILE = STATE_DIR / "projects.json"
DEFAULT_WORKSPACE_ROOT = ROOT / ".forge-workspaces" / "demo"

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".next",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
}


class WorkspaceError(ValueError):
    pass


@dataclass(frozen=True)
class Workspace:
    project_id: str
    root: Path
    warnings: list[str]


def _load_projects() -> dict:
    if not PROJECTS_FILE.exists():
        return {}
    try:
        return json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_projects(projects: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_FILE.write_text(json.dumps(projects, indent=2), encoding="utf-8")


def _risky_root_warnings(root: Path) -> list[str]:
    home = Path.home().resolve()
    warnings: list[str] = []
    risky_names = {"Desktop", "Downloads", "Documents"}
    system_roots = {
        Path(os.environ.get("WINDIR", "C:/Windows")).resolve(),
        Path(os.environ.get("ProgramFiles", "C:/Program Files")).resolve(),
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")).resolve(),
    }
    if root in system_roots or any(parent in system_roots for parent in root.parents):
        warnings.append("System folders are risky project roots. Select a source-code folder instead.")
    if root.parent == home and root.name in risky_names:
        warnings.append(f"{root.name} is broad; choose the exact project folder when possible.")
    if any(part.startswith(".") for part in root.parts if part not in {root.anchor, "."}):
        warnings.append("Hidden folders can contain tool state. Forge will still enforce this root boundary.")
    return warnings


def normalize_root(path: str) -> Workspace:
    if not path or not path.strip():
        raise WorkspaceError("Project folder is required.")
    root = Path(path).expanduser()
    if not root.is_absolute():
        raise WorkspaceError("Project folder must be an absolute path.")
    root = root.resolve()
    if not root.exists():
        raise WorkspaceError("Project folder does not exist.")
    if not root.is_dir():
        raise WorkspaceError("Project folder must be a directory.")
    return Workspace(project_id="", root=root, warnings=_risky_root_warnings(root))


def register_project(project_id: str, path: str) -> Workspace:
    workspace = normalize_root(path)
    projects = _load_projects()
    projects[project_id] = {
        "project_id": project_id,
        "root": str(workspace.root),
        "warnings": workspace.warnings,
    }
    _save_projects(projects)
    return Workspace(project_id=project_id, root=workspace.root, warnings=workspace.warnings)


def get_workspace(project_id: str) -> Workspace:
    projects = _load_projects()
    data = projects.get(project_id)
    if data:
        root = Path(data["root"]).resolve()
        return Workspace(project_id=project_id, root=root, warnings=data.get("warnings", []))
    DEFAULT_WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    return Workspace(project_id=project_id, root=DEFAULT_WORKSPACE_ROOT.resolve(), warnings=[])


def recent_projects() -> list[dict]:
    return list(_load_projects().values())


def validate_path(project_id: str, candidate: str, *, for_write: bool = False) -> Path:
    workspace = get_workspace(project_id)
    root = workspace.root.resolve()
    path = Path(candidate)
    if path.is_absolute():
        target = path.resolve()
    else:
        target = (root / path).resolve()

    if target != root and root not in target.parents:
        raise WorkspaceError("Blocked path outside the selected project folder.")
    if ".." in Path(candidate).parts:
        raise WorkspaceError("Blocked path traversal outside the selected project folder.")
    if for_write and target == root:
        raise WorkspaceError("Refusing to overwrite the project folder itself.")
    return target


def backup_file(project_id: str, relative_path: str, diff_id: str) -> str | None:
    source = validate_path(project_id, relative_path)
    if not source.exists() or not source.is_file():
        return None
    workspace = get_workspace(project_id)
    backup_root = workspace.root / ".forge-backups" / diff_id
    backup = backup_root / Path(relative_path)
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, backup)
    return str(backup)


def tree_for(project_id: str, *, max_depth: int = 4, max_entries: int = 400) -> list[dict]:
    workspace = get_workspace(project_id)
    count = 0

    def walk(path: Path, depth: int) -> list[dict]:
        nonlocal count
        if depth > max_depth or count >= max_entries:
            return []
        children: list[dict] = []
        try:
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return []
        for entry in entries:
            if count >= max_entries:
                break
            if entry.name in IGNORED_DIRS:
                continue
            relative = entry.relative_to(workspace.root).as_posix()
            count += 1
            if entry.is_dir():
                children.append({"path": relative, "type": "dir", "children": walk(entry, depth + 1)})
            elif entry.is_file():
                children.append({"path": relative, "type": "file"})
        return children

    return walk(workspace.root, 1)
