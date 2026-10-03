"""Transparent verification report (differentiator #5).

Every run produces a single structured report that shows exactly why a change
was accepted or rejected: which gates ran, their results, the hallucination
confidence, the multi-agent review verdict, risky actions, and the full cost
breakdown. This is the artifact a human reviews instead of blindly trusting the
agent.
"""
from __future__ import annotations

from ..models.router import cost_summary


def _artifact_preview(patch: dict) -> dict | None:
    file_path = patch.get("file_path")
    diff = patch.get("patch", "")
    if not file_path or not diff:
        return None

    lines: list[str] = []
    in_hunk = False
    for line in diff.splitlines():
        if line.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])

    content = "\n".join(lines)
    if not content.strip():
        return None
    truncated = len(content) > 6000
    return {
        "file_path": file_path,
        "content": content[:6000],
        "truncated": truncated,
    }


def _risk_for(patches: list[dict]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    level = "low"
    for patch in patches:
        file_path = patch.get("file_path", "")
        diff = patch.get("patch", "")
        if "deleted file mode" in diff:
            level = "high"
            reasons.append(f"{file_path}: deletes a file")
        if file_path.endswith((".env", ".pem", ".key", ".p12", ".sqlite", ".db")):
            level = "high"
            reasons.append(f"{file_path}: sensitive file type")
        if len(diff.splitlines()) > 300 and level != "high":
            level = "medium"
            reasons.append(f"{file_path}: large diff")
    return level, reasons or ["ordinary text/code edit"]


def build(state) -> dict:
    cost = cost_summary(state.run_id)
    state.cost_usd = cost["total_cost_usd"]
    risk_level, risk_reasons = _risk_for(state.patches)
    gates = {
        "tests": {"passed": bool(state.test_results.get("passed")), "failures": state.test_results.get("failures", [])},
        "hallucination": {
            "passed": bool(state.hallucination_results.get("passed", True)),
            "confidence": state.hallucination_results.get("confidence"),
            "flags": state.hallucination_results.get("flags", []),
        },
        "security": {"passed": bool(state.security_results.get("passed")), "high": state.security_results.get("high", 0)},
        "static": {"passed": bool(state.verify_results.get("passed")), "failures": state.verify_results.get("failures", [])},
        "review": {"approved": bool(state.review_results.get("approved")), "panel": state.panel_results.get("votes", [])},
    }
    report = {
        "run_id": state.run_id,
        "goal": state.goal,
        "verdict": "accepted"
        if (state.all_green() and not state.pending_approval)
        else ("awaiting_approval" if state.pending_approval else "rejected"),
        "router_mode": state.router_mode,
        "hybrid_local_only": state.local_only,
        "iterations": state.iteration,
        "files_changed": sorted({p.get("file_path") for p in state.patches if p.get("file_path")}),
        "patches": state.patches,
        "artifacts": [a for a in (_artifact_preview(p) for p in state.patches) if a],
        "risk_level": risk_level,
        "risk_reasons": risk_reasons,
        "model_output_errors": state.context.get("model_output_errors", []),
        "requires_save_approval": bool(state.patches),
        "gates": gates,
        "risky_actions": state.risky_actions,
        "pending_approval": state.pending_approval,
        "cost": cost,
        "tokens_used": state.tokens_used,
        "explanation": state.explanation,
    }
    state.verification_report = report
    return report


def to_markdown(report: dict) -> str:
    g = report["gates"]

    def mark(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    lines = [
        f"# Verification report - {report['verdict'].upper()}",
        f"**Goal:** {report['goal']}",
        f"**Mode:** {report['router_mode']} | local-only: {report['hybrid_local_only']} | iterations: {report['iterations']}",
        "",
        "## Gates",
        f"- {mark(g['tests']['passed'])} Tests",
        f"- {mark(g['hallucination']['passed'])} Hallucination check (confidence {g['hallucination']['confidence']})",
        f"- {mark(g['security']['passed'])} Security (high findings: {g['security']['high']})",
        f"- {mark(g['static']['passed'])} Static checks (lint/type/build)",
        f"- {mark(g['review']['approved'])} Multi-agent review",
        "",
        "## Cost",
        f"- Total: ${report['cost']['total_cost_usd']} across {report['cost']['calls']} calls, {report['cost']['total_tokens']} tokens",
    ]
    for model, m in report["cost"]["by_model"].items():
        lines.append(f"  - {model}: ${m['cost_usd']} ({m['calls']} calls)")
    lines += ["", "## Files changed"] + [f"- {f}" for f in report["files_changed"]]
    if report["risky_actions"]:
        lines += ["", "## Risky actions (require approval)"] + [
            f"- {a['kind']}: {a.get('detail', '')}" for a in report["risky_actions"]
        ]
    return "\n".join(lines)
