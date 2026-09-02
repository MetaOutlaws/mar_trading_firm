"""
Strategy registry.

Strategies are looked up by name so that research artifacts, database records
and dashboard displays can all refer to a strategy with a stable string. A
backtest result recorded as "rsi_trend" must resolve to the same code six months
later, or the result is meaningless.
"""

from __future__ import annotations

from pathlib import Path

from core.strategy.base import Strategy

_REGISTRY: dict[str, type[Strategy]] = {}
_SKIP_MODULES = frozenset({"__init__", "base", "registry", "indicators", "sleeve_spec"})


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
    """Import every strategy module on disk.

    A long-running paper loop used to keep the sleeve list it had at process
    start. Scanning this folder means a new family file is importable on the
    next cycle without restarting the process.
    """
    import importlib
    import inspect
    import logging

    log = logging.getLogger(__name__)
    pkg = Path(__file__).parent
    for path in sorted(pkg.glob("*.py")):
        stem = path.stem
        if stem in _SKIP_MODULES:
            continue
        try:
            mod = importlib.import_module(f"core.strategy.{stem}")
        except Exception:
            log.exception("Could not import strategy module %s", stem)
            continue
        for _, cls in inspect.getmembers(mod, inspect.isclass):
            if (
                not issubclass(cls, Strategy)
                or cls is Strategy
                or not getattr(cls, "name", "")
                or cls.name == "unnamed"
            ):
                continue
            if cls.name not in _REGISTRY:
                register_strategy(cls)
    try:
        from core.strategy.spec_sleeve import load_spec_sleeves

        load_spec_sleeves()
    except Exception:
        log.exception("Could not load JSON sleeve specs")


__all__: list[str] = ["get_strategy", "list_strategies", "register_strategy"]
