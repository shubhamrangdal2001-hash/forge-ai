"""Per-project Docker sandbox. Patches and verification commands run here —
never on the host. Network is off by default; mounts are scoped to the project
workspace.
"""
import os
import subprocess
from ..intelligence.workspace import project_root

try:
    import docker
except Exception:
    docker = None

SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "forge-sandbox:latest")


def _client():
    if docker is None:
        return None
    try:
        return docker.from_env()
    except Exception:
        return None


def apply_patches(project_id: str, patches: list[dict]) -> None:
    """Apply unified-diff patches inside the workspace."""
    root = project_root(project_id)
    for p in patches:
        diff = p.get("patch", "")
        if not diff.strip():
            continue
        proc = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", "-"],
            input=diff,
            text=True,
            cwd=root,
            capture_output=True,
        )
        if proc.returncode != 0 and ("new file mode" in diff or "--- /dev/null" in diff):
            _apply_new_file_diff(root, diff)


def _apply_new_file_diff(root, diff: str) -> None:
    """Fallback for starter workspaces that are not Git repos yet."""
    root = root.resolve()
    target = None
    lines: list[str] = []
    in_hunk = False

    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            relative = line.removeprefix("+++ b/")
            target = (root / relative).resolve()
            if root != target and root not in target.parents:
                raise ValueError(f"Patch target escapes workspace: {relative}")
            continue
        if line.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk or target is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])

    if target is None:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_in_sandbox(project_id: str, command: str, timeout: int = 300) -> dict:
    """Run a command in the sandbox container (falls back to subprocess in dev)."""
    root = project_root(project_id)
    client = _client()
    if client is None:
        proc = subprocess.run(command, shell=True, cwd=root, capture_output=True, text=True, timeout=timeout)
        return {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    container = client.containers.run(
        SANDBOX_IMAGE, command=["/bin/sh", "-c", command],
        volumes={str(root): {"bind": "/workspace", "mode": "rw"}},
        working_dir="/workspace", network_disabled=True, mem_limit="2g",
        detach=True,
    )
    result = container.wait(timeout=timeout)
    logs = container.logs().decode(errors="ignore")
    container.remove(force=True)
    return {"exit_code": result.get("StatusCode", 1), "stdout": logs, "stderr": ""}
