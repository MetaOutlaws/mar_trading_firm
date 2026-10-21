"""Paper sleeves appended to the approval book.

Old rows stay byte-identical. New rows are paper overrides with the frozen
params and the 4h clock. Live ``build_plan`` does not select them.
``core/risk/limits.py`` is hash-pinned, including the paper cap of 15.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from config.universe import parse_approval_key
from core.strategy.ema_adx_trend import EmaAdxParams
from core.strategy.range_compression_volume_thrust import (
    RangeCompressionVolumeThrustParams,
)
from core.strategy.doji_star_reversal import DojiStarParams
from firm.paper_universe_sleeves import (
    BOOK_PATH,
    C1C2_OUTSIDE_UNIVERSE,
    C1C2_ROWS,
    C1C2_SOURCE_KEY,
    CLOSED_REASON,
    DOJI_SOURCE_KEY,
    EXCHANGE_STATUS_BY_SYMBOL,
    RISK_LIMITS_PATH,
    append_c1c2_sleeves,
    append_doji_sleeves,
    append_sleeves,
    approved_doji_params,
    book_sha256,
    closed_exclusions,
    feature_exclusions,
    frozen_params,
    frozen_timeframe,
    outside_universe_block,
    plan_c1c2_sleeves,
    plan_doji_sleeves,
    plan_sleeves,
    required_complete_bars,
    sgp1_paper_universe,
    splice_records,
)
from firm.research_jobs import CLOCK_BY_FAMILY

# SHA-256 of the deployed SGP1 book before this append.
# Same method as research.revalidation.fingerprint_approval_book: raw bytes.
# The file ends in ``}\n}\n``; the splice puts a comma on the last record brace.
OLD_BOOK_SHA256 = (
    "9fe4bdd9dc0a22ea6ef6a270145df8d0cef465c1eba0dd9818bcd6d3c178e4f0"
)
OLD_BOOK_LEN = 1579403
OLD_BOOK_CLOSER = b"\n}\n"
# core/risk/limits.py after the paper max_concurrent_positions=15 pin.
# RiskLimits defaults and INITIAL_LIVE_LIMITS stay at their b00c4f73 values.
RISK_LIMITS_SHA256 = (
    "8a9c3e8aee449814767d00e148f015d7d70bb022f76c934056052738e9f67684"
)

RULES = ("ema_adx_trend", "range_compression_volume_thrust")


def _historical_book(current: bytes) -> bytes:
    """Recover the pre-append file from the spliced bytes.

    The splice writes a comma at the old index of the final newline. Putting
    that newline back and dropping everything after it is the old file.
    """
    assert len(current) >= OLD_BOOK_LEN
    comma_at = OLD_BOOK_LEN - len(OLD_BOOK_CLOSER)
    assert current[comma_at : comma_at + 1] == b","
    restored = current[:comma_at] + OLD_BOOK_CLOSER
    assert len(restored) == OLD_BOOK_LEN
    assert book_sha256(restored) == OLD_BOOK_SHA256
    return restored


def test_frozen_clocks_and_params_are_the_repo_defaults() -> None:
    assert CLOCK_BY_FAMILY["ema_adx_trend"] == "4h/4h"
    assert CLOCK_BY_FAMILY["range_compression_volume_thrust"] == "4h/4h"
    assert frozen_timeframe("ema_adx_trend") == "4h"
    assert frozen_timeframe("range_compression_volume_thrust") == "4h"

    ema = frozen_params("ema_adx_trend")
    assert ema == {
        "ema_fast": EmaAdxParams.ema_fast,
        "ema_slow": EmaAdxParams.ema_slow,
        "adx_period": EmaAdxParams.adx_period,
        "min_adx": EmaAdxParams.min_adx,
        "take_profit_pct": EmaAdxParams.take_profit_pct,
        "stop_loss_pct": EmaAdxParams.stop_loss_pct,
        "max_holding_bars": EmaAdxParams.max_holding_bars,
    }
    assert ema["min_adx"] == 20.0
    assert "side" not in ema

    thrust = frozen_params("range_compression_volume_thrust")
    defaults = RangeCompressionVolumeThrustParams()
    assert thrust["compress_pct"] == defaults.compress_pct == 0.30
    assert thrust["thrust_mult"] == defaults.thrust_mult == 1.5
    assert thrust["atr_period"] == 20
    assert thrust["compress_lookback"] == 100
    assert "side" not in thrust
    assert required_complete_bars() == 102


def test_universe_is_the_96_sgp1_symbols() -> None:
    symbols = sgp1_paper_universe()
    assert len(symbols) == 96
    assert symbols[0] == "1000BONKUSDT"
    assert "BTCUSDT" in symbols and "ETHUSDT" in symbols and "SOLUSDT" in symbols


def test_feature_history_covers_the_universe_and_closed_needs_a_census() -> None:
    symbols = sgp1_paper_universe()
    assert feature_exclusions(symbols) == {}
    assert closed_exclusions(symbols, {}) == {}
    assert closed_exclusions(["MATICUSDT"], {"MATICUSDT": "Closed"}) == {
        "MATICUSDT": CLOSED_REASON
    }
    assert set(EXCHANGE_STATUS_BY_SYMBOL) == {
        "AERGOUSDT",
        "AKROUSDT",
        "BLZUSDT",
        "EOSUSDT",
        "FETUSDT",
        "FLMUSDT",
        "FTMUSDT",
        "LINAUSDT",
        "LUNAUSDT",
        "MATICUSDT",
        "REEFUSDT",
        "RNDRUSDT",
        "SXPUSDT",
        "TOMOUSDT",
        "TONUSDT",
        "UNFIUSDT",
        "UXLINKUSDT",
    }
    assert all(status == "Closed" for status in EXCHANGE_STATUS_BY_SYMBOL.values())
    assert closed_exclusions(["BTCUSDT"], {"BTCUSDT": "Trading"}) == {}
    # A short tape is a feature exclusion. The real seed is not short.
    short = feature_exclusions.__wrapped__ if hasattr(feature_exclusions, "__wrapped__") else None
    assert short is None


def test_short_tape_is_excluded(monkeypatch, tmp_path) -> None:
    seed = tmp_path / "seed.json"
    seed.write_text(
        json.dumps({"records": {"BTCUSDT": {"complete_bars": 10}, "ETHUSDT": {"complete_bars": 500}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr("firm.paper_universe_sleeves.SEED_PATH", seed)
    reasons = feature_exclusions(["BTCUSDT", "ETHUSDT", "GONEUSDT"])
    assert "complete_bars 10" in reasons["BTCUSDT"]
    assert "GONEUSDT" in reasons
    assert "ETHUSDT" not in reasons


def test_splice_keeps_old_bytes_and_refuses_to_overwrite(tmp_path) -> None:
    original = b'{\n  "old:BTCUSDT:LONG:4h": {"approved": false}\n}'
    added = {
        "ema_adx_trend:ETHUSDT:LONG:4h": {
            "approved": False,
            "paper_override": True,
            "strategy": "ema_adx_trend",
            "timeframe": "4h",
        }
    }
    updated = splice_records(original, added)
    assert updated.startswith(original[:-2])
    assert updated[len(original) - 2 : len(original) - 1] == b","
    parsed = json.loads(updated)
    assert parsed["old:BTCUSDT:LONG:4h"] == {"approved": False}
    assert parsed["ema_adx_trend:ETHUSDT:LONG:4h"]["approved"] is False
    assert splice_records(updated, {}) == updated
    # Deployed SGP1 book: root brace, then a trailing newline.
    deployed = b'{\n  "old:BTCUSDT:LONG:4h": {"approved": false}\n}\n'
    deployed_updated = splice_records(deployed, added)
    assert deployed_updated[: len(deployed) - 3] == deployed[:-3]
    assert deployed_updated[len(deployed) - 3 : len(deployed) - 2] == b","
    assert deployed_updated.endswith(b"\n}\n")
    assert json.loads(deployed_updated)["old:BTCUSDT:LONG:4h"] == {"approved": False}


def test_plan_skips_only_the_same_timeframe() -> None:
    """A 1h ema row does not block the 4h paper sleeve. The 4h key does."""
    book = {
        "ema_adx_trend:BTCUSDT:LONG:1h": {
            "approved": False,
            "strategy": "ema_adx_trend",
            "timeframe": "1h",
        }
    }
    decision = plan_sleeves(book, symbols=["BTCUSDT"])
    assert decision["skipped"] == []
    assert "ema_adx_trend:BTCUSDT:LONG:4h" in decision["added"]
    assert "ema_adx_trend:BTCUSDT:SHORT:4h" in decision["added"]
    assert all(row["approved"] is False for row in decision["added"].values())
    assert all(row["live_authorized"] is False for row in decision["added"].values())

    booked = {
        "ema_adx_trend:BTCUSDT:LONG:4h": {
            "approved": False,
            "strategy": "ema_adx_trend",
            "timeframe": "4h",
        }
    }
    again = plan_sleeves(booked, symbols=["BTCUSDT"])
    skipped = {
        (row["strategy"], row["symbol"], row["side"], row["timeframe"])
        for row in again["skipped"]
    }
    assert skipped == {("ema_adx_trend", "BTCUSDT", "LONG", "4h")}
    assert "ema_adx_trend:BTCUSDT:SHORT:4h" in again["added"]
    assert "ema_adx_trend:BTCUSDT:LONG:4h" not in again["added"]


def test_committed_book_old_rows_are_byte_identical() -> None:
    """The pre-append file hashes to the recorded digest. New keys only follow it."""
    current = BOOK_PATH.read_bytes()
    historical = _historical_book(current)
    old = json.loads(historical)
    new = json.loads(current)
    for key, value in old.items():
        assert new[key] == value
    added_keys = [key for key in new if key not in old]
    assert added_keys
    allowed_families = {
        *RULES,
        "doji_star_reversal",
        "monday_range_sweep_reversal",
        "week_open_reclaim",
        "double_top_neckline_break",
        "fib_extension_break",
    }
    assert all(key.split(":")[0] in allowed_families for key in added_keys)
    assert all(new[key]["approved"] is False for key in added_keys)
    assert all(new[key]["paper_override"] is True for key in added_keys)
    assert all(
        new[key]["timeframe"] == "4h" for key in added_keys if key.split(":")[0] in RULES
    )
    # A second append is a no-op, so the digest cannot move under a re-run.
    again, decision = append_sleeves(current)
    assert again == current
    assert decision["added"] == {}


def test_skipped_majors_and_added_count() -> None:
    current = BOOK_PATH.read_bytes()
    historical = json.loads(_historical_book(current))
    decision = plan_sleeves(historical)
    skipped = {
        (row["strategy"], row["symbol"], row["side"], row["timeframe"])
        for row in decision["skipped"]
    }
    majors = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "AVAXUSDT")
    expected_skips = {
        ("range_compression_volume_thrust", symbol, side, "4h")
        for symbol in majors
        for side in ("LONG", "SHORT")
    }
    expected_skips.update(
        {
            ("ema_adx_trend", symbol, side, "4h")
            for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT")
            for side in ("LONG", "SHORT")
        }
    )
    expected_skips.update(
        {
            ("ema_adx_trend", symbol, "SHORT", "4h")
            for symbol in ("BNBUSDT", "XRPUSDT", "AVAXUSDT")
        }
    )
    assert skipped == expected_skips
    excluded = {row["symbol"]: row["reason"] for row in decision["excluded"]}
    assert set(excluded) == set(EXCHANGE_STATUS_BY_SYMBOL)
    assert set(excluded.values()) == {CLOSED_REASON}
    # 96 tokens, minus 17 Closed, times 2 rules times 2 sides, minus 21 existing 4h keys.
    assert len(decision["added"]) == (96 - 17) * 2 * 2 - 21
    new = json.loads(current)
    assert set(decision["added"]) <= set(new)
    closed_names = set(EXCHANGE_STATUS_BY_SYMBOL)
    assert all(key.split(":")[1] not in closed_names for key in decision["added"])
    old_rows = sum(1 for key in historical if parse_approval_key(key) is not None)
    new_rows = sum(1 for key in new if parse_approval_key(key) is not None)
    doji_added = [
        key
        for key in new
        if key not in historical and key.split(":")[0] == "doji_star_reversal"
    ]
    c1c2_added = [
        key
        for key in new
        if key not in historical
        and key not in decision["added"]
        and key.split(":")[0] != "doji_star_reversal"
    ]
    assert old_rows == 1812
    assert new_rows == old_rows + len(decision["added"]) + len(doji_added) + len(c1c2_added)
    assert book_sha256(current) != OLD_BOOK_SHA256


def test_live_plan_does_not_select_the_new_sleeves(monkeypatch) -> None:
    from config.universe import Universe
    from core.execution.engine import build_plan

    book = json.loads(BOOK_PATH.read_text(encoding="utf-8"))
    universe = Universe(approvals={k: v for k, v in book.items() if isinstance(v, dict)})
    monkeypatch.setattr("core.execution.engine.get_universe", lambda: universe)
    monkeypatch.setattr("core.data.soko_trend.read_live_soko_trend", lambda: "chop")
    live = build_plan(require_approval=True)
    live_ids = {
        (entry.strategy.name, entry.symbol, entry.side.value, entry.timeframe)
        for entry in live.entries
    }
    # Already approved on the deployed book. The new rows are not.
    assert ("range_compression_volume_thrust", "XRPUSDT", "SHORT", "4h") in live_ids
    assert ("ema_adx_trend", "ADAUSDT", "LONG", "4h") not in live_ids
    assert ("range_compression_volume_thrust", "ADAUSDT", "LONG", "4h") not in live_ids
    assert ("ema_adx_trend", "MATICUSDT", "LONG", "4h") not in live_ids
    paper = build_plan(require_approval=False)
    paper_ids = {
        (entry.strategy.name, entry.symbol, entry.side.value, entry.timeframe)
        for entry in paper.entries
    }
    # Already in the book as rejected walks, not promoted to paper.
    assert ("range_compression_volume_thrust", "BTCUSDT", "LONG", "4h") not in paper_ids
    assert ("ema_adx_trend", "BTCUSDT", "LONG", "4h") not in paper_ids
    assert ("ema_adx_trend", "ADAUSDT", "LONG", "4h") in paper_ids
    assert ("ema_adx_trend", "ADAUSDT", "SHORT", "4h") in paper_ids
    assert ("range_compression_volume_thrust", "ADAUSDT", "LONG", "4h") in paper_ids
    assert ("range_compression_volume_thrust", "ADAUSDT", "SHORT", "4h") in paper_ids
    assert ("ema_adx_trend", "MATICUSDT", "LONG", "4h") not in paper_ids


def test_risk_limits_file_is_unchanged() -> None:
    digest = hashlib.sha256(RISK_LIMITS_PATH.read_bytes()).hexdigest()
    assert digest == RISK_LIMITS_SHA256


def test_append_refuses_an_approved_row(monkeypatch) -> None:
    raw = b'{\n  "_verdict": "x"\n}'
    bad = {
        "ema_adx_trend:ADAUSDT:LONG:4h": {
            "approved": True,
            "paper_override": True,
            "strategy": "ema_adx_trend",
            "timeframe": "4h",
            "params": {},
        }
    }

    def _plan(_book):
        return {"added": bad, "skipped": [], "excluded": []}

    monkeypatch.setattr("firm.paper_universe_sleeves.plan_sleeves", _plan)
    with pytest.raises(ValueError, match="must not be approved"):
        append_sleeves(raw)


# SHA-256 of the book after the ema/thrust append (#134) and before doji.
PRIOR_BOOK_SHA256 = (
    "c69ac33f7cf08eb4bb0eb80591b240193351a6bd54584eba483e05b16a103117"
)
PRIOR_BOOK_LEN = 1808682


def _book_before_doji(current: bytes) -> bytes:
    """Recover the c69ac33f file from the doji splice."""
    assert len(current) >= PRIOR_BOOK_LEN
    comma_at = PRIOR_BOOK_LEN - len(OLD_BOOK_CLOSER)
    assert current[comma_at : comma_at + 1] == b","
    restored = current[:comma_at] + OLD_BOOK_CLOSER
    assert len(restored) == PRIOR_BOOK_LEN
    assert book_sha256(restored) == PRIOR_BOOK_SHA256
    return restored


def test_doji_params_come_from_the_approved_sol_short_row() -> None:
    current = BOOK_PATH.read_bytes()
    historical = json.loads(_book_before_doji(current))
    params = approved_doji_params(historical)
    assert params == {"run_bars": 3, "take_profit_pct": 0.05, "stop_loss_pct": 0.03}
    defaults = DojiStarParams()
    assert params["run_bars"] == defaults.run_bars == 3
    assert params["take_profit_pct"] != defaults.take_profit_pct
    assert params["stop_loss_pct"] != defaults.stop_loss_pct
    assert defaults.take_profit_pct == 0.04
    assert defaults.stop_loss_pct == 0.02
    assert "max_body_frac" not in params
    assert "max_holding_bars" not in params


def test_doji_append_keeps_c69ac33f_and_skips_existing_1h() -> None:
    current = BOOK_PATH.read_bytes()
    historical_raw = _book_before_doji(current)
    historical = json.loads(historical_raw)
    # The approved SOL short row is the same object before and after.
    assert historical[DOJI_SOURCE_KEY]["approved"] is True
    assert json.loads(current)[DOJI_SOURCE_KEY] == historical[DOJI_SOURCE_KEY]
    decision = plan_doji_sleeves(historical)
    skipped = {
        (row["strategy"], row["symbol"], row["side"], row["timeframe"])
        for row in decision["skipped"]
    }
    expected_skips = {
        ("doji_star_reversal", symbol, side, "1h")
        for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT")
        for side in ("LONG", "SHORT")
    }
    expected_skips.update(
        {
            ("doji_star_reversal", symbol, "SHORT", "1h")
            for symbol in ("BNBUSDT", "XRPUSDT", "AVAXUSDT")
        }
    )
    assert skipped == expected_skips
    assert ("doji_star_reversal", "SOLUSDT", "SHORT", "1h") in skipped
    excluded = {row["symbol"] for row in decision["excluded"]}
    assert excluded == set(EXCHANGE_STATUS_BY_SYMBOL)
    # 79 tradable symbols, both sides, minus 9 existing 1h keys.
    assert len(decision["added"]) == 79 * 2 - 9
    assert DOJI_SOURCE_KEY not in decision["added"]
    new = json.loads(current)
    assert set(decision["added"]) <= set(new)
    assert all(new[key]["approved"] is False for key in decision["added"])
    assert all(new[key]["live_authorized"] is False for key in decision["added"])
    assert all(new[key]["timeframe"] == "1h" for key in decision["added"])
    assert all(new[key]["params"] == decision["params"] for key in decision["added"])
    assert all(key.split(":")[1] not in excluded for key in decision["added"])
    old_rows = sum(1 for key in historical if parse_approval_key(key) is not None)
    new_rows = sum(1 for key in new if parse_approval_key(key) is not None)
    later = [
        key
        for key in new
        if key not in historical and key not in decision["added"]
    ]
    assert old_rows == 2107
    assert new_rows == old_rows + len(decision["added"]) + len(later)
    approved = sum(
        1
        for key, value in new.items()
        if parse_approval_key(key) is not None and value.get("approved") is True
    )
    assert approved == 12
    again, second = append_doji_sleeves(current)
    assert again == current
    assert second["added"] == {}


def test_live_plan_does_not_select_new_doji_rows(monkeypatch) -> None:
    from config.universe import Universe
    from core.execution.engine import build_plan

    book = json.loads(BOOK_PATH.read_text(encoding="utf-8"))
    universe = Universe(approvals={k: v for k, v in book.items() if isinstance(v, dict)})
    monkeypatch.setattr("core.execution.engine.get_universe", lambda: universe)
    monkeypatch.setattr("core.data.soko_trend.read_live_soko_trend", lambda: "chop")
    live = build_plan(require_approval=True)
    live_ids = {
        (entry.strategy.name, entry.symbol, entry.side.value, entry.timeframe)
        for entry in live.entries
    }
    # Pre-existing approval. New paper rows stay off the live plan.
    assert ("doji_star_reversal", "SOLUSDT", "SHORT", "1h") in live_ids
    assert ("doji_star_reversal", "ADAUSDT", "LONG", "1h") not in live_ids
    assert ("doji_star_reversal", "ADAUSDT", "SHORT", "1h") not in live_ids
    assert ("doji_star_reversal", "BNBUSDT", "LONG", "1h") not in live_ids
    assert ("doji_star_reversal", "MATICUSDT", "LONG", "1h") not in live_ids
    paper = build_plan(require_approval=False)
    paper_ids = {
        (entry.strategy.name, entry.symbol, entry.side.value, entry.timeframe)
        for entry in paper.entries
    }
    assert ("doji_star_reversal", "ADAUSDT", "LONG", "1h") in paper_ids
    assert ("doji_star_reversal", "ADAUSDT", "SHORT", "1h") in paper_ids
    assert ("doji_star_reversal", "BNBUSDT", "LONG", "1h") in paper_ids
    # Existing rejected 1h rows were not promoted.
    assert ("doji_star_reversal", "BTCUSDT", "LONG", "1h") not in paper_ids
    assert ("doji_star_reversal", "MATICUSDT", "SHORT", "1h") not in paper_ids


# SHA-256 of the book after the doji append (#137) and before the C1/C2 rows.
DOJI_BOOK_SHA256 = (
    "a6140daf5d6d996d22fab79fc3fe0f8d97a7814d58b7cd90546253c3fa60b643"
)
DOJI_BOOK_LEN = 1908603


def _book_before_c1c2(current: bytes) -> bytes:
    """Recover the a6140daf file from the C1/C2 splice."""
    assert len(current) >= DOJI_BOOK_LEN
    comma_at = DOJI_BOOK_LEN - len(OLD_BOOK_CLOSER)
    assert current[comma_at : comma_at + 1] == b","
    restored = current[:comma_at] + OLD_BOOK_CLOSER
    assert len(restored) == DOJI_BOOK_LEN
    assert book_sha256(restored) == DOJI_BOOK_SHA256
    return restored


def test_c1c2_families_are_registered_and_outside_symbols_are_planable() -> None:
    """No new strategy code. UNI and FIL are outside the 96 and still planable."""
    from core.strategy.registry import get_strategy

    families = {row[0] for row in C1C2_ROWS}
    for family in families:
        assert get_strategy(family).name == family
    universe = set(sgp1_paper_universe())
    assert C1C2_OUTSIDE_UNIVERSE.isdisjoint(universe)
    assert outside_universe_block("UNIUSDT") is None
    assert outside_universe_block("FILUSDT") is None
    assert outside_universe_block("SHIB1000USDT") == "SHIB1000USDT is in KNOWN_INVALID_SYMBOLS"


def test_c1c2_append_keeps_a6140daf_and_adds_fourteen() -> None:
    """Clocks are the C1/C2 result rows. Params are the approved survivor's."""
    current = BOOK_PATH.read_bytes()
    historical_raw = _book_before_c1c2(current)
    historical = json.loads(historical_raw)
    decision = plan_c1c2_sleeves(historical)
    assert decision["skipped"] == []
    assert list(decision["added"]) == [
        f"{family}:{symbol}:{side}:{timeframe}" for family, symbol, side, timeframe in C1C2_ROWS
    ]
    assert len(decision["added"]) == 14
    params = decision["params"]
    assert decision["sources"] == C1C2_SOURCE_KEY
    for family, source_key in C1C2_SOURCE_KEY.items():
        source = historical[source_key]
        assert source["approved"] is True
        assert list(params[family]) == list(source["params"])
        assert params[family] == source["params"]
        assert "side" not in params[family]
    # Exact approved-row params. Omitted dataclass fields stay omitted.
    assert params["monday_range_sweep_reversal"] == {
        "max_sweep_pct": 0.01,
        "take_profit_pct": 0.05,
        "stop_loss_pct": 0.03,
    }
    assert params["week_open_reclaim"] == {
        "min_wrong_closes": 3,
        "vol_lookback": 20,
        "take_profit_pct": 0.03,
        "stop_loss_pct": 0.03,
    }
    assert params["double_top_neckline_break"] == {
        "lookback": 30,
        "atr_tol": 0.15,
        "take_profit_pct": 0.03,
        "stop_loss_pct": 0.03,
    }
    assert params["fib_extension_break"] == {
        "fib_ratio": 1.618,
        "take_profit_pct": 0.05,
        "stop_loss_pct": 0.02,
    }
    assert "skip_bull" not in params["fib_extension_break"]
    assert params["range_compression_volume_thrust"] == {
        "compress_pct": 0.3,
        "thrust_mult": 1.5,
        "take_profit_pct": 0.03,
        "stop_loss_pct": 0.03,
    }
    assert params["range_compression_volume_thrust"] != frozen_params(
        "range_compression_volume_thrust"
    )
    new = json.loads(current)
    assert set(decision["added"]) <= set(new)
    for source_key in C1C2_SOURCE_KEY.values():
        assert new[source_key] == historical[source_key]
    for key in decision["added"]:
        row = new[key]
        family = key.split(":")[0]
        assert row["approved"] is False
        assert row["paper_override"] is True
        assert row["live_authorized"] is False
        assert row["activation_mode"] == "unrestricted"
        assert row["params"] == params[family]
        assert row["timeframe"] == key.split(":")[3]
        assert C1C2_SOURCE_KEY[family] in row["paper_override_reason"]
    old_rows = sum(1 for key in historical if parse_approval_key(key) is not None)
    new_rows = sum(1 for key in new if parse_approval_key(key) is not None)
    assert old_rows == 2256
    assert new_rows == 2270
    approved = sum(
        1
        for key, value in new.items()
        if parse_approval_key(key) is not None and value.get("approved") is True
    )
    assert approved == 12
    again, second = append_c1c2_sleeves(current)
    assert again == current
    assert second["added"] == {}


def test_live_plan_does_not_select_c1c2_rows(monkeypatch) -> None:
    from config.universe import Universe
    from core.execution.engine import build_plan

    book = json.loads(BOOK_PATH.read_text(encoding="utf-8"))
    universe = Universe(approvals={k: v for k, v in book.items() if isinstance(v, dict)})
    monkeypatch.setattr("core.execution.engine.get_universe", lambda: universe)
    monkeypatch.setattr("core.data.soko_trend.read_live_soko_trend", lambda: "chop")
    expected = {
        (family, symbol, side, timeframe) for family, symbol, side, timeframe in C1C2_ROWS
    }
    live = build_plan(require_approval=True)
    live_ids = {
        (entry.strategy.name, entry.symbol, entry.side.value, entry.timeframe)
        for entry in live.entries
    }
    assert expected.isdisjoint(live_ids)
    # Pre-existing approvals stay on the live plan.
    assert ("monday_range_sweep_reversal", "BNBUSDT", "SHORT", "4h") in live_ids
    assert ("fib_extension_break", "BTCUSDT", "SHORT", "4h") in live_ids
    paper = build_plan(require_approval=False)
    paper_ids = {
        (entry.strategy.name, entry.symbol, entry.side.value, entry.timeframe)
        for entry in paper.entries
    }
    assert expected <= paper_ids
