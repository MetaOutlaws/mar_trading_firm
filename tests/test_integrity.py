"""Walk-forward and paper clocks must be independently certified."""

from __future__ import annotations

from firm.integrity import certify_job, parse_job_log


def test_parse_job_log_reads_setup(tmp_path) -> None:
    log = tmp_path / "job.log"
    log.write_text(
        "\n".join(
            [
                "LONG: 3 symbols on 4h candles",
                "strategy=ema_adx_trend",
                "BTCUSDT LONG 4h: 12000 bars 2021-01-01..2026-08-31 (slippage 10.00 bps)",
                "ETHUSDT LONG 4h: 11000 bars 2021-01-01..2026-08-31 (slippage 10.00 bps)",
                "SOLUSDT LONG 4h: 10000 bars 2021-01-01..2026-08-31 (slippage 10.00 bps)",
                "SHORT: 3 symbols on 4h candles",
                "strategy=ema_adx_trend",
                "BTCUSDT SHORT 4h: 12000 bars 2021-01-01..2026-08-31 (slippage 10.00 bps)",
                "ETHUSDT SHORT 4h: 11000 bars 2021-01-01..2026-08-31 (slippage 10.00 bps)",
                "SOLUSDT SHORT 4h: 10000 bars 2021-01-01..2026-08-31 (slippage 10.00 bps)",
                "Approved: 0 of 6",
            ]
        ),
        encoding="utf-8",
    )
    parsed = parse_job_log(log)
    assert parsed["family"] == "ema_adx_trend"
    assert parsed["long_tf"] == "4h"
    assert parsed["short_tf"] == "4h"
    assert parsed["tested"] == 6
    assert parsed["slippage_bps"][0] == 10.0


def test_certify_job_fails_when_log_clock_differs_from_job(tmp_path) -> None:
    log = tmp_path / "job.log"
    log.write_text(
        "LONG: 3 symbols on 15m candles\nstrategy=donchian_breakout\n"
        "BTCUSDT LONG 15m: 1000 bars x..y (slippage 10.00 bps)\n"
        "SHORT: 3 symbols on 4h candles\nstrategy=donchian_breakout\n"
        "BTCUSDT SHORT 4h: 1000 bars x..y (slippage 10.00 bps)\n"
        "Approved: 0 of 6\n",
        encoding="utf-8",
    )
    cert = certify_job(
        {
            "id": 9,
            "family": "donchian_breakout",
            "clock": "1h/4h",
            "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            "side": "BOTH",
            "log_path": str(log),
        }
    )
    assert cert["ok"] is False
    names = {c["name"]: c["ok"] for c in cert["checks"]}
    assert names["clock_matches_job"] is False
    assert names["strategy_in_log"] is True


def test_certify_job_carries_when_the_walk_forward_finished(tmp_path) -> None:
    log = tmp_path / "job.log"
    log.write_text("strategy=rsi_trend\nApproved: 0 of 6\n", encoding="utf-8")
    cert = certify_job(
        {
            "id": 18,
            "family": "rsi_trend",
            "clock": "1h/1h",
            "symbols": ["BTCUSDT"],
            "side": "BOTH",
            "log_path": str(log),
            "started_at": "2026-08-31T10:28:36+00:00",
            "finished_at": "2026-08-31T11:06:51+00:00",
            "created_at": "2026-08-31T10:07:00+00:00",
        }
    )
    assert cert["finished_at"] == "2026-08-31T11:06:51+00:00"
    assert cert["occurred_at"] == "2026-08-31T11:06:51+00:00"
    assert cert["started_at"] == "2026-08-31T10:28:36+00:00"


def test_certify_implementation_fails_when_sleeve_missing(monkeypatch) -> None:
    from firm.integrity import certify_implementation

    monkeypatch.setattr(
        "firm.research_jobs.implementation_gaps",
        lambda: [{"family": "trend_pullback_htf", "phase": "implement"}],
    )
    pack = certify_implementation()
    assert pack["ok"] is False
    assert pack["checks"][0]["name"] == "approved_sleeve_coded"
    assert "not in list_strategies" in pack["checks"][0]["detail"]
