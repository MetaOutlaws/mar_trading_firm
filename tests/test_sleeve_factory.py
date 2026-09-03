"""Template sleeve factory: JSON specs, no freeform Python, novel -> Cursor."""

from __future__ import annotations

from core.strategy.base import SignalSide
from core.strategy.registry import list_strategies
from core.strategy.spec_sleeve import spec_kit
from firm.sleeve_factory import (
    CANDIDATE_SPECS,
    materialize_spec,
    ready_novel_specs,
    spec_for_family,
    write_coding_request,
)
from tests.test_strategy import make_candles


def test_coded_candidate_novels_are_registered_not_ready() -> None:
    """Factory novels that have a .py file must be in the registry, not the coding queue."""
    ready = ready_novel_specs()
    names = {spec.name for spec in ready}
    assert "kama_trend" not in names
    assert "volume_force_divergence" not in names
    assert "session_liquidity_sweep" not in names
    assert "bar_vwap_inflow_surge" not in names
    assert "fib_retracement_bounce" not in names
    assert "fib_extension_break" not in names
    assert "measured_move_break" not in names
    assert "up_down_turnover_imbalance" not in names
    assert "signed_range_turnover_trend" not in names
    assert "swing_anchored_vwap_pullback" not in names
    assert "monday_range_sweep_reversal" not in names
    assert "volume_imbalance_delta_reversal" not in names
    assert "session_boundary_volume_fade" not in names
    assert "vwap_spread_exhaustion" not in names
    assert "vwap_volatility_band_fade" not in names
    assert "london_close_inventory_fade" not in names
    assert "utc_open_fail_reversion" not in names
    assert "range_compression_volume_thrust" not in names
    assert "turnover_climax_rejection_fade" not in names
    assert "volume_dryup_range_break" not in names
    assert "body_efficiency_follow" not in names
    assert "week_open_reclaim" not in names
    assert "prior_session_mid_reclaim" not in names
    assert "vidya_trend" not in names
    assert "t3_trend" not in names
    assert "williams_fractal_break" not in names
    assert "gator_oscillator_cross" not in names
    assert "elder_impulse_trend" not in names
    assert "smi_fade" not in names
    assert "rsi_laguerre_fade" not in names
    assert "choppiness_index_break" not in names
    assert "connors_rsi_fade" not in names
    assert "mama_fama_cross" not in names
    assert "mass_index_reversal" not in names
    assert "demarker_fade" not in names
    assert "elder_ray_fade" not in names
    assert "hull_ma_trend" not in names
    assert "fisher_transform_cross" not in names
    assert "tsi_cross" not in names
    assert "kst_cross" not in names
    assert "ultimate_oscillator_fade" not in names
    assert "ppo_cross" not in names
    assert "mfi_fade" not in names
    assert "ichimoku_tk_cross" not in names
    assert "obv_break" not in names
    assert "williams_r_fade" not in names
    assert "heikin_ashi_trend" not in names
    assert "utc_session_vwap_reversion" not in names
    assert "opening_range_breakout" not in names
    from pathlib import Path

    names = list_strategies()
    strategy_dir = Path(__file__).resolve().parents[1] / "core" / "strategy"
    for spec in CANDIDATE_SPECS:
        implemented = spec.auto_code or (strategy_dir / f"{spec.name}.py").exists()
        if implemented:
            assert spec.name in names, spec.name
        else:
            assert spec.name not in names, spec.name


def test_spec_kit_is_not_rsi() -> None:
    kit = spec_kit("bb_squeeze_breakout", SignalSide.LONG)
    assert kit is not None
    factory, base, space = kit
    sleeve = factory(base)
    assert sleeve.name == "bb_squeeze_breakout"
    assert "take_profit_pct" in space


def test_spec_sleeve_no_lookahead() -> None:
    kit = spec_kit("rsi_fade_chop", SignalSide.LONG)
    assert kit is not None
    factory, base, _ = kit
    sleeve = factory(base)
    candles = make_candles(n=400, seed=7)
    full = sleeve.generate_signals(candles)
    cut = 300
    truncated = sleeve.generate_signals(candles.iloc[:cut])
    import pandas as pd

    pd.testing.assert_series_equal(
        full["signal"].iloc[:cut],
        truncated["signal"],
        check_names=False,
    )
    shocked = candles.copy()
    shocked.iloc[-1, shocked.columns.get_loc("close")] *= 1.5
    original = sleeve.generate_signals(candles)["signal"].iloc[:-1]
    after = sleeve.generate_signals(shocked)["signal"].iloc[:-1]
    pd.testing.assert_series_equal(original, after)


def test_unknown_strategy_kit_does_not_silently_become_rsi() -> None:
    from research.validate import strategy_kit
    import pytest

    with pytest.raises(KeyError, match="Unknown strategy"):
        strategy_kit("not_a_real_family", SignalSide.LONG)


def test_novel_spec_writes_coding_request_not_python(tmp_path, monkeypatch) -> None:
    from firm import sleeve_factory

    monkeypatch.setattr(sleeve_factory, "CODING_REQUESTS_DIR", tmp_path)
    spec = spec_for_family("opening_range_breakout")
    assert spec is not None
    assert spec.auto_code is False
    path = write_coding_request(spec)
    assert path.exists()
    assert not (tmp_path / "opening_range_breakout.py").exists()
    assert "core/strategy/opening_range_breakout.py" in path.read_text(encoding="utf-8")


def test_materialize_refuses_novel(tmp_path, monkeypatch) -> None:
    import pytest
    from firm import sleeve_factory

    monkeypatch.setattr(sleeve_factory, "SLEEVES_DIR", tmp_path)
    spec = spec_for_family("opening_range_breakout")
    assert spec is not None
    with pytest.raises(ValueError, match="not auto-codable"):
        materialize_spec(spec)
