"""Owner-approved PAPER combination with a cap only below ER24 0.30.

ER24 excludes the signal hour. The extension cap is one prior ATR beyond the
prior 20-bar boundary. These constants are frozen; no year-dependent switch.
"""
import numpy as np
import pandas as pd

from core.strategy.hourly_compression_btc_connors_v1 import HourlyCompressionBtcConnorsV1Strategy


def prior_efficiency24(closes):
    net = (closes.shift(1) - closes.shift(25)).abs()
    path = closes.diff().abs().shift(1).rolling(24, min_periods=24).sum()
    return (net / path.replace(0, np.nan)).mask(path == 0, 0.)


def conditional_cap_pass(efficiency, extension):
    valid = np.isfinite(efficiency) & np.isfinite(extension)
    return valid & ((efficiency >= .30) | (extension <= 1.0))


class HourlyCompressionBtcConnorsLoweffV1Strategy(HourlyCompressionBtcConnorsV1Strategy):
    name = 'hourly_compression_btc_connors_loweff_v1'

    def generate_signals(self, candles):
        out = super().generate_signals(candles)
        er = prior_efficiency24(candles.close)
        if self.params.side.sign == 1:
            boundary = candles.high.shift(1).rolling(20).max()
        else:
            boundary = candles.low.shift(1).rolling(20).min()
        extension = self.params.side.sign * (candles.close - boundary) / out.prior_atr.replace(0, np.nan)
        passes = conditional_cap_pass(er, extension)
        if len(candles) >= self.min_bars and not (np.isfinite(er.iloc[-1]) and np.isfinite(extension.iloc[-1])):
            raise ValueError('Missing finite prior efficiency/extension context')
        blocked = (out.signal != 0) & ~passes
        blank = self.empty_signals(candles)
        for col in ['signal', 'side', 'score', 'reason']:
            out.loc[blocked, col] = blank.loc[blocked, col]
        out['efficiency24_before_signal'] = er
        out['directional'] = er >= .30
        out['entry_boundary'] = boundary
        out['extension_atr'] = extension
        out['passes_loweff_cap'] = passes
        out.loc[out.signal != 0, 'reason'] = 'hourly compression + CRSI + BTC24; extension <=1 ATR only when prior ER24 <0.30'
        return out
