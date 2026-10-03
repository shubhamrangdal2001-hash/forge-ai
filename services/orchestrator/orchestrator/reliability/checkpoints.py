"""Deterministic checkpointing via git. Every patch loop snapshots first so a
failed verify can roll back to a known-good state — no partial corruption.
"""
import subprocess
import shutil
import uuid
from ..intelligence.workspace import project_root


def _git(root, *args: str) -> subprocess.CompletedProcess[str] | None:
    if not shutil.which("git"):
        return None
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    except FileNotFoundError:
        return None


def _git_output(root, *args: str) -> str:
    proc = _git(root, *args)
    if proc is None:
        return ""
    return proc.stdout.strip()


def snapshot(project_id: str) -> str:
    """Stash-like checkpoint; returns a checkpoint id (a git stash/tag ref)."""
    cid = f"forge-ckpt-{uuid.uuid4().hex[:8]}"
    root = project_root(project_id)
    inside_worktree = _git_output(root, "rev-parse", "--is-inside-work-tree") == "true"
    if not inside_worktree:
        return f"no-git:{cid}"

    _git_output(root, "add", "-A")
    _git_output(root, "commit", "-m", cid, "--allow-empty")
    return _git_output(root, "rev-parse", "HEAD") or cid


def restore(project_id: str, checkpoint_id: str | None) -> None:
    if not checkpoint_id or checkpoint_id.startswith("no-git:"):
        return
    root = project_root(project_id)
    _git_output(root, "reset", "--hard", checkpoint_id)
