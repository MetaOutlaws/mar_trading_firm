"""Paper fib_extension_break: empty regime label must not abort the bar.

SGP1 paper polls BTC/AVAX/BNB/UNI 4h SHORT every few seconds and logged
``could not convert string to float: ''``. The book params on those rows are
numbers. The empty string is the ``regime`` column ``generate_signals`` writes
when the poll's window (``min_bars + 50``) has not warmed SMA(200).
``latest_signal`` used to float every extra column, so ``float('')`` raised
and the paper poll counted an eval error.

The label is not a trade input. The cell is left out of the indicator
payload (no invented 0) and the signal ``generate_signals`` already computed
is unchanged.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
import pytest

from core.execution.engine import _named_strategy
from core.execution.paper_bar_eval import poll_paper_book, sleeve_key
from core.strategy.base import (
    SIGNAL_COLUMNS,
    SignalSide,
    Strategy,
    _SKIPPED_INDICATOR_LOGGED,
)
from tests.test_novel_sleeves import _impulse_then_extension
from tests.test_paper_bar_eval import Clock, _at, _engine, _entry

ROOT = Path(__file__).resolve().parents[1]
BOOK_PATH = ROOT / "config" / "approved_strategies.json"

# The four sleeves that logged the ValueError on SGP1.
BOOK_KEYS = (
    "fib_extension_break:BTCUSDT:SHORT:4h",
    "fib_extension_break:AVAXUSDT:SHORT:4h",
    "fib_extension_break:BNBUSDT:SHORT:4h",
    "fib_extension_break:UNIUSDT:SHORT:4h",
)


def _book() -> dict:
    return json.loads(BOOK_PATH.read_text(encoding="utf-8"))


def _empty_strings(value: object, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.extend(_empty_strings(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_empty_strings(item, f"{path}[{index}]"))
    elif isinstance(value, str) and value.strip() == "":
        found.append(path or "<root>")
    return found


def _production_window(min_bars: int) -> pd.DataFrame:
    """Same shape the paper poll fetches: min_bars+50 closed-style OHLCV, no regime."""
    bars = int(min_bars) + 50
    index = pd.date_range("2026-01-01", periods=bars, freq="4h", tz="UTC")
    close = [100_000.0] * bars
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": [1.0] * bars,
            "turnover": [1.0] * bars,
        },
        index=index,
    )
    frame.index.name = "timestamp"
    return frame


def _sleeve(key: str):
    record = _book()[key]
    symbol = key.split(":")[1]
    strategy = _named_strategy(
        "fib_extension_break",
        symbol,
        SignalSide.SHORT,
        record["params"],
    )
    return record, symbol, strategy


@pytest.mark.parametrize("key", BOOK_KEYS)
def test_empty_regime_raises_on_float_and_latest_signal_skips_the_cell(key, caplog) -> None:
    """Production window: float('') is the old error; the sleeve does not raise.

    Flat prices so the bar itself is not an entry. The logged reason names the
    empty field. A second call on the same bar does not log it again.
    """
    record, symbol, strategy = _sleeve(key)
    assert _empty_strings(record) == []
    params = record["params"]
    assert isinstance(params["fib_ratio"], (int, float))
    assert params["fib_ratio"] != ""

    candles = _production_window(strategy.min_bars)
    assert "regime" not in candles.columns
    signals = strategy.generate_signals(candles)
    regime = signals["regime"].iloc[-1]
    assert regime == ""
    with pytest.raises(ValueError, match="could not convert string to float"):
        float(regime)

    _SKIPPED_INDICATOR_LOGGED.clear()
    caplog.set_level(logging.INFO, logger="core.strategy.base")
    first = strategy.latest_signal(symbol, candles)
    second = strategy.latest_signal(symbol, candles)

    assert first is None
    assert second is None
    assert strategy._last_eval_reason == "no_signal"
    skipped = [
        rec.message
        for rec in caplog.records
        if rec.message.startswith("sleeve indicator skipped")
        and "skip_reason=missing_value:regime" in rec.message
        and f"symbol={symbol}" in rec.message
    ]
    assert skipped == [
        "sleeve indicator skipped "
        f"strategy=fib_extension_break symbol={symbol} "
        f"bar={signals.index[-1].isoformat()} skip_reason=missing_value:regime"
    ]
    assert all(rec.levelno == logging.INFO for rec in caplog.records if rec.message in skipped)


def test_paper_poll_does_not_count_empty_regime_as_eval_error(
    tmp_path, monkeypatch, firm_db, caplog
) -> None:
    """The 15s poll used to warn and leave the bar unmarked, so every retry errored."""
    strategy = _sleeve("fib_extension_break:BTCUSDT:SHORT:4h")[2]
    clock_at = _at(12, 1)
    engine = _engine(
        tmp_path,
        monkeypatch,
        Clock(clock_at),
        [_entry("BTCUSDT", SignalSide.SHORT, strategy, "4h")],
    )
    _SKIPPED_INDICATOR_LOGGED.clear()
    caplog.set_level(logging.INFO, logger="core.strategy.base")
    caplog.set_level(logging.INFO, logger="core.execution.paper_bar_eval")

    assert poll_paper_book(engine, budget_seconds=30) == 1
    assert poll_paper_book(engine, budget_seconds=30) == 0

    failed = [rec for rec in caplog.records if "paper bar eval failed" in rec.message]
    assert failed == []
    assert not any("could not convert string to float" in rec.message for rec in caplog.records)

    state = json.loads((tmp_path / "paper_bar_eval_state.json").read_text(encoding="utf-8"))
    row = state["sleeves"][sleeve_key(engine.plan.entries[0])]
    assert row["signal"] == "none"
    assert row["reason"] == "no_signal"
    assert "could not convert string to float" not in row["reason"]

    skipped = [
        rec.message
        for rec in caplog.records
        if "skip_reason=missing_value:regime" in rec.message
    ]
    assert len(skipped) == 1
    evals = [
        rec.message
        for rec in caplog.records
        if rec.message.startswith("paper bar eval sleeve=BTCUSDT|4h|SHORT|fib_extension_break")
    ]
    assert len(evals) == 1
    assert "signal=none" in evals[0]
    assert "reason=no_signal" in evals[0]


def test_valid_numeric_entry_matches_generate_signals() -> None:
    """A real SHORT, with the same empty regime cell, still matches the backtest row.

    Numeric indicator cells are the floats they were before. regime is omitted,
    not replaced with 0.
    """
    strategy = _sleeve("fib_extension_break:BTCUSDT:SHORT:4h")[2]
    candles = _impulse_then_extension(long_side=False)
    scanned = strategy.generate_signals(candles)
    fired = list(scanned.index[scanned["signal"] == -1])
    assert fired
    window = candles.loc[: fired[0]]
    expected = strategy.generate_signals(window)
    last = expected.iloc[-1]
    assert int(last["signal"]) == -1
    assert last["regime"] == ""
    with pytest.raises(ValueError, match="could not convert string to float"):
        float(last["regime"])

    _SKIPPED_INDICATOR_LOGGED.clear()
    live = strategy.latest_signal("BTCUSDT", window)
    assert live is not None
    assert live.side.value == last["side"]
    assert live.score == pytest.approx(float(last["score"]))
    assert live.reason == last["reason"]
    assert live.price == pytest.approx(float(window["close"].iloc[-1]))
    assert live.take_profit_pct == pytest.approx(strategy.params.take_profit_pct)
    assert live.stop_loss_pct == pytest.approx(strategy.params.stop_loss_pct)

    numeric = {
        column: float(last[column])
        for column in expected.columns
        if column not in SIGNAL_COLUMNS and pd.notna(last[column])
        and _coerces(last[column])
    }
    assert live.indicators == pytest.approx(numeric)
    assert "regime" not in live.indicators


def _coerces(value: object) -> bool:
    try:
        float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return True


class _NumericProbe(Strategy):
    """Extra columns are only numbers, including a bool flag."""

    name = "numeric_probe"
    min_bars = 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        out = self.empty_signals(candles)
        out["level"] = candles["close"].astype(float)
        out["flag"] = True
        out.iloc[-1, out.columns.get_loc("signal")] = -1
        out.iloc[-1, out.columns.get_loc("side")] = SignalSide.SHORT.value
        out.iloc[-1, out.columns.get_loc("score")] = 0.25
        out.iloc[-1, out.columns.get_loc("reason")] = "probe"
        return out


def test_numeric_indicator_columns_stay_identical() -> None:
    """The old float() payload for an all-numeric frame is unchanged."""
    candles = _production_window(2)
    strategy = _NumericProbe()
    signals = strategy.generate_signals(candles)
    last = signals.iloc[-1]
    old = {
        column: float(last[column])
        for column in signals.columns
        if column not in SIGNAL_COLUMNS and pd.notna(last[column])
    }
    live = strategy.latest_signal("BTCUSDT", candles)
    assert live is not None
    assert live.side is SignalSide.SHORT
    assert live.score == pytest.approx(0.25)
    assert live.reason == "probe"
    assert live.indicators == old
    assert live.indicators["flag"] == pytest.approx(1.0)
    assert live.indicators["level"] == pytest.approx(100_000.0)
