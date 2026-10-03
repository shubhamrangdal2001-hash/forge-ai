from __future__ import annotations

import os
import asyncio
import re
import subprocess

from fastapi import APIRouter, HTTPException

from ..schemas import TerminalCommand
from ..workspace_guard import get_workspace

router = APIRouter(prefix="/api/terminal", tags=["terminal"])

MAX_COMMAND_LENGTH = 500
MAX_TIMEOUT_SECONDS = 120

BLOCKED_COMMANDS = [
    (re.compile(pattern, re.IGNORECASE), reason)
    for pattern, reason in [
        (r"\brm\s+-rf\b", "Recursive force delete is blocked."),
        (r"\bdel\s+/[sq]\b", "Recursive/silent delete is blocked."),
        (r"\brmdir\s+/s\b", "Recursive directory delete is blocked."),
        (r"\bformat\b", "Disk formatting is blocked."),
        (r"\bdiskpart\b", "Disk partition tools are blocked."),
        (r"\bshutdown\b", "System shutdown is blocked."),
        (r"\brestart-computer\b", "System restart is blocked."),
        (r"\bstop-computer\b", "System shutdown is blocked."),
        (r"\bstop-process\b", "Killing processes from Forge terminal is blocked."),
        (r"\btaskkill\b.*\s/f\b", "Force-killing processes from Forge terminal is blocked."),
        (r"\bstart-process\b", "Launching detached processes is blocked."),
        (r"\bcmd\s+/c\s+start\b", "Opening external windows is blocked."),
        (r"\bgit\s+reset\s+--hard\b", "Destructive git reset is blocked."),
        (r"\bgit\s+clean\s+-[fdx]+", "Destructive git clean is blocked."),
        (r"\bset-executionpolicy\b", "Changing PowerShell execution policy is blocked."),
    ]
]


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


def _blocked_reason(command: str) -> str | None:
    for pattern, reason in BLOCKED_COMMANDS:
        if pattern.search(command):
            return reason
    return None


def _run_command(argv: list[str], cwd, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        **_windows_process_options(),
    )


@router.post("/run")
async def run_terminal_command(body: TerminalCommand):
    command = body.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="Command is required.")
    if "\x00" in command or "\n" in command or "\r" in command:
        raise HTTPException(status_code=400, detail="Only one terminal command can run at a time.")
    if len(command) > MAX_COMMAND_LENGTH:
        raise HTTPException(status_code=400, detail=f"Command must be {MAX_COMMAND_LENGTH} characters or fewer.")
    blocked = _blocked_reason(command)
    if blocked:
        raise HTTPException(status_code=400, detail=blocked)

    workspace = get_workspace(body.project_id)
    timeout = max(1, min(int(body.timeout or 30), MAX_TIMEOUT_SECONDS))
    if os.name == "nt":
        argv = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
    else:
        argv = ["/bin/sh", "-lc", command]

    try:
        proc = await asyncio.to_thread(_run_command, argv, workspace.root, timeout)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "command": command,
            "cwd": str(workspace.root),
            "exit_code": 124,
            "stdout": stdout,
            "stderr": (stderr + f"\nCommand timed out after {timeout}s.").strip(),
            "timed_out": True,
        }
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "command": command,
        "cwd": str(workspace.root),
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "timed_out": False,
    }
