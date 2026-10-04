"""Entry-time features and the two frozen rule families.

Every input is a completed 15-minute bar. The bar labelled T covers
[T-15min, T). Nothing after T is read. Range and distance windows are
shifted by one bar so the signal bar does not write its own compression.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from entry_trailing_20261004.budget import FEATURE_COLUMNS


def bars_15m(candles: pd.DataFrame) -> pd.DataFrame:
    """Completed 15-minute bars. Incomplete edge bins are dropped."""
    grouped = candles.resample('15min', closed='left', label='right')
    bars = grouped.agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum',
    })
    counts = grouped['close'].count()
    return bars.loc[counts == 15].copy()


def compute_features(bars: pd.DataFrame) -> pd.DataFrame:
    """Nine frozen features. A row is usable only when every column is finite."""
    close = bars['close']
    high = bars['high']
    low = bars['low']
    prev = close.shift(1)
    log_return = np.log(close).diff()
    rv = log_return.rolling(96, min_periods=96).std(ddof=1)
    true_range = pd.concat(
        [high - low, (high - prev).abs(), (low - prev).abs()], axis=1,
    ).max(axis=1)
    atr_pct = true_range.rolling(14, min_periods=14).mean() / close
    prior_volume = bars['volume'].shift(1).rolling(96, min_periods=96).median()
    rel_volume = bars['volume'] / prior_volume
    prior_high_16 = high.shift(1).rolling(16, min_periods=16).max()
    prior_low_16 = low.shift(1).rolling(16, min_periods=16).min()
    prior_high_96 = high.shift(1).rolling(96, min_periods=96).max()
    prior_low_96 = low.shift(1).rolling(96, min_periods=96).min()
    width_96 = (prior_high_96 - prior_low_96).replace(0, np.nan)
    compression = (prior_high_16 - prior_low_16) / width_96
    ema = close.ewm(span=48, adjust=False, min_periods=48).mean()
    trend = close / ema - 1
    hour = bars.index.hour.to_numpy()
    angle = 2 * np.pi * hour / 24.0
    frame = pd.DataFrame({
        'rv_24h': rv,
        'atr_pct': atr_pct,
        'rel_volume': rel_volume,
        'range_compression': compression,
        'trend': trend,
        'dist_high': close / prior_high_96 - 1,
        'dist_low': close / prior_low_96 - 1,
        'hour_sin': np.sin(angle),
        'hour_cos': np.cos(angle),
    }, index=bars.index)
    return frame[list(FEATURE_COLUMNS)]


def atr_price(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    """Absolute ATR frozen at the signal bar: atr_pct times that bar's close."""
    return features['atr_pct'] * bars['close'].reindex(features.index)


def rule_mask(features: pd.DataFrame, family: str, side: int) -> pd.Series:
    """Boolean signal at T. Missing features do not fire."""
    if family == 'compression' and side == 1:
        mask = (
            (features['range_compression'] <= 0.40)
            & (features['rel_volume'] >= 2.0)
            & (features['trend'] >= 0)
            & (features['dist_high'] > 0)
        )
    elif family == 'compression' and side == -1:
        mask = (
            (features['range_compression'] <= 0.40)
            & (features['rel_volume'] >= 2.0)
            & (features['trend'] <= 0)
            & (features['dist_low'] < 0)
        )
    elif family == 'fade' and side == 1:
        mask = (features['dist_low'] <= -0.01) & (features['rel_volume'] >= 2.0)
    elif family == 'fade' and side == -1:
        mask = (features['dist_high'] >= 0.01) & (features['rel_volume'] >= 2.0)
    else:
        raise ValueError((family, side))
    return mask.fillna(False)
