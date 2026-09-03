"""
The validation pipeline: the only route by which a strategy earns trading rights.

Combines every guard built in this package into a single verdict per
symbol/side, then writes `config/approved_strategies.json`. Nothing else in the
firm can grant trading approval -- not a config flag, not an agent, not a human
editing a Python file.

Gate structure, deliberately two-tier:

* **Per-symbol approval** clears one symbol/side to trade. Requires enough
  out-of-sample trades to be measurable, a profit factor above 1, positive
  expectancy whose bootstrap interval excludes zero, and stable parameters.
* **Portfolio go-live** (checked separately, in `scripts/check_go_live.py`)
  requires the full plan gates: 300+ OOS trades across 3+ regimes including a
  bear, aggregate PF >= 1.3, drawdown < 15%.

A symbol can be approved for paper trading while the portfolio remains far from
live-ready. That is the intended state for a long time.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from config.universe import APPROVALS_PATH, approval_record_key, migrate_approval_keys
from core.data.funding import FundingHistory
from core.strategy.base import SignalSide, StrategyParams
from core.strategy.rsi_golden_cross import RsiTrendParams, RsiTrendStrategy
from research.datasets import Period, Regime
from research.engine import BacktestConfig, BacktestEngine
from research.significance import SignificanceReport, assess
from research.walkforward import WalkForwardResult, walk_forward

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-symbol approval thresholds
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ApprovalCriteria:
    """Thresholds a single symbol/side must clear to be allowed to trade."""

    min_oos_trades: int = 30
    min_profit_factor: float = 1.15
    min_expectancy_pct: float = 0.0
    require_significant_expectancy: bool = True
    max_drawdown_pct: float = 25.0
    min_profitable_fold_ratio: float = 50.0
    #: Coefficient of variation above which optimised parameters are considered
    #: unstable, i.e. fitted to noise.
    max_parameter_cv: float = 0.35


DEFAULT_CRITERIA = ApprovalCriteria()


@dataclass
class SymbolVerdict:
    """Validation outcome for one symbol/side."""

    symbol: str
    side: str
    timeframe: str = "15m"
    strategy: str = "rsi_trend"
    reoptimise_days: int = 60
    walk_forward: WalkForwardResult | None = None
    significance: SignificanceReport | None = None
    regime_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def approved(self) -> bool:
        return not self.failures and self.error is None and self.walk_forward is not None

    @property
    def selected_params(self) -> dict[str, Any]:
        """Parameters live trading should use right now.

        Walk-forward validates a *process* -- "optimise on the trailing window,
        trade the next one" -- not a single fixed parameter set. The honest
        translation to live trading is therefore the choice the most recent fold
        made, refreshed every `reoptimise_days`. Freezing the whole-history
        optimum instead would be trading a parameter set that was never tested
        out of sample.
        """
        if self.walk_forward is None:
            return {}
        for fold in reversed(self.walk_forward.folds):
            if fold.best_params:
                return dict(fold.best_params)
        return {}

    def summary(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "strategy": self.strategy,
            "timeframe": self.timeframe,
            "approved": self.approved,
            "failures": self.failures,
            "error": self.error,
            "selected_params": self.selected_params,
            "walk_forward": self.walk_forward.summary() if self.walk_forward else None,
            "significance": self.significance.summary() if self.significance else None,
            "by_regime": self.regime_results,
        }

    def __str__(self) -> str:
        if self.error:
            return f"{self.symbol} {self.side}: ERROR - {self.error}"
        status = "APPROVED" if self.approved else "REJECTED"
        detail = f" ({'; '.join(self.failures)})" if self.failures else ""
        wf = f" | {self.walk_forward}" if self.walk_forward else ""
        return f"{self.symbol} {self.side}: {status}{detail}{wf}"


def strategy_kit(name: str, side: SignalSide):
    """Factory, baseline params, and a small search grid for one coded family."""
    if name == "donchian_breakout":
        from core.strategy.donchian_breakout import DonchianBreakoutStrategy, DonchianParams

        def factory(params: StrategyParams) -> DonchianBreakoutStrategy:
            return DonchianBreakoutStrategy(params)  # type: ignore[arg-type]

        base = DonchianParams(side=side)
        space = {
            "lookback": [20, 55],
            "min_adx": [0.0, 20.0],
            "take_profit_pct": [0.03, 0.05],
            "stop_loss_pct": [0.02, 0.03],
        }
        return factory, base, space

    if name == "ema_adx_trend":
        from core.strategy.ema_adx_trend import EmaAdxParams, EmaAdxTrendStrategy

        def factory(params: StrategyParams) -> EmaAdxTrendStrategy:
            return EmaAdxTrendStrategy(params)  # type: ignore[arg-type]

        base = EmaAdxParams(side=side)
        space = {
            "ema_fast": [12, 20],
            "min_adx": [0.0, 20.0],
            "take_profit_pct": [0.03, 0.05],
            "stop_loss_pct": [0.02, 0.03],
        }
        return factory, base, space

    if name == "bollinger_mean_reversion":
        from core.strategy.bollinger_mean_reversion import (
            BollingerMeanReversionStrategy,
            BollingerMrParams,
        )

        def factory(params: StrategyParams) -> BollingerMeanReversionStrategy:
            return BollingerMeanReversionStrategy(params)  # type: ignore[arg-type]

        base = BollingerMrParams(side=side)
        space = {
            "bb_period": [20],
            "band_k": [2.0, 2.5],
            "max_adx": [0.0, 20.0],
            "take_profit_pct": [0.03, 0.05],
            "stop_loss_pct": [0.02, 0.03],
        }
        return factory, base, space

    if name == "trend_pullback_htf":
        from core.strategy.trend_pullback_htf import (
            TrendPullbackHtfParams,
            TrendPullbackHtfStrategy,
        )

        def factory(params: StrategyParams) -> TrendPullbackHtfStrategy:
            return TrendPullbackHtfStrategy(params)  # type: ignore[arg-type]

        base = TrendPullbackHtfParams(side=side)
        space = {
            "pullback_ema": [12, 20],
            "min_adx": [0.0, 20.0],
            "take_profit_pct": [0.03, 0.05],
            "stop_loss_pct": [0.02, 0.03],
        }
        return factory, base, space

    if name == "atr_channel_breakout":
        from core.strategy.atr_channel_breakout import (
            AtrChannelBreakoutStrategy,
            AtrChannelParams,
        )

        def factory(params: StrategyParams) -> AtrChannelBreakoutStrategy:
            return AtrChannelBreakoutStrategy(params)  # type: ignore[arg-type]

        base = AtrChannelParams(side=side)
        space = {
            "ema_period": [20],
            "atr_k": [2.0, 2.5],
            "min_adx": [20.0],
            "take_profit_pct": [0.03, 0.05],
            "stop_loss_pct": [0.02, 0.03],
        }
        return factory, base, space

    if name == "opening_range_breakout":
        from core.strategy.opening_range_breakout import (
            OpeningRangeBreakoutStrategy,
            OpeningRangeParams,
        )

        def factory(params: StrategyParams) -> OpeningRangeBreakoutStrategy:
            return OpeningRangeBreakoutStrategy(params)  # type: ignore[arg-type]

        base = OpeningRangeParams(side=side)
        space = {
            "range_hours": [1, 2],
            "take_profit_pct": [0.03, 0.05],
            "stop_loss_pct": [0.02, 0.03],
        }
        return factory, base, space

    novel = _novel_kit(name, side)
    if novel is not None:
        return novel

    from core.strategy.spec_sleeve import spec_kit

    kit = spec_kit(name, side)
    if kit is not None:
        return kit

    if name in {"rsi_trend", "rsi_golden_cross"}:
        def factory(params: StrategyParams) -> RsiTrendStrategy:
            return RsiTrendStrategy(params)  # type: ignore[arg-type]

        return factory, RsiTrendParams(side=side), default_search_space(side)

    raise KeyError(f"Unknown strategy {name!r} — not a coded family or JSON spec")


def merge_search_space(
    base: dict[str, list[Any]],
    param_change: dict[str, Any] | None,
) -> dict[str, list[Any]]:
    """Overlay a catalog `param_change` onto the family's walk-forward grid.

    Clock/side belong on the job, not the grid. A frozen `min_adx: [20.0]` is
    how a near-miss retest stops folds from hunting the filter that just failed CV.
    """
    merged = {str(k): list(v) for k, v in (base or {}).items()}
    for raw_key, raw_val in (param_change or {}).items():
        key = str(raw_key)
        if key in {"clock", "side"}:
            continue
        values = list(raw_val) if isinstance(raw_val, (list, tuple)) else [raw_val]
        merged[key] = values
    return merged


def _novel_kit(name: str, side: SignalSide):
    """Walk-forward kit for Cursor-coded novel families."""
    import importlib

    kits = {
        "utc_session_vwap_reversion": (
            "core.strategy.utc_session_vwap_reversion",
            "UtcSessionVwapParams",
            "UtcSessionVwapReversionStrategy",
            {"stretch_pct": [0.003, 0.006]},
        ),
        "asian_range_breakout": (
            "core.strategy.asian_range_breakout",
            "AsianRangeParams",
            "AsianRangeBreakoutStrategy",
            {"end_hour": [8.0]},
        ),
        "inside_bar_breakout": (
            "core.strategy.inside_bar_breakout",
            "InsideBarParams",
            "InsideBarBreakoutStrategy",
            {},
        ),
        "swing_failure_reversal": (
            "core.strategy.swing_failure_reversal",
            "SwingFailureParams",
            "SwingFailureReversalStrategy",
            {"pivot_left": [3, 5]},
        ),
        "consecutive_bar_exhaustion": (
            "core.strategy.consecutive_bar_exhaustion",
            "ConsecutiveBarParams",
            "ConsecutiveBarExhaustionStrategy",
            {"run_length": [4, 6]},
        ),
        "wick_rejection_reversal": (
            "core.strategy.wick_rejection_reversal",
            "WickRejectionParams",
            "WickRejectionReversalStrategy",
            {"min_wick_frac": [0.5, 0.7]},
        ),
        "prior_day_pivot_breakout": (
            "core.strategy.prior_day_pivot_breakout",
            "PriorDayPivotParams",
            "PriorDayPivotBreakoutStrategy",
            {},
        ),
        "weekend_gap_fill": (
            "core.strategy.weekend_gap_fill",
            "WeekendGapParams",
            "WeekendGapFillStrategy",
            {},
        ),
        "engulfing_reversal": (
            "core.strategy.engulfing_reversal",
            "EngulfingParams",
            "EngulfingReversalStrategy",
            {},
        ),
        "utc_midnight_gap_fill": (
            "core.strategy.utc_midnight_gap_fill",
            "MidnightGapParams",
            "UtcMidnightGapFillStrategy",
            {},
        ),
        "nr7_breakout": (
            "core.strategy.nr7_breakout",
            "Nr7Params",
            "Nr7BreakoutStrategy",
            {"lookback": [7]},
        ),
        "failed_higher_high": (
            "core.strategy.failed_higher_high",
            "FailedHigherHighParams",
            "FailedHigherHighStrategy",
            {"pivot_left": [3]},
        ),
        "utc_session_twap_reversion": (
            "core.strategy.utc_session_twap_reversion",
            "UtcSessionTwapParams",
            "UtcSessionTwapReversionStrategy",
            {"stretch_pct": [0.003, 0.006]},
        ),
        "prior_week_high_break": (
            "core.strategy.prior_week_high_break",
            "PriorWeekParams",
            "PriorWeekHighBreakStrategy",
            {},
        ),
        "round_number_fade": (
            "core.strategy.round_number_fade",
            "RoundNumberParams",
            "RoundNumberFadeStrategy",
            {},
        ),
        "doji_star_reversal": (
            "core.strategy.doji_star_reversal",
            "DojiStarParams",
            "DojiStarReversalStrategy",
            {"run_bars": [3]},
        ),
        "stochastic_fade": (
            "core.strategy.stochastic_fade",
            "StochasticFadeParams",
            "StochasticFadeStrategy",
            {"period": [14], "os_level": [20.0], "ob_level": [80.0]},
        ),
        "cci_reversion": (
            "core.strategy.cci_reversion",
            "CciReversionParams",
            "CciReversionStrategy",
            {"period": [20], "stretch": [100.0]},
        ),
        "supertrend_flip": (
            "core.strategy.supertrend_flip",
            "SupertrendFlipParams",
            "SupertrendFlipStrategy",
            {"atr_period": [10], "multiplier": [3.0]},
        ),
        "heikin_ashi_trend": (
            "core.strategy.heikin_ashi_trend",
            "HeikinAshiTrendParams",
            "HeikinAshiTrendStrategy",
            {},
        ),
        "williams_r_fade": (
            "core.strategy.williams_r_fade",
            "WilliamsRFadeParams",
            "WilliamsRFadeStrategy",
            {"period": [14], "os_level": [-80.0], "ob_level": [-20.0]},
        ),
        "obv_break": (
            "core.strategy.obv_break",
            "ObvBreakParams",
            "ObvBreakStrategy",
            {"lookback": [20]},
        ),
        "ichimoku_tk_cross": (
            "core.strategy.ichimoku_tk_cross",
            "IchimokuTkCrossParams",
            "IchimokuTkCrossStrategy",
            {"tenkan_period": [9], "kijun_period": [26]},
        ),
        "mfi_fade": (
            "core.strategy.mfi_fade",
            "MfiFadeParams",
            "MfiFadeStrategy",
            {"period": [14], "os_level": [20.0], "ob_level": [80.0]},
        ),
        "chaikin_oscillator_cross": (
            "core.strategy.chaikin_oscillator_cross",
            "ChaikinOscillatorCrossParams",
            "ChaikinOscillatorCrossStrategy",
            {"fast": [3], "slow": [10]},
        ),
        "chande_momentum_fade": (
            "core.strategy.chande_momentum_fade",
            "ChandeMomentumFadeParams",
            "ChandeMomentumFadeStrategy",
            {"period": [14], "os_level": [-50.0], "ob_level": [50.0]},
        ),
        "vortex_cross": (
            "core.strategy.vortex_cross",
            "VortexCrossParams",
            "VortexCrossStrategy",
            {"period": [14]},
        ),
        "dpo_cycle_fade": (
            "core.strategy.dpo_cycle_fade",
            "DpoCycleFadeParams",
            "DpoCycleFadeStrategy",
            {"period": [20], "stretch_pct": [0.02]},
        ),
        "trix_cross": (
            "core.strategy.trix_cross",
            "TrixCrossParams",
            "TrixCrossStrategy",
            {"period": [15]},
        ),
        "force_index_fade": (
            "core.strategy.force_index_fade",
            "ForceIndexFadeParams",
            "ForceIndexFadeStrategy",
            {"period": [13], "z_lookback": [40], "z_stretch": [1.5]},
        ),
        "awesome_oscillator_saucer": (
            "core.strategy.awesome_oscillator_saucer",
            "AwesomeOscillatorSaucerParams",
            "AwesomeOscillatorSaucerStrategy",
            {},
        ),
        "aroon_crossover": (
            "core.strategy.aroon_crossover",
            "AroonCrossoverParams",
            "AroonCrossoverStrategy",
            {"period": [25]},
        ),
        "ppo_cross": (
            "core.strategy.ppo_cross",
            "PpoCrossParams",
            "PpoCrossStrategy",
            {"fast": [12], "slow": [26], "signal": [9]},
        ),
        "ultimate_oscillator_fade": (
            "core.strategy.ultimate_oscillator_fade",
            "UltimateOscillatorFadeParams",
            "UltimateOscillatorFadeStrategy",
            {"short": [7], "mid": [14], "long": [28], "os_level": [30.0], "ob_level": [70.0]},
        ),
        "kst_cross": (
            "core.strategy.kst_cross",
            "KstCrossParams",
            "KstCrossStrategy",
            {"signal": [9]},
        ),
        "tsi_cross": (
            "core.strategy.tsi_cross",
            "TsiCrossParams",
            "TsiCrossStrategy",
            {"long": [25], "short": [13]},
        ),
        "fisher_transform_cross": (
            "core.strategy.fisher_transform_cross",
            "FisherTransformCrossParams",
            "FisherTransformCrossStrategy",
            {"period": [10]},
        ),
        "hull_ma_trend": (
            "core.strategy.hull_ma_trend",
            "HullMaTrendParams",
            "HullMaTrendStrategy",
            {"period": [16]},
        ),
        "elder_ray_fade": (
            "core.strategy.elder_ray_fade",
            "ElderRayFadeParams",
            "ElderRayFadeStrategy",
            {"period": [13], "z_lookback": [40]},
        ),
        "schaff_trend_cross": (
            "core.strategy.schaff_trend_cross",
            "SchaffTrendCrossParams",
            "SchaffTrendCrossStrategy",
            {"fast": [23], "slow": [50], "cycle": [10]},
        ),
        "mass_index_reversal": (
            "core.strategy.mass_index_reversal",
            "MassIndexReversalParams",
            "MassIndexReversalStrategy",
            {"ema_len": [9], "sum_len": [25]},
        ),
        "ease_of_movement_fade": (
            "core.strategy.ease_of_movement_fade",
            "EaseOfMovementFadeParams",
            "EaseOfMovementFadeStrategy",
            {"period": [14], "lookback": [40]},
        ),
        "coppock_curve_cross": (
            "core.strategy.coppock_curve_cross",
            "CoppockCurveCrossParams",
            "CoppockCurveCrossStrategy",
            {"roc_long": [14], "roc_short": [11], "wma_len": [10]},
        ),
        "qstick_cross": (
            "core.strategy.qstick_cross",
            "QstickCrossParams",
            "QstickCrossStrategy",
            {"period": [8]},
        ),
        "relative_vigor_cross": (
            "core.strategy.relative_vigor_cross",
            "RelativeVigorCrossParams",
            "RelativeVigorCrossStrategy",
            {"period": [10], "signal": [4]},
        ),
        "klinger_volume_cross": (
            "core.strategy.klinger_volume_cross",
            "KlingerVolumeCrossParams",
            "KlingerVolumeCrossStrategy",
            {"fast": [34], "slow": [55], "signal": [13]},
        ),
        "kaufman_efficiency_trend": (
            "core.strategy.kaufman_efficiency_trend",
            "KaufmanEfficiencyTrendParams",
            "KaufmanEfficiencyTrendStrategy",
            {"period": [10], "min_er": [0.5]},
        ),
        "demarker_fade": (
            "core.strategy.demarker_fade",
            "DemarkerFadeParams",
            "DemarkerFadeStrategy",
            {"period": [14], "os_level": [0.30], "ob_level": [0.70]},
        ),
        "choppiness_index_break": (
            "core.strategy.choppiness_index_break",
            "ChoppinessIndexBreakParams",
            "ChoppinessIndexBreakStrategy",
            {"period": [14], "chop_level": [61.8]},
        ),
        "psychological_line_cross": (
            "core.strategy.psychological_line_cross",
            "PsychologicalLineCrossParams",
            "PsychologicalLineCrossStrategy",
            {"period": [12]},
        ),
        "kairi_relative_fade": (
            "core.strategy.kairi_relative_fade",
            "KairiRelativeFadeParams",
            "KairiRelativeFadeStrategy",
            {"period": [20], "os_level": [-5.0], "ob_level": [5.0]},
        ),
        "linreg_slope_cross": (
            "core.strategy.linreg_slope_cross",
            "LinregSlopeCrossParams",
            "LinregSlopeCrossStrategy",
            {"period": [20]},
        ),
        "ehlers_decycler_cross": (
            "core.strategy.ehlers_decycler_cross",
            "EhlersDecyclerCrossParams",
            "EhlersDecyclerCrossStrategy",
            {"fast": [20], "slow": [40]},
        ),
        "volume_price_trend_break": (
            "core.strategy.volume_price_trend_break",
            "VolumePriceTrendBreakParams",
            "VolumePriceTrendBreakStrategy",
            {"lookback": [20]},
        ),
        "balance_of_power_cross": (
            "core.strategy.balance_of_power_cross",
            "BalanceOfPowerCrossParams",
            "BalanceOfPowerCrossStrategy",
            {"period": [14]},
        ),
        "twiggs_money_flow_fade": (
            "core.strategy.twiggs_money_flow_fade",
            "TwiggsMoneyFlowFadeParams",
            "TwiggsMoneyFlowFadeStrategy",
            {"period": [21]},
        ),
        "parabolic_sar_flip": (
            "core.strategy.parabolic_sar_flip",
            "ParabolicSarFlipParams",
            "ParabolicSarFlipStrategy",
            {"af_start": [0.02], "af_step": [0.02]},
        ),
        "center_of_gravity_cross": (
            "core.strategy.center_of_gravity_cross",
            "CenterOfGravityCrossParams",
            "CenterOfGravityCrossStrategy",
            {"period": [10]},
        ),
        "mama_fama_cross": (
            "core.strategy.mama_fama_cross",
            "MamaFamaCrossParams",
            "MamaFamaCrossStrategy",
            {"fastlimit": [0.5], "slowlimit": [0.05]},
        ),
        "connors_rsi_fade": (
            "core.strategy.connors_rsi_fade",
            "ConnorsRsiFadeParams",
            "ConnorsRsiFadeStrategy",
            {"rsi_len": [3], "rank_len": [100], "os_level": [10.0]},
        ),
        "rsi_laguerre_fade": (
            "core.strategy.rsi_laguerre_fade",
            "RsiLaguerreFadeParams",
            "RsiLaguerreFadeStrategy",
            {"gamma": [0.5], "os_level": [0.20], "ob_level": [0.80]},
        ),
        "vidya_trend": (
            "core.strategy.vidya_trend",
            "VidyaTrendParams",
            "VidyaTrendStrategy",
            {"period": [9]},
        ),
        "t3_trend": (
            "core.strategy.t3_trend",
            "T3TrendParams",
            "T3TrendStrategy",
            {"period": [5], "vfactor": [0.7]},
        ),
        "chaikin_money_flow_fade": (
            "core.strategy.chaikin_money_flow_fade",
            "ChaikinMoneyFlowFadeParams",
            "ChaikinMoneyFlowFadeStrategy",
            {"period": [20], "os_level": [-0.05], "ob_level": [0.05]},
        ),
        "accumulation_distribution_break": (
            "core.strategy.accumulation_distribution_break",
            "AccumulationDistributionBreakParams",
            "AccumulationDistributionBreakStrategy",
            {"lookback": [20]},
        ),
        "zero_lag_ema_cross": (
            "core.strategy.zero_lag_ema_cross",
            "ZeroLagEmaCrossParams",
            "ZeroLagEmaCrossStrategy",
            {"fast": [10], "slow": [20]},
        ),
        "smi_fade": (
            "core.strategy.smi_fade",
            "SmiFadeParams",
            "SmiFadeStrategy",
            {"q": [25], "os_level": [-40.0], "ob_level": [40.0]},
        ),
        "elder_impulse_trend": (
            "core.strategy.elder_impulse_trend",
            "ElderImpulseTrendParams",
            "ElderImpulseTrendStrategy",
            {"ema_len": [13], "fast": [12], "slow": [26]},
        ),
        "rainbow_oscillator_cross": (
            "core.strategy.rainbow_oscillator_cross",
            "RainbowOscillatorCrossParams",
            "RainbowOscillatorCrossStrategy",
            {"steps": [10], "step": [2]},
        ),
        "laguerre_filter_cross": (
            "core.strategy.laguerre_filter_cross",
            "LaguerreFilterCrossParams",
            "LaguerreFilterCrossStrategy",
            {"gamma": [0.5]},
        ),
        "gator_oscillator_cross": (
            "core.strategy.gator_oscillator_cross",
            "GatorOscillatorCrossParams",
            "GatorOscillatorCrossStrategy",
            {"jaw": [13], "teeth": [8], "lips": [5]},
        ),
        "williams_fractal_break": (
            "core.strategy.williams_fractal_break",
            "WilliamsFractalBreakParams",
            "WilliamsFractalBreakStrategy",
            {},
        ),
        "kama_trend": (
            "core.strategy.kama_trend",
            "KamaTrendParams",
            "KamaTrendStrategy",
            {"period": [10], "fast": [2], "slow": [30]},
        ),
        "dema_cross": (
            "core.strategy.dema_cross",
            "DemaCrossParams",
            "DemaCrossStrategy",
            {"fast": [10], "slow": [20]},
        ),
        "tema_cross": (
            "core.strategy.tema_cross",
            "TemaCrossParams",
            "TemaCrossStrategy",
            {"fast": [8], "slow": [16]},
        ),
        "alma_trend": (
            "core.strategy.alma_trend",
            "AlmaTrendParams",
            "AlmaTrendStrategy",
            {"period": [9]},
        ),
        "keltner_break": (
            "core.strategy.keltner_break",
            "KeltnerBreakParams",
            "KeltnerBreakStrategy",
            {"ema_period": [20], "atr_k": [1.5]},
        ),
        "stochrsi_fade": (
            "core.strategy.stochrsi_fade",
            "StochRsiFadeParams",
            "StochRsiFadeStrategy",
            {"rsi_period": [14], "stoch_period": [14], "os_level": [20.0]},
        ),
        "chandelier_exit_flip": (
            "core.strategy.chandelier_exit_flip",
            "ChandelierExitFlipParams",
            "ChandelierExitFlipStrategy",
            {"period": [22], "atr_k": [3.0]},
        ),
        "mcginley_dynamic_cross": (
            "core.strategy.mcginley_dynamic_cross",
            "McginleyDynamicCrossParams",
            "McginleyDynamicCrossStrategy",
            {"period": [12]},
        ),
        "super_smoother_cross": (
            "core.strategy.super_smoother_cross",
            "SuperSmootherCrossParams",
            "SuperSmootherCrossStrategy",
            {"period": [10]},
        ),
        "roofing_filter_cross": (
            "core.strategy.roofing_filter_cross",
            "RoofingFilterCrossParams",
            "RoofingFilterCrossStrategy",
            {"hp_period": [48], "lp_period": [10]},
        ),
        "squeeze_momentum_break": (
            "core.strategy.squeeze_momentum_break",
            "SqueezeMomentumBreakParams",
            "SqueezeMomentumBreakStrategy",
            {"bb_period": [20], "mom_period": [20]},
        ),
        "volume_weighted_macd_cross": (
            "core.strategy.volume_weighted_macd_cross",
            "VolumeWeightedMacdCrossParams",
            "VolumeWeightedMacdCrossStrategy",
            {"fast": [12], "slow": [26], "signal": [9]},
        ),
        "volume_force_divergence": (
            "core.strategy.volume_force_divergence",
            "VolumeForceDivergenceParams",
            "VolumeForceDivergenceStrategy",
            {"lookback": [20], "max_adx": [0.0, 20.0]},
        ),
        "session_liquidity_sweep": (
            "core.strategy.session_liquidity_sweep",
            "SessionLiquiditySweepParams",
            "SessionLiquiditySweepStrategy",
            {"max_sweep_pct": [0.005, 0.01]},
        ),
        "bar_vwap_inflow_surge": (
            "core.strategy.bar_vwap_inflow_surge",
            "BarVwapInflowSurgeParams",
            "BarVwapInflowSurgeStrategy",
            {"surge_k": [2.0], "baseline_lookback": [20]},
        ),
        "fib_retracement_bounce": (
            "core.strategy.fib_retracement_bounce",
            "FibRetracementBounceParams",
            "FibRetracementBounceStrategy",
            {"fib_ratio": [0.5, 0.618, 0.786], "atr_buffer": [0.0, 0.15]},
        ),
        "fib_extension_break": (
            "core.strategy.fib_extension_break",
            "FibExtensionBreakParams",
            "FibExtensionBreakStrategy",
            # 1.272 is the inner-zone display only. Searching both ratios
            # lets fold CV blame the grid; lock 1.618. skip_bull / skip_bear
            # stay off unless a near-miss overlay freezes them.
            {"fib_ratio": [1.618]},
        ),
        "measured_move_break": (
            "core.strategy.measured_move_break",
            "MeasuredMoveBreakParams",
            "MeasuredMoveBreakStrategy",
            # AB=CD ratio is hardcoded at 1.0. Do not search 1.618 or 0.618.
            {},
        ),
        "up_down_turnover_imbalance": (
            "core.strategy.up_down_turnover_imbalance",
            "UpDownTurnoverImbalanceParams",
            "UpDownTurnoverImbalanceStrategy",
            {"lookback": [20], "imbalance_k": [0.30]},
        ),
        "signed_range_turnover_trend": (
            "core.strategy.signed_range_turnover_trend",
            "SignedRangeTurnoverTrendParams",
            "SignedRangeTurnoverTrendStrategy",
            {"lookback": [20], "trend_k": [1.0]},
        ),
        "swing_anchored_vwap_pullback": (
            "core.strategy.swing_anchored_vwap_pullback",
            "SwingAnchoredVwapPullbackParams",
            "SwingAnchoredVwapPullbackStrategy",
            # Same locked swing engine as fib_extension_break. Do not
            # search 0.618 / 1.618 — those are other families.
            {},
        ),
        "monday_range_sweep_reversal": (
            "core.strategy.monday_range_sweep_reversal",
            "MondayRangeSweepReversalParams",
            "MondayRangeSweepReversalStrategy",
            {"max_sweep_pct": [0.01, 0.015]},
        ),
        "volume_imbalance_delta_reversal": (
            "core.strategy.volume_imbalance_delta_reversal",
            "VolumeImbalanceDeltaReversalParams",
            "VolumeImbalanceDeltaReversalStrategy",
            {"lookback": [20], "exhaust_share": [0.20]},
        ),
        "session_boundary_volume_fade": (
            "core.strategy.session_boundary_volume_fade",
            "SessionBoundaryVolumeFadeParams",
            "SessionBoundaryVolumeFadeStrategy",
            # Volume MA period is locked at 20. Do not search a sweep-pct
            # close-back-inside (that is session_liquidity_sweep / monday).
            {"vol_period": [20]},
        ),
        "vwap_spread_exhaustion": (
            "core.strategy.vwap_spread_exhaustion",
            "VwapSpreadExhaustionParams",
            "VwapSpreadExhaustionStrategy",
            # VWAP/SMA/ATR stay at 20. Search N-bar extreme + chop filter.
            {"extreme_lookback": [10, 20], "max_adx": [0.0, 20.0]},
        ),
        "vwap_volatility_band_fade": (
            "core.strategy.vwap_volatility_band_fade",
            "VwapVolatilityBandFadeParams",
            "VwapVolatilityBandFadeStrategy",
            # Squeeze locked at bottom 30% of 100 bars. Search band_k only.
            {"band_k": [1.5, 2.0]},
        ),
        "london_close_inventory_fade": (
            "core.strategy.london_close_inventory_fade",
            "LondonCloseInventoryFadeParams",
            "LondonCloseInventoryFadeStrategy",
            # Extreme 20% and prior-20 volume mean. At most two free params.
            {"extreme_frac": [0.20], "vol_lookback": [20]},
        ),
        "utc_open_fail_reversion": (
            "core.strategy.utc_open_fail_reversion",
            "UtcOpenFailReversionParams",
            "UtcOpenFailReversionStrategy",
            # First-4h box and second-4h fail are locked. Do not search ORB hours.
            {},
        ),
        "range_compression_volume_thrust": (
            "core.strategy.range_compression_volume_thrust",
            "RangeCompressionVolumeThrustParams",
            "RangeCompressionVolumeThrustStrategy",
            # ATR period / 100-bar lookback locked. Search compress + thrust.
            {"compress_pct": [0.30], "thrust_mult": [1.5]},
        ),
        "turnover_climax_rejection_fade": (
            "core.strategy.turnover_climax_rejection_fade",
            "TurnoverClimaxRejectionFadeParams",
            "TurnoverClimaxRejectionFadeStrategy",
            {"lookback": [20], "reject_frac": [0.20]},
        ),
        "volume_dryup_range_break": (
            "core.strategy.volume_dryup_range_break",
            "VolumeDryupRangeBreakParams",
            "VolumeDryupRangeBreakStrategy",
            {"dry_bars": [3], "vol_lookback": [20]},
        ),
        "body_efficiency_follow": (
            "core.strategy.body_efficiency_follow",
            "BodyEfficiencyFollowParams",
            "BodyEfficiencyFollowStrategy",
            # Two-bar follow is locked. Search the efficiency floor only.
            {"min_efficiency": [0.7]},
        ),
        "week_open_reclaim": (
            "core.strategy.week_open_reclaim",
            "WeekOpenReclaimParams",
            "WeekOpenReclaimStrategy",
            # Monday 00:00 open is locked. Search wrong-side count + volume.
            {"min_wrong_closes": [3], "vol_lookback": [20]},
        ),
        "prior_session_mid_reclaim": (
            "core.strategy.prior_session_mid_reclaim",
            "PriorSessionMidReclaimParams",
            "PriorSessionMidReclaimStrategy",
            # 8h UTC slots locked. Search the volume lookback only.
            {"vol_lookback": [20]},
        ),
        "outside_bar_reversal": (
            "core.strategy.outside_bar_reversal",
            "OutsideBarParams",
            "OutsideBarReversalStrategy",
            {},
        ),
        "three_bar_play": (
            "core.strategy.three_bar_play",
            "ThreeBarPlayParams",
            "ThreeBarPlayStrategy",
            {},
        ),
        "ny_cash_open_drive": (
            "core.strategy.ny_cash_open_drive",
            "NyCashOpenParams",
            "NyCashOpenDriveStrategy",
            {},
        ),
        "london_session_breakout": (
            "core.strategy.london_session_breakout",
            "LondonRangeParams",
            "LondonSessionBreakoutStrategy",
            {},
        ),
    }
    spec = kits.get(name)
    if spec is None:
        return None
    module_path, params_name, strategy_name, extra = spec
    mod = importlib.import_module(module_path)
    params_cls = getattr(mod, params_name)
    strategy_cls = getattr(mod, strategy_name)

    def factory(params: StrategyParams):
        return strategy_cls(params)

    space = {
        **extra,
        "take_profit_pct": [0.03, 0.05],
        "stop_loss_pct": [0.02, 0.03],
    }
    return factory, params_cls(side=side), space


def strategy_factory_for(side: SignalSide):
    """Return a factory that builds the RSI/trend strategy for one side."""
    factory, _, _ = strategy_kit("rsi_trend", side)
    return factory


def default_search_space(side: SignalSide) -> dict[str, list[Any]]:
    """Parameter grid searched per walk-forward fold.

    Kept deliberately small. A grid of thousands of combinations against a
    180-day training window guarantees an overfit winner; the point of the
    search is to adapt coarsely to regime, not to find a magic setting.
    """
    if side is SignalSide.LONG:
        return {
            "rsi_min": [25.0, 30.0, 35.0],
            "rsi_max": [40.0, 45.0, 50.0],
            "volume_threshold": [1.0, 1.2, 1.5],
            "take_profit_pct": [0.03, 0.05],
            "stop_loss_pct": [0.02, 0.03, 0.05],
        }
    return {
        "rsi_threshold": [60.0, 65.0, 70.0],
        "volume_threshold": [1.0, 1.2, 1.5],
        "take_profit_pct": [0.03, 0.05],
        "stop_loss_pct": [0.02, 0.03, 0.05],
    }


def validate_symbol(
    symbol: str,
    side: SignalSide,
    candles: pd.DataFrame,
    config: BacktestConfig,
    periods: list[Period] | None = None,
    funding: FundingHistory | None = None,
    criteria: ApprovalCriteria = DEFAULT_CRITERIA,
    search_space: dict[str, list[Any]] | None = None,
    train_days: int = 180,
    test_days: int = 60,
    timeframe: str = "15m",
    strategy_name: str = "rsi_trend",
) -> SymbolVerdict:
    """Run the full validation pipeline for one symbol/side."""
    verdict = SymbolVerdict(
        symbol=symbol,
        side=side.value,
        timeframe=timeframe,
        strategy=strategy_name,
        reoptimise_days=test_days,
    )

    if candles.empty or len(candles) < 3_000:
        verdict.error = f"insufficient history ({len(candles)} bars)"
        return verdict

    factory, base_params, default_space = strategy_kit(strategy_name, side)
    space = search_space if search_space is not None else default_space

    try:
        wf = walk_forward(
            symbol=symbol,
            candles=candles,
            strategy_factory=factory,
            base_params=base_params,
            search_space=space,
            config=config,
            train_days=train_days,
            test_days=test_days,
            funding=funding,
        )
    except Exception as exc:
        logger.exception("Walk-forward failed for %s %s", symbol, side.value)
        verdict.error = f"walk-forward failed: {exc}"
        return verdict

    verdict.walk_forward = wf
    oos_trades = wf.oos_trades

    verdict.significance = assess(
        oos_trades, candles=candles, position_fraction=config.position_fraction
    )

    if periods:
        verdict.regime_results = _regime_breakdown(oos_trades, periods)

    verdict.failures = _evaluate_gates(wf, verdict.significance, verdict.regime_results, criteria)
    return verdict


def _evaluate_gates(
    wf: WalkForwardResult,
    significance: SignificanceReport,
    regime_results: dict[str, dict[str, Any]],
    criteria: ApprovalCriteria,
) -> list[str]:
    """Collect every reason a symbol fails approval.

    All gates are evaluated rather than short-circuiting, so the report explains
    the full picture instead of only the first problem.
    """
    failures: list[str] = []

    if wf.total_oos_trades < criteria.min_oos_trades:
        failures.append(
            f"only {wf.total_oos_trades} OOS trades (need >= {criteria.min_oos_trades})"
        )

    pf = wf.oos_profit_factor
    if np.isfinite(pf) and pf < criteria.min_profit_factor:
        failures.append(f"OOS profit factor {pf:.2f} < {criteria.min_profit_factor}")

    if wf.oos_expectancy_pct <= criteria.min_expectancy_pct:
        failures.append(f"OOS expectancy {wf.oos_expectancy_pct:+.3f}% is not positive")

    if wf.oos_max_drawdown_pct > criteria.max_drawdown_pct:
        failures.append(
            f"OOS drawdown {wf.oos_max_drawdown_pct:.1f}% > {criteria.max_drawdown_pct}%"
        )

    if wf.profitable_fold_ratio < criteria.min_profitable_fold_ratio:
        failures.append(
            f"only {wf.profitable_fold_ratio:.0f}% of folds profitable "
            f"(need >= {criteria.min_profitable_fold_ratio:.0f}%)"
        )

    if criteria.require_significant_expectancy:
        if significance.bootstrap is None or not significance.bootstrap.is_significant:
            failures.append("expectancy confidence interval includes zero")
        if significance.permutation and not significance.permutation.beats_random:
            failures.append(
                f"does not beat random entries (p={significance.permutation.p_value:.3f})"
            )

    unstable = [
        f"{name} (cv={stats['cv']:.2f})"
        for name, stats in wf.parameter_stability().items()
        if stats["cv"] > criteria.max_parameter_cv
    ]
    if unstable:
        failures.append("unstable parameters: " + ", ".join(unstable))

    # A strategy that only works in one regime is a bet on that regime.
    if regime_results:
        losing = [
            name
            for name, stats in regime_results.items()
            if stats.get("trades", 0) >= 5 and stats.get("expectancy_pct", 0.0) <= 0
        ]
        if losing:
            failures.append(f"loses money in regime(s): {', '.join(sorted(losing))}")

    return failures


def _regime_breakdown(trades: list, periods: list[Period]) -> dict[str, dict[str, Any]]:
    """Aggregate out-of-sample trades by market regime.

    Reported per regime rather than per quarter: the question is whether the
    strategy survives a bear market, not how it did in one specific quarter.
    """
    buckets: dict[str, list] = {r.value: [] for r in Regime}

    for trade in trades:
        entry = pd.Timestamp(trade.entry_time)
        for period in periods:
            if pd.Timestamp(period.start) <= entry <= pd.Timestamp(period.end):
                buckets[period.regime.value].append(trade)
                break

    breakdown: dict[str, dict[str, Any]] = {}
    for regime, bucket in buckets.items():
        if not bucket:
            breakdown[regime] = {"trades": 0}
            continue

        returns = [t.return_pct for t in bucket]
        wins = [t for t in bucket if t.is_win]
        profit = sum(t.net_pnl for t in wins)
        loss = abs(sum(t.net_pnl for t in bucket if not t.is_win))

        breakdown[regime] = {
            "trades": len(bucket),
            "win_rate": round(len(wins) / len(bucket) * 100.0, 2),
            "expectancy_pct": round(float(np.mean(returns)), 4),
            "profit_factor": round(profit / loss, 3) if loss > 0 else None,
            "net_pnl": round(sum(t.net_pnl for t in bucket), 2),
        }

    return breakdown


def evaluate_baseline_by_regime(
    symbol: str,
    side: SignalSide,
    candles: pd.DataFrame,
    periods: list[Period],
    config: BacktestConfig,
    funding: FundingHistory | None = None,
) -> dict[str, Any]:
    """Run the *unoptimised* baseline parameters separately in each period.

    Complements walk-forward by answering a simpler question: do the legacy
    parameters, exactly as configured, work outside the window they were fitted
    to? This is the direct test the legacy project never ran.
    """
    engine = BacktestEngine(config)
    strategy = RsiTrendStrategy(RsiTrendParams(side=side))
    out: dict[str, Any] = {}

    for period in periods:
        start_index = candles.index.searchsorted(pd.Timestamp(period.start))
        end_index = candles.index.searchsorted(pd.Timestamp(period.end), side="right")
        window = candles.iloc[max(0, start_index - 300) : end_index]

        if len(window) < strategy.min_bars + 50:
            continue

        result = engine.run(symbol, window, strategy, funding)
        out[period.name] = {
            "regime": period.regime.value,
            "trades": result.total_trades,
            "win_rate": round(result.win_rate, 2),
            "profit_factor": (
                round(result.profit_factor, 3) if np.isfinite(result.profit_factor) else None
            ),
            "return_pct": round(result.total_return_pct, 3),
            "expectancy_pct": round(result.expectancy_pct, 4),
        }

    return out


def write_approvals(verdicts: list[SymbolVerdict], path=APPROVALS_PATH) -> dict[str, Any]:
    """Merge approval decisions into `config/approved_strategies.json`.

    Records rejections as well as approvals: an auditable "why is this symbol
    not trading?" record matters as much as the permission itself.

    Merges rather than overwrites, because longs and shorts are validated in
    separate runs on different timeframes. Keys include the candle clock so a
    1h retest cannot erase a 15m verdict for the same pair.
    """
    payload: dict[str, Any] = {}
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Existing approvals unreadable (%s); starting fresh.", exc)
            payload = {}

    payload = migrate_approval_keys(payload)
    payload["_generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["_readme"] = (
        "Written by research/validate.py. This file is the ONLY source of "
        "trading rights. Do not hand-edit: rerun validation instead."
    )

    for verdict in verdicts:
        wf = verdict.walk_forward
        record_key = approval_record_key(
            verdict.strategy, verdict.symbol, verdict.side, verdict.timeframe
        )
        previous = payload.get(record_key) if isinstance(payload.get(record_key), dict) else {}
        payload[record_key] = {
            "approved": verdict.approved,
            "failures": verdict.failures,
            "error": verdict.error,
            "timeframe": verdict.timeframe,
            "strategy": verdict.strategy,
            # The live engine trades these, refreshed every reoptimise_days.
            "params": verdict.selected_params,
            "reoptimise_days": verdict.reoptimise_days,
            "oos_trades": wf.total_oos_trades if wf else 0,
            "oos_win_rate": round(wf.oos_win_rate, 2) if wf else 0.0,
            "oos_profit_factor": (
                round(wf.oos_profit_factor, 3)
                if wf and np.isfinite(wf.oos_profit_factor)
                else None
            ),
            "oos_expectancy_pct": round(wf.oos_expectancy_pct, 4) if wf else 0.0,
            "oos_max_drawdown_pct": round(wf.oos_max_drawdown_pct, 2) if wf else 0.0,
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }
        # Keep an operator paper veto if research still has not fully approved.
        if previous.get("paper_override") is True and not verdict.approved:
            payload[record_key]["paper_override"] = True
            payload[record_key]["paper_override_at"] = previous.get("paper_override_at")
            payload[record_key]["paper_override_reason"] = previous.get("paper_override_reason")
            payload[record_key]["paper_override_by"] = previous.get("paper_override_by")

    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote approvals for %d symbol/side pairs to %s", len(verdicts), path)
    return payload


def operator_paper_approve(
    keys: list[str],
    *,
    reason: str,
    decided_by: str = "operator",
    path=APPROVALS_PATH,
) -> list[str]:
    """Promote rejected walk-forward rows to paper only. Live stays gated.

    Sets `paper_override` on existing records. Does not flip `approved`, so
    go-live and the live engine still require every research gate.
    """
    if not path.exists():
        raise FileNotFoundError(f"No approvals file at {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    stamped = datetime.now(timezone.utc).isoformat()
    applied: list[str] = []
    for key in keys:
        rec = payload.get(key)
        if not isinstance(rec, dict):
            raise KeyError(f"Unknown approval key {key}")
        rec["paper_override"] = True
        rec["paper_override_at"] = stamped
        rec["paper_override_by"] = decided_by
        rec["paper_override_reason"] = reason
        rec["approved"] = False
        payload[key] = rec
        applied.append(key)
    payload["_generated_at"] = stamped
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Operator paper override on %s: %s", applied, reason)
    return applied
