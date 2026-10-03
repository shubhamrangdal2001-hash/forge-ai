"""Local coder model catalog, hardware tiers, and recommendation helpers.

The numbers here are conservative product-planning estimates for quantized
local inference. Runtime checks still validate actual RAM/VRAM before loading.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class LocalModel:
    id: str
    name: str
    family: str
    parameter_size: str
    params_b: float
    best_use_case: str
    min_ram_gb: int
    recommended_ram_gb: int
    min_vram_gb: int
    recommended_vram_gb: int
    cpu_only: bool
    coding: str
    debugging: str
    repo_reasoning: str
    quantization: str
    ollama: str | None
    lm_studio: str
    vllm: str
    product_role: str
    tier: int
    provider: str = "ollama"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


COMPATIBILITY_TIERS = [
    {
        "tier": 1,
        "name": "Low-end laptop",
        "ram_gb": "8",
        "gpu_vram_gb": "0",
        "recommended_models": ["qwen2.5-coder-0.5b", "qwen2.5-coder-1.5b", "llama3.2-1b", "llama3.2-3b"],
        "notes": "Use Q4 quantization, short context, CPU-first inference.",
    },
    {
        "tier": 2,
        "name": "Standard laptop",
        "ram_gb": "16",
        "gpu_vram_gb": "4",
        "recommended_models": ["qwen2.5-coder-3b", "qwen2.5-coder-7b", "codellama-7b", "deepseek-coder-6.7b"],
        "notes": "Best for autocomplete, function edits, and small debugging tasks.",
    },
    {
        "tier": 3,
        "name": "Good developer laptop",
        "ram_gb": "32",
        "gpu_vram_gb": "6-8",
        "recommended_models": ["qwen2.5-coder-7b", "qwen2.5-coder-14b", "deepseek-r1-distill-14b"],
        "notes": "Balanced local coding and debugging with Q4/Q5.",
    },
    {
        "tier": 4,
        "name": "Workstation",
        "ram_gb": "64",
        "gpu_vram_gb": "12-24",
        "recommended_models": ["qwen2.5-coder-14b", "qwen2.5-coder-32b", "codestral-22b", "deepseek-coder-33b"],
        "notes": "Use Q5/Q8 for accuracy-sensitive local work.",
    },
    {
        "tier": 5,
        "name": "High-end workstation/server",
        "ram_gb": "128+",
        "gpu_vram_gb": "48+",
        "recommended_models": ["qwen2.5-coder-32b", "llama3.1-70b", "llama3.3-70b", "llama4-scout", "llama4-maverick"],
        "notes": "Use vLLM or multi-GPU serving for repo-level agents.",
    },
    {
        "tier": 6,
        "name": "Cloud-only",
        "ram_gb": "managed",
        "gpu_vram_gb": "multi-GPU",
        "recommended_models": ["llama3.1-405b"],
        "notes": "Use cloud API, hosted vLLM, or a managed multi-GPU server.",
    },
]


RUNTIME_MODES = [
    {"id": "fast", "label": "Fast mode", "goal": "lowest latency for small edits and autocomplete"},
    {"id": "balanced", "label": "Balanced mode", "goal": "local-first model with cloud fallback"},
    {"id": "accurate", "label": "Accurate mode", "goal": "larger local model or expert cloud fallback"},
    {"id": "offline", "label": "Offline mode", "goal": "local-only, privacy-preserving execution"},
    {"id": "nvidia_only", "label": "NVIDIA-only mode", "goal": "use validated NVIDIA-hosted models only"},
    {"id": "hybrid", "label": "Hybrid mode", "goal": "local-first with NVIDIA and cloud fallback"},
    {"id": "cloud_fallback", "label": "Cloud fallback mode", "goal": "local model, then NVIDIA, then secondary cloud provider"},
    {"id": "cheap", "label": "Cheap mode", "goal": "prefer local and low-cost models"},
    {"id": "cloud_expert", "label": "Cloud expert mode", "goal": "use strongest cloud model for critical work"},
    {"id": "low_ram", "label": "Low RAM mode", "goal": "tiny quantized models or cloud fallback"},
    {"id": "gpu", "label": "GPU mode", "goal": "prefer higher-accuracy models that fit VRAM"},
    {"id": "cpu_only", "label": "CPU-only mode", "goal": "local models that remain usable without a dedicated GPU"},
]


LOCAL_MODELS: list[LocalModel] = [
    LocalModel("qwen2.5-coder-0.5b", "Qwen2.5-Coder 0.5B", "Qwen Coder", "0.5B", 0.5, "tiny autocomplete and syntax help", 4, 8, 0, 2, True, "Medium", "Low", "Low", "Q4", "ollama run qwen2.5-coder:0.5b", "Yes (GGUF)", "Yes (HF)", "autocomplete", 1),
    LocalModel("qwen2.5-coder-1.5b", "Qwen2.5-Coder 1.5B", "Qwen Coder", "1.5B", 1.5, "fast edits on low-end laptops", 8, 12, 0, 2, True, "Medium", "Medium", "Low", "Q4/Q5", "ollama run qwen2.5-coder:1.5b", "Yes (GGUF)", "Yes (HF)", "autocomplete", 1),
    LocalModel("qwen2.5-coder-3b", "Qwen2.5-Coder 3B", "Qwen Coder", "3B", 3, "small functions and explanations", 8, 16, 2, 4, True, "High", "Medium", "Medium", "Q4/Q5", "ollama run qwen2.5-coder:3b", "Yes (GGUF)", "Yes (HF)", "small-task coder", 2),
    LocalModel("qwen2.5-coder-7b", "Qwen2.5-Coder 7B", "Qwen Coder", "7B", 7, "default local coder", 16, 32, 4, 8, True, "High", "High", "Medium", "Q4/Q5", "ollama run qwen2.5-coder:7b", "Yes (GGUF)", "Yes (HF)", "coder", 2),
    LocalModel("qwen2.5-coder-14b", "Qwen2.5-Coder 14B", "Qwen Coder", "14B", 14, "debugging and medium refactors", 32, 64, 8, 16, True, "High", "High", "High", "Q4/Q5", "ollama run qwen2.5-coder:14b", "Yes (GGUF)", "Yes (HF)", "debugger/reviewer", 3),
    LocalModel("qwen2.5-coder-32b", "Qwen2.5-Coder 32B", "Qwen Coder", "32B", 32, "repo-level planning and large refactors", 64, 128, 20, 40, True, "High", "High", "High", "Q4/Q5/Q8", "ollama run qwen2.5-coder:32b", "Yes (GGUF)", "Yes (HF)", "local expert", 4),
    LocalModel("llama3.2-1b", "Llama 3.2 1B", "Llama", "1B", 1, "tiny offline assistant", 4, 8, 0, 2, True, "Low", "Low", "Low", "Q4", "ollama run llama3.2:1b", "Yes (GGUF)", "Yes (HF)", "offline helper", 1),
    LocalModel("llama3.2-3b", "Llama 3.2 3B", "Llama", "3B", 3, "fast local assistant and rename/explain", 8, 16, 2, 4, True, "Medium", "Medium", "Low", "Q4/Q5", "ollama run llama3.2:3b", "Yes (GGUF)", "Yes (HF)", "small-task assistant", 2),
    LocalModel("llama3.1-8b", "Llama 3.1 8B", "Llama", "8B", 8, "general local coding assistant", 16, 32, 5, 8, True, "Medium", "Medium", "Medium", "Q4/Q5", "ollama run llama3.1:8b", "Yes (GGUF)", "Yes (HF)", "general assistant", 2),
    LocalModel("llama3.1-70b", "Llama 3.1 70B", "Llama", "70B", 70, "large local/cloud reasoning", 128, 192, 48, 80, False, "High", "High", "High", "Q4/FP16", "ollama run llama3.1:70b", "Yes (GGUF)", "Yes (HF)", "repo reasoner", 5),
    LocalModel("llama3.1-405b", "Llama 3.1 405B", "Llama", "405B", 405, "cloud-only frontier local-open alternative", 512, 1024, 240, 400, False, "High", "High", "High", "FP8/FP16", None, "No practical desktop use", "Yes (multi-GPU)", "cloud-only expert", 6, provider="lmstudio"),
    LocalModel("llama3.2-vision-11b", "Llama 3.2 Vision 11B", "Llama", "11B", 11, "screenshot and UI reasoning", 32, 64, 8, 16, True, "Medium", "Medium", "Medium", "Q4/Q5", "ollama run llama3.2-vision:11b", "Yes (GGUF)", "Partial", "visual reviewer", 3),
    LocalModel("llama3.2-vision-90b", "Llama 3.2 Vision 90B", "Llama", "90B", 90, "large multimodal UI review", 160, 256, 64, 100, False, "Medium", "High", "High", "Q4/FP16", "ollama run llama3.2-vision:90b", "Limited", "Yes (multi-GPU)", "visual expert", 5),
    LocalModel("llama3.3-70b", "Llama 3.3 70B", "Llama", "70B", 70, "large reasoning and code review", 128, 192, 48, 80, False, "High", "High", "High", "Q4/FP16", "ollama run llama3.3:70b", "Yes (GGUF)", "Yes (HF)", "reviewer", 5),
    LocalModel("llama4-scout", "Llama 4 Scout", "Llama", "17B active / 109B total", 109, "long-context multimodal repo review", 128, 192, 48, 80, False, "High", "High", "High", "FP8/FP16", None, "Limited", "Yes (supported stacks)", "long-context expert", 5, provider="lmstudio"),
    LocalModel("llama4-maverick", "Llama 4 Maverick", "Llama", "17B active / 400B total", 400, "cloud/server expert coding and reasoning", 256, 512, 96, 160, False, "High", "High", "High", "FP8/FP16", None, "No practical desktop use", "Yes (multi-GPU)", "cloud/server expert", 6, provider="lmstudio"),
    LocalModel("deepseek-coder-1.3b", "DeepSeek-Coder 1.3B", "DeepSeek", "1.3B", 1.3, "tiny code completion", 8, 12, 0, 2, True, "Medium", "Low", "Low", "Q4/Q5", "ollama run deepseek-coder", "Yes (GGUF)", "Yes (HF)", "autocomplete", 1),
    LocalModel("deepseek-coder-6.7b", "DeepSeek-Coder 6.7B", "DeepSeek", "6.7B", 6.7, "function writing and bug fixing", 16, 32, 4, 8, True, "High", "High", "Medium", "Q4/Q5", "ollama run deepseek-coder:6.7b", "Yes (GGUF)", "Yes (HF)", "coder/debugger", 2),
    LocalModel("deepseek-coder-33b", "DeepSeek-Coder 33B", "DeepSeek", "33B", 33, "large coding and repair", 64, 128, 20, 40, True, "High", "High", "High", "Q4/Q5", "ollama run deepseek-coder:33b", "Yes (GGUF)", "Yes (HF)", "local expert", 4),
    LocalModel("deepseek-r1-distill-7b", "DeepSeek-R1 Distill 7B", "DeepSeek", "7B", 7, "reasoning-heavy bug triage", 16, 32, 4, 8, True, "Medium", "High", "Medium", "Q4/Q5", "ollama run deepseek-r1:7b", "Yes (GGUF)", "Yes (HF)", "debugger", 2),
    LocalModel("deepseek-r1-distill-14b", "DeepSeek-R1 Distill 14B", "DeepSeek", "14B", 14, "local reasoning reviewer", 32, 64, 8, 16, True, "Medium", "High", "High", "Q4/Q5", "ollama run deepseek-r1:14b", "Yes (GGUF)", "Yes (HF)", "reasoning reviewer", 3),
    LocalModel("codellama-7b", "CodeLlama 7B", "CodeLlama", "7B", 7, "legacy local code completion", 16, 32, 4, 8, True, "Medium", "Medium", "Low", "Q4/Q5", "ollama run codellama:7b", "Yes (GGUF)", "Yes (HF)", "fallback coder", 2),
    LocalModel("starcoder2-7b", "StarCoder2 7B", "StarCoder2", "7B", 7, "polyglot code completion", 16, 32, 4, 8, True, "High", "Medium", "Medium", "Q4/Q5", "ollama run starcoder2:7b", "Yes (GGUF)", "Yes (HF)", "completion specialist", 2),
    LocalModel("codestral-22b", "Codestral 22B", "Mistral", "22B", 22, "strong code generation", 48, 96, 16, 24, True, "High", "High", "High", "Q4/Q5", "ollama run codestral", "Yes (GGUF)", "Yes (HF)", "coder expert", 4),
    LocalModel("phi-3.5-mini", "Phi 3.5 Mini", "Phi", "3.8B", 3.8, "fast low-memory assistant", 8, 16, 2, 4, True, "Medium", "Medium", "Low", "Q4/Q5", "ollama run phi3.5", "Yes (GGUF)", "Yes (HF)", "cheap assistant", 2),
    LocalModel("gemma-3-4b", "Gemma 3 4B", "Gemma", "4B", 4, "small general coding assistant", 12, 24, 3, 6, True, "Medium", "Medium", "Medium", "Q4/Q5", "ollama run gemma3:4b", "Yes (GGUF)", "Yes (HF)", "small assistant", 2),
    LocalModel("mistral-7b", "Mistral 7B", "Mistral", "7B", 7, "general local assistant", 16, 32, 4, 8, True, "Medium", "Medium", "Medium", "Q4/Q5", "ollama run mistral", "Yes (GGUF)", "Yes (HF)", "general fallback", 2),
    LocalModel("mixtral-8x7b", "Mixtral 8x7B", "Mistral", "8x7B MoE", 47, "MoE reasoning and refactor planning", 64, 128, 24, 48, False, "High", "High", "High", "Q4/Q5", "ollama run mixtral", "Yes (GGUF)", "Yes (HF)", "planning expert", 5),
    LocalModel("yi-coder-9b", "Yi-Coder 9B", "Yi", "9B", 9, "code generation and repair", 24, 48, 6, 12, True, "High", "Medium", "Medium", "Q4/Q5", "ollama run yi-coder:9b", "Yes (GGUF)", "Yes (HF)", "coder", 3),
    LocalModel("granite-code-8b", "Granite Code 8B", "Granite", "8B", 8, "enterprise code completion", 16, 32, 5, 8, True, "High", "Medium", "Medium", "Q4/Q5", "ollama run granite-code:8b", "Yes (GGUF)", "Yes (HF)", "enterprise coder", 2),
    LocalModel("minicpm-2.4b", "MiniCPM 2.4B", "MiniCPM", "2.4B", 2.4, "tiny assistant and explain mode", 8, 16, 0, 4, True, "Low", "Medium", "Low", "Q4", "ollama run minicpm-v", "Yes (GGUF)", "Partial", "small assistant", 1),
    LocalModel("internlm2.5-7b", "InternLM 2.5 7B", "InternLM", "7B", 7, "general local reasoning", 16, 32, 4, 8, True, "Medium", "Medium", "Medium", "Q4/Q5", "ollama run internlm2", "Yes (GGUF)", "Yes (HF)", "reasoning fallback", 2),
    LocalModel("nous-hermes-2-mixtral", "Nous Hermes 2 Mixtral", "Nous Hermes", "8x7B MoE", 47, "instruction following and planning", 64, 128, 24, 48, False, "Medium", "High", "High", "Q4/Q5", "ollama run nous-hermes2-mixtral", "Yes (GGUF)", "Yes (HF)", "planner fallback", 5),
    LocalModel("openchat-7b", "OpenChat 7B", "OpenChat", "7B", 7, "chatty local assistant fallback", 16, 32, 4, 8, True, "Medium", "Medium", "Low", "Q4/Q5", "ollama run openchat", "Yes (GGUF)", "Yes (HF)", "assistant fallback", 2),
]


def local_catalog() -> list[dict[str, Any]]:
    return [m.to_dict() for m in LOCAL_MODELS]


def model_by_id(model_id: str) -> LocalModel | None:
    return next((m for m in LOCAL_MODELS if m.id == model_id), None)


def detect_tier(total_ram_gb: float, gpu_vram_gb: float) -> dict[str, Any]:
    if total_ram_gb >= 128 and gpu_vram_gb >= 48:
        return COMPATIBILITY_TIERS[4]
    if total_ram_gb >= 64 and gpu_vram_gb >= 12:
        return COMPATIBILITY_TIERS[3]
    if total_ram_gb >= 32 and gpu_vram_gb >= 6:
        return COMPATIBILITY_TIERS[2]
    if total_ram_gb >= 16:
        return COMPATIBILITY_TIERS[1]
    return COMPATIBILITY_TIERS[0]


def recommend_models(
    total_ram_gb: float,
    gpu_vram_gb: float,
    mode: str = "balanced",
    task_complexity: str = "medium",
    privacy: str = "hybrid",
    limit: int = 6,
) -> list[dict[str, Any]]:
    local_only = mode == "offline" or privacy == "local"
    max_tier = detect_tier(total_ram_gb, gpu_vram_gb)["tier"]
    candidates = [m for m in LOCAL_MODELS if m.tier <= max_tier and m.min_ram_gb <= total_ram_gb]
    if gpu_vram_gb:
        candidates = [m for m in candidates if m.min_vram_gb <= gpu_vram_gb or m.cpu_only]
    if local_only:
        candidates = [m for m in candidates if m.cpu_only or m.min_vram_gb <= gpu_vram_gb]

    complexity_weight = {"small": 1, "medium": 2, "large": 3, "critical": 4}.get(task_complexity, 2)
    mode_bias = {
        "fast": lambda m: (m.tier, m.params_b),
        "cheap": lambda m: (m.tier, m.params_b),
        "accurate": lambda m: (-m.tier, -m.params_b),
        "cloud_expert": lambda m: (-m.tier, -m.params_b),
        "offline": lambda m: (abs(m.tier - min(max_tier, 3)), m.params_b),
        "low_ram": lambda m: (m.recommended_ram_gb, m.params_b),
        "gpu": lambda m: (abs(m.tier - min(max_tier + 1, 5)), -m.params_b),
        "cpu_only": lambda m: (not m.cpu_only, m.recommended_ram_gb, m.params_b),
        "balanced": lambda m: (abs(m.tier - min(max_tier, complexity_weight + 1)), m.params_b),
    }.get(mode, lambda m: (m.tier, m.params_b))
    return [m.to_dict() for m in sorted(candidates, key=mode_bias)[:limit]]
