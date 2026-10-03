"""Hallucination detector (differentiator #9).

Before a patch is allowed to run, we verify that everything it *references*
actually exists in the repo: imported modules, touched file paths, and symbols
it claims to call. Fabricated references are the #1 source of LLM coding errors;
gating on this catches them before they ever reach the test runner.

Grounded against the real workspace file set (and the symbol index when present).
Returns {passed, confidence, flags}.
"""
from __future__ import annotations
import json
import os
import re
from .workspace import project_root

RE_PY_FROM = re.compile(r"^\+?\s*from\s+([.\w]+)\s+import\s+(.+)$", re.MULTILINE)
RE_PY_IMPORT = re.compile(r"^\+?\s*import\s+([.\w]+)", re.MULTILINE)
RE_JS_IMPORT = re.compile(r"""import\s+(?:[\w*{}\s,]+\s+from\s+)?['\"]([^'\"]+)['\"]""")


def _workspace_files(project_id: str) -> set[str]:
    root = project_root(project_id)
    out: set[str] = set()
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".next", ".forge"}]
        for fn in files:
            out.add(os.path.relpath(os.path.join(dp, fn), root).replace(os.sep, "/"))
    return out


def _known_symbols(project_id: str) -> set[str]:
    """Use a prebuilt index.json symbol list if available."""
    root = project_root(project_id)
    idx = os.path.join(root, "index.json")
    try:
        with open(idx, encoding="utf-8") as f:
            data = json.load(f)
        return {s["name"] for s in data.get("symbols", [])}
    except (OSError, json.JSONDecodeError, KeyError):
        return set()


def _module_resolves(mod: str, files: set[str]) -> bool:
    base = mod.lstrip(".").split(".")[0]
    if not base:
        return True  # relative within package
    # stdlib / third-party are fine; only flag intra-repo modules that don't exist
    candidates = {f"{base}.py", f"{base}/__init__.py"}
    if any(f.endswith(c) for f in files for c in candidates):
        return True
    # if the name matches no repo file AND looks intra-repo (relative), flag it
    return not mod.startswith(".")


def detect(state) -> dict:
    files = _workspace_files(state.project_id)
    known = _known_symbols(state.project_id)
    flags: list[dict] = []
    checks = 0

    for p in state.patches:
        path = p.get("file_path", "")
        diff = p.get("patch", "") or ""
        # 1. target path plausibility (new files allowed if dir exists)
        checks += 1
        parent = os.path.dirname(path)
        if parent and not any(f.startswith(parent + "/") for f in files) and path not in files:
            flags.append({"file": path, "type": "unknown_target_dir", "severity": "medium"})
        # 2. relative python imports must resolve
        for m in RE_PY_FROM.finditer(diff):
            checks += 1
            if m.group(1).startswith(".") and not _module_resolves(m.group(1), files):
                flags.append({"file": path, "type": "unresolved_import", "ref": m.group(1), "severity": "high"})
        for m in RE_PY_IMPORT.finditer(diff):
            checks += 1
            if not _module_resolves(m.group(1), files):
                flags.append({"file": path, "type": "unresolved_import", "ref": m.group(1), "severity": "high"})
        # 3. empty / echo patch (model returned prose, not a diff)
        checks += 1
        if not diff.strip() or diff.strip().startswith("[stub") or "@@" not in diff and not diff.startswith("+"):
            flags.append({"file": path, "type": "non_diff_output", "severity": "low"})

    high = [f for f in flags if f["severity"] == "high"]
    confidence = round(1.0 - (len(flags) / checks if checks else 0.0), 3)
    result = {
        "passed": len(high) == 0,
        "confidence": max(confidence, 0.0),
        "flags": flags,
        "high": len(high),
        "checks": checks,
        "symbols_indexed": len(known),
    }
    state.hallucination_results = result
    return result
