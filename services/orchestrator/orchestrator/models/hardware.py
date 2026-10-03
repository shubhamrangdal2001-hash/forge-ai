"""Safe local runtime detection for model selection."""
from __future__ import annotations

import ctypes
import json
import os
import platform
import shutil
import subprocess
from typing import Any

from .local_catalog import detect_tier, recommend_models


def _ram_gb() -> float:
    if platform.system() == "Windows":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return round(stat.ullTotalPhys / (1024 ** 3), 1)
    if hasattr(os, "sysconf"):
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return round(pages * page_size / (1024 ** 3), 1)
    return 0.0


def _available_ram_gb() -> float:
    if platform.system() == "Windows":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return round(stat.ullAvailPhys / (1024 ** 3), 1)
    if hasattr(os, "sysconf"):
        total = _ram_gb()
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemAvailable:"):
                        kb = float(line.split()[1])
                        return round(kb / (1024 ** 2), 1)
        except OSError:
            pass
        return total
    return 0.0


def _cpu_name() -> str:
    if platform.system() == "Windows":
        try:
            value = subprocess.run(
                ["wmic", "cpu", "get", "name"],
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.splitlines()
            names = [line.strip() for line in value if line.strip() and line.strip().lower() != "name"]
            if names:
                return names[0]
        except Exception:
            pass
    return platform.processor() or platform.machine()


def _nvidia_gpu_name() -> str | None:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        names = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        return names[0] if names else None
    except Exception:
        return None


def _nvidia_vram_gb() -> float:
    if not shutil.which("nvidia-smi"):
        return 0.0
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        values = [float(line.strip()) for line in proc.stdout.splitlines() if line.strip()]
        return round(max(values) / 1024, 1) if values else 0.0
    except Exception:
        return 0.0


def installed_ollama_models() -> list[dict[str, Any]]:
    if not shutil.which("ollama"):
        return []
    try:
        proc = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=8)
    except Exception:
        return []
    rows = []
    for line in proc.stdout.splitlines()[1:]:
        parts = line.split()
        if not parts:
            continue
        rows.append({"name": parts[0], "raw": line})
    return rows


def detect_lm_studio() -> dict[str, Any]:
    # LM Studio exposes an OpenAI-compatible local server when enabled.
    base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    return {"base_url": base_url, "configured": bool(base_url)}


def internet_online() -> bool:
    import socket

    try:
        socket.create_connection(("integrate.api.nvidia.com", 443), timeout=3).close()
        return True
    except OSError:
        return False


def cloud_recommendation(ram_gb: float, vram_gb: float, online: bool) -> dict[str, Any]:
    if not online:
        return {"mode": "offline", "reason": "No internet connection detected."}
    if ram_gb < 16 or vram_gb < 4:
        return {"mode": "nvidia_cloud", "reason": "Prefer NVIDIA cloud for low-memory machines."}
    if ram_gb >= 64 and vram_gb >= 12:
        return {"mode": "local_first", "reason": "Local models fit comfortably; use NVIDIA for large-context fallback."}
    return {"mode": "hybrid", "reason": "Use local models for small edits and NVIDIA for heavier reasoning."}


def hardware_profile(mode: str = "balanced", task_complexity: str = "medium") -> dict[str, Any]:
    ram = _ram_gb()
    available_ram = _available_ram_gb()
    vram = _nvidia_vram_gb()
    online = internet_online()
    tier = detect_tier(ram, vram)
    recommendations = recommend_models(ram, vram, mode=mode, task_complexity=task_complexity)
    return {
        "os": platform.platform(),
        "ram_gb": ram,
        "available_ram_gb": available_ram,
        "cpu": _cpu_name(),
        "gpu": _nvidia_gpu_name(),
        "gpu_vram_gb": vram,
        "internet_online": online,
        "tier": tier,
        "ollama_installed": bool(shutil.which("ollama")),
        "ollama_models": installed_ollama_models(),
        "lm_studio": detect_lm_studio(),
        "recommendations": recommendations,
        "cloud_recommendation": cloud_recommendation(ram, vram, online),
    }


def benchmark_stub(model_id: str) -> dict[str, Any]:
    profile = hardware_profile()
    return {
        "model_id": model_id,
        "status": "not_run",
        "tokens_per_second": None,
        "memory_gb": None,
        "profile": profile,
        "next_step": "Run an Ollama or LM Studio timed completion to record benchmark data.",
    }


def as_json(data: Any) -> str:
    return json.dumps(data, indent=2)
