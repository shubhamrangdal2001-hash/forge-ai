"""Model catalog endpoint.

Exposes the worldwide, user-selectable model catalog so the web IDE can render a
model picker. The user can pick any popular coding model (US, Chinese, European,
or fully local) per agent role, and the orchestrator honors the choice.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["models"])

# Agent roles the user can assign a model to (maps to router Task values).
ROLES = [
    {"task": "plan", "label": "Planner"},
    {"task": "code", "label": "Coder"},
    {"task": "debug", "label": "Debugger"},
    {"task": "test", "label": "Tester"},
    {"task": "security", "label": "Security"},
    {"task": "review", "label": "Reviewer"},
    {"task": "docs", "label": "Documentation"},
    {"task": "deploy", "label": "Deployment"},
    {"task": "autocomplete", "label": "Autocomplete"},
    {"task": "long_context", "label": "Long-context"},
]


@router.get("/models")
async def list_models():
    from orchestrator.models.router import list_models as catalog  # type: ignore
    from orchestrator.models.providers import PROVIDERS  # type: ignore
    from orchestrator.models.nvidia import load_settings as nvidia_settings  # type: ignore
    models = catalog()
    nvidia = nvidia_settings()
    providers = []
    for pid, p in PROVIDERS.items():
        configured = pid == "nvidia" and nvidia.get("provider_enabled")
        providers.append({
            "id": pid,
            "label": p["label"],
            "local": p.get("env_key") is None,
            "configured": bool(configured),
        })
    return {"models": models, "providers": providers, "roles": ROLES}
