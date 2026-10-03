from __future__ import annotations

import difflib
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import DiffDecision, StageDiff
from ..workspace_guard import WorkspaceError, backup_file, get_workspace, validate_path

router = APIRouter(prefix="/api/diffs", tags=["diffs"])

_PENDING: dict[str, dict] = {}


def _risk_for(patches: list[dict]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    level = "low"
    for patch in patches:
        text = patch["patch"]
        path = patch["file_path"]
        if "deleted file mode" in text:
            level = "high"
            reasons.append(f"{path}: deletes a file")
        if path.endswith((".env", ".pem", ".key", ".p12", ".sqlite", ".db")):
            level = "high"
            reasons.append(f"{path}: sensitive file type")
        if len(text.splitlines()) > 300 and level != "high":
            level = "medium"
            reasons.append(f"{path}: large diff")
    return level, reasons or ["ordinary text/code edit"]


def _patch_files(diff: str) -> list[str]:
    files: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            files.append(line.removeprefix("+++ b/"))
        elif line.startswith("--- a/"):
            candidate = line.removeprefix("--- a/")
            if candidate not in files:
                files.append(candidate)
    return [file for file in files if file != "/dev/null"]


def _diff_from_content(project_id: str, file_path: str, content: str) -> dict:
    target = validate_path(project_id, file_path, for_write=True)
    before = target.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True) if target.exists() else []
    after = content.splitlines(keepends=True)
    if content and not content.endswith("\n"):
        after[-1] = after[-1] + "\n"
    diff = "".join(
        difflib.unified_diff(
            before,
            after,
            fromfile=f"a/{file_path}" if before else "/dev/null",
            tofile=f"b/{file_path}",
        )
    )
    if not diff.startswith("diff --git"):
        mode = "new file mode 100644\n" if not before else ""
        diff = f"diff --git a/{file_path} b/{file_path}\n{mode}{diff}"
    return {"file_path": file_path, "patch": diff}


def _apply_new_file_diff(root: Path, diff: str) -> None:
    target: Path | None = None
    lines: list[str] = []
    in_hunk = False
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            target = (root / line.removeprefix("+++ b/")).resolve()
            continue
        if line.startswith("@@"):
            in_hunk = True
            continue
        if in_hunk and line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
    if target is None:
        raise WorkspaceError("Patch does not name a target file.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _windows_process_options() -> dict:
    if os.name != "nt":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": subprocess.CREATE_NO_WINDOW,
        "startupinfo": startupinfo,
    }


def _git_apply(root: Path, diff: str) -> subprocess.CompletedProcess[str] | None:
    if not shutil.which("git"):
        return None
    try:
        return subprocess.run(
            ["git", "apply", "--whitespace=nowarn", "-"],
            input=diff,
            text=True,
            cwd=root,
            capture_output=True,
            **_windows_process_options(),
        )
    except FileNotFoundError:
        return None


def _apply_patch(project_id: str, patch: dict) -> None:
    workspace = get_workspace(project_id)
    for file_path in _patch_files(patch["patch"]):
        validate_path(project_id, file_path, for_write=True)

    proc = _git_apply(workspace.root, patch["patch"])
    if proc is None and ("new file mode" in patch["patch"] or "--- /dev/null" in patch["patch"]):
        _apply_new_file_diff(workspace.root, patch["patch"])
        return
    if proc is None:
        raise WorkspaceError("Git is required to apply non-new-file patches in this workspace.")
    if proc.returncode != 0 and ("new file mode" in patch["patch"] or "--- /dev/null" in patch["patch"]):
        _apply_new_file_diff(workspace.root, patch["patch"])
        return
    if proc.returncode != 0:
        raise WorkspaceError(proc.stderr.strip() or "Patch failed to apply.")


@router.post("/stage")
async def stage_diff(body: StageDiff):
    patches = [_diff_from_content(body.project_id, f.file_path, f.content) for f in body.files]
    for patch in body.patches:
        validate_path(body.project_id, patch.file_path, for_write=True)
        for file_path in _patch_files(patch.patch):
            validate_path(body.project_id, file_path, for_write=True)
        patches.append({"file_path": patch.file_path, "patch": patch.patch})
    if not patches:
        raise HTTPException(status_code=400, detail="No files or patches were provided.")

    risk_level, risk_reasons = _risk_for(patches)
    diff_id = str(uuid.uuid4())
    record = {
        "id": diff_id,
        "project_id": body.project_id,
        "status": "staged",
        "files_changed": sorted({p["file_path"] for p in patches}),
        "risk_level": risk_level,
        "risk_reasons": risk_reasons,
        "patches": patches,
        "backups": [],
    }
    _PENDING[diff_id] = record
    return record


@router.get("/{diff_id}")
async def get_diff(diff_id: str):
    record = _PENDING.get(diff_id)
    if not record:
        raise HTTPException(status_code=404, detail="Staged diff not found.")
    return record


@router.post("/{diff_id}/decision")
async def decide(diff_id: str, body: DiffDecision):
    record = _PENDING.get(diff_id)
    if not record:
        raise HTTPException(status_code=404, detail="Staged diff not found.")
    if not body.accepted:
        record["status"] = "rejected"
        return record

    selected = set(body.selected_files or record["files_changed"])
    applied: list[str] = []
    backups: list[str] = []
    for patch in record["patches"]:
        if patch["file_path"] not in selected:
            continue
        if "deleted file mode" in patch["patch"] and not body.allow_delete:
            raise HTTPException(status_code=400, detail="Deletion requires explicit allow_delete approval.")
        try:
            if body.backup:
                for file_path in _patch_files(patch["patch"]):
                    backup = backup_file(record["project_id"], file_path, diff_id)
                    if backup:
                        backups.append(backup)
            _apply_patch(record["project_id"], patch)
            applied.append(patch["file_path"])
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    record["status"] = "saved"
    record["applied_files"] = applied
    record["backups"] = backups
    return record
