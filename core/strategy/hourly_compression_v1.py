"""Owner-approved paper pilot: frozen hourly compression entry, 7 Oct 2026.

This is not range_compression_volume_thrust. The entry predicate matches the
BTC/ETH/SOL hourly research; production execution remains exec-f04-v1 (see the
deployment note for differences from the minute-path research simulator).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class HourlyCompressionV1Params(StrategyParams):
    side: SignalSide = SignalSide.LONG
    take_profit_pct: float = 0.025
    stop_loss_pct: float = 0.02
    max_holding_bars: int = 0


class HourlyCompressionV1Strategy(Strategy):
    name = "hourly_compression_v1"
    # More than the frozen study's 200 completed 4h-bar feature warmup.
    # fetch_latest requests another 50 bars, reducing ATR seed dependence.
    min_bars = 800
    symbols = frozenset({"BTCUSDT", "ETHUSDT", "SOLUSDT"})

    def __init__(self, params=None):
        super().__init__(params or HourlyCompressionV1Params())
        if (self.params.stop_loss_pct, self.params.take_profit_pct,
                self.params.max_holding_bars) != (0.02, 0.025, 0):
            raise ValueError("v1 paper approval is fixed at SL 2%, TP 2.5%, no timeout")
        if self.params.side not in (SignalSide.LONG, SignalSide.SHORT):
            raise ValueError("v1 requires LONG or SHORT")

    def generate_signals(self, candles):
        self.validate_candles(candles)
        if not candles.index.is_unique:
            raise ValueError("duplicate candles")
        if len(candles) > 1 and not (candles.index.to_series().diff().iloc[1:] == pd.Timedelta(hours=1)).all():
            raise ValueError("v1 requires contiguous hourly candles")
        values = candles[["open", "high", "low", "close", "volume"]]
        if not np.isfinite(values.to_numpy()).all() or (values.iloc[:, :4] <= 0).any().any() or (values.volume < 0).any():
            raise ValueError("invalid OHLCV")
        out = self.empty_signals(candles)
        prev = candles.close.shift(1)
        tr = pd.concat([candles.high-candles.low, (candles.high-prev).abs(),
                        (candles.low-prev).abs()], axis=1).max(axis=1)
        # Match the frozen research's arithmetic and Wilder seed exactly.
        x = tr.to_numpy(float)
        atr = np.full(len(x), np.nan)
        if len(x) >= 14:
            atr[13] = x[:14].mean()
            for i in range(14, len(x)):
                atr[i] = (13*atr[i-1]+x[i])/14
        prior_atr = pd.Series(atr, index=candles.index).shift(1)
        compression = tr.shift(1).rolling(6).mean() / tr.shift(1).rolling(60).median().replace(0, np.nan)
        volume_ratio = candles.volume / candles.volume.shift(1).rolling(20).median().replace(0, np.nan)
        location = (candles.close-candles.low)/(candles.high-candles.low).replace(0, np.nan)
        r24 = candles.close.pct_change(24, fill_method=None)
        side = self.params.side.sign
        mask = ((compression <= .7) & (tr >= 1.5*prior_atr) & (volume_ratio >= 1.5)
                & (side*(candles.close-candles.open) > 0) & (side*r24 >= 0))
        if side == 1:
            mask &= (candles.close > candles.high.shift(1).rolling(20).max()) & (location >= .75)
        else:
            mask &= (candles.close < candles.low.shift(1).rolling(20).min()) & (location <= .25)
        mask.iloc[:self.min_bars-1] = False
        out.loc[mask, "signal"] = side
        out.loc[mask, "side"] = self.params.side.value
        out.loc[mask, "score"] = 1.0
        out.loc[mask, "reason"] = "hourly compression v1: 6/60 TR squeeze, volume expansion, 20-bar break, 24h direction"
        for name, value in {"compression": compression, "volume_ratio": volume_ratio,
                            "close_location": location, "prior_atr": prior_atr, "r24": r24}.items():
            out[name] = value
        return out

    def latest_signal(self, symbol, candles):
        # Defense in depth: this owner approval grants paper use only.
        from config.settings import TradingMode, get_settings
        if get_settings().trading_mode is not TradingMode.PAPER:
            raise RuntimeError("hourly_compression_v1 is paper-only")
        if symbol not in self.symbols:
            raise ValueError("hourly_compression_v1 is approved only for BTC/ETH/SOL")
        return super().latest_signal(symbol, candles)
