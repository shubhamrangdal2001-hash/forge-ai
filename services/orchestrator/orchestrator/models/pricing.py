"""Pricing + tier helpers, derived from the worldwide model catalog.

Kept as a thin layer so existing imports (`cost`, `is_local`, `MODEL_INFO`)
keep working while the single source of truth lives in `providers.py`.
"""
from .providers import MODELS

# Backwards-compatible view: model id -> {price, tier, speed, accuracy}
MODEL_INFO: dict[str, dict] = {
    mid: {
        "price": meta["price"],
        "tier": meta["tier"],
        "speed": meta["speed"],
        "accuracy": meta["accuracy"],
    }
    for mid, meta in MODELS.items()
}


def _refresh_dynamic() -> None:
    try:
        from .providers import refresh_dynamic_models

        refresh_dynamic_models()
        for mid, meta in MODELS.items():
            MODEL_INFO.setdefault(
                mid,
                {
                    "price": meta.get("price", 0.0),
                    "tier": meta.get("tier", "cloud"),
                    "speed": meta.get("speed", 3),
                    "accuracy": meta.get("accuracy", 3),
                },
            )
    except Exception:
        pass


def is_local(model: str) -> bool:
    _refresh_dynamic()
    return MODELS.get(model, {}).get("tier") == "local"


def price_per_1m(model: str) -> float:
    _refresh_dynamic()
    return float(MODELS.get(model, {}).get("price", 0.0))


def cost(model: str, tokens: int) -> float:
    """Blended USD cost for `tokens` on `model`."""
    return round(tokens / 1_000_000 * price_per_1m(model), 6)
