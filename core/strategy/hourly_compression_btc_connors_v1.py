"""Approved BTC direction + own-token Connors hourly compression; paper only."""
import numpy as np
import pandas as pd
from core.strategy.hourly_compression_connors_v1 import HourlyCompressionConnorsV1Strategy


class HourlyCompressionBtcConnorsV1Strategy(HourlyCompressionConnorsV1Strategy):
    name = 'hourly_compression_btc_connors_v1'
    requires_btc_confirmation = True

    def prepare_market_context(self, symbol, candles, btc_candles):
        """Bind exact closed-hour BTC observations; no network calls or filling."""
        if symbol not in self.symbols:
            raise ValueError('BTC/ETH/SOL approval only')
        self.validate_candles(candles)
        source = candles if symbol == 'BTCUSDT' else btc_candles
        if source is None or len(source) < 25:
            raise ValueError('BTC confirmation needs 25 completed hourly closes')
        self.validate_candles(source)
        if not source.index.is_unique or not (source.index.to_series().diff().iloc[1:] == pd.Timedelta(hours=1)).all():
            raise ValueError('BTC context must have unique contiguous hourly timestamps')
        if not np.isfinite(source.close).all() or not (source.close > 0).all():
            raise ValueError('BTC closes must be finite and positive')
        btc = pd.DataFrame({'btc_close': source.close, 'btc_close_24h_ago': source.close.shift(24)}, index=source.index)
        btc['btc24'] = btc.btc_close / btc.btc_close_24h_ago - 1
        # Exact reindex; a later BTC candle cannot fill a missing matching hour.
        aligned = btc.reindex(candles.index)
        if aligned.iloc[-1].isna().any():
            raise ValueError('Missing exact BTC24 context for latest token hour')
        out = candles.copy()
        for col in aligned: out[col] = aligned[col]
        out.attrs['btc_confirmation_symbol'] = symbol
        return out

    def generate_signals(self, candles):
        symbol = candles.attrs.get('btc_confirmation_symbol')
        if symbol not in self.symbols or not {'btc_close', 'btc_close_24h_ago', 'btc24'}.issubset(candles.columns):
            raise ValueError('Explicit aligned BTC market context required')
        out = super().generate_signals(candles)
        r = candles.btc24.to_numpy(float)
        # BTC's existing own-token predicate remains unchanged, including zero.
        passes = np.ones(len(r), dtype=bool) if symbol == 'BTCUSDT' else np.isfinite(r) & (self.params.side.sign*r > 0)
        blocked = (out.signal != 0) & ~passes
        blank = self.empty_signals(candles)
        for col in ['signal', 'side', 'score', 'reason']:
            out.loc[blocked, col] = blank.loc[blocked, col]
        for col in ['btc_close', 'btc_close_24h_ago', 'btc24']: out[col] = candles[col]
        out['passes_btc'] = passes
        out.loc[out.signal != 0, 'reason'] = 'hourly compression + CRSI(3,2,100) + BTC24 direction (alts only)'
        return out

    def latest_signal(self, symbol, candles):
        if candles.attrs.get('btc_confirmation_symbol') != symbol:
            raise ValueError('BTC context symbol does not match requested token')
        return super().latest_signal(symbol, candles)
