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
