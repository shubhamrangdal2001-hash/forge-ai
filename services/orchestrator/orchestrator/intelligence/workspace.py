import json
import os
from pathlib import Path

DEFAULT_WORKSPACES = Path(__file__).resolve().parents[4] / ".forge-workspaces"
WORKSPACES = Path(os.getenv("FORGE_WORKSPACES", str(DEFAULT_WORKSPACES)))
STATE_FILE = Path(__file__).resolve().parents[4] / ".forge-state" / "projects.json"


def _registered_project_root(project_id: str) -> Path | None:
    if os.getenv("FORGE_WORKSPACES"):
        return None
    try:
        projects = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    data = projects.get(project_id)
    root = data.get("root") if isinstance(data, dict) else None
    if not root:
        return None

    path = Path(root).expanduser().resolve()
    return path if path.exists() and path.is_dir() else None


def project_root(project_id: str) -> Path:
    registered = _registered_project_root(project_id)
    if registered is not None:
        return registered
    root = WORKSPACES / project_id
    root.mkdir(parents=True, exist_ok=True)
    return root
