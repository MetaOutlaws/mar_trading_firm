"""Materialize template specs and escalate novel families to Cursor.

Does not LLM-write `core/strategy/*.py`. Template families become JSON under
`config/sleeves/`. Anything that needs new math or a feed becomes a coding
request under `research/coding_requests/`.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT
from core.strategy.spec_sleeve import SLEEVES_DIR, load_spec, load_spec_sleeves, make_spec_strategy
from core.strategy.sleeve_spec import SleeveSpec

logger = logging.getLogger(__name__)

CODING_REQUESTS_DIR = PROJECT_ROOT / "research" / "coding_requests"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# New bets that are not a clock clone of a rejected family. Order is the
# research agenda: vol-regime break, chop fade, MACD pullback, opposite ATR
# fade, volume climax, then a novel session-range idea that needs Cursor.
CANDIDATE_SPECS: list[SleeveSpec] = [
    SleeveSpec(
        name="bb_squeeze_breakout",
        template="channel_break",
        channel="atr",
        squeeze=True,
        clock="4h/4h",
        summary="Break an ATR channel only after Bollinger width printed an N-bar low.",
        justification=(
            "Donchian and raw ATR breakouts failed in chop. A squeeze filter "
            "requires volatility compression first — a different regime bet."
        ),
    ),
    SleeveSpec(
        name="rsi_fade_chop",
        template="fade_stretch",
        stretch="rsi",
        clock="4h/4h",
        summary="Fade RSI extremes only when ADX says there is no trend.",
        justification=(
            "rsi_trend is a golden-cross pullback with the trend. This is the "
            "opposite: mean-revert RSI in chop."
        ),
        defaults={"rsi_os": 30.0, "rsi_ob": 70.0, "max_adx": 20.0},
    ),
    SleeveSpec(
        name="macd_trend_pullback",
        template="pullback_trend",
        trend="macd",
        clock="4h/4h",
        summary="Trade with MACD histogram, enter on an RSI pullback not a breakout.",
        justification=(
            "ema_adx_trend tags the fast EMA. This uses MACD for regime and RSI "
            "for the pullback so it is not a silent rename."
        ),
    ),
    SleeveSpec(
        name="atr_fade_chop",
        template="fade_stretch",
        stretch="atr",
        channel="atr",
        clock="4h/4h",
        summary="Fade ATR-channel extremes when ADX is weak.",
        justification=(
            "atr_channel_breakout buys the break. This sells the same stretch "
            "in chop — the opposite bet on the same indicator."
        ),
        defaults={"max_adx": 20.0, "atr_k": 2.0},
    ),
    SleeveSpec(
        name="volume_climax_fade",
        template="fade_stretch",
        stretch="rsi",
        volume_filter=True,
        clock="4h/4h",
        summary="Fade an RSI extreme only on a volume spike (exhaustion, not drift).",
        justification=(
            "Requires a volume climax plus RSI extreme. Not a clock change of "
            "rsi_trend or a raw Bollinger fade."
        ),
        defaults={"volume_spike": 1.8, "max_adx": 25.0},
    ),
    SleeveSpec(
        name="opening_range_breakout",
        template="novel",
        clock="1h/1h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs a session opening-range high/low (UTC or US cash hours) that "
            "the indicator library does not compute. Do not fake it with a "
            "rolling Donchian."
        ),
        summary="Break the first N-hour range of the UTC day.",
        justification="Crypto session structure is untested here; requires new bar math.",
    ),
    SleeveSpec(
        name="utc_session_vwap_reversion",
        template="novel",
        clock="1h/1h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs VWAP reset at each UTC midnight from typical-price * volume. "
            "Not a rolling SMA and not a Bollinger fade."
        ),
        summary="Fade stretch away from the UTC-day VWAP.",
        justification="Session VWAP is untested here; requires cumulative volume math.",
    ),
    SleeveSpec(
        name="asian_range_breakout",
        template="novel",
        clock="1h/1h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs the high/low of 00:00–08:00 UTC, published only after 08:00. "
            "Not the 1-hour opening range and not a rolling Donchian."
        ),
        summary="Break the completed Asian (00:00–08:00 UTC) range.",
        justification="An 8-hour session box is different bar math from a 1-hour ORB.",
    ),
    SleeveSpec(
        name="inside_bar_breakout",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs a mother-bar high/low: current bar range fully inside the prior "
            "bar, then a later close through that mother range. Not N-bar Donchian."
        ),
        summary="Break the mother bar after an inside bar.",
        justification="Pattern is two-bar structure, not a channel lookback.",
    ),
    SleeveSpec(
        name="swing_failure_reversal",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs swing highs/lows (N-bar pivots) and a failed break of the last "
            "swing. Not ATR/Donchian channel break."
        ),
        summary="Fade a failed break of the last swing high or low.",
        justification="Market-structure pivots are not in the indicator library.",
    ),
    SleeveSpec(
        name="consecutive_bar_exhaustion",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs a count of consecutive up/down closes, then a fade. Not RSI "
            "and not a volume climax template."
        ),
        summary="Fade after N consecutive closes in one direction.",
        justification="Run-length of directional closes is new bar math.",
    ),
    SleeveSpec(
        name="wick_rejection_reversal",
        template="novel",
        clock="1h/1h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs wick/body ratios vs the bar range, with close back inside. "
            "Not a Bollinger touch and not ATR stretch."
        ),
        summary="Enter when a long wick rejects and close re-enters the body zone.",
        justification="Candle geometry is not an existing template input.",
    ),
    SleeveSpec(
        name="prior_day_pivot_breakout",
        template="novel",
        clock="1h/1h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs classic floor-trader pivots from the prior UTC day "
            "(H+L+C)/3 plus R1/S1. Not a rolling Donchian."
        ),
        summary="Break prior UTC-day pivot / R1 / S1 after that day has closed.",
        justification="Daily floor pivots require calendar-day aggregation.",
    ),
    SleeveSpec(
        name="weekend_gap_fill",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Friday UTC close vs the first Monday bar (or Sat–Sun range). "
            "Calendar weekend, not a rolling gap of N bars."
        ),
        summary="Fade or fill the weekend gap versus Friday's UTC close.",
        justification="Weekend calendar math is not in the indicator library.",
    ),
    SleeveSpec(
        name="engulfing_reversal",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs a two-bar engulfing rule (current body fully covers prior body) "
            "plus close direction. Not RSI fade and not inside-bar."
        ),
        summary="Reverse when a bar's body fully engulfs the prior body.",
        justification="Two-bar engulfing is pattern math, not a stretch template.",
    ),
    SleeveSpec(
        name="utc_midnight_gap_fill",
        template="novel",
        clock="1h/1h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs the gap from prior UTC day close to today's first hour open, "
            "then a fade toward the prior close. Not VWAP and not opening-range break."
        ),
        summary="Fade the UTC-midnight gap back toward the prior day's close.",
        justification="Daily gap vs prior close is calendar math, not a channel.",
    ),
    SleeveSpec(
        name="london_session_breakout",
        template="novel",
        clock="1h/1h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs the high/low of 08:00–16:00 UTC, published only after 16:00. "
            "Not Asian 00–08 and not the 1-hour opening range."
        ),
        summary="Break the completed London (08:00–16:00 UTC) range.",
        justification="London cash hours are a different session box than Asia or ORB.",
    ),
    SleeveSpec(
        name="ny_cash_open_drive",
        template="novel",
        clock="1h/1h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs the 13:00–14:00 UTC (08:00–09:00 ET) cash-open hour as a drive "
            "bar. Not ORB and not a Donchian."
        ),
        summary="Trade in the direction of the US cash-open hour after it closes.",
        justification="US cash open is a calendar hour the library does not isolate.",
    ),
    SleeveSpec(
        name="three_bar_play",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs a 3-bar play: trend bar, narrow rest bar inside it, then a "
            "break of the rest bar in the trend direction."
        ),
        summary="Break the rest bar of a 3-bar play.",
        justification="Three-bar structure is not inside-bar and not Donchian.",
    ),
    SleeveSpec(
        name="outside_bar_reversal",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs an outside bar (range fully contains the prior bar) plus close "
            "direction. Opposite of inside-bar breakout."
        ),
        summary="Reverse in the close direction of an outside bar.",
        justification="Outside-bar geometry is not an existing template.",
    ),
    SleeveSpec(
        name="doji_star_reversal",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs a doji (small body vs range) after a directional run, then the "
            "next close. Not wick-rejection and not engulfing."
        ),
        summary="Fade after a doji that prints following a directional run.",
        justification="Doji body/range ratio plus run context is new candle math.",
    ),
    SleeveSpec(
        name="round_number_fade",
        template="novel",
        clock="1h/1h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs psychological round levels (100/1000 steps of price) and a "
            "rejection. Not floor pivots from H+L+C."
        ),
        summary="Fade a rejection of a round psychological price.",
        justification="Round-number grid is not a pivot and not a channel.",
    ),
    SleeveSpec(
        name="prior_week_high_break",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs last completed UTC week's high/low, published only after Sunday "
            "closes. Not prior-day pivots and not a rolling Donchian."
        ),
        summary="Break the prior UTC week's high or low after that week has closed.",
        justification="Weekly calendar aggregation is not in the indicator library.",
    ),
    SleeveSpec(
        name="utc_session_twap_reversion",
        template="novel",
        clock="1h/1h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs time-weighted average price resetting at UTC midnight (equal "
            "weight per bar, not volume). Not session VWAP."
        ),
        summary="Fade stretch away from the UTC-day TWAP.",
        justification="TWAP is equal-time, VWAP is volume — different math.",
    ),
    SleeveSpec(
        name="failed_higher_high",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs two consecutive swing highs where the second makes a higher "
            "high then closes back below the first. Not a single swing-failure."
        ),
        summary="Fade a failed higher-high against the prior swing high.",
        justification="Two-swing structure is not one wick through one pivot.",
    ),
    SleeveSpec(
        name="nr7_breakout",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs the narrowest range of the last 7 bars (NR7), then a close "
            "beyond that bar. Not BB squeeze and not Donchian."
        ),
        summary="Break the NR7 bar after the narrowest of 7 prints.",
        justification="NR7 is a range-rank, not a squeeze of Bollinger width.",
    ),
    SleeveSpec(
        name="stochastic_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Stochastic %K from rolling high/low. Not RSI and not a "
            "golden-cross pullback."
        ),
        summary="Fade Stochastic %K extremes after a turn.",
        justification="Oscillator math is %K, not RSI(close).",
    ),
    SleeveSpec(
        name="cci_reversion",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Commodity Channel Index on typical price vs its mean deviation. "
            "Not Bollinger z-score and not RSI."
        ),
        summary="Fade CCI stretches beyond ±100.",
        justification="CCI uses typical price and mean absolute deviation.",
    ),
    SleeveSpec(
        name="supertrend_flip",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs a causal SuperTrend trailing stop (ATR bands that ratchets). "
            "Not an EMA±ATR channel break."
        ),
        summary="Enter when SuperTrend flips direction.",
        justification="Trailing ATR stop flip is a different bet from ATR channel breakout.",
    ),
    SleeveSpec(
        name="heikin_ashi_trend",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Heikin-Ashi open/close (HA close = OHLC/4, HA open = prior HA "
            "midpoint). Not raw candle direction."
        ),
        summary="Trade in the direction of a Heikin-Ashi run.",
        justification="HA averaging is new bar math, not EMA trend.",
    ),
    SleeveSpec(
        name="williams_r_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Williams %R = (HH-C)/(HH-LL). Related to Stochastic but inverted "
            "and typically −100..0. Not RSI fade."
        ),
        summary="Fade Williams %R extremes.",
        justification="Williams %R is a distinct range oscillator.",
    ),
    SleeveSpec(
        name="obv_break",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs On-Balance Volume cumulative signed volume, then a break of its "
            "own N-bar high/low. Not price Donchian."
        ),
        summary="Break the OBV channel, not the price channel.",
        justification="Volume ledger break is not a price-channel clone.",
    ),
    SleeveSpec(
        name="ichimoku_tk_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Tenkan/Kijun midpoints of 9/26-bar high-low (no displaced cloud, "
            "which would leak future bars). Not EMA cross."
        ),
        summary="Trade Tenkan crossing Kijun.",
        justification="Ichimoku midpoints are high-low averages, not EMAs.",
    ),
    SleeveSpec(
        name="mfi_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Money Flow Index (typical price * volume, positive vs negative "
            "flow RSI). Not RSI(close) and not volume climax."
        ),
        summary="Fade Money Flow Index extremes.",
        justification="MFI is volume-weighted RSI, not close-only RSI.",
    ),
    SleeveSpec(
        name="aroon_crossover",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Aroon up/down: bars since N-bar high vs low. Not Donchian break "
            "and not ADX."
        ),
        summary="Trade Aroon up crossing Aroon down.",
        justification="Time-since-extreme is different from a channel break.",
    ),
    SleeveSpec(
        name="awesome_oscillator_saucer",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Awesome Oscillator: SMA(HL2,5) - SMA(HL2,34). Saucer is three "
            "histogram bars, not MACD."
        ),
        summary="Enter on an Awesome Oscillator saucer.",
        justification="AO uses midpoint SMAs, not close MACD.",
    ),
    SleeveSpec(
        name="force_index_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Elder Force Index = (close-prior close)*volume, then EMA. "
            "Not volume climax RSI."
        ),
        summary="Fade an extreme Force Index print.",
        justification="Force Index is signed volume, not RSI.",
    ),
    SleeveSpec(
        name="trix_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs TRIX: rate of change of a triple EMA of close. Not a single "
            "EMA+ADX trend."
        ),
        summary="Trade TRIX crossing zero.",
        justification="Triple-smoothed ROC is not ema_adx_trend.",
    ),
    SleeveSpec(
        name="dpo_cycle_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Detrended Price Oscillator with a causal lag (shift SMA by "
            "N/2+1 of PAST bars only). Fade DPO extremes."
        ),
        summary="Fade causal DPO extremes.",
        justification="DPO removes trend; not a Bollinger mean-reversion.",
    ),
    SleeveSpec(
        name="vortex_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Vortex +VI/-VI from true-range-normalized VM+ / VM-. "
            "Not ADX and not SuperTrend."
        ),
        summary="Trade +VI crossing -VI.",
        justification="Vortex is a directional movement ratio, not ADX.",
    ),
    SleeveSpec(
        name="chande_momentum_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Chande Momentum Oscillator: (sum up - sum down)/(sum up + sum down) "
            "over N closes, scaled to -100..100. Not RSI Wilder smoothing."
        ),
        summary="Fade CMO extremes.",
        justification="CMO is a sum-of-change oscillator, not RSI.",
    ),
    SleeveSpec(
        name="chaikin_oscillator_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Chaikin Oscillator: EMA(ADL,3)-EMA(ADL,10) where ADL is "
            "cumulative CLV*volume. Not OBV and not MACD of close."
        ),
        summary="Trade Chaikin Oscillator crossing zero.",
        justification="ADL uses close location in the bar, not close-to-close OBV.",
    ),
    SleeveSpec(
        name="ppo_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Percentage Price Oscillator: 100*(EMA12-EMA26)/EMA26, signal "
            "EMA9 of PPO. Not MACD histogram in price units."
        ),
        summary="Trade PPO crossing its signal line.",
        justification="PPO is a percent MACD, not ema_adx_trend.",
    ),
    SleeveSpec(
        name="ultimate_oscillator_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Ultimate Oscillator: weighted average of 7/14/28 buying-pressure "
            "over true-range sums. Not RSI and not MFI."
        ),
        summary="Fade Ultimate Oscillator extremes.",
        justification="UO mixes three BP/TR windows; it is not a single RSI period.",
    ),
    SleeveSpec(
        name="kst_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Know Sure Thing: weighted sum of four ROC SMAs plus a signal SMA. "
            "Not MACD of close and not PPO."
        ),
        summary="Trade KST crossing its signal line.",
        justification="KST is a stacked ROC composite, not a dual-EMA MACD.",
    ),
    SleeveSpec(
        name="tsi_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs True Strength Index: double-smoothed momentum over double-smoothed "
            "absolute momentum. Not CMO and not RSI."
        ),
        summary="Trade TSI crossing zero.",
        justification="TSI is double-smoothed momentum, not Chande's raw sum ratio.",
    ),
    SleeveSpec(
        name="fisher_transform_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Fisher Transform of a normalized median price, then a trigger of "
            "the prior Fisher value. Not a z-score fade of close."
        ),
        summary="Trade Fisher Transform crossing its trigger.",
        justification="Fisher maps prices onto a Gaussian; it is not RSI or DPO.",
    ),
    SleeveSpec(
        name="hull_ma_trend",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Hull Moving Average: WMA(2*WMA(n/2) - WMA(n), sqrt(n)). "
            "Not EMA and not SMA."
        ),
        summary="Trade in the direction of a Hull MA turn.",
        justification="HMA weighting is distinct from EMA/SMA trend sleeves.",
    ),
    SleeveSpec(
        name="elder_ray_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Elder Ray Bull/Bear Power: high-EMA and low-EMA, fade extreme "
            "Bear Power turning up. Not ATR channel and not Force Index."
        ),
        summary="Fade extreme Elder Ray Bear/Bull Power.",
        justification="Elder Ray measures bar extremes vs EMA, not signed volume.",
    ),
    SleeveSpec(
        name="schaff_trend_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Schaff Trend Cycle: a stochastic of MACD, then a second stochastic. "
            "Not MACD histogram and not Stochastic %K of price."
        ),
        summary="Trade STC crossing 25/75.",
        justification="STC is a cycle transform of MACD, not ema_adx_trend.",
    ),
    SleeveSpec(
        name="mass_index_reversal",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Mass Index: EMA(high-low,9) / EMA of that EMA, then a 25-bar sum "
            "and a bulge-then-reversal. Not ATR and not BB width."
        ),
        summary="Reverse after a Mass Index bulge.",
        justification="Mass Index is a range-ratio bulge, not a squeeze of Bollinger width.",
    ),
    SleeveSpec(
        name="ease_of_movement_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Ease of Movement: midpoint change scaled by volume/range, then SMA. "
            "Not Force Index and not OBV."
        ),
        summary="Fade extreme Ease of Movement.",
        justification="EOM scales distance by box volume, not close-to-close force.",
    ),
    SleeveSpec(
        name="coppock_curve_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Coppock Curve: WMA of ROC(14)+ROC(11). Long-horizon ROC sum, "
            "not MACD and not TRIX."
        ),
        summary="Trade Coppock Curve crossing zero.",
        justification="Coppock is a WMA of two ROCs, not a triple EMA.",
    ),
    SleeveSpec(
        name="qstick_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Qstick: SMA of (close-open). Candle-body oscillator, not close MACD "
            "and not Heikin-Ashi."
        ),
        summary="Trade Qstick crossing zero.",
        justification="Qstick averages raw candle bodies, not reconstructed HA bars.",
    ),
    SleeveSpec(
        name="relative_vigor_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Relative Vigor Index: SMA of (close-open)/(high-low) vs its signal SMA. "
            "Not RSI and not Qstick of close-open alone."
        ),
        summary="Trade RVI crossing its signal line.",
        justification="RVI normalizes body by range; Qstick does not.",
    ),
    SleeveSpec(
        name="klinger_volume_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Klinger Volume Oscillator: EMA of signed volume based on high-low-close "
            "trend, fast minus slow, plus a signal EMA. Not Force Index and not Chaikin."
        ),
        summary="Trade Klinger Volume Oscillator crossing its signal.",
        justification="KVO signs volume from HLC trend, not close-to-close force.",
    ),
    SleeveSpec(
        name="kaufman_efficiency_trend",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Kaufman Efficiency Ratio: abs(close-close[n]) / sum(|close diffs|). "
            "Not ADX and not Aroon time-since-extreme."
        ),
        summary="Trade in the direction of a high-ER move.",
        justification="ER is path-efficiency, not DI smoothing.",
    ),
    SleeveSpec(
        name="demarker_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs DeMarker: SMA of DeMax / (DeMax+DeMin) from high-to-high and low-to-low "
            "steps. Not Stochastic %K of close and not RSI."
        ),
        summary="Fade DeMarker extremes.",
        justification="DeMarker uses bar-to-bar high/low steps, not a close oscillator.",
    ),
    SleeveSpec(
        name="choppiness_index_break",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Choppiness Index: 100*log10(sum(ATR)/range)/log10(n). Break when CI "
            "falls from a high reading. Not BB width squeeze and not ADX."
        ),
        summary="Break after Choppiness Index compresses.",
        justification="CI is a range-efficiency log ratio, not ATR-channel breakout.",
    ),
    SleeveSpec(
        name="connors_rsi_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Connors RSI: average of RSI(3), streak RSI, and percentile rank of ROC. "
            "Not a single-period RSI fade."
        ),
        summary="Fade Connors RSI extremes.",
        justification="Connors RSI mixes streak and rank; Wilder RSI does not.",
    ),
    SleeveSpec(
        name="mama_fama_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Ehlers MAMA/FAMA: MESA adaptive moving averages from Hilbert period. "
            "Not EMA cross and not Hull MA."
        ),
        summary="Trade MAMA crossing FAMA.",
        justification="MAMA is a Hilbert-period adaptive MA, not a fixed-length EMA.",
    ),
    SleeveSpec(
        name="center_of_gravity_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Ehlers Center of Gravity: weighted sum of closes / sum of weights, "
            "then a trigger. Not SMA and not Fisher."
        ),
        summary="Trade CG oscillator crossing its trigger.",
        justification="CG is a finite FIR oscillator, not a z-score of close.",
    ),
    SleeveSpec(
        name="parabolic_sar_flip",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Wilder Parabolic SAR: accelerating stop that flips on a stop hit. "
            "Not SuperTrend ATR bands."
        ),
        summary="Trade a Parabolic SAR flip.",
        justification="SAR acceleration is a distinct stop geometry from SuperTrend.",
    ),
    SleeveSpec(
        name="twiggs_money_flow_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Twiggs Money Flow: true-range AD buffer into volume, then EMA ratio. "
            "Not MFI and not Chaikin."
        ),
        summary="Fade Twiggs Money Flow extremes.",
        justification="TMF uses a TR buffer, not typical-price MFI.",
    ),
    SleeveSpec(
        name="balance_of_power_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Balance of Power: (close-open)/(high-low), then SMA. Not Qstick "
            "of raw bodies and not RVI of those SMAs."
        ),
        summary="Trade BOP crossing zero.",
        justification="BOP is a single-bar body/range ratio, not RVI's dual SMA.",
    ),
    SleeveSpec(
        name="volume_price_trend_break",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Volume Price Trend: cumulative (close-change %)*volume, then a break "
            "of its own N-bar high. Not OBV which uses only close direction."
        ),
        summary="Break the VPT channel.",
        justification="VPT scales volume by percent change; OBV is only sign(close).",
    ),
    SleeveSpec(
        name="kairi_relative_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Kairi Relative Index: 100*(close-SMA)/SMA. Percent-from-mean, "
            "not Bollinger z-score and not RSI."
        ),
        summary="Fade Kairi Relative Index extremes.",
        justification="Kairi is percent from SMA, not a band of standard deviation.",
    ),
    SleeveSpec(
        name="linreg_slope_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs least-squares slope of close over N bars, then a zero cross. "
            "Not EMA trend and not Coppock ROC."
        ),
        summary="Trade linear-regression slope crossing zero.",
        justification="OLS slope is a fit, not a moving-average difference.",
    ),
    SleeveSpec(
        name="ehlers_decycler_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Ehlers high-pass decycler of close vs a slow decycler. "
            "Not DPO with a causal SMA lag."
        ),
        summary="Trade the Ehlers decycler crossing zero.",
        justification="Decycler is a high-pass FIR, not detrended price vs SMA.",
    ),
    SleeveSpec(
        name="psychological_line_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Psychological Line: 100 * share of up-closes over N. "
            "Not RSI Wilder smoothing and not CMO."
        ),
        summary="Trade PSY crossing 50.",
        justification="PSY is a count of up days, not an average-gain oscillator.",
    ),
    SleeveSpec(
        name="rsi_laguerre_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Ehlers Laguerre RSI: a 4-pole Laguerre filter of close mapped to 0..1. "
            "Not Wilder RSI and not Connors RSI."
        ),
        summary="Fade Laguerre RSI extremes.",
        justification="Laguerre RSI is a FIR gamma filter, not Wilder smoothing.",
    ),
    SleeveSpec(
        name="vidya_trend",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs VIDYA: CMO-scaled EMA of close. Adaptive alpha from Chande momentum, "
            "not Kaufman ER and not MAMA Hilbert period."
        ),
        summary="Trade a VIDYA turn.",
        justification="VIDYA uses CMO for alpha; KAMA uses efficiency ratio.",
    ),
    SleeveSpec(
        name="t3_trend",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Tillson T3: six cascaded EMAs with a volume factor. Not Hull MA "
            "and not a single EMA."
        ),
        summary="Trade in the direction of a T3 turn.",
        justification="T3 is a six-pole EMA cascade, not HMA's WMA construction.",
    ),
    SleeveSpec(
        name="chaikin_money_flow_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Chaikin Money Flow: sum(CLV*volume)/sum(volume) over N. "
            "Not Twiggs TR-buffer and not Chaikin Oscillator of ADL."
        ),
        summary="Fade Chaikin Money Flow extremes.",
        justification="CMF is a windowed CLV volume ratio, not an EMA of ADL.",
    ),
    SleeveSpec(
        name="accumulation_distribution_break",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Accumulation/Distribution Line: cumulative CLV*volume, then a break "
            "of its N-bar high. Not OBV and not VPT percent-change volume."
        ),
        summary="Break the A/D line channel.",
        justification="ADL uses close location in the bar; OBV uses only close direction.",
    ),
    SleeveSpec(
        name="zero_lag_ema_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Ehlers zero-lag EMA: 2*EMA - EMA(EMA). Not MACD of raw EMAs "
            "and not T3."
        ),
        summary="Trade zero-lag EMA crossing a slow EMA.",
        justification="ZLEMA error-corrects lag; a plain EMA cross does not.",
    ),
    SleeveSpec(
        name="smi_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Stochastic Momentum Index: double-smoothed close vs midpoint of HH/LL. "
            "Not Stochastic %K and not Williams %R."
        ),
        summary="Fade SMI extremes.",
        justification="SMI double-smooths distance to the range midpoint, not %K of close.",
    ),
    SleeveSpec(
        name="elder_impulse_trend",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Elder Impulse: EMA slope and MACD histogram both green/red. "
            "Not ema_adx_trend and not MACD-only."
        ),
        summary="Trade when Elder Impulse turns green or red.",
        justification="Impulse requires EMA slope AND MACD hist, not ADX.",
    ),
    SleeveSpec(
        name="rainbow_oscillator_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Rainbow Oscillator: stacked SMAs of close, oscillator of the ribbon "
            "width. Not a dual-EMA MACD."
        ),
        summary="Trade Rainbow Oscillator crossing zero.",
        justification="Rainbow is a multi-SMA ribbon oscillator, not MACD.",
    ),
    SleeveSpec(
        name="laguerre_filter_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Ehlers Laguerre filter of close (four-pole gamma FIR), then a cross "
            "of filter vs its prior-bar trigger. Not Laguerre RSI and not EMA."
        ),
        summary="Trade the Laguerre filter crossing its trigger.",
        justification="The Laguerre filter is a gamma FIR of price, not RSI-mapped poles.",
    ),
    SleeveSpec(
        name="gator_oscillator_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Bill Williams Gator: SMMA of median price at 13/8/5 with 8/5/3 offsets, "
            "then jaw-teeth and teeth-lips as a two-sided oscillator. Not Alligator-only "
            "and not MACD of close."
        ),
        summary="Trade Gator Oscillator turning from sleep to awake.",
        justification="Gator is offset SMMA of median price, not an EMA histogram.",
    ),
    SleeveSpec(
        name="williams_fractal_break",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Williams 5-bar fractals: a confirmed swing high/low at t-2, then a close "
            "through that fractal. Not Donchian N-bar max and not swing-failure."
        ),
        summary="Break a confirmed Williams fractal.",
        justification="A fractal is a 5-bar pivot confirmation, not a rolling channel.",
    ),
    SleeveSpec(
        name="kama_trend",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Kaufman Adaptive Moving Average: ER-scaled smoothing constant between "
            "fast and slow SC. Not the ER-only kaufman_efficiency_trend sleeve and not VIDYA."
        ),
        summary="Trade a KAMA turn.",
        justification="KAMA adapts with efficiency ratio; VIDYA adapts with CMO.",
    ),
    SleeveSpec(
        name="dema_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs double EMA (DEMA) crossing a slow DEMA. Distinct from zero-lag 2*EMA-EMA(EMA) "
            "used as a fast line versus a raw EMA."
        ),
        summary="Trade DEMA crossing a slow DEMA.",
        justification="Two DEMAs, not ZLEMA versus a single EMA.",
    ),
    SleeveSpec(
        name="tema_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs triple EMA: 3*EMA - 3*EMA(EMA) + EMA^3. Not T3's volume-factor cascade "
            "and not DEMA."
        ),
        summary="Trade TEMA crossing a slow TEMA.",
        justification="TEMA is a three-EMA identity, not Tillson T3.",
    ),
    SleeveSpec(
        name="alma_trend",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Arnaud Legoux MA: Gaussian weights with offset. Not SMA, EMA, Hull, or T3."
        ),
        summary="Trade an ALMA turn.",
        justification="ALMA uses a Gaussian window, not cascaded EMAs.",
    ),
    SleeveSpec(
        name="keltner_break",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Keltner Channel: EMA mid with ATR bands, then a close through the band. "
            "Not Bollinger stdev bands and not SuperTrend."
        ),
        summary="Break a Keltner Channel band.",
        justification="Keltner is ATR around EMA, not a stdev envelope.",
    ),
    SleeveSpec(
        name="stochrsi_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Stochastic RSI: %K of Wilder RSI over N. Not Stochastic of price and not "
            "a single RSI fade."
        ),
        summary="Fade Stochastic RSI extremes.",
        justification="StochRSI ranks RSI, not close, inside its own window.",
    ),
    SleeveSpec(
        name="chandelier_exit_flip",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Chandelier Exit: ATR trail from the extreme high/low since entry side, "
            "flip on a close through the trail. Not Parabolic SAR acceleration."
        ),
        summary="Trade a Chandelier Exit flip.",
        justification="Chandelier trails ATR from HH/LL, not SAR AF steps.",
    ),
    SleeveSpec(
        name="mcginley_dynamic_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs McGinley Dynamic: MD = MD_prev + (close-MD_prev) / (N * (close/MD_prev)^4). "
            "Not EMA and not VIDYA."
        ),
        summary="Trade McGinley Dynamic crossing price.",
        justification="McGinley speed-adjusts with a fourth-power ratio, not CMO.",
    ),
    SleeveSpec(
        name="super_smoother_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Ehlers SuperSmoother 2-pole IIR of close, then a cross of filter vs trigger. "
            "Not Laguerre gamma FIR and not EMA."
        ),
        summary="Trade SuperSmoother crossing its trigger.",
        justification="SuperSmoother is a 2-pole Butterworth, not Laguerre poles.",
    ),
    SleeveSpec(
        name="roofing_filter_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs Ehlers roofing filter: high-pass then SuperSmoother of close. Not a "
            "single high-pass decycler."
        ),
        summary="Trade the roofing filter crossing zero.",
        justification="Roofing is HP then SuperSmoother; decycler is HP minus slow HP.",
    ),
    SleeveSpec(
        name="squeeze_momentum_break",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs TTM-style squeeze: Bollinger inside Keltner, then a linreg momentum release. "
            "Not BB-width squeeze alone."
        ),
        summary="Break after a BB-inside-Keltner squeeze.",
        justification="Squeeze requires BB inside KC, then momentum, not width only.",
    ),
    SleeveSpec(
        name="volume_weighted_macd_cross",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs MACD of VWMA(close, volume) rather than EMA of close. Not PPO and not "
            "a volume-less MACD."
        ),
        summary="Trade volume-weighted MACD crossing its signal.",
        justification="VW-MACD weights by volume; standard MACD does not.",
    ),
    SleeveSpec(
        name="volume_force_divergence",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs cumulative Volume Force: signed volume of close-to-close change "
            "normalized by ATR, then a fade when price makes a new N-bar high/low "
            "that force does not confirm. Not Elder Force Index z-score fade and "
            "not VPT percent-change volume."
        ),
        summary="Fade a price extreme that ATR-normalized volume force does not confirm.",
        justification=(
            "ATR-normalized cumulative force is a different ledger from EMA(ΔC*V) "
            "and from VPT. Divergence plus a low-ADX chop filter is the bet."
        ),
    ),
    SleeveSpec(
        name="session_liquidity_sweep",
        template="novel",
        clock="1h/1h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs the completed Asian (00:00–08:00 UTC) high/low, then a London/NY "
            "bar that sweeps that box by less than 1% and closes back inside. "
            "Opposite of asian_range_breakout; not wick-rejection without a session box."
        ),
        summary=(
            "Fade a failed London/NY sweep of the completed Asian session range."
        ),
        justification=(
            "Failed session-box stop-runs are a different bet from breaking the "
            "Asian range and from a generic wick-rejection with no session clock."
        ),
    ),
    SleeveSpec(
        name="bar_vwap_inflow_surge",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs per-bar VWAP from unused turnover/volume, then pulse = "
            "volume*(close-bar_vwap)/ATR versus the prior-20 |pulse| baseline "
            "(current bar excluded). LONG surge>2, SHORT<-2. Optional "
            "same-direction body. Not OBV/VPT/Force/volume_force_divergence/"
            "ADL/CMF/Klinger/climax fade. Do not cumsum. Do not fade. Do not "
            "invent taker/CVD/netflow/on-chain/funding columns."
        ),
        summary="Follow a per-bar VWAP inflow surge from unused turnover.",
        justification=(
            "Turnover/volume is a bar VWAP the other volume ledgers never use. "
            "A one-bar pulse versus its own prior |pulse| is not a cumulative "
            "force and not a fade of a price extreme."
        ),
    ),
    SleeveSpec(
        name="fib_retracement_bounce",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs a 0.618 bounce of a completed impulse from causal "
            "confirmed_swings. LONG: last event is swing high after a distinct "
            "low, tag 0.618, close back above it, origin intact. SHORT "
            "symmetric. Ratios 0.500/0.618/0.786. Optional 0.15*ATR buffer. "
            "Not Donchian, not floor pivots, not round_number_fade, not "
            "swing_failure_reversal. Do not implement 1.272/1.618 extensions."
        ),
        summary="Bounce the 0.618 retracement of a completed confirmed-swing impulse.",
        justification=(
            "The 0.618 tag is two confirmed swings, not a rolling Donchian, "
            "not a daily floor pivot, and not a failed swing break. Extensions "
            "are a different family."
        ),
    ),
    SleeveSpec(
        name="fib_extension_break",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs a 1.618 extension break of a completed impulse from causal "
            "confirmed_swings. Last event +1 new swing high, -1 new swing low, "
            "ffill. LONG: up-impulse ready, close>ext, close>H. SHORT "
            "symmetric. ext=end+0.618*(end-start). Optional inner 1.272 as "
            "zone start, not a second family. Invalidation is close back "
            "through impulse end. Search 1.618 only; inner 1.272 is display. "
            "Not Donchian, not fib_retracement_bounce. Do not implement the "
            "0.618 retracement bounce."
        ),
        summary="Break a 1.618 extension of a completed confirmed-swing impulse.",
        justification=(
            "The 1.618 break is two confirmed swings projected past the "
            "impulse end, not a rolling Donchian and not the 0.618 bounce of "
            "the same impulse. Follow-on to fib_retracement_bounce, not a clone."
        ),
    ),
    SleeveSpec(
        name="measured_move_break",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs an AB=CD measured-move break of a completed impulse from "
            "causal confirmed_swings. Same last-event impulse as "
            "fib_extension_break. LONG: up-impulse ready, close>mm, close>H. "
            "SHORT symmetric. mm=end+1.0*(end-start)=2*end-start. "
            "Invalidation is close back through impulse end. Ratio locked at "
            "1.0. Not Donchian, not H+0.618*R, not fib_extension_break. Do "
            "not implement 1.618 or 0.618 in this family."
        ),
        summary="Break a 100% measured move (AB=CD) of a completed confirmed-swing impulse.",
        justification=(
            "The measured move projects 100% of two confirmed swings past the "
            "impulse end. That is not a rolling Donchian and not the 1.618 "
            "extension of the same impulse. Follow-on to fib_extension_break, "
            "not a clone."
        ),
    ),
    SleeveSpec(
        name="up_down_turnover_imbalance",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs up-bar vs down-bar turnover (close>prior close vs "
            "close<prior close). imb=(sum_N up_to - sum_N down_to)/"
            "(sum_N up_to + sum_N down_to). LONG imb>k, SHORT imb<-k. "
            "Follow-the-money, not a fade. Not a close-only oscillator. "
            "Not OBV/VPT/Force/bar_vwap_inflow_surge/ADL/CMF. Do not "
            "cumsum. Do not invent taker/CVD/netflow/on-chain/funding "
            "columns."
        ),
        summary="Follow the money via up-bar vs down-bar turnover.",
        justification=(
            "Turnover on up-closes versus down-closes is a participation "
            "split the close-only oscillators never see. A rolling "
            "imbalance of unused quote volume is not an OBV ledger and "
            "not a per-bar VWAP pulse."
        ),
    ),
    SleeveSpec(
        name="signed_range_turnover_trend",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs pulse = (close-open)*turnover, then trend = sum_N pulse "
            "/ (prior-N mean|pulse| * N) with the current bar excluded "
            "from the baseline. LONG trend>k, SHORT trend<-k. Direction "
            "plus participation. Not an EMA/ADX clone. Not Qstick, not "
            "Force Index, not bar_vwap_inflow_surge, not BOP. Do not "
            "invent taker/CVD/netflow/on-chain/funding columns."
        ),
        summary="Follow signed range times turnover (direction plus participation).",
        justification=(
            "The product of (close-open) and unused quote turnover is not "
            "an EMA of close and not ADX. Qstick ignores participation; "
            "Force Index uses Δclose × base volume. This is a rolling "
            "trend of signed-range × turnover."
        ),
    ),
    SleeveSpec(
        name="swing_anchored_vwap_pullback",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs a pullback to VWAP anchored on causal confirmed_swings. "
            "Same last-event impulse as fib_extension_break (+1 new swing "
            "high, -1 new swing low, ffill). LONG: up-impulse ready, "
            "end>avwap, low<=avwap, close>avwap, origin intact. SHORT "
            "symmetric. avwap=Σturnover/Σvolume from origin publish. "
            "Invalidation is close back through origin. Not "
            "fib_retracement_bounce (dead 0.618). Not fib_extension_break "
            "(already in the book). Do not implement 0.618 or 1.618 in "
            "this family."
        ),
        summary="Pullback to VWAP anchored on confirmed_swings.",
        justification=(
            "Same swing engine as fib_extension_break, different path: "
            "volume-weighted continuation. AVWAP is Σturnover/Σvolume "
            "from the impulse origin, not a 0.618 fib tag and not a "
            "1.618 extension break."
        ),
    ),
    SleeveSpec(
        name="monday_range_sweep_reversal",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs the completed UTC weekend (Sat 00:00–Sun 23:59) high/low, "
            "then a Monday London/NY bar that sweeps that box by less than "
            "1.5% and closes back inside, fading toward the weekend mid. "
            "Calendar weekend, not the Asian 00:00–08:00 session box "
            "(session_liquidity_sweep is dead). Not weekend_gap_fill."
        ),
        summary="Fade a failed Monday London/NY sweep of the completed UTC weekend range.",
        justification=(
            "A Sat–Sun calendar box faded on Monday London/NY is a different "
            "bet from the Asian session sweep and from fading Friday's close."
        ),
    ),
    SleeveSpec(
        name="volume_imbalance_delta_reversal",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs bar-level buy/sell volume share at a 20-bar high/low. "
            "LONG: new 20-bar low and selling share < 20%. SHORT: new "
            "20-bar high and buying share < 20%. Share is "
            "(close-low)/(high-low) on this bar only. Target 20-EMA. Not "
            "cumulative force (volume_force_divergence is dead). Do not "
            "cumsum. Do not invent taker/CVD/netflow columns."
        ),
        summary="Fade a 20-bar extreme when that bar's buy/sell volume share is exhausted.",
        justification=(
            "One bar's close-location volume split at a rolling extreme is "
            "not a cumulative force ledger and not Elder Force / OBV / VPT."
        ),
    ),
    SleeveSpec(
        name="session_boundary_volume_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs the prior UTC calendar day's high/low, then a 4h bar "
            "that sweeps that box on volume below the 20-period volume MA, "
            "fading toward daily VWAP. Calendar UTC day box + weak-volume "
            "filter. Not prior_day_pivot_breakout (floor P/R1/S1 breakout, "
            "rejected OOS). Not session_liquidity_sweep (Asian 00:00–08:00 "
            "failed-sweep close). Not session_volume_profile_*. Do not "
            "require close back inside."
        ),
        summary="Fade a weak-volume 4h sweep of the prior UTC day high/low toward daily VWAP.",
        justification=(
            "A calendar UTC day box faded on weak volume is not a floor-pivot "
            "breakout and not an Asian-session failed sweep."
        ),
    ),
    SleeveSpec(
        name="vwap_spread_exhaustion",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs abs(rolling 20 VWAP − 20 SMA) / 20 ATR. When that "
            "spread is an N-bar extreme and volume is expanding, fade "
            "back to the rolling VWAP, filtered by low ADX. Rolling VWAP "
            "vs SMA dislocation, not a session VWAP "
            "(utc_session_vwap_reversion is a book row). Do not reset at "
            "UTC midnight."
        ),
        summary="Fade an N-bar extreme of rolling-VWAP vs SMA, scaled by ATR, in low ADX.",
        justification=(
            "A rolling VWAP−SMA gap / ATR is not a UTC-session VWAP stretch "
            "and not a Bollinger fade of close versus SMA."
        ),
    ),
    SleeveSpec(
        name="vwap_volatility_band_fade",
        template="novel",
        clock="1h/1h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs bands around rolling 20 VWAP using stdev of close. Fade "
            "when price touches the outer band on 1h AND Bollinger Band "
            "Width is in the bottom 30% of its 100-bar range, targeting "
            "VWAP. VWAP ± σ only inside a BB-width squeeze. Not "
            "bollinger_mean_reversion (book-row SMA bands). Do not use "
            "BB mid as the mean."
        ),
        summary="Fade a rolling-VWAP ± σ band only inside a Bollinger-width squeeze.",
        justification=(
            "VWAP ± σ gated by BB-width compression is not a raw Bollinger "
            "fade of close versus the SMA."
        ),
    ),
    SleeveSpec(
        name="london_close_inventory_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs the 4h bar covering 15:00–16:00 UTC and London-session "
            "VWAP (08:00–16:00), not UTC-midnight VWAP. Fade when that close "
            "is in the extreme 20% of the bar on volume above the prior-20 "
            "mean. Calendar London-close inventory. Not london_session_breakout "
            "(break the completed 08–16 box after 16:00). Not "
            "session_boundary_volume_fade. Not monday_range_sweep_reversal."
        ),
        summary="Fade an extreme London-close 4h bar on high volume, back to London VWAP.",
        justification=(
            "The London cash-close 4h bar faded to London VWAP is not a "
            "London-range breakout and not a UTC-day box fade."
        ),
    ),
    SleeveSpec(
        name="utc_open_fail_reversion",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs the UTC day's first 4h (00:00–04:00) as a box, then a "
            "failed break on the second 4h (04:00–08:00) that closes back "
            "inside, fading toward the first-4h mid. Not utc_midnight_gap_fill "
            "(first-bar open vs prior close). Not asian_range_breakout "
            "(break the 00–08 box after 08:00). Not session_liquidity_sweep."
        ),
        summary="Fade a failed break of the UTC day's first 4h box on the second 4h bar.",
        justification=(
            "A failed second-4h break of the first-4h UTC box is not a "
            "midnight gap fill and not an Asian-range breakout."
        ),
    ),
    SleeveSpec(
        name="range_compression_volume_thrust",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs 20-bar ATR in the bottom 30% of its 100-bar range, then a "
            "bar with true range > 1.5× ATR, close in the bar's direction, "
            "and volume above the prior-20 mean. Compression is ATR "
            "percentile only. Not squeeze_momentum_break (BB inside Keltner). "
            "Not nr7_breakout. Not bb_squeeze_breakout."
        ),
        summary="Follow a volume-thrust bar that exits ATR compression.",
        justification=(
            "ATR-percentile compression plus a volume-confirmed range "
            "expansion is not a BB-width squeeze and not NR7."
        ),
    ),
    SleeveSpec(
        name="turnover_climax_rejection_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs unused quote turnover as a 20-bar high, then a fade when "
            "that climax bar breaks the 20-bar price high and closes in the "
            "lower 20% (SHORT) or breaks the 20-bar low and closes in the "
            "upper 20% (LONG). Climax + rejection. Not volume_climax_fade "
            "(RSI + base volume). Not bar_vwap_inflow_surge. Not "
            "up_down_turnover_imbalance. Do not invent taker/CVD columns."
        ),
        summary="Fade a quote-turnover climax whose close rejects the 20-bar extreme.",
        justification=(
            "A 20-bar turnover climax with a rejected close is not an RSI "
            "volume-climax fade and not a follow-the-money imbalance."
        ),
    ),
    SleeveSpec(
        name="volume_dryup_range_break",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs 3 consecutive bars with volume below the prior-20 mean "
            "(current bar excluded), then a thrust bar with volume above that "
            "mean that closes beyond the 3-bar high (LONG) or 3-bar low "
            "(SHORT). Consecutive dry-up box then expansion. Not "
            "range_compression_volume_thrust (ATR percentile). Not "
            "nr7_breakout. Not squeeze_momentum_break."
        ),
        summary="Break a 3-bar dry-up box on the first volume-confirmed thrust.",
        justification=(
            "Three quiet-volume bars then a volume-confirmed range break is "
            "not ATR-percentile compression and not NR7."
        ),
    ),
    SleeveSpec(
        name="body_efficiency_follow",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs two consecutive 4h bars with body efficiency "
            "|close-open|/true_range >= 0.7, the same close direction, and "
            "the second bar's volume >= the first. Follow that direction. "
            "Not three_bar_play (trend + rest + break). Not "
            "engulfing_reversal (body swallow, reverse). Not "
            "consecutive_bar_exhaustion (fade after N closes)."
        ),
        summary="Follow two consecutive high body-efficiency 4h bars in the same direction.",
        justification=(
            "Two efficient same-direction bodies with non-decreasing volume "
            "is a follow, not a 3-bar rest break, not an engulfing reverse, "
            "and not a consecutive-close fade."
        ),
    ),
    SleeveSpec(
        name="week_open_reclaim",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs this week's UTC Monday 00:00 open (first 4h open of the "
            "ISO week). After at least 3 4h closes on the wrong side of that "
            "open, trade the reclaim: LONG when close crosses back above "
            "with volume above the prior-20 mean; SHORT when close crosses "
            "back below. Not monday_range_sweep_reversal (weekend H/L fade). "
            "Not swing_anchored_vwap_pullback. Not prior_week_high_break."
        ),
        summary="Reclaim this week's UTC Monday 00:00 open after a wrong-side excursion.",
        justification=(
            "A Monday-open reclaim after three wrong-side 4h closes is not "
            "a weekend-range fade, not a prior-week high break, and not an "
            "AVWAP pullback."
        ),
    ),
    SleeveSpec(
        name="prior_session_mid_reclaim",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs UTC 8h sessions 00-08 / 08-16 / 16-24. After the session "
            "closes through one side of its (high+low)/2 midpoint, a later "
            "4h bar that closes back through that mid on volume above the "
            "prior-20 mean trades the reclaim. Not session_boundary_volume_fade "
            "(prior UTC day H/L). Not utc_session_vwap_reversion. Not "
            "utc_open_fail_reversion (first-4h box fail)."
        ),
        summary="Reclaim the prior completed UTC 8h session midpoint.",
        justification=(
            "An 8h session-mid reclaim after the session closes through one "
            "side is not a UTC-day box fade, not a session-VWAP stretch, and "
            "not a first-4h opening-box fail."
        ),
    ),
    SleeveSpec(
        name="close_location_persistence",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Needs CLV=(close-low)/(high-low) averaged over lookback "
            "(default 8). LONG when mean CLV>=0.75 and current close is not "
            "a 20-bar high. SHORT when mean CLV<=0.25 and current close is "
            "not a 20-bar low. Free params: lookback, clv_threshold. Not "
            "body_efficiency_follow (body occupancy). Not "
            "wick_rejection_reversal. Not turnover, session/VWAP, or week-open."
        ),
        summary="Follow persistent close location (mean CLV) without a new 20-bar close extreme.",
        justification=(
            "Auction location persistence across bars is not body occupancy, "
            "not a wick rejection, not turnover, not session/VWAP, and not "
            "week-open. A doji at the high has CLV near 1 and efficiency near 0."
        ),
    ),
    SleeveSpec(
        name="open_in_prior_range_fail",
        template="novel",
        clock="4h/4h",
        novel_reason=(
            "If this 4h opens outside the prior 4h high-low, then the close "
            "fails back inside that prior range, fade toward the prior-bar "
            "mid (SHORT if opened above prior high and closed back inside; "
            "LONG if opened below prior low and closed back inside). Not "
            "utc_open_fail_reversion (UTC first-4h box, 0/12). Not "
            "ny_cash_open_drive."
        ),
        summary="Fade a same-bar fail of an open that started outside the prior bar's range, toward the prior-bar mid.",
        justification=(
            "An adjacent-bar open-outside then close-back-inside fail is not "
            "a UTC first-4h box fail and not a NY cash-open drive."
        ),
    ),
    SleeveSpec(
        name="equal_high_low_restest_fade",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "Rolling equal high/low restest fail. If a 4h high (low) matches "
            "a prior high (low) within a small tick/ATR tolerance inside a "
            "lookback, then this bar trades through that level and closes "
            "back inside, fade the failed restest. Family id is restest as "
            "spelled, not retest. Not monday_range_sweep_reversal (weekend "
            "box). Not session_liquidity_sweep (dead, do not recode)."
        ),
        summary="Fade a failed restest of a rolling equal high or equal low.",
        justification=(
            "A rolling equal-high/low restest fail is not a weekend-box "
            "Monday sweep and not the dead Asian-session liquidity sweep."
        ),
    ),
    SleeveSpec(
        name="double_bottom_neckline_break",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "In lookback (default 40) identify two swing lows whose prices "
            "differ by <= 0.15*ATR(20) and an intervening swing high "
            "(neckline). LONG when close_t crosses above that neckline. "
            "SHORT when the second low is in place and close_t crosses below "
            "it (pattern invalidation), not a neckline break of two highs. "
            "Free params: lookback, atr_tol. Not equal_high_low_restest_fade "
            "(job 110, fades a failed restest without neckline break). Not "
            "swing_failure_reversal. Not monday_range_sweep_reversal. Not "
            "failed_higher_high. Not a rename of double_top."
        ),
        summary="Long a confirmed double-bottom neckline break; short the second-low invalidation.",
        justification=(
            "A confirmed close through the intervening high of two matched "
            "swing lows is a different event from a failed equal-high/low "
            "restest fade."
        ),
    ),
    SleeveSpec(
        name="double_top_neckline_break",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "In lookback (default 40) identify two swing highs whose prices "
            "differ by <= 0.15*ATR(20) and an intervening swing low "
            "(neckline). SHORT when close_t crosses below that neckline. "
            "LONG when the second high is in place and close_t crosses above "
            "it (invalidation), not a neckline break of two lows. Free "
            "params: lookback, atr_tol. High-high-neckline geometry, not a "
            "sign-flipped double_bottom file. Distinct from 110: 110 fades "
            "a failed restest; this trades the confirmed neckline break."
        ),
        summary="Short a confirmed double-top neckline break; long the second-high invalidation.",
        justification=(
            "Two matched swing highs and a close through the intervening low "
            "is not a failed restest fade and not a flipped double-bottom file."
        ),
    ),
    SleeveSpec(
        name="ascending_triangle_break",
        template="novel",
        clock="4h/4h",
        needs_new_indicator=True,
        novel_reason=(
            "LONG: at least two rising swing lows (each low > prior swing "
            "low) into a flat swing-high cap (highs within 0.15*ATR(20)), "
            "then close_t through the cap AND volume_t > mean(volume_"
            "{t-20..t-1}). SHORT: descending-triangle inverse, at least two "
            "falling swing highs into a flat swing-low floor, then close "
            "through the floor on volume above prior-20 mean. Free params: "
            "lookback (default 40), atr_tol. Volume threshold is fixed as "
            "prior-20 mean, not a third param. Not NR7. Not "
            "range_compression_volume_thrust (102, compression then thrust, "
            "no triangle geometry). Not inside_bar_breakout. Not "
            "squeeze_momentum_break (dead, do not recode)."
        ),
        summary="Break an ascending triangle on volume (descending-triangle inverse for shorts).",
        justification=(
            "Rising lows into a flat high cap, broken on volume, is triangle "
            "geometry — not ATR-percentile compression, not NR7, and not an "
            "inside-bar box."
        ),
    ),
    SleeveSpec(
        name="prior_day_extreme_reject",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Fade a 4h tag of the prior UTC day's high or low that closes "
            "back inside that day's range. SHORT when high_t >= "
            "prior_day_high and close_t < prior_day_high. LONG when "
            "low_t <= prior_day_low and "
            "close_t > prior_day_low. Quant-locked: require_close_inside=True, "
            "touch_tol_atr search [0.0, 0.10], raw prior UTC day H/L (not "
            "R1/S1, not weekend box). Not monday_range_sweep_reversal "
            "(weekend Sat-Sun box). Not week_open_reclaim. Not "
            "equal_high_low_restest_fade (rolling equal H/L). Not "
            "double_top/double_bottom neckline. Not classic_floor_pivot_reject "
            "(R1/S1 from P). Not session_boundary_volume_fade (weak-volume "
            "sweep, no close-inside). Do not recode asia_close_inventory_fade "
            "or wyckoff_spring_reclaim."
        ),
        summary=(
            "Fade a 4h tag of the prior UTC day's high or low that closes "
            "back inside that day's range."
        ),
        justification=(
            "A failed 4h tag of yesterday's UTC high/low that closes back "
            "inside the day box is not a weekend sweep, not a Monday-open "
            "reclaim, not a rolling equal-H/L restest, not a neckline break, "
            "and not a floor-pivot R1/S1 fade."
        ),
    ),
    SleeveSpec(
        name="failed_range_break_reversion",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Fade a 4h close back inside a prior N-bar range after a "
            "close-through that fails to hold. SHORT: a prior bar closed "
            "above range_high, then close_t is back below range_high "
            "(within max_bars_since_break). LONG: a prior bar closed below "
            "range_low, then close_t is back above range_low. Quant-locked: "
            "require_close_inside=True, lookback [16, 20], "
            "max_bars_since_break [2, 3], no volume. Not "
            "range_compression_volume_thrust (successful thrust). Not "
            "expansion_fail_fade (single ATR expansion bar). Not nr7 / orb "
            "fail. Not ascending_triangle_break / H&S neckline confirmed "
            "breaks. Not prior_day_extreme_reject (prior UTC day H/L). Do "
            "not recode asia_close_inventory_fade, wyckoff_spring_reclaim, "
            "or the Garwe buffer three."
        ),
        summary=(
            "Fade a 4h close back inside a prior N-bar range after a break "
            "that fails to hold."
        ),
        justification=(
            "A failed close-through of a rolling N-bar range that re-closes "
            "inside is not a successful volume thrust, not a single ATR "
            "expansion fade, not NR7/ORB, not a neckline break, and not a "
            "prior UTC day H/L reject."
        ),
    ),
    SleeveSpec(
        name="asia_range_london_reject",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "London bar tags the completed Asia 00:00–08:00 UTC high/low "
            "then closes back inside that Asia range (failed hold of the "
            "Asia extreme). LONG: London low tags/pierces Asia low within "
            "touch_tol_atr*ATR, close back above Asia low / inside the box. "
            "SHORT: London high tags/pierces Asia high, close back below "
            "Asia high / inside the box. Quant-locked: "
            "require_close_inside=True, touch_tol_atr [0.0, 0.10], fixed "
            "Asia 00:00–08:00 and London 07:00–16:00, raw Asia H/L only, "
            "no volume. Not "
            "asia_close_inventory_fade (fade AT Asia close inventory). Not "
            "asian_range_breakout (close-through breakout). Not "
            "session_liquidity_sweep (1h London+NY, max_sweep_pct cap). "
            "Not prior_day_extreme_reject (prior UTC calendar day H/L). "
            "Not failed_range_break_reversion (rolling N-bar range). Not "
            "monday_range_sweep_reversal. Not "
            "range_compression_volume_thrust. Not orb / nr7 fail, H&S, or "
            "wyckoff."
        ),
        summary=(
            "Fade a London tag of the completed Asia session high/low that "
            "closes back inside that Asia range."
        ),
        justification=(
            "A London failed hold of the same-day Asia session extreme is "
            "not a close-through Asia breakout, not a 1h London+NY "
            "max_sweep_pct fade, not a prior UTC day H/L reject, and not a "
            "rolling N-bar failed-range reversion."
        ),
    ),
    SleeveSpec(
        name="orb_fail_reversion",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Fade a failed UTC-day opening-range break: price breaks the "
            "day ORB then fails to hold and reverts back inside. SHORT: "
            "break above ORB high then close back below within "
            "max_bars_since_break. LONG: break below ORB low then close "
            "back above. Quant-locked: require_close_inside=True, "
            "orb_bars [1, 2], max_bars_since_break [2, 4], no volume. Not "
            "opening_range_breakout (finished leftover / breakout "
            "direction). Not failed_range_break_reversion (119 — rolling "
            "N-bar range). Not prior_day_extreme_reject (118 — prior UTC "
            "day H/L reject). Not asia_range_london_reject (120 — Asia "
            "box / London reject). Not nr7_fail_reversion (stays buffer). "
            "Not range_compression_volume_thrust (102). Not H&S / "
            "asia_close / wyckoff."
        ),
        summary=(
            "Fade a failed UTC-day opening-range break: price breaks the "
            "day ORB then fails to hold and reverts back inside."
        ),
        justification=(
            "A close-through of the UTC-day opening range that fails to "
            "hold and re-closes inside is not a successful ORB follow, "
            "not a rolling N-bar failed-range, not a prior UTC day H/L "
            "reject, and not an Asia-box London reject."
        ),
    ),
    SleeveSpec(
        name="nr7_fail_reversion",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Fade a failed NR7 break: after an NR7 bar (narrowest range "
            "of last 7), price breaks the NR7 high/low then fails to "
            "hold and reverts back inside. SHORT: break above NR7 high "
            "then close back below within max_bars_since_break. LONG: "
            "break below NR7 low then close back above. Quant-locked: "
            "NR7 definition fixed, require_close_inside=True, "
            "max_bars_since_break [1, 3], no volume. Not nr7_breakout "
            "(breakout direction / leftover). Not expansion_fail_fade "
            "(single ATR expansion). Not "
            "range_compression_volume_thrust (102 — thrust). Not "
            "failed_range_break_reversion (119 — rolling N-bar). Not "
            "orb_fail_reversion (121/122 — UTC day ORB). Not "
            "prior_day_extreme_reject (118), asia_range_london_reject "
            "(120). Not H&S / asia_close / wyckoff."
        ),
        summary=(
            "Fade a failed NR7 break: after an NR7 bar (narrowest range "
            "of last 7), price breaks the NR7 high/low then fails to "
            "hold and reverts back inside."
        ),
        justification=(
            "A close-through of a locked NR7 bar that fails to hold and "
            "re-closes inside is not a successful NR7 follow, not a "
            "single ATR expansion fade, not a volume thrust, not a "
            "rolling N-bar failed-range, and not a UTC-day ORB fail."
        ),
    ),
    SleeveSpec(
        name="ib_fail_reversion",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Fade a failed London inside-bar break: after an inside bar "
            "whose mother is the first 4h bar with UTC open in "
            "07:00–11:00, price breaks the mother/IB high/low then "
            "fails to hold and reverts back inside. SHORT: break above "
            "mother high then close back below within "
            "max_bars_since_break. LONG: break below mother low then "
            "close back above. Quant-locked: London IB open 07:00–11:00 "
            "fixed, require_close_inside=True, "
            "max_bars_since_break [2, 4], no volume. Not "
            "nr7_fail_reversion (123 — narrowest-of-7). Not "
            "failed_range_break_reversion (119 — rolling N-bar). Not "
            "orb_fail_reversion (121 — UTC day ORB). Not "
            "asia_range_london_reject (120 — Asia H/L London tag). Not "
            "prior_day / prior_week extreme reject. Not "
            "inside_bar_breakout (breakout direction). Not "
            "engulfing_reversal. Not H&S / asia_close / wyckoff."
        ),
        summary=(
            "Fade a failed London inside-bar break: after an inside bar "
            "whose mother is the first 4h bar with UTC open in "
            "07:00–11:00, price breaks the mother high/low then fails "
            "to hold and reverts back inside."
        ),
        justification=(
            "A close-through of a locked first-4h-open-in-07:00–11:00 "
            "mother after a true inside bar that fails to hold and "
            "re-closes inside is "
            "not a successful IB follow, not NR7, not a rolling N-bar "
            "failed-range, not a UTC-day ORB fail, and not an Asia-box "
            "London tag."
        ),
    ),
    SleeveSpec(
        name="converging_wedge_break",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        needs_new_indicator=True,
        novel_reason=(
            "Break a converging wedge where BOTH rails slope and converge. "
            "Rising wedge (HH+HL both slope up, converge): SHORT on close "
            "below the lower rail. Falling wedge (LH+LL both slope down, "
            "converge): LONG on close above the upper rail. Quant-locked: "
            "min_touches=3 (not searched), lookback [30, 40], no volume. "
            "Not ascending_triangle_break (one rail flat). Not "
            "ib_fail_reversion (124 — inside-bar fail). Not nr7 / orb_fail "
            "/ asia_range / prior_day / failed_range (118–123). Not "
            "engulfing_fail / prior_week_extreme. Not H&S / asia_close / "
            "wyckoff."
        ),
        summary=(
            "Break a converging wedge (both rails slope and converge): "
            "SHORT a rising wedge below the lower rail, LONG a falling "
            "wedge above the upper rail."
        ),
        justification=(
            "A close through an OLS rail of a both-rails-sloping "
            "converging wedge is not a flat-cap triangle, not an IB fail, "
            "not NR7/ORB/Asia/prior-day/failed-range, and not a neckline "
            "or session-inventory fade."
        ),
    ),
    SleeveSpec(
        name="engulfing_fail_reversion",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Fade a failed engulfing continuation: after a "
            "bullish/bearish engulfing bar, price breaks the engulf "
            "extreme then fails with a close back through the engulf "
            "open (not a wick-only tag). SHORT: after a bullish engulf, "
            "break above the engulf high then close back through the "
            "engulf open within max_bars_since_engulf. LONG: after a "
            "bearish engulf, break below the engulf low then close back "
            "through the open. Quant-locked: require_close_inside=True, "
            "body_eff locked OFF, max_bars_since_engulf [1, 2], no "
            "volume. Not book engulfing_reversal (fires on the engulf "
            "bar). Not failed_range_break_reversion (119 — rolling "
            "N-bar). Not orb_fail_reversion (121 — UTC day ORB). Not "
            "nr7_fail_reversion (123). Not ib_fail / asia_range / "
            "prior_day / converging_wedge (125 spent n-starve). Not "
            "H&S / asia_close / wyckoff."
        ),
        summary=(
            "Fade a failed engulfing continuation: after a "
            "bullish/bearish engulfing bar, price breaks the engulf "
            "extreme then closes back through the engulf open."
        ),
        justification=(
            "A close back through a two-bar body-engulf's open after a "
            "failed continuation through that bar's extreme is not "
            "trading the engulf bar itself, not a rolling N-bar "
            "failed-range, not a UTC-day ORB fail, and not NR7."
        ),
    ),
    SleeveSpec(
        name="wyckoff_spring_reclaim",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Wyckoff spring / failed-breakdown reclaim: identify a recent "
            "range low over lookback prior bars, then a liquidity grab "
            "that trades below that low and CLOSES back above it within "
            "hold_bars. LONG on the reclaim close. SHORT is the upthrust "
            "(trade above a range high, close back below). Quant-locked: "
            "lookback [16, 20], hold_bars [1, 2], no volume. Not "
            "failed_range_break_reversion (119 — close-through then later "
            "fail). Not prior_day_extreme_reject (118). Not "
            "asia_range_london_reject (120). Not orb / nr7 / ib fail "
            "(121–124). Not converging_wedge / engulfing_fail (125–126). "
            "Not equal_high_low_restest_fade. Not swing_failure_reversal. "
            "Not H&S / asia_close / prior_close_magnet_fade. Do not recode "
            "the 118–126 spent families."
        ),
        summary=(
            "Long a Wyckoff spring: trade below a recent lookback range "
            "low then close back above within hold_bars. Short the "
            "upthrust mirror."
        ),
        justification=(
            "A same-bar (or next-bar) wick grab of a rolling lookback "
            "range extreme that closes back through that extreme is not "
            "a close-through failed-range fade, not a prior UTC day H/L "
            "reject, and not a session-box or NR7/ORB/IB fail."
        ),
    ),
    SleeveSpec(
        name="prior_close_magnet_fade",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Fade / mean-reversion stretch away from the prior bar close "
            "(magnet). Distance is (close_t - close_{t-1}) / ATR(atr_n). "
            "LONG when stretched k ATR below the magnet; SHORT when "
            "stretched k ATR above. Quant-locked: atr_n=20 (not "
            "searched), k search [1.2, 1.4], max 2 free params (only k "
            "is free), no volume. Not VWAP / session-VWAP band. Not "
            "session mid. Not week-open reclaim. Not CLV persistence. "
            "Not Wyckoff spring. Not prior_day_extreme_reject / "
            "failed_range_break_reversion / asia_range_london_reject / "
            "orb_fail_reversion / nr7_fail_reversion / ib_fail_reversion "
            "/ converging_wedge_break / engulfing_fail_reversion / "
            "wyckoff_spring_reclaim (118–127). Not H&S / "
            "asia_close_inventory_fade."
        ),
        summary=(
            "Fade a k-ATR stretch away from the prior bar close: LONG "
            "below the magnet, SHORT above."
        ),
        justification=(
            "A close stretched k ATR from the immediately prior close "
            "is not a VWAP/session-mid/week-open magnet, not CLV "
            "persistence, and not a Wyckoff spring or a spent 118–127 "
            "fail/reject family."
        ),
    ),
    SleeveSpec(
        name="classic_floor_pivot_reject",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Classic daily floor-trader pivot reject from the prior UTC "
            "day H,L,C: P=(H+L+C)/3, R1=2P-L, S1=2P-H. SHORT when a 4h "
            "bar tags R1 (within touch_tol_atr) and closes back below P. "
            "LONG when a 4h bar tags S1 (within touch_tol_atr) and "
            "closes back above P. Quant-locked: P/R1/S1 formula FIXED "
            "(not searched), touch_tol_atr search [0.0, 0.10], max 2 "
            "free params (only touch_tol_atr is free), no volume. Not "
            "prior_session_mid_reclaim (107). Not week_open_reclaim. "
            "Not prior_close_magnet_fade (128). Not "
            "prior_day_extreme_reject raw H/L (118). Not "
            "prior_day_pivot_breakout (close-through R1/S1). Not H&S / "
            "asia_close / displacement_gap_follow. Do not recode spent "
            "families 118–128."
        ),
        summary=(
            "Fade a 4h tag of prior-UTC-day floor R1/S1 that closes "
            "back through the pivot P."
        ),
        justification=(
            "A failed 4h tag of yesterday's floor R1/S1 that closes "
            "back through P is not a raw prior-day H/L reject, not a "
            "close-through pivot breakout, not a session-mid or "
            "week-open reclaim, and not a prior-close magnet fade."
        ),
    ),
    SleeveSpec(
        name="failed_break_reclaim",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Multi-bar range/swing probe that closes back inside, then "
            "fade the failed break. Rolling range over lookback prior "
            "bars only. SHORT: highs beyond range_high for "
            "min_probe_bars then close_t back below range_high AND "
            "inside [range_low, range_high]. LONG: lows beyond "
            "range_low then close_t back above range_low AND inside. "
            "Quant-locked: require_close_inside=True, lookback [16, 20], "
            "min_probe_bars [2, 3], ATR period locked 20 if used, no "
            "volume. Not prior_day_extreme_reject (118 PDH). Not "
            "failed_range_break_reversion (119 single-bar "
            "closed-outside). Not ib_fail_reversion (124 IB). Not "
            "wyckoff_spring_reclaim (127). Not "
            "classic_floor_pivot_reject (129 P/R1/S1). Do not recode "
            "spent families 118–129. Do not code displacement_gap_follow."
        ),
        summary=(
            "Fade a multi-bar probe of a prior-bar lookback range that "
            "fails and closes back inside."
        ),
        justification=(
            "A multi-bar wick probe of a frozen lookback range that "
            "re-closes inside is not a single-bar close-through fade, "
            "not a same-bar Wyckoff spring, not a prior UTC day H/L "
            "reject, not a London IB fail, and not a floor P/R1/S1 reject."
        ),
    ),
    SleeveSpec(
        name="expansion_fail_fade",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Fade a failed 4h range-expansion bar when the next bar "
            "closes back inside that expansion bar's high-low on "
            "non-expanding volume. Expansion: true range > "
            "expansion_mult * ATR(20). Fail: next close inside that "
            "bar's H/L. Fade toward the expansion midpoint (SHORT if "
            "expansion was up / close near high side failed; LONG if "
            "expansion was down). Quant-locked: atr_n=20 (not "
            "searched), expansion_mult search [1.5, 2.0], weak-vol "
            "gate volume_t <= prior-20 mean (not searched), max 2 "
            "free params (only expansion_mult is free). Not "
            "range_compression_volume_thrust (102 — successful "
            "squeeze thrust). Not failed_range_break_reversion (119 "
            "— rolling N-bar close-through). Not nr7 / orb / ib "
            "fail. Not failed_break_reclaim (130 — multi-bar "
            "probe). Not displacement_gap_follow (PARKED). Do not "
            "recode spent families 118–130."
        ),
        summary=(
            "Fade a failed 4h ATR-expansion bar when the next bar "
            "closes back inside on weak volume, toward the expansion "
            "midpoint."
        ),
        justification=(
            "A single ATR-expansion bar that fails on the next "
            "close-inside print with locked weak volume is not a "
            "successful squeeze thrust, not a rolling Donchian "
            "close-through fade, not NR7/ORB/IB, and not a multi-bar "
            "probe reclaim."
        ),
    ),
    SleeveSpec(
        name="candle_reject_reversal",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Classic hammer/hanging reject candle as a single family. "
            "LONG = hammer shape (long lower wick, stub upper, "
            "non-doji body, close in upper half). SHORT = hanging-man "
            "shape (same geometry). Geometry: "
            "lower_wick_frac=(min(open,close)-low)/(high-low), "
            "upper_wick_frac=(high-max(open,close))/(high-low), "
            "body_frac=|close-open|/(high-low). Quant-locked: "
            "max_upper_wick_frac=0.15 (not searched), "
            "min_body_frac=0.15 (not a doji; doji_star uses max_body "
            "~0.10), close in upper half locked, no run_bars / no "
            "doji-star confirm. Free search (2 only): "
            "min_lower_wick_frac [0.55, 0.65], max_body_frac "
            "[0.20, 0.35]. Not wick_rejection_reversal (generic long "
            "wick; no stub-upper / non-doji / close-upper-half kit). "
            "Not doji_star_reversal (doji body + run + confirm). Do "
            "not recode spent families 118–131. Displacement parked. "
            "Rectangle / three_black_crows buffer only."
        ),
        summary=(
            "Enter on a classic hammer / hanging-man reject candle "
            "(long lower wick, stub upper, non-doji body, close in "
            "the upper half) as one 4h BOTH family."
        ),
        justification=(
            "A single-bar hammer / hanging-man with locked stub-upper, "
            "non-doji body, and close-in-upper-half is not generic "
            "wick rejection and not a doji-star run-plus-confirm."
        ),
    ),
    SleeveSpec(
        name="bullish_rectangle_fail_reclaim",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Classic flat dual-rail rectangle (multi-touch support + "
            "resistance). LONG = close below the flat lower rail, then "
            "close back inside the box. SHORT = close above the flat "
            "upper rail, then close back inside. Rails are published "
            "swing clusters whose span is <= atr_tol · ATR(20), at "
            "least two touches per rail. Quant-locked: "
            "max_bars_outside=2 (not searched; clearer of job 119), "
            "require_close_inside=True, ATR period 20, "
            "min_touches_per_rail=2, PIVOT_LEFT=3. Free search (2 "
            "only): lookback [24, 32], atr_tol [0.10, 0.15]. Not "
            "failed_range_break_reversion (119 — Donchian "
            "close-through, no dual-rail multi-touch flat rectangle). "
            "Not failed_break_reclaim (130 — Donchian wick-probe, no "
            "flat rectangle rails / multi-touch box). Not a triangle / "
            "wedge / H&S / cup / pennant / three_black_crows / "
            "displacement recode. Do not recode spent families 118–132."
        ),
        summary=(
            "Fade a close back inside a flat dual-rail rectangle after "
            "a close-outside probe of support (LONG) or resistance "
            "(SHORT) as one 4h BOTH family."
        ),
        justification=(
            "A multi-touch flat support-and-resistance box that fades "
            "a close-outside fail-reclaim is not a Donchian "
            "close-through (119), not a Donchian wick-probe reclaim "
            "(130), and not a breakout continuation."
        ),
    ),
    SleeveSpec(
        name="three_black_crows",
        template="novel",
        clock="4h/4h",
        side="SHORT",
        needs_feed=False,
        novel_reason=(
            "Classic three black crows as a SHORT-only family. Three "
            "consecutive bearish candles with descending closes; each "
            "opens within the prior candle's high-low; substantial "
            "bodies; limited upper wicks. SHORT entry after the third "
            "crow confirms. Quant-locked: n_bars=3 (not searched), "
            "open-in-prior-range locked, SHORT only (not BOTH / not "
            "three white soldiers). Free search (2 only): "
            "min_body_frac [0.40, 0.50], max_upper_wick_frac "
            "[0.15, 0.25]. Not three_bar_play (trend + narrow rest + "
            "break of rest leftover). Not engulfing_fail_reversion "
            "(job 126 — two-bar body engulf then fail through engulf "
            "open). Not candle_reject_reversal / consecutive_bar_exhaustion / "
            "open_in_prior_range_fail / rectangle. Do not recode "
            "spent families 118–133. Do not code three white "
            "soldiers / BOTH."
        ),
        summary=(
            "SHORT after a classic three-black-crows print (three "
            "consecutive bearish descending closes, each opening in "
            "the prior range, substantial bodies, limited upper "
            "wicks) as one 4h SHORT family."
        ),
        justification=(
            "A locked three-crow descending-close SHORT with "
            "open-in-prior-range and searched body/upper-wick floors "
            "is not a three-bar-play leftover and not an "
            "engulfing-fail reversion."
        ),
    ),
    SleeveSpec(
        name="bb_medium_bw_upper_reject",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Bollinger medium-bandwidth band reject / fade as one 4h "
            "BOTH family. Same-bar tag-then-close-back inside the "
            "envelope, only when BW is in the locked medium window. "
            "Not a squeeze breakout, not NR7, not an ATR "
            "expansion-fail / blowoff fade. Quant-locked: BB20, "
            "medium BW [0.04, 0.10], SHORT=upper / LONG=lower. Free "
            "search (1 only): k [1.8, 2.0]. Not "
            "squeeze_momentum_break / bb_squeeze_breakout leftover. "
            "Not expansion_fail_fade (131 — single ATR expansion bar "
            "then next-bar fail). Not nr7_fail_reversion. Not "
            "bollinger_mean_reversion (close-through stretch, no "
            "medium-BW reject). Not displacement / H&S / cup / "
            "diamond / pennant / wedge. Do not recode spent "
            "families 118–135."
        ),
        summary=(
            "Fade a same-bar Bollinger tag that closes back inside "
            "the envelope only when bandwidth is in the locked "
            "medium window, as one 4h BOTH family."
        ),
        justification=(
            "A locked medium-BW same-bar band reject (SHORT upper / "
            "LONG lower, search k only) is not a squeeze-release "
            "leftover, not NR7, and not an ATR expansion-fail / "
            "blowoff fade."
        ),
    ),
    SleeveSpec(
        name="atr_open_flush_fade",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Same-bar open flush then fade through the open as one "
            "4h BOTH family. Flush distance is k*ATR(20) from the "
            "signal-bar open (ATR known before the bar so the flush "
            "cannot lift its own threshold). Not a London IB fail, "
            "not a prior-close magnet stretch, not a next-bar "
            "expansion fail, not a UTC-day ORB fail. Quant-locked: "
            "ATR20, same-bar geometry, SHORT=up-flush / "
            "LONG=down-flush. Free search (1 only): k [1.0, 1.5]. "
            "Not ib_fail_reversion (124). Not "
            "prior_close_magnet_fade (128). Not expansion_fail_fade "
            "(131). Not orb_fail_reversion. Not "
            "prior_week_extreme_reject (CEO superseded — do not "
            "implement). Not NR7 / rectangle / three_black / "
            "bb_medium. Do not recode spent families 118–137."
        ),
        summary=(
            "Fade a same-bar open flush that closes back through "
            "the open (SHORT = up-flush fade, LONG = down-flush "
            "fade) as one 4h BOTH family."
        ),
        justification=(
            "A locked ATR20 same-bar open-flush fade (SHORT up / "
            "LONG down, search k only) is not a London IB fail, "
            "not a prior-close magnet stretch, not a next-bar "
            "expansion fail, and not a UTC-day ORB fail."
        ),
    ),
    SleeveSpec(
        name="utc_day_open_flush_fade",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Fade a flush of the frozen UTC day-open (not the "
            "signal bar's own open) as one 4h BOTH family. Same "
            "UTC day only. Not atr_open_flush_fade (138 — RETIRED "
            "same-bar bar-open flush). Not a prior-day / "
            "prior-week extreme reject, not a prior-close magnet "
            "stretch, not a London IB fail, not a UTC-day ORB "
            "fail, not a next-bar expansion fail, not an "
            "inventory-close / NY-close fade. Quant-locked: "
            "ATR20, UTC day-open anchor, SHORT=up-flush / "
            "LONG=down-flush. Free search (1 only): k [1.0, 1.5]. "
            "Do not recode spent family 138. Do not modify "
            "atr_open_flush_fade geometry."
        ),
        summary=(
            "Fade a flush of the UTC day-open that closes back "
            "through that open (SHORT = up-flush fade, LONG = "
            "down-flush fade) as one 4h BOTH family."
        ),
        justification=(
            "A locked ATR20 UTC-day-open flush fade (SHORT up / "
            "LONG down, search k only, same calendar day only) "
            "is not a same-bar bar-open flush, not a prior-day "
            "extreme, not a prior-close magnet, not a London IB "
            "fail, not a UTC-day ORB fail, and not an "
            "inventory-close fade."
        ),
    ),
    SleeveSpec(
        name="three_white_soldiers",
        template="novel",
        clock="4h/4h",
        side="LONG",
        needs_feed=False,
        novel_reason=(
            "Classic three white soldiers as a LONG-only family. "
            "Three consecutive bullish candles with ascending "
            "closes; each opens within the prior candle's high-low; "
            "substantial bodies; limited lower wicks. LONG entry "
            "after the third soldier confirms. Quant-locked: "
            "n_bars=3 (not searched), open-in-prior-range locked, "
            "LONG only (not BOTH / not three black crows). Free "
            "search (2 only): min_body_frac [0.40, 0.50], "
            "max_lower_wick_frac [0.15, 0.25]. Not "
            "three_black_crows (job 134 — SHORT-only descending "
            "bearish crows). Not three_bar_play (trend + narrow "
            "rest + break of rest leftover). Not "
            "engulfing_fail_reversion (job 126 — two-bar body "
            "engulf then fail through engulf open). Not "
            "atr_open_flush_fade (138 — same-bar bar-open flush "
            "fade). Not utc_day_open_flush_fade (139 — UTC "
            "day-open flush fade). Not ny_close_inventory_fade "
            "(banned/parked). Do not recode spent families "
            "118–139. Do not modify three_black_crows geometry."
        ),
        summary=(
            "LONG after a classic three-white-soldiers print "
            "(three consecutive bullish ascending closes, each "
            "opening in the prior range, substantial bodies, "
            "limited lower wicks) as one 4h LONG family."
        ),
        justification=(
            "A locked three-soldier ascending-close LONG with "
            "open-in-prior-range and searched body/lower-wick "
            "floors is not three_black_crows SHORT, not a "
            "three-bar-play leftover, and not an engulfing-fail "
            "or open-flush fade."
        ),
    ),
    SleeveSpec(
        name="sma20_stretch_fade",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "SMA20 stretch fade as one 4h BOTH family. Wick stretch "
            "vs SMA(20) of close by k*ATR(20), then same-bar close "
            "reclaims toward SMA (halfway: 0.5*k*ATR). LONG = "
            "stretch below SMA then reclaim toward SMA. SHORT = "
            "stretch above SMA then fade toward SMA. Quant-locked: "
            "SMA20 + ATR20 (not searched). Free search (1 only): "
            "k [1.5, 2.0]. Not bb_medium_bw_upper_reject (BB tag + "
            "medium-BW close-inside). Not kairi_relative_fade "
            "(percent from SMA, no ATR wick + half-k reclaim). Not "
            "bollinger_mean_reversion (close-through BB). Not "
            "prior_close_magnet_fade (magnet is prior close). Not "
            "atr_open_flush_fade (138 — same-bar bar-open flush). "
            "Not utc_day_open_flush_fade (139 — UTC day-open "
            "flush). Not london_close_inventory_fade (100). Not "
            "three_white_soldiers (140). Not ny_close_inventory_fade "
            "(banned/parked). Do not recode spent families 118–140. "
            "Do not modify atr / three_* geometry."
        ),
        summary=(
            "Fade a same-bar SMA20 wick stretch that reclaims "
            "toward SMA (SHORT = stretch above, LONG = stretch "
            "below) as one 4h BOTH family."
        ),
        justification=(
            "A locked SMA20+ATR20 wick-stretch fade with searched "
            "k and a halfway reclaim toward SMA is not a BB "
            "medium-BW reject, not a bar-open / UTC-day-open "
            "flush, not a London-close inventory fade, and not a "
            "three-white-soldiers leftover."
        ),
    ),
    SleeveSpec(
        name="outside_bar_fail_reversion",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Outside-bar fail reversion as one 4h BOTH family. "
            "Outside bar is t-1 vs t-2 (range containment). "
            "Fail/reversion is bar t closing strictly inside that "
            "outside high-low. Side is the fail close vs the "
            "outside mid — not the outside bar's own close, not a "
            "body-engulf open fail, not a Donchian / IB / NR7 "
            "rail. Quant-locked: ATR20, outside definition, "
            "require_close_inside_outside, mid-side split (not "
            "searched). Free search (1 only): min_outside_atr "
            "[0.8, 1.2]. Not engulfing_fail_reversion (126 — "
            "two-bar body engulf then fail through engulf open). "
            "Not failed_range_break_reversion (119 — rolling "
            "N-bar Donchian). Not failed_break_reclaim (130 — "
            "multi-bar wick probe). Not expansion_fail_fade "
            "(131 — ATR true-range expansion + weak-vol; side "
            "from expansion close vs mid). Not "
            "candle_reject_reversal. Not ib_fail_reversion "
            "(124). Not nr7_fail_reversion (123). Not "
            "atr_open_flush_fade (138). Not "
            "utc_day_open_flush_fade (139). Not "
            "three_white_soldiers (140) / three_black_crows "
            "(134). Not sma20_stretch_fade (141). Not "
            "london_close_inventory_fade (100) / "
            "ny_close_inventory_fade (banned/parked). Not "
            "outside_bar_reversal (fires ON the outside bar). "
            "Do not recode spent families 118–141. Do not "
            "modify sibling geometry."
        ),
        summary=(
            "Fade a failed outside bar when the next close sits "
            "strictly back inside that bar (LONG = close above "
            "mid, SHORT = close below mid) as one 4h BOTH family."
        ),
        justification=(
            "A locked ATR20 outside-bar containment then "
            "next-bar strict close-inside, with searched "
            "min_outside_atr and a mid-side split, is not a "
            "body-engulf open fail, not a Donchian / IB / NR7 "
            "fail, not an ATR expansion-fail, and not a "
            "same-bar outside-bar reversal."
        ),
    ),
    SleeveSpec(
        name="keltner_channel_fade",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Keltner channel fade as one 4h BOTH family. Same-bar "
            "wick tag of EMA(20) of close ± k*ATR(20), then close "
            "rejects back inside that tagged band. ATR known before "
            "the signal bar (atr.shift(1)). Quant-locked: EMA20 of "
            "close (not typical), ATR20, require close-inside, "
            "SHORT=high>upper AND close<upper / LONG=low<lower AND "
            "close>lower (strict tag, not >=). Free search (1 only): "
            "k [1.5, 2.0]. Not keltner_break (close-through "
            "typical-price Keltner / ATR10). Not sma20_stretch_fade "
            "(141 — SMA wick stretch + halfway reclaim). Not "
            "bb_medium_bw_upper_reject (BB + medium-BW). Not "
            "outside_bar_fail_reversion (142). Not "
            "three_black_crows / three_white_soldiers. Not "
            "atr_open_flush_fade / utc_day_open_flush_fade. Not "
            "failed_break_reclaim / expansion_fail_fade / "
            "candle_reject_reversal. Not ib_fail / nr7_fail / "
            "engulfing_fail. Not asia_range_london_reject / "
            "prior_day_extreme_reject. Not displacement_gap_follow "
            "(PARKED). Not range_compression_volume_thrust / "
            "inventory fades. Do not recode spent families 118–142. "
            "Do not modify sibling geometry."
        ),
        summary=(
            "Fade a same-bar Keltner tag that closes back inside "
            "the EMA20 ± k*ATR20 band (SHORT = upper reject, LONG "
            "= lower reject) as one 4h BOTH family."
        ),
        justification=(
            "A locked EMA20-of-close + prior-bar ATR20 band fade "
            "with searched k and a strict tag-then-close-inside is "
            "not a Keltner close-through breakout, not an SMA "
            "stretch fade, and not a Bollinger medium-BW reject."
        ),
    ),
    SleeveSpec(
        name="prior_poc_reclaim_fade",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Prior-day volume-profile POC reclaim fade as one 4h "
            "BOTH family. POC is the volume-profile point of "
            "control from the prior COMPLETED UTC day only "
            "(00:00–24:00 yesterday). Never a forming day. "
            "Histogram: 20 equal-width price bins across that "
            "day's [low, high]; volume spread uniformly across "
            "overlapping bins; POC = highest-volume bin midpoint. "
            "SHORT: high[t] >= POC - touch_tol_atr*ATR AND "
            "close[t] < POC (tag then reclaim toward value below "
            "POC). LONG: low[t] <= POC + touch_tol_atr*ATR AND "
            "close[t] > POC. ATR period locked 20, known before "
            "the signal bar (atr.shift(1)). No k-stretch "
            "geometry. Free search (1 only): touch_tol_atr "
            "[0.0, 0.10]. Not prior_day_extreme_reject (118 — "
            "raw prior UTC day H/L). Not sma20_stretch_fade "
            "(141 — SMA wick stretch + halfway reclaim). Not "
            "keltner_channel_fade (Job 144 0/12 — do not revive). "
            "Not keltner_break. Not bb_medium_bw_upper_reject. "
            "Not outside_bar_fail_reversion (142). Not "
            "asia_range_london_reject. Not inventory fades. Not "
            "hvn_mean_revert / rolling_va_extreme_reject. Not "
            "prior_day_vwap_reject / session_vwap_band_fade. Not "
            "displacement_gap_follow (PARKED). Not "
            "week_open_reclaim / orb_fail_reversion. Do not recode "
            "spent families 118–144. Do not modify sibling "
            "geometry."
        ),
        summary=(
            "Fade a 4h tag of the prior completed UTC-day "
            "volume-profile POC that closes back through POC "
            "(SHORT = tag then close below, LONG = tag then close "
            "above) as one 4h BOTH family."
        ),
        justification=(
            "A locked prior-completed-UTC-day volume-profile POC "
            "tag-then-reclaim, with ATR20 known before the signal "
            "bar and searched touch_tol_atr only, is not a raw "
            "prior-day H/L reject, not an SMA/Keltner stretch "
            "fade, and not a VWAP / rolling value-area sleeve."
        ),
    ),
    SleeveSpec(
        name="hvn_mean_revert",
        template="novel",
        clock="4h/4h",
        side="BOTH",
        needs_feed=False,
        novel_reason=(
            "Prior-day HVN mean-revert as one 4h BOTH family. "
            "Profile is the prior COMPLETED UTC day only "
            "(00:00–24:00 yesterday). Never a forming day. "
            "Same locked histogram as prior_poc_reclaim_fade: "
            "20 equal-width price bins; volume spread uniformly "
            "across overlapping bins; node = bin midpoint. HVN "
            "set = top lookback_nodes volume nodes; signal uses "
            "the nearest HVN to the bar extreme among that set "
            "(SHORT → high[t], LONG → low[t]). SHORT: high[t] "
            ">= HVN - touch_tol_atr*ATR AND close[t] < HVN. "
            "LONG: low[t] <= HVN + touch_tol_atr*ATR AND "
            "close[t] > HVN. ATR period locked 20, known before "
            "the signal bar (atr.shift(1)). Fill t+1 open. Free "
            "search (2 only): lookback_nodes [1, 3], "
            "touch_tol_atr [0.0, 0.15]. Family id "
            "hvn_mean_revert only (not hvn_node_fade). "
            "Withdrawn: leave_atr, bar-lookback [20, 48]. Not "
            "prior_poc_reclaim_fade (Job 145 — single POC). Not "
            "prior_day_vwap_reject / session_vwap_band_fade. Not "
            "session_volume_profile_reversal (skip-list). Not "
            "asia / inventory fades. Not sma20_stretch_fade / "
            "keltner_channel_fade. Not prior_day_extreme_reject "
            "(118 H/L). Not rolling_va_extreme_reject. Do not "
            "recode spent families 118–145. Do not modify "
            "sibling geometry."
        ),
        summary=(
            "Fade a 4h tag of the nearest prior-completed-UTC-day "
            "HVN (top lookback_nodes volume nodes) that closes "
            "back through that HVN (SHORT = tag then close below, "
            "LONG = tag then close above) as one 4h BOTH family."
        ),
        justification=(
            "A locked prior-completed-UTC-day HVN nearest-of-top-N "
            "tag-then-reclaim, with ATR20 known before the signal "
            "bar and searched lookback_nodes + touch_tol_atr only, "
            "is not a single-POC reclaim, not a raw prior-day H/L "
            "reject, not a VWAP / rolling value-area sleeve, and "
            "not a session-volume-profile skip-list family."
        ),
    ),
]


def novel_specs() -> list[SleeveSpec]:
    """Catalog families that need Cursor Python, not JSON templates."""
    return [spec for spec in CANDIDATE_SPECS if not spec.auto_code and not spec.needs_feed]


def ready_novel_specs() -> list[SleeveSpec]:
    """Uncoded novel families that can be approved into a Cursor ticket."""
    from core.strategy.registry import list_strategies

    coded = set(list_strategies())
    return [spec for spec in novel_specs() if spec.name not in coded]


def spec_for_family(name: str) -> SleeveSpec | None:
    slug = (name or "").strip().lower()
    path = SLEEVES_DIR / f"{slug}.json"
    if path.exists():
        try:
            return load_spec(path)
        except Exception:
            logger.exception("Could not read sleeve spec %s", path)
    for spec in CANDIDATE_SPECS:
        if spec.name == slug:
            return spec
    return None


def known_spec_names() -> set[str]:
    names = {spec.name for spec in CANDIDATE_SPECS}
    if SLEEVES_DIR.exists():
        names.update(path.stem for path in SLEEVES_DIR.glob("*.json"))
    return names


def next_template_candidate(*, existing: set[str]) -> SleeveSpec | None:
    """Next auto-codable family that is not already in the catalog or registry."""
    for spec in CANDIDATE_SPECS:
        if not spec.auto_code:
            continue
        if spec.name in existing:
            continue
        return spec
    return None


def next_novel_candidate(*, existing: set[str]) -> SleeveSpec | None:
    for spec in CANDIDATE_SPECS:
        if spec.auto_code:
            continue
        if spec.name in existing:
            continue
        return spec
    return None


def materialize_spec(spec: SleeveSpec) -> Path:
    """Write JSON, register the strategy class. Does not write a .py file."""
    if not spec.auto_code:
        raise ValueError(f"{spec.name} is not auto-codable: {spec.novel_reason or spec.template}")
    SLEEVES_DIR.mkdir(parents=True, exist_ok=True)
    path = SLEEVES_DIR / f"{spec.name}.json"
    path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
    from core.strategy.registry import _REGISTRY, register_strategy

    cls = make_spec_strategy(spec)
    if spec.name not in _REGISTRY:
        register_strategy(cls)
    else:
        load_spec_sleeves()
    logger.info("Materialized sleeve spec %s -> %s", spec.name, path)
    return path


def write_coding_request(spec: SleeveSpec) -> Path:
    """Operator/Cursor brief. Sleeve Engineer does not fill this in with generated Python."""
    CODING_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "family": spec.name,
        "template": spec.template,
        "clock": spec.clock,
        "side": spec.side,
        "needs_feed": spec.needs_feed,
        "needs_new_indicator": spec.needs_new_indicator,
        "novel_reason": spec.novel_reason,
        "summary": spec.summary,
        "justification": spec.justification,
        "written_at": utcnow_iso(),
        "owner": "sleeve_engineer",
        "instruction": (
            "Write core/strategy/{name}.py implementing Strategy. "
            "Use only bars <= t. Fill at t+1 open. Add a lookahead test. "
            "Register via class name. Do not LLM-dump an unverified file."
        ).format(name=spec.name),
    }
    json_path = CODING_REQUESTS_DIR / f"{spec.name}.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path = CODING_REQUESTS_DIR / f"{spec.name}.md"
    md_path.write_text(
        "\n".join(
            [
                f"# Proposal: `{spec.name}`",
                "",
                spec.summary,
                "",
                spec.justification,
                "",
                "## Coding brief (implement this after Inbox approve)",
                "",
                f"- Clock: `{spec.clock}`",
                f"- Side: `{spec.side}`",
                f"- Why this is novel: {spec.novel_reason or 'not an allowed template'}",
                "",
                "## What to write",
                "",
                f"1. `core/strategy/{spec.name}.py` — `Strategy` subclass, `name = \"{spec.name}\"`.",
                "2. Signals may use bars `<= t` only; the engine fills at `t+1` open.",
                "3. Tests: schema, no lookahead (truncation + future shock), at least one entry.",
                "4. Do not copy a rejected family and rename it.",
                f"5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done(\"{spec.name}\")`.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    logger.info("Opened coding request %s", json_path)
    return json_path


def materialize_pending_specs(*, existing: set[str] | None = None) -> dict[str, Any]:
    """Code every pending template candidate; escalate novel ones once."""
    from core.strategy.registry import list_strategies

    coded = set(list_strategies())
    known = set(existing or ()) | coded | known_spec_names()
    materialized: list[str] = []
    novel: list[str] = []
    for spec in CANDIDATE_SPECS:
        if spec.name in coded:
            continue
        if spec.auto_code:
            if spec.name in materialized:
                continue
            materialize_spec(spec)
            materialized.append(spec.name)
            continue
        if spec.name in known and (CODING_REQUESTS_DIR / f"{spec.name}.json").exists():
            novel.append(spec.name)
            continue
        write_coding_request(spec)
        _escalate_novel(spec)
        novel.append(spec.name)
    load_spec_sleeves()
    return {"materialized": materialized, "novel": novel}


def _escalate_novel(spec: SleeveSpec) -> None:
    try:
        from firm import memory

        memory.escalate_once(
            agent="sleeve_engineer",
            title=f"Novel sleeve needs Cursor: {spec.name}",
            detail=(
                f"{spec.name}: {spec.novel_reason or spec.summary} "
                f"Brief: research/coding_requests/{spec.name}.md. "
                "Sleeve Engineer will not write core/strategy Python."
            ),
            severity="warning",
            root_cause=f"novel_sleeve:{spec.name}",
            owner_seat="sleeve_engineer",
        )
    except Exception:
        logger.exception("Could not escalate novel sleeve %s", spec.name)
