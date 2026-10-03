"""Risk classification + human-approval gate (differentiator #10).

Forge auto-applies low-risk changes but refuses to silently perform dangerous
actions. Patches and the plan are scanned for risky operations (deleting files,
changing dependencies, DB migrations, infra/deploy edits, secret/network/auth
changes). Anything risky must be explicitly approved by a human before the run
finalizes — the agent stages it and waits instead of guessing.
"""
from __future__ import annotations
import re

RISK_RULES = [
    ("dependency_change", re.compile(r"(requirements\.txt|package\.json|pyproject\.toml|poetry\.lock|package-lock\.json)")),
    ("db_migration",      re.compile(r"(migrations?/|alembic|CREATE TABLE|DROP TABLE|ALTER TABLE)", re.I)),
    ("infra_or_deploy",   re.compile(r"(Dockerfile|docker-compose|\.github/workflows|k8s|kubernetes|deploy/|terraform)", re.I)),
    ("auth_or_secrets",   re.compile(r"(SECRET|PASSWORD|TOKEN|api[_-]?key|auth|jwt|oauth)", re.I)),
    ("network_egress",    re.compile(r"(requests\.|httpx\.|fetch\(|urllib|socket\.)", re.I)),
]
DELETE_HUNK = re.compile(r"^-(?!--)", re.MULTILINE)  # net deletions in a diff


def classify(state) -> list[dict]:
    actions: list[dict] = []
    for p in state.patches:
        path = p.get("file_path", "")
        diff = p.get("patch", "") or ""
        blob = f"{path}\n{diff}"
        for kind, rx in RISK_RULES:
            if rx.search(blob):
                actions.append({"kind": kind, "file": path, "detail": path})
        # large deletion heuristic
        if len(DELETE_HUNK.findall(diff)) >= 20:
            actions.append({"kind": "large_deletion", "file": path, "detail": f"{len(DELETE_HUNK.findall(diff))} lines removed"})
    # deployment is always gated
    if state.deploy_requested:
        actions.append({"kind": "deployment", "file": "-", "detail": "ship to environment"})
    state.risky_actions = actions
    return actions


def requires_approval(state) -> bool:
    if not state.risky_actions:
        return False
    if state.auto_approve_risky:
        return False
    approved = set(state.approved_actions)
    return any(a["kind"] not in approved for a in state.risky_actions)
