"""Versioned F111 configuration.

The file bytes are the hash input. The hash is not stored inside the file,
because writing it back would change it. Telemetry and logs report the hash of
the bytes that were actually read.

Paper-only is enforced here so a live plan, a testnet plan, and a process with
the go-live confirmation flag cannot activate the sleeve.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from config.settings import PROJECT_ROOT, TradingMode, get_settings

STRATEGY_ID = "mar_f111_r12_extension_latefloor_v1"
STRATEGY_VERSION = "f111-paper-v1"
CONFIG_PATH = PROJECT_ROOT / "config" / "sleeves" / "mar_f111_r12_extension_latefloor_v1.json"
# Operator rollback switch. It is not part of the hashed config: creating it
# stops new F111 entries without pretending the research thresholds changed.
DISABLE_FLAG_PATH = PROJECT_ROOT / "data" / "f111_paper_scan_disabled"
STATE_PATH = PROJECT_ROOT / "data" / "f111_paper_state.json"
TELEMETRY_PATH = PROJECT_ROOT / "data" / "f111_telemetry.jsonl"

RETIRED_ENTRY_SLEEVES = (
    "hourly_compression_v1",
    "hourly_compression_connors_v1",
    "hourly_compression_btc_connors_v1",
    "hourly_compression_btc_connors_loweff_v1",
)

TELEMETRY_FIELDS = (
    "strategy_version",
    "configuration_sha256",
    "source_signal_id",
    "source_signal_time",
    "symbol",
    "cohort",
    "sector",
    "side",
    "feature_values",
    "feature_asof_times",
    "gate_decision",
    "rejection_reason",
    "pending_retest_created_at",
    "touch_time",
    "reclaim_time",
    "pending_expiry",
    "action_time",
    "quote_time",
    "reference_price",
    "simulated_fill",
    "fill_assumptions",
    "original_ATR",
    "original_risk_R_units",
    "initial_stop",
    "target",
    "activation_time",
    "floor_decided_at",
    "floor_effective_at",
    "configured_stop",
    "estimated_cost_aware_exit_value",
    "realised_net_profit",
    "entry_fee",
    "exit_fee",
    "funding_events",
    "net_R",
    "poll_latency",
    "missing_candle_or_quote",
    "instrument_unavailable",
    "occupancy_or_risk_rejection",
    "run_id",
)


def load_f111_config(path: Path | None = None) -> tuple[dict, str]:
    """Return ``(config, sha256 hex of the file bytes)``."""
    source = path or CONFIG_PATH
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    config = json.loads(raw)
    if config.get("strategy_id") != STRATEGY_ID:
        raise RuntimeError("F111 config strategy_id does not match the implementation")
    if config.get("live_authorized") is not False:
        raise RuntimeError("F111 config must keep live_authorized false")
    if config.get("paper_authorized") is not True:
        raise RuntimeError("F111 config is not paper-authorized")
    if config.get("historical_2026_backtest_opened") is not False:
        raise RuntimeError("F111 historical 2026 backtests stay closed")
    if config.get("saved_path_parity") != "UNVERIFIED":
        raise RuntimeError("saved-path parity must stay UNVERIFIED without the private archive")
    universe = config.get("universe") or []
    if len(universe) != 96 or len(set(universe)) != 96:
        raise RuntimeError("F111 universe must be the 96 supplied symbols")
    if int(config.get("expected_scan_sleeves") or 0) != 192:
        raise RuntimeError("F111 scan must cover 192 sleeves")
    return config, digest


def configuration_sha256(path: Path | None = None) -> str:
    _config, digest = load_f111_config(path)
    return digest


def scan_enabled(config: dict, disable_flag: Path | None = None) -> bool:
    """True only when the versioned config allows a scan and the operator flag is absent."""
    if config.get("paper_scan_enabled") is not True:
        return False
    flag = DISABLE_FLAG_PATH if disable_flag is None else disable_flag
    return not flag.exists()


def assert_f111_paper_only(settings=None) -> None:
    """Refuse anything except an unconfirmed paper process.

    ``TRADING_MODE`` other than paper is refused. The go-live confirmation
    phrase is refused even if the mode still says paper, because that flag is
    the live arming switch.
    """
    from config.settings import LIVE_CONFIRMATION_PHRASE

    settings = settings or get_settings()
    mode = settings.trading_mode
    if mode is not TradingMode.PAPER:
        raise RuntimeError(
            f"F111 refuses to run: TRADING_MODE={getattr(mode, 'value', mode)} is not paper"
        )
    confirmed = str(getattr(settings, "go_live_confirmed", "") or "")
    if confirmed:
        raise RuntimeError(
            "F111 refuses to run: a live confirmation flag is set "
            f"(go-live phrase is {LIVE_CONFIRMATION_PHRASE!r})"
        )
    config, _digest = load_f111_config()
    if config.get("live_authorized") is not False:
        raise RuntimeError("F111 refuses to run: live_authorized is not false")


def cohort_of(symbol: str, config: dict | None = None) -> str:
    """BTC/ETH/SOL are reference3. Every other supplied symbol is additional93."""
    if config is None:
        config, _digest = load_f111_config()
    reference = set(config.get("reference3_symbols") or ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    if symbol in reference:
        return "reference3"
    return "additional93"


def refuse_historical_backtest(requested: bool) -> None:
    """The 2026 research window stays closed. Forward paper after activation is separate."""
    if requested:
        raise RuntimeError("F111 historical 2026 backtests stay closed")


def assert_not_a_second_worker(start_process: bool) -> None:
    """F111 attaches to the existing paper loop. It does not start another one."""
    if start_process:
        raise RuntimeError(
            "F111 must not start a duplicate paper worker. "
            "Use the existing SGP1 paper process."
        )
