"""The verification spine: lint -> type -> test -> build, each in the sandbox.
The critic gates on these mechanical signals before any change is surfaced.
"""
from pathlib import Path

from .sandbox import run_in_sandbox
from ..intelligence.workspace import project_root

# Ordered checks. Each returns a pass/fail with captured output.
STATIC_CHECKS = [
    ("ruff", "ruff check ."),
    ("mypy", "mypy ."),
    ("eslint", "npx --no-install eslint ."),
    ("build", "npm run -s build"),
]

TEST_CHECKS = [
    ("pytest", "pytest -q"),
    ("jest", "npx --no-install jest --silent"),
]


def _has_any(root: Path, patterns: list[str]) -> bool:
    return any(any(root.rglob(pattern)) for pattern in patterns)


def _run(project_id: str, checks) -> dict:
    results, failures = {}, []
    for name, cmd in checks:
        out = run_in_sandbox(project_id, cmd)
        ok = out["exit_code"] == 0
        results[name] = {"passed": ok, "output": out["stdout"][-2000:]}
        if not ok:
            failures.append(name)
    return {"passed": len(failures) == 0, "failures": failures, "checks": results}


def run_static_checks(project_id: str) -> dict:
    root = project_root(project_id)
    checks = []
    if _has_any(root, ["*.py"]):
        checks.extend([("ruff", "ruff check ."), ("mypy", "mypy .")])
    if (root / "package.json").exists():
        checks.extend([("eslint", "npx --no-install eslint ."), ("build", "npm run -s build")])
    if not checks:
        return {"passed": True, "failures": [], "checks": {}, "skipped": "no supported project files found"}
    return _run(project_id, checks)


def run_tests(project_id: str) -> dict:
    root = project_root(project_id)
    checks = []
    if (root / "tests").exists() or _has_any(root, ["test_*.py", "*_test.py"]):
        checks.append(("pytest", "pytest -q"))
    if (root / "package.json").exists() and (
        (root / "__tests__").exists()
        or _has_any(root, ["*.test.ts", "*.test.tsx", "*.spec.ts", "*.spec.tsx", "*.test.js", "*.spec.js"])
    ):
        checks.append(("jest", "npx --no-install jest --silent"))
    if not checks:
        return {"passed": True, "failures": [], "checks": {}, "skipped": "no runnable tests found"}
    return _run(project_id, checks)
