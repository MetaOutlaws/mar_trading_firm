"""Bybit positioning feed and paper crowding overlay."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from config.settings import TradingMode
from core.data.positioning import (
    CACHE_TTL,
    PositioningFeed,
    crowding_decision,
    crowding_label,
    crypto_cross_metrics,
    snapshot_symbols,
)
from core.execution.engine import TradingEngine, TradingPlan
from core.risk.engine import RiskDecision, RiskEngine, RiskVerdict
from core.risk.limits import PAPER_LIMITS
from core.strategy.base import Signal, SignalSide


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeClient:
    def __init__(self, routes: dict) -> None:
        self.routes = routes
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, params: dict | None = None) -> FakeResponse:
        params = params or {}
        path = url.split(".com", 1)[-1]
        self.calls.append((path, dict(params)))
        payload = self.routes.get((path, params.get("symbol")))
        if payload is None:
            payload = self.routes.get(path)
        if payload is None:
            raise RuntimeError(f"unexpected {path} {params}")
        if isinstance(payload, Exception):
            raise payload
        return FakeResponse(payload)

    def close(self) -> None:
        return None


def _ok(rows: list[dict]) -> dict:
    return {"retCode": 0, "retMsg": "OK", "result": {"list": rows}}


def _routes(
    symbol: str = "BTCUSDT",
    *,
    funding: str = "0.0001",
    oi_now: str = "110",
    oi_then: str = "100",
    buy: str = "0.50",
    hours: int = 24,
) -> dict:
    latest = 1_700_000_000_000
    prior = latest - hours * 3_600_000
    return {
        ("/v5/market/tickers", symbol): _ok(
            [{"fundingRate": funding, "openInterest": oi_now, "lastPrice": "100000"}]
        ),
        ("/v5/market/open-interest", symbol): _ok(
            [
                {"openInterest": oi_now, "timestamp": str(latest)},
                {"openInterest": oi_then, "timestamp": str(prior)},
            ]
        ),
        ("/v5/market/account-ratio", symbol): _ok(
            [{"buyRatio": buy, "sellRatio": str(1.0 - float(buy)), "timestamp": str(latest)}]
        ),
    }


def _signal(side: SignalSide = SignalSide.LONG) -> Signal:
    return Signal(
        symbol="BTCUSDT",
        side=side,
        timestamp=pd.Timestamp("2026-09-01T00:00:00Z"),
        price=100_000.0,
        score=1.0,
        reason="test",
        strategy="test",
        take_profit_pct=0.02,
        stop_loss_pct=0.01,
    )


def test_crowded_long_is_skipped() -> None:
    row = {"funding_rate": 0.0004, "oi_change_24h_pct": 3.0, "buy_ratio": 0.5}
    decision = crowding_decision(row, "LONG")
    assert decision.action == "skip"
    assert decision.size_mult == 0.0
    assert "crowding: skip LONG" in decision.reason
    assert crowding_label(row) == "crowded long"


def test_crowded_short_is_skipped() -> None:
    row = {"funding_rate": -0.0004, "oi_change_24h_pct": 5.0, "buy_ratio": 0.5}
    decision = crowding_decision(row, "SHORT")
    assert decision.action == "skip"
    assert "crowding: skip SHORT" in decision.reason


def test_high_funding_without_oi_expansion_passes() -> None:
    row = {"funding_rate": 0.0005, "oi_change_24h_pct": 0.4, "buy_ratio": 0.5}
    assert crowding_decision(row, "LONG").action == "pass"
    assert crowding_label(row) == "balanced"


def test_accounts_leaning_long_sizes_down() -> None:
    row = {"funding_rate": 0.0001, "oi_change_24h_pct": 0.5, "buy_ratio": 0.70}
    decision = crowding_decision(row, "LONG")
    assert decision.action == "size"
    assert decision.size_mult == pytest.approx(0.5)
    assert crowding_decision(row, "SHORT").action == "pass"


def test_accounts_leaning_short_sizes_down() -> None:
    row = {"funding_rate": 0.0, "oi_change_24h_pct": 0.0, "buy_ratio": 0.30}
    decision = crowding_decision(row, "SHORT")
    assert decision.action == "size"
    assert crowding_decision(row, "LONG").action == "pass"


def test_skip_wins_over_size() -> None:
    row = {"funding_rate": 0.0004, "oi_change_24h_pct": 4.0, "buy_ratio": 0.80}
    assert crowding_decision(row, "LONG").action == "skip"


def test_missing_fields_fail_open() -> None:
    assert crowding_decision(None, "LONG").action == "pass"
    assert crowding_decision({}, "LONG").action == "pass"
    assert crowding_decision({"funding_rate": 0.001}, "LONG").action == "pass"


def test_fetch_symbol_computes_oi_change() -> None:
    client = FakeClient(_routes(oi_now="120", oi_then="100"))
    feed = PositioningFeed(client=client)
    row = feed.fetch_symbol("BTCUSDT")
    assert row["oi_change_24h_pct"] == pytest.approx(20.0)
    assert row["funding_rate"] == pytest.approx(0.0001)
    assert row["buy_ratio"] == pytest.approx(0.50)


def test_fetch_symbol_fail_open_on_http_error() -> None:
    client = FakeClient(
        {
            ("/v5/market/tickers", "BTCUSDT"): RuntimeError("down"),
            ("/v5/market/open-interest", "BTCUSDT"): RuntimeError("down"),
            ("/v5/market/account-ratio", "BTCUSDT"): RuntimeError("down"),
        }
    )
    row = PositioningFeed(client=client).fetch_symbol("BTCUSDT")
    assert row["open_interest"] is None
    assert row["label"] == "unknown"
    assert crowding_decision(row, "LONG").action == "pass"


def test_snapshot_reuses_fresh_cache(tmp_path) -> None:
    path = tmp_path / "last_positioning.json"
    feed = MagicMock()
    feed.fetch_symbol.side_effect = AssertionError("network should not run")
    first = snapshot_symbols(
        ["BTCUSDT"],
        feed=PositioningFeed(client=FakeClient(_routes())),
        path=path,
        force=True,
    )
    assert "BTCUSDT" in first["symbols"]
    reused = snapshot_symbols(["BTCUSDT"], feed=feed, path=path)
    assert reused["as_of"] == first["as_of"]
    feed.fetch_symbol.assert_not_called()


def test_stale_cache_is_refetched(tmp_path) -> None:
    path = tmp_path / "last_positioning.json"
    first = snapshot_symbols(
        ["BTCUSDT"],
        feed=PositioningFeed(client=FakeClient(_routes(funding="0.0001"))),
        path=path,
        force=True,
    )
    first["as_of"] = (datetime.now(timezone.utc) - CACHE_TTL - timedelta(minutes=1)).isoformat()
    path.write_text(__import__("json").dumps(first), encoding="utf-8")
    second = snapshot_symbols(
        ["BTCUSDT"],
        feed=PositioningFeed(client=FakeClient(_routes(funding="0.0005"))),
        path=path,
    )
    assert second["symbols"]["BTCUSDT"]["funding_rate"] == pytest.approx(0.0005)


def test_eth_btc_cross_from_daily_closes(monkeypatch) -> None:
    btc = pd.DataFrame({"close": [100.0] * 7 + [100.0]}, index=range(8))
    eth = pd.DataFrame({"close": [10.0] * 7 + [12.0]}, index=range(8))

    class Stub:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def fetch_latest(self, symbol: str, timeframe: str, bars: int = 14):
            del timeframe, bars
            return eth if symbol.startswith("ETH") else btc

    monkeypatch.setattr("core.data.ohlcv.BybitOHLCV", Stub)
    cross = crypto_cross_metrics()
    assert cross["eth_btc"] == pytest.approx(0.12)
    assert cross["eth_btc_7d_pct"] == pytest.approx(20.0)


def _engine(*, mode: TradingMode) -> TradingEngine:
    engine = TradingEngine(
        broker=MagicMock(),
        risk_engine=RiskEngine(limits=PAPER_LIMITS),
        ledger=MagicMock(),
        plan=TradingPlan(),
        data_source=MagicMock(),
    )
    engine._crowding = {
        "BTCUSDT": {
            "funding_rate": 0.0004,
            "oi_change_24h_pct": 3.5,
            "buy_ratio": 0.5,
        }
    }
    return engine


def test_paper_engine_skips_crowded_long(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.execution.engine.get_settings",
        lambda: SimpleNamespace(trading_mode=TradingMode.PAPER),
    )
    engine = _engine(mode=TradingMode.PAPER)
    approved = RiskDecision(
        verdict=RiskVerdict.APPROVED, quantity=1.0, notional=1000.0, risk_amount=50.0
    )
    out = engine._apply_crowding(approved, _signal(SignalSide.LONG))
    assert not out.is_approved
    assert engine._crowding_skips == 1
    assert "crowding: skip LONG" in out.reasons[0]


def test_live_engine_does_not_apply_crowding(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.execution.engine.get_settings",
        lambda: SimpleNamespace(trading_mode=TradingMode.LIVE),
    )
    engine = _engine(mode=TradingMode.LIVE)
    approved = RiskDecision(
        verdict=RiskVerdict.APPROVED, quantity=1.0, notional=1000.0, risk_amount=50.0
    )
    out = engine._apply_crowding(approved, _signal(SignalSide.LONG))
    assert out.is_approved
    assert engine._crowding_skips == 0


def test_paper_engine_sizes_down_leaning_accounts(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.execution.engine.get_settings",
        lambda: SimpleNamespace(trading_mode=TradingMode.PAPER),
    )
    engine = _engine(mode=TradingMode.PAPER)
    engine._crowding = {
        "BTCUSDT": {
            "funding_rate": 0.0001,
            "oi_change_24h_pct": 0.5,
            "buy_ratio": 0.70,
        }
    }
    approved = RiskDecision(
        verdict=RiskVerdict.APPROVED, quantity=1.0, notional=1000.0, risk_amount=50.0
    )
    out = engine._apply_crowding(approved, _signal(SignalSide.LONG))
    assert out.is_approved
    assert out.quantity == pytest.approx(0.5)
    assert engine._crowding_cuts == 1


def test_quiet_reasons_mention_crowding() -> None:
    from api.app import _quiet_reasons

    reasons = _quiet_reasons(
        {
            "symbols_scanned": 3,
            "signals_found": 1,
            "orders_placed": 0,
            "rejections": 1,
            "crowding_skips": 1,
            "crowding_size_cuts": 0,
            "plan": [],
        },
        employee_llm_ok=True,
        xai_ok=True,
    )
    assert any("Crowding overlay skipped" in r for r in reasons)
