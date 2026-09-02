"""Execute a JSON sleeve spec using only the shared indicator library.

No freeform Python. Channel levels use the prior completed bar (`shift(1)`)
so a breakout is not measured against a high that includes the signal bar.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from config.settings import PROJECT_ROOT
from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams
from core.strategy.sleeve_spec import SleeveSpec

SLEEVES_DIR = PROJECT_ROOT / "config" / "sleeves"


@dataclass(frozen=True)
class SpecSleeveParams(StrategyParams):
    """Numeric knobs every template may read. Unused fields stay at defaults."""

    side: SignalSide = SignalSide.LONG
    ema_period: int = 20
    ema_fast: int = 12
    ema_slow: int = 26
    atr_period: int = 14
    atr_k: float = 2.0
    lookback: int = 20
    bb_period: int = 20
    band_k: float = 2.0
    adx_period: int = 14
    min_adx: float = 20.0
    max_adx: float = 20.0
    rsi_period: int = 14
    rsi_os: float = 30.0
    rsi_ob: float = 70.0
    volume_period: int = 20
    volume_spike: float = 1.8
    squeeze_lookback: int = 20
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class SpecSleeveStrategy(Strategy):
    """Generic runner. Subclasses set `name` and `sleeve_spec`."""

    name = "unnamed"
    sleeve_spec: SleeveSpec | None = None

    def __init__(self, params: SpecSleeveParams | None = None) -> None:
        spec = self.sleeve_spec
        merged = SpecSleeveParams()
        if spec and spec.defaults:
            allowed = {f.name for f in SpecSleeveParams.__dataclass_fields__.values()}
            overrides = {k: v for k, v in spec.defaults.items() if k in allowed}
            if overrides:
                merged = SpecSleeveParams(**{**merged.to_dict(), **overrides})
        super().__init__(params or merged)
        self.params: SpecSleeveParams = self.params  # type: ignore[assignment]
        p = self.params
        self.min_bars = max(
            p.ema_slow + 10,
            p.atr_period + 40,
            p.adx_period + 40,
            p.bb_period + 5,
            p.lookback + 5,
            p.squeeze_lookback + 5,
            80,
        )

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        spec = self.sleeve_spec
        signals = self.empty_signals(candles)
        if spec is None or len(candles) < self.min_bars:
            signals["reason"] = "insufficient history" if spec else "missing spec"
            return signals

        if spec.template == "channel_break":
            entry, extras = self._channel_break(candles)
        elif spec.template == "fade_stretch":
            entry, extras = self._fade_stretch(candles)
        elif spec.template == "pullback_trend":
            entry, extras = self._pullback_trend(candles)
        else:
            signals["reason"] = f"template {spec.template} is not auto-coded"
            return signals

        for column, series in extras.items():
            signals[column] = series

        long = self.params.side is SignalSide.LONG
        signal_value = 1 if long else -1
        side_value = SignalSide.LONG.value if long else SignalSide.SHORT.value
        mask = entry.fillna(False).astype(bool)
        mask.iloc[: self.min_bars] = False
        signals.loc[mask, "signal"] = signal_value
        signals.loc[mask, "side"] = side_value
        signals.loc[mask, "score"] = 1.0
        signals["reason"] = ""
        signals.loc[mask, "reason"] = f"{spec.name} {side_value}"
        return signals

    def _channel_break(self, candles: pd.DataFrame) -> tuple[pd.Series, dict[str, pd.Series]]:
        spec = self.sleeve_spec
        params = self.params
        high, low, close = candles["high"], candles["low"], candles["close"]
        upper, lower, extras = self._channel_levels(candles)
        adx_value, plus_di, minus_di = ind.adx(high, low, close, params.adx_period)
        extras.update({"adx": adx_value, "plus_di": plus_di, "minus_di": minus_di})
        adx_ok = True if params.min_adx <= 0 else adx_value >= params.min_adx
        regime = adx_ok
        if spec and spec.squeeze:
            squeezed, width = self._bb_squeeze(close)
            extras["bb_width"] = width
            extras["squeeze"] = squeezed.astype(float)
            regime = regime & squeezed
        if spec and spec.volume_filter:
            vr = ind.volume_ratio(candles["volume"], params.volume_period)
            extras["volume_ratio"] = vr
            regime = regime & (vr >= params.volume_spike)
        if params.side is SignalSide.LONG:
            entry = (close > upper) & regime
        else:
            entry = (close < lower) & regime
        extras["upper"] = upper
        extras["lower"] = lower
        return entry, extras

    def _fade_stretch(self, candles: pd.DataFrame) -> tuple[pd.Series, dict[str, pd.Series]]:
        spec = self.sleeve_spec
        params = self.params
        high, low, close = candles["high"], candles["low"], candles["close"]
        adx_value, plus_di, minus_di = ind.adx(high, low, close, params.adx_period)
        extras: dict[str, pd.Series] = {
            "adx": adx_value,
            "plus_di": plus_di,
            "minus_di": minus_di,
        }
        chop_ok = True if params.max_adx <= 0 else adx_value <= params.max_adx
        stretch = spec.stretch if spec else "rsi"
        if stretch == "rsi":
            rsi_value = ind.rsi(close, params.rsi_period)
            extras["rsi"] = rsi_value
            if params.side is SignalSide.LONG:
                extreme = rsi_value <= params.rsi_os
            else:
                extreme = rsi_value >= params.rsi_ob
        else:
            upper, lower, channel_extras = self._channel_levels(candles)
            extras.update(channel_extras)
            extras["upper"] = upper
            extras["lower"] = lower
            if params.side is SignalSide.LONG:
                extreme = close <= lower
            else:
                extreme = close >= upper
        if spec and spec.volume_filter:
            vr = ind.volume_ratio(candles["volume"], params.volume_period)
            extras["volume_ratio"] = vr
            chop_ok = chop_ok & (vr >= params.volume_spike)
        return extreme & chop_ok, extras

    def _pullback_trend(self, candles: pd.DataFrame) -> tuple[pd.Series, dict[str, pd.Series]]:
        spec = self.sleeve_spec
        params = self.params
        high, low, close = candles["high"], candles["low"], candles["close"]
        ema_fast = ind.ema(close, params.ema_fast)
        ema_slow = ind.ema(close, params.ema_slow)
        adx_value, plus_di, minus_di = ind.adx(high, low, close, params.adx_period)
        rsi_value = ind.rsi(close, params.rsi_period)
        extras: dict[str, pd.Series] = {
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "adx": adx_value,
            "plus_di": plus_di,
            "minus_di": minus_di,
            "rsi": rsi_value,
        }
        adx_ok = True if params.min_adx <= 0 else adx_value >= params.min_adx
        trend = spec.trend if spec else "ema"
        if trend == "macd":
            macd_line, signal_line, hist = ind.macd(
                close, params.macd_fast, params.macd_slow, params.macd_signal
            )
            extras.update({"macd": macd_line, "macd_signal": signal_line, "macd_hist": hist})
            bull = macd_line > signal_line
            bear = macd_line < signal_line
        elif trend == "adx":
            bull = plus_di > minus_di
            bear = minus_di > plus_di
        else:
            bull = ema_fast > ema_slow
            bear = ema_fast < ema_slow
        # Pullback: RSI in the dip/rally zone, close still on the trend side of fast EMA.
        if params.side is SignalSide.LONG:
            pullback = (rsi_value >= params.rsi_os) & (rsi_value <= 50.0) & (close >= ema_fast)
            entry = bull & adx_ok & pullback
        else:
            pullback = (rsi_value <= params.rsi_ob) & (rsi_value >= 50.0) & (close <= ema_fast)
            entry = bear & adx_ok & pullback
        return entry, extras

    def _channel_levels(
        self, candles: pd.DataFrame
    ) -> tuple[pd.Series, pd.Series, dict[str, pd.Series]]:
        spec = self.sleeve_spec
        params = self.params
        high, low, close = candles["high"], candles["low"], candles["close"]
        kind = spec.channel if spec else "atr"
        extras: dict[str, pd.Series] = {}
        if kind == "donchian":
            upper = high.shift(1).rolling(params.lookback, min_periods=params.lookback).max()
            lower = low.shift(1).rolling(params.lookback, min_periods=params.lookback).min()
        elif kind == "bollinger":
            mid, raw_upper, raw_lower = ind.bollinger_bands(close, params.bb_period, params.band_k)
            extras["bb_mid"] = mid
            upper = raw_upper.shift(1)
            lower = raw_lower.shift(1)
        else:
            mid = ind.ema(close, params.ema_period)
            atr_value = ind.atr(high, low, close, params.atr_period)
            extras["mid"] = mid
            extras["atr"] = atr_value
            upper = mid.shift(1) + params.atr_k * atr_value.shift(1)
            lower = mid.shift(1) - params.atr_k * atr_value.shift(1)
        return upper, lower, extras

    def _bb_squeeze(self, close: pd.Series) -> tuple[pd.Series, pd.Series]:
        params = self.params
        mid, upper, lower = ind.bollinger_bands(close, params.bb_period, params.band_k)
        width = (upper - lower) / mid.replace(0, pd.NA)
        prior = width.shift(1)
        floor = prior.rolling(params.squeeze_lookback, min_periods=params.squeeze_lookback).min()
        squeezed = prior <= floor
        return squeezed.fillna(False), width.fillna(0.0)


def load_spec(path: Path) -> SleeveSpec:
    return SleeveSpec.model_validate_json(path.read_text(encoding="utf-8"))


def make_spec_strategy(spec: SleeveSpec) -> type[SpecSleeveStrategy]:
    """Build a named Strategy subclass so the registry and walk-forward can find it."""

    class Generated(SpecSleeveStrategy):
        name = spec.name
        sleeve_spec = spec

    Generated.__name__ = "".join(part.title() for part in spec.name.split("_")) + "Strategy"
    Generated.__qualname__ = Generated.__name__
    Generated.__module__ = "core.strategy.spec_sleeve"
    return Generated


def load_spec_sleeves() -> list[str]:
    """Register every auto-coded JSON spec. Novel specs are skipped on purpose."""
    from core.strategy.registry import register_strategy

    loaded: list[str] = []
    if not SLEEVES_DIR.exists():
        return loaded
    for path in sorted(SLEEVES_DIR.glob("*.json")):
        try:
            spec = load_spec(path)
        except Exception:
            continue
        if not spec.auto_code:
            continue
        cls = make_spec_strategy(spec)
        from core.strategy.registry import _REGISTRY

        if spec.name in _REGISTRY and _REGISTRY[spec.name] is not cls:
            continue
        if spec.name not in _REGISTRY:
            register_strategy(cls)
        loaded.append(spec.name)
    return loaded


def spec_kit(name: str, side: SignalSide):
    """Walk-forward factory for a JSON family, or None if it is not auto-coded."""
    from core.strategy.registry import get_strategy

    path = SLEEVES_DIR / f"{name}.json"
    if not path.exists():
        return None
    spec = load_spec(path)
    if not spec.auto_code:
        return None
    cls = get_strategy(name)
    defaults = dict(spec.defaults)
    defaults["side"] = side

    def factory(params: StrategyParams) -> SpecSleeveStrategy:
        return cls(params)  # type: ignore[arg-type]

    allowed = {f.name for f in SpecSleeveParams.__dataclass_fields__.values()}
    clean = {k: v for k, v in defaults.items() if k in allowed}
    base = SpecSleeveParams(**clean)
    return factory, base, spec.search_space()
