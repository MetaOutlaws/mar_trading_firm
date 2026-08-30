"""
Port per-asset strategy parameters out of the predecessor project into JSON.

The legacy configs live as ~1,200 lines of hand-written dataclass constructor
calls across `long_strategy_config.py` and `short_strategy_config.py`. Rather
than re-typing them (and inevitably introducing transcription errors), this
imports the legacy modules and serialises them to `config/asset_params.json`.

IMPORTANT: the `expected_*` and `profit_factor` fields carried over from the
legacy configs are UNVALIDATED CLAIMS. They came from ~5 weeks of Q4 2024 bull
market data and disagree with the project's own enhanced backtest. They are
preserved only as a historical baseline to re-verify against, and are stored
under `legacy_claims` so nothing can mistake them for measured results.

Usage:
    python scripts/port_legacy_configs.py
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT

LEGACY_PROJECT = PROJECT_ROOT.parent / "mar_trading_bot"
OUTPUT_PATH = PROJECT_ROOT / "config" / "asset_params.json"

# Fields that are performance *claims*, not strategy parameters. Segregated so
# they can never be read as if they were verified metrics.
CLAIM_FIELDS = {
    "expected_win_rate",
    "expected_trades_per_quarter",
    "backtest_return_q1",
    "backtest_return_q4",
    "profit_factor",
}


def load_legacy_managers() -> tuple[Any, Any]:
    """Import the legacy strategy managers from the predecessor project."""
    if not LEGACY_PROJECT.exists():
        raise FileNotFoundError(f"Legacy project not found: {LEGACY_PROJECT}")

    sys.path.insert(0, str(LEGACY_PROJECT))
    try:
        from long_strategy_config import LongStrategyManager
        from short_strategy_config import ShortStrategyManager
    except ImportError as exc:  # pragma: no cover - environment specific
        raise ImportError(f"Could not import legacy configs from {LEGACY_PROJECT}: {exc}") from exc

    return LongStrategyManager(), ShortStrategyManager()


def split_config(config: Any) -> dict[str, Any]:
    """Convert a legacy dataclass into {params, legacy_claims, enabled}."""
    raw = dataclasses.asdict(config)

    enabled = raw.pop("enabled", False)
    raw.pop("symbol", None)

    claims = {k: raw.pop(k) for k in list(raw) if k in CLAIM_FIELDS}
    # Drop null claims so the JSON stays readable.
    claims = {k: v for k, v in claims.items() if v is not None}

    return {
        "enabled": bool(enabled),
        "params": raw,
        "legacy_claims": claims,
    }


def main() -> int:
    long_mgr, short_mgr = load_legacy_managers()

    long_out: dict[str, Any] = {}
    for symbol, config in sorted(long_mgr.configs.items()):
        long_out[symbol] = split_config(config)

    short_out: dict[str, Any] = {}
    for symbol, config in sorted(short_mgr.configs.items()):
        short_out[symbol] = split_config(config)

    payload = {
        "_readme": (
            "Ported from mar_trading_bot legacy configs. 'params' are strategy "
            "inputs. 'legacy_claims' are UNVALIDATED backtest figures from ~5 "
            "weeks of Q4 2024 bull-market data; treat them as hypotheses to "
            "re-verify via research/, never as measured performance. "
            "'enabled' is the legacy trading flag and is IGNORED by this "
            "project: nothing trades until research/ validation passes."
        ),
        "long": long_out,
        "short": short_out,
    }

    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")

    long_enabled = sum(1 for v in long_out.values() if v["enabled"])
    short_enabled = sum(1 for v in short_out.values() if v["enabled"])

    print(f"Wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"  LONG  configs: {len(long_out):3d} ({long_enabled} legacy-enabled)")
    print(f"  SHORT configs: {len(short_out):3d} ({short_enabled} legacy-enabled)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
