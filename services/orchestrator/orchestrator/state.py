from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AgentState:
    """Shared state threaded through the DAG (LangGraph-compatible shape)."""

    run_id: str
    project_id: str
    goal: str
    token_budget: int = 200_000
    tokens_used: int = 0

    # routing / hybrid controls (differentiators #4, #7)
    router_mode: str = "accuracy"   # speed | accuracy | auto
    local_only: bool = False         # prefer on-device models (sensitive/offline)
    # User's model picks, task value -> model id (or {"all": "<model>"}). Lets the
    # user choose any popular coding model worldwide; empty = smart defaults.
    model_overrides: dict[str, str] = field(default_factory=dict)

    plan: list[dict] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    memory: list[dict] = field(default_factory=list)   # recalled prior experience (#3)
    tests_written: list[dict] = field(default_factory=list)  # test-first (#1)
    patches: list[dict] = field(default_factory=list)

    # per-phase results
    test_results: dict = field(default_factory=dict)
    hallucination_results: dict = field(default_factory=dict)  # (#9)
    security_results: dict = field(default_factory=dict)
    verify_results: dict = field(default_factory=dict)
    review_results: dict = field(default_factory=dict)
    panel_results: dict = field(default_factory=dict)          # multi-agent review (#6)
    doc_results: dict = field(default_factory=dict)
    deploy_results: dict = field(default_factory=dict)
    verification_report: dict = field(default_factory=dict)     # (#5)

    # risk + human approval (#10)
    risky_actions: list[dict] = field(default_factory=list)
    approved_actions: list[str] = field(default_factory=list)
    auto_approve_risky: bool = False
    pending_approval: bool = False

    explanation: Optional[str] = None
    cost_usd: float = 0.0
    checkpoint_id: Optional[str] = None
    failed: bool = False
    iteration: int = 0
    max_iterations: int = 4

    deploy_requested: bool = False
    deploy_approved: bool = False

    def over_budget(self) -> bool:
        return self.tokens_used >= self.token_budget

    def all_green(self) -> bool:
        return (
            bool(self.test_results.get("passed"))
            and bool(self.verify_results.get("passed"))
            and bool(self.security_results.get("passed"))
            and bool(self.hallucination_results.get("passed", True))
            and bool(self.review_results.get("approved"))
        )
