"""Strategy Advisor constraints on Inbox walk order and BOTH honesty."""

from __future__ import annotations

from core.strategy.base import SignalSide
from core.strategy.registry import list_strategies
from firm.research_catalog import (
    BANNED_SHORT_CLONES,
    FIB_EXTENSION_NEAR_MISS,
    INBOX_BOTH_FAMILIES,
    INBOX_WALK_ORDER,
    NEAR_MISS_RETESTS,
    RESEARCH_HYPOTHESES,
    TODAY_CLOSE_RETESTS,
    is_banned_side_clone,
    remaining_hypotheses,
)
from firm.sleeve_factory import CANDIDATE_SPECS
from research.validate import strategy_kit


def test_inbox_walk_order_is_london_then_utc_open_then_thrust_then_climax_then_dryup() -> None:
    assert INBOX_WALK_ORDER == (
        "london_close_inventory_fade",
        "utc_open_fail_reversion",
        "range_compression_volume_thrust",
        "turnover_climax_rejection_fade",
        "volume_dryup_range_break",
    )
    leftover = remaining_hypotheses([])
    families = [str(row.get("family") or "") for row in leftover]
    first = [f for f in families if f in INBOX_WALK_ORDER]
    assert first[:5] == list(INBOX_WALK_ORDER)
    by_id = {str(row["id"]): row for row in leftover}
    for name in INBOX_WALK_ORDER:
        row = by_id[f"{name}@4h/4h"]
        assert row["side"] == "BOTH"
        assert row["clock"] == "4h/4h"


def test_inbox_names_stay_both_max_two_free_params_no_skip_bull() -> None:
    """Inbox walk-order families: five names, BOTH honest, at most two free params."""
    assert len(INBOX_BOTH_FAMILIES) == 5
    assert list(INBOX_BOTH_FAMILIES) == list(INBOX_WALK_ORDER)
    coded = set(list_strategies())
    specs = {spec.name: spec for spec in CANDIDATE_SPECS}
    for name in INBOX_BOTH_FAMILIES:
        assert name in coded
        spec = specs[name]
        assert spec.side == "BOTH"
        factory, base, space = strategy_kit(name, SignalSide.LONG)
        assert factory(base).name == name
        extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
        assert len(extra) <= 2
        assert "skip_bull" not in space
        assert "skip_bear" not in space
        _factory_s, base_s, space_s = strategy_kit(name, SignalSide.SHORT)
        assert base_s.side is SignalSide.SHORT
        assert "skip_bull" not in space_s


def test_monday_and_volume_imbalance_stay_both() -> None:
    """PR-9 families stay BOTH. No BNB SHORT monday overlay."""
    specs = {spec.name: spec for spec in CANDIDATE_SPECS}
    for name in ("monday_range_sweep_reversal", "volume_imbalance_delta_reversal"):
        assert specs[name].side == "BOTH"
        _factory, _base, space = strategy_kit(name, SignalSide.LONG)
        extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
        assert len(extra) <= 2
        assert "skip_bull" not in space


def test_no_monday_short_or_bnb_clone_overlay() -> None:
    assert ("monday_range_sweep_reversal", "SHORT") in BANNED_SHORT_CLONES
    banned = {
        "monday_range_sweep_reversal@4h/4h@SHORT",
        "monday_range_sweep_reversal@4h/4h@SHORT@bnb",
    }
    catalog = list(RESEARCH_HYPOTHESES) + list(NEAR_MISS_RETESTS)
    catalog += list(TODAY_CLOSE_RETESTS) + list(FIB_EXTENSION_NEAR_MISS)
    for row in catalog:
        assert is_banned_side_clone(row) is False
        assert str(row.get("id") or "") not in banned
        if str(row.get("family") or "") == "monday_range_sweep_reversal":
            assert str(row.get("side") or "BOTH").upper() == "BOTH"
            assert "bnbusdt" not in str(row).lower()
    from config.pipeline import PAPER_SCAN_SLEEVES

    for family, symbol, side, _tf in PAPER_SCAN_SLEEVES:
        assert not (
            family == "monday_range_sweep_reversal"
            and symbol == "BNBUSDT"
            and side == "SHORT"
        )


def test_postmortem_does_not_keep_monday_bnb_short(tmp_path, monkeypatch) -> None:
    from firm import postmortem

    monkeypatch.setattr(postmortem, "POSTMORTEM_DIR", tmp_path)
    monkeypatch.setattr(postmortem, "RANKING_PATH", tmp_path / "ranking.json")
    monday_near = postmortem.write_postmortem(
        {
            "id": 101,
            "family": "monday_range_sweep_reversal",
            "clock": "4h/4h",
            "side": "BOTH",
            "pairs_approved": 0,
            "detail": "monday_range_sweep_reversal: 0 of 6 pairs approved.",
            "hypothesis_id": "monday_range_sweep_reversal@4h/4h",
        },
        pair_blurbs="BNBUSDT SHORT: REJECTED | PF 1.30 | Exp +0.20%/trade",
    )
    assert monday_near["keep_short_followup"] is False


def test_append_hypothesis_refuses_monday_short_bnb_clone(tmp_path, monkeypatch) -> None:
    from firm import research_catalog

    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    (tmp_path / "ranking.json").write_text(
        '{"added":[],"ranks":{},"retired":[],"justifications":{},"dispositions":{}}',
        encoding="utf-8",
    )
    refused = research_catalog.append_hypothesis(
        {
            "id": "monday_range_sweep_reversal@4h/4h@SHORT@bnb",
            "family": "monday_range_sweep_reversal",
            "clock": "4h/4h",
            "side": "SHORT",
            "coded": True,
            "justification": "BNB SHORT clone",
            "param_change": {"side": "SHORT", "symbol": "BNBUSDT"},
        },
        added_by="test",
    )
    assert refused is None
