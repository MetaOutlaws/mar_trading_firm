"""
Strategy registry.

Strategies are looked up by name so that research artifacts, database records
and dashboard displays can all refer to a strategy with a stable string. A
backtest result recorded as "rsi_trend" must resolve to the same code six months
later, or the result is meaningless.
"""

from __future__ import annotations

from core.strategy.base import Strategy

_REGISTRY: dict[str, type[Strategy]] = {}


def register_strategy(cls: type[Strategy]) -> type[Strategy]:
    """Register a strategy class under its `name`. Usable as a decorator."""
    if not cls.name or cls.name == "unnamed":
        raise ValueError(f"{cls.__qualname__} must set a class-level `name`")
    if cls.name in _REGISTRY and _REGISTRY[cls.name] is not cls:
        raise ValueError(f"Strategy name {cls.name!r} is already registered")
    _REGISTRY[cls.name] = cls
    return cls


def get_strategy(name: str) -> type[Strategy]:
    """Look up a registered strategy class by name."""
    _ensure_builtins_loaded()
    if name not in _REGISTRY:
        raise KeyError(f"Unknown strategy {name!r}. Registered: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def list_strategies() -> list[str]:
    """Names of all registered strategies."""
    _ensure_builtins_loaded()
    return sorted(_REGISTRY)


def _ensure_builtins_loaded() -> None:
    """Import built-in strategies on first use.

    Deferred to avoid a circular import: strategy modules import from
    `core.strategy`, which would otherwise need them at package import time.
    """
    if _REGISTRY:
        return
    from core.strategy.rsi_golden_cross import RsiTrendStrategy

    register_strategy(RsiTrendStrategy)


__all__: list[str] = ["get_strategy", "list_strategies", "register_strategy"]
