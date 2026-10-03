"""Coding agent: produces unified-diff patches grounded in retrieved context."""
from __future__ import annotations

import json
import re

from ..models.router import Task, complete
from ..state import AgentState

CODE_PROMPT = """You are the Coder. Implement the task as unified diffs.
Inspect the provided context, touch only files needed for the task, and match
repo conventions. Return ONLY JSON, with no prose and no markdown fences.
The JSON must be a list of objects with "file_path" and "patch". Each patch
must be a complete applyable unified diff, preferably in git diff format.
If you create a new file, use --- /dev/null, +++ b/path, and a valid @@ hunk.
Task: {task}
Context: {context}
"""


def _looks_like_unified_diff(text: str) -> bool:
    return bool(
        text.strip().startswith("diff --git ")
        or re.search(r"(?m)^--- .+\n\+\+\+ .+\n@@", text)
    )


def _strip_fence(text: str) -> str:
    stripped = text.strip()
    match = re.fullmatch(r"```(?:json|diff)?\s*(.*?)\s*```", stripped, re.DOTALL)
    return match.group(1).strip() if match else stripped


def _json_candidates(text: str) -> list[str]:
    stripped = _strip_fence(text)
    candidates = [stripped]
    for opener, closer in [("[", "]"), ("{", "}")]:
        start = stripped.find(opener)
        end = stripped.rfind(closer)
        if 0 <= start < end:
            candidates.append(stripped[start : end + 1])
    return candidates


def _parse_patch_list(text: str) -> list[dict]:
    parsed = None
    for candidate in _json_candidates(text):
        try:
            parsed = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue
    if parsed is None:
        return []

    if isinstance(parsed, dict):
        items = parsed.get("patches") or parsed.get("files") or [parsed]
    else:
        items = parsed
    if not isinstance(items, list):
        return []

    patches: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        file_path = item.get("file_path") or item.get("path") or item.get("file")
        patch = item.get("patch") or item.get("diff")
        if isinstance(file_path, str) and isinstance(patch, str) and _looks_like_unified_diff(patch):
            patches.append({"file_path": file_path, "patch": patch})
    return patches


def write_patches(s: AgentState) -> list[dict]:
    patches: list[dict] = []
    for task in s.plan:
        prompt = CODE_PROMPT.format(task=task, context=s.context.get("plan_hits", []))
        out = complete(Task.CODE, prompt)
        s.tokens_used += out.tokens
        parsed = _parse_patch_list(out.text)
        if parsed:
            patches.extend(parsed)
        elif _looks_like_unified_diff(_strip_fence(out.text)):
            patches.append({"file_path": (task.get("files") or ["NOTES.md"])[0], "patch": _strip_fence(out.text)})
        else:
            s.context.setdefault("model_output_errors", []).append({
                "task": task.get("id") or task.get("summary") or "task",
                "model": out.model,
                "reason": "Model did not return JSON patches or a unified diff.",
                "preview": out.text[:500],
            })

    if not patches and s.plan:
        s.failed = True
        s.explanation = "No source files changed because the selected model did not return an applyable diff."
    return patches
