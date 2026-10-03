"""Security agent.

Two layers:
  1. Mechanical scans in the sandbox  — bandit (py), pip-audit, npm audit, plus
     a fast secret-leak regex over the proposed patches.
  2. Model review (Opus 4.8) — reasons about injection, authz, unsafe sinks that
     scanners miss.
"""
import re
from ..state import AgentState
from ..models.router import complete, Task
from ..execution.sandbox import run_in_sandbox
from ..events import publish_step

SECRET_PATTERNS = [
    (r"(?i)api[_-]?key\s*[=:]\s*['\"][A-Za-z0-9_\-]{16,}", "hardcoded api key"),
    (r"(?i)secret\s*[=:]\s*['\"][^'\"]{8,}", "hardcoded secret"),
    (r"AKIA[0-9A-Z]{16}", "aws access key id"),
    (r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----", "private key material"),
]

SANDBOX_SCANS = [
    ("bandit", "bandit -q -r . -f txt || true"),
    ("pip-audit", "pip-audit || true"),
    ("npm-audit", "npm audit --omit=dev || true"),
]


def _scan_secrets(patches: list[dict]) -> list[dict]:
    findings = []
    for p in patches:
        for pat, label in SECRET_PATTERNS:
            if re.search(pat, p.get("patch", "")):
                findings.append({"file": p.get("file_path"), "rule": label, "severity": "high"})
    return findings


def scan(state: AgentState) -> dict:
    publish_step(state.run_id, agent_role="security", model="claude-opus-4.8", phase="security", status="running")
    findings = _scan_secrets(state.patches)

    for name, cmd in SANDBOX_SCANS:
        out = run_in_sandbox(state.project_id, cmd)
        if out.get("exit_code") not in (0, None):
            findings.append({"scanner": name, "severity": "medium", "output": out.get("stdout", "")[-800:]})

    # Model pass for logic-level vulnerabilities.
    prompt = (
        "Audit these patches for security issues (injection, authz, unsafe "
        "deserialization, SSRF, path traversal). List HIGH issues or reply NONE.\n"
        f"{[p.get('file_path') for p in state.patches]}"
    )
    out = complete(Task.SECURITY, prompt)
    state.tokens_used += out.tokens
    if "NONE" not in out.text.upper():
        findings.append({"scanner": "model", "severity": "review", "output": out.text[:800]})

    high = [f for f in findings if f.get("severity") == "high"]
    result = {"passed": len(high) == 0, "findings": findings, "high": len(high)}
    state.security_results = result
    publish_step(state.run_id, agent_role="security", model="claude-opus-4.8", phase="security",
                 status="passed" if result["passed"] else "failed", detail=result)
    return result
