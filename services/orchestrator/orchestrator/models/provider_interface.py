"""Provider abstraction shared by cloud and local model adapters."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Protocol


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ChatCompletionOptions:
    temperature: float = 0.2
    max_tokens: int | None = None
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    response_format: dict[str, Any] | None = None


@dataclass
class ProviderResponse:
    model: str
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class ProviderModel:
    id: str
    display_name: str
    provider: str
    provider_label: str
    model_name: str
    model_provider: str | None = None
    parameter_size: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    capabilities: list[str] = field(default_factory=list)
    supported_languages: list[str] = field(default_factory=list)
    coding_capability: str = "unknown"
    reasoning_capability: str = "unknown"
    vision_support: bool = False
    embedding_support: bool = False
    chat_capability: bool = True
    function_calling_support: bool = False
    structured_output_support: bool = False
    recommended_use_cases: list[str] = field(default_factory=list)
    relative_latency: str = "unknown"
    relative_quality: str = "unknown"
    relative_cost: str = "account-dependent"
    availability_status: str = "unknown"
    rate_limits: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AIProvider(Protocol):
    id: str
    label: str

    def list_available_models(self, refresh: bool = False) -> list[ProviderModel]:
        ...

    def validate_api_key(self, api_key: str | None = None) -> dict[str, Any]:
        ...

    def chat_completion(
        self,
        messages: list[ChatMessage],
        model: str,
        options: ChatCompletionOptions | None = None,
    ) -> ProviderResponse:
        ...

    def stream_chat_completion(
        self,
        messages: list[ChatMessage],
        model: str,
        options: ChatCompletionOptions | None = None,
    ) -> Iterable[str]:
        ...

    def embeddings(self, inputs: list[str], model: str) -> dict[str, Any]:
        ...

    def model_info(self, model: str) -> ProviderModel | None:
        ...

    def count_tokens(self, text: str, model: str | None = None) -> int:
        ...

    def health_check(self) -> dict[str, Any]:
        ...
