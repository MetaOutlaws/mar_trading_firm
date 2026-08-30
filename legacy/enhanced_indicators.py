"""
Enhanced Indicator Calculations for Backtesting
Mirrors the live trading strategy from new_multi_indicator.py
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class IndicatorConfig:
    """Configuration matching live trading strategy"""
    def __init__(self):
        # RSI Configuration
        self.RSI_PERIOD = 21
        self.RSI_OVERSOLD = 50
        self.RSI_OVERBOUGHT = 80

        # MACD Configuration
        self.MACD_FAST = 12
        self.MACD_SLOW = 26
        self.MACD_SIGNAL = 9

        # EMA Configuration
        self.EMA_FAST = 5
        self.EMA_SLOW = 10
        self.EMA_50 = 50
        self.EMA_200 = 200

        # Volume Configuration
        self.VOLUME_MA_PERIOD = 20
        self.VOLUME_THRESHOLD = 0.05

        # ADX Configuration
        self.ADX_PERIOD = 14
        self.ADX_THRESHOLD = 20


class EnhancedIndicators:
    """
    Enhanced indicator calculations matching live trading strategy
    """

    def __init__(self, config: IndicatorConfig = None):
        self.config = config or IndicatorConfig()

    def calculate_rsi(self, df: pd.DataFrame) -> Optional[pd.Series]:
        """
        Calculate RSI matching live strategy
        Uses Wilder's smoothing method
        """
        try:
            if 'close' not in df.columns:
                raise ValueError("Close price required for RSI")

            # Calculate price changes
            delta = df['close'].diff()

            # Separate gains and losses
            gains = pd.Series(0.0, index=delta.index)
            losses = pd.Series(0.0, index=delta.index)

            gains[delta > 0] = delta[delta > 0]
            losses[delta < 0] = -delta[delta < 0]

            # Calculate average gain/loss with Wilder's smoothing
            avg_gain = gains.rolling(
                window=self.config.RSI_PERIOD,
                min_periods=self.config.RSI_PERIOD
            ).mean()
            avg_loss = losses.rolling(
                window=self.config.RSI_PERIOD,
                min_periods=self.config.RSI_PERIOD
            ).mean()

            # Apply Wilder's smoothing
            for i in range(self.config.RSI_PERIOD, len(gains)):
                avg_gain.iloc[i] = (
                    avg_gain.iloc[i-1] * (self.config.RSI_PERIOD - 1) + gains.iloc[i]
                ) / self.config.RSI_PERIOD
                avg_loss.iloc[i] = (
                    avg_loss.iloc[i-1] * (self.config.RSI_PERIOD - 1) + losses.iloc[i]
                ) / self.config.RSI_PERIOD

            # Handle division by zero
            avg_loss = avg_loss.replace(0, 0.0001)

            # Calculate RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            return rsi.round(4)

        except Exception as e:
            logger.error(f"Error calculating RSI: {str(e)}")
            return None

    def calculate_macd(self, df: pd.DataFrame) -> Tuple[Optional[pd.Series], Optional[pd.Series], Optional[pd.Series]]:
        """
        Calculate MACD matching live strategy
        Returns: (macd, signal, histogram)
        """
        try:
            if 'close' not in df.columns:
                raise ValueError("Close price required for MACD")

            # Calculate EMAs
            ema_fast = df['close'].ewm(span=self.config.MACD_FAST, adjust=False).mean()
            ema_slow = df['close'].ewm(span=self.config.MACD_SLOW, adjust=False).mean()

            # Calculate MACD line
            macd = ema_fast - ema_slow

            # Calculate signal line
            signal = macd.ewm(span=self.config.MACD_SIGNAL, adjust=False).mean()

            # Calculate histogram
            histogram = macd - signal

            return macd, signal, histogram

        except Exception as e:
            logger.error(f"Error calculating MACD: {str(e)}")
            return None, None, None

    def calculate_emas(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """
        Calculate all EMAs matching live strategy
        """
        try:
            if 'close' not in df.columns:
                raise ValueError("Close price required for EMAs")

            emas = {
                'ema_fast': df['close'].ewm(span=self.config.EMA_FAST, adjust=False).mean(),
                'ema_slow': df['close'].ewm(span=self.config.EMA_SLOW, adjust=False).mean(),
                'ema_50': df['close'].ewm(span=self.config.EMA_50, adjust=False).mean(),
                'ema_200': df['close'].ewm(span=self.config.EMA_200, adjust=False).mean(),
            }

            return emas

        except Exception as e:
            logger.error(f"Error calculating EMAs: {str(e)}")
            return {}

    def calculate_adx(self, df: pd.DataFrame) -> Tuple[Optional[pd.Series], Optional[pd.Series], Optional[pd.Series]]:
        """
        Calculate ADX with DI+ and DI- matching live strategy
        Returns: (adx, plus_di, minus_di)
        """
        try:
            if not all(col in df.columns for col in ['high', 'low', 'close']):
                raise ValueError("High, low, close required for ADX")

            period = self.config.ADX_PERIOD

            # Calculate True Range components
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift(1))
            low_close = abs(df['low'] - df['close'].shift(1))

            # True Range
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

            # Directional Movement
            plus_dm = df['high'].diff()
            minus_dm = -df['low'].diff()

            # Apply directional movement rules
            plus_dm[plus_dm < 0] = 0
            minus_dm[minus_dm < 0] = 0
            plus_dm[(plus_dm < minus_dm)] = 0
            minus_dm[(minus_dm < plus_dm)] = 0

            # Smoothed TR and DM
            atr = tr.rolling(window=period).mean()
            plus_dm_smooth = plus_dm.rolling(window=period).mean()
            minus_dm_smooth = minus_dm.rolling(window=period).mean()

            # Calculate DI+ and DI-
            plus_di = 100 * (plus_dm_smooth / atr)
            minus_di = 100 * (minus_dm_smooth / atr)

            # Calculate DX
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

            # Calculate ADX (smoothed DX)
            adx = dx.rolling(window=period).mean()

            return adx, plus_di, minus_di

        except Exception as e:
            logger.error(f"Error calculating ADX: {str(e)}")
            return None, None, None

    def calculate_volume_ratio(self, df: pd.DataFrame) -> Optional[pd.Series]:
        """
        Calculate volume ratio matching live strategy
        """
        try:
            if 'volume' not in df.columns:
                raise ValueError("Volume required")

            volume_ma = df['volume'].rolling(window=self.config.VOLUME_MA_PERIOD).mean()
            volume_ratio = df['volume'] / volume_ma

            return volume_ratio

        except Exception as e:
            logger.error(f"Error calculating volume ratio: {str(e)}")
            return None


class SignalScoring:
    """
    Signal scoring system matching live trading strategy
    """

    @staticmethod
    def calculate_rsi_score(rsi_value: float, rsi_momentum: float) -> dict:
        """
        Calculate RSI score based on value and momentum
        Matches live strategy scoring
        """
        score_details = {
            'range_score': 0,
            'momentum_score': 0,
            'total_score': 0,
            'components': {}
        }

        # 1. Range Score (0-2 points)
        if 70 <= rsi_value <= 100:
            score_details['range_score'] = 2.0
            score_details['components']['range'] = 'optimal_range'
        elif 60 <= rsi_value < 70:
            score_details['range_score'] = 1.0
            score_details['components']['range'] = 'moderate_range'
        else:
            score_details['range_score'] = 0
            score_details['components']['range'] = 'out_of_range'

        # 2. Momentum Score (0-1 point)
        if rsi_momentum > 0:
            score_details['momentum_score'] = 1.0
            score_details['components']['momentum'] = 'rising'
        else:
            score_details['momentum_score'] = 0
            score_details['components']['momentum'] = 'falling'

        # Calculate total score
        score_details['total_score'] = score_details['range_score'] + score_details['momentum_score']
        score_details['components']['rsi_value'] = rsi_value
        score_details['components']['rsi_momentum'] = rsi_momentum

        return score_details

    @staticmethod
    def is_valid_rsi_setup(score_details: dict) -> Tuple[bool, str]:
        """
        Validate if RSI setup meets minimum criteria
        Matches live strategy validation
        """
        min_total_score = 1.0

        if score_details['total_score'] < min_total_score:
            return False, f"Total score {score_details['total_score']} below minimum {min_total_score}"

        if score_details['range_score'] < 1.0:
            return False, "RSI not in favorable range"

        return True, "Valid RSI setup"

    @staticmethod
    def calculate_adx_score(adx: float, plus_di: float, minus_di: float) -> dict:
        """
        Calculate ADX score with DI+/DI- trend strength filtering
        Matches live strategy scoring

        Score Components (Total 3 points):
        - ADX Strength (0-1 point)
        - Trend Direction (0-1 point)
        - Trend Consistency (0-1 point)
        """
        score_details = {
            'strength_score': 0,
            'direction_score': 0,
            'consistency_score': 0,
            'total_score': 0,
            'components': {
                'adx': float(adx),
                'plus_di': float(plus_di),
                'minus_di': float(minus_di),
                'di_spread': float(abs(plus_di - minus_di))
            }
        }

        # 1. ADX Strength Score (0-1 point)
        if adx >= 40:
            score_details['strength_score'] = 1.0
            score_details['components']['strength'] = 'very_strong'
        elif adx >= 25:
            score_details['strength_score'] = 0.5
            score_details['components']['strength'] = 'strong'
        else:
            score_details['components']['strength'] = 'weak'

        # 2. Trend Direction Score (0-1 point)
        di_diff = plus_di - minus_di
        if di_diff > 0:  # Bullish trend
            if di_diff > 5:  # Strong bullish
                score_details['direction_score'] = 1.0
                score_details['components']['direction'] = 'strong_bullish'
            else:  # Weak bullish
                score_details['direction_score'] = 0.5
                score_details['components']['direction'] = 'weak_bullish'
        else:
            score_details['components']['direction'] = 'bearish'

        # 3. Trend Consistency Score (0-1 point)
        di_spread = abs(plus_di - minus_di)
        if di_spread >= 10:
            score_details['consistency_score'] = 1.0
            score_details['components']['consistency'] = 'high'
        elif di_spread >= 5:
            score_details['consistency_score'] = 0.5
            score_details['components']['consistency'] = 'moderate'
        else:
            score_details['components']['consistency'] = 'low'

        # Calculate total score
        score_details['total_score'] = (
            score_details['strength_score'] +
            score_details['direction_score'] +
            score_details['consistency_score']
        )

        return score_details

    @staticmethod
    def is_valid_adx_setup(score_details: dict) -> Tuple[bool, str]:
        """
        Validate if ADX setup meets minimum criteria
        Matches live strategy validation
        """
        min_total_score = 1.5

        if score_details['total_score'] < min_total_score:
            return False, f"Total score {score_details['total_score']} below minimum {min_total_score}"

        if score_details['direction_score'] == 0:
            return False, "Not in bullish trend"

        if score_details['strength_score'] == 0:
            return False, "Insufficient trend strength"

        return True, "Valid ADX setup"


class EnhancedSignalGenerator:
    """
    Generate trading signals matching live strategy logic
    """

    def __init__(self, config: IndicatorConfig = None):
        self.config = config or IndicatorConfig()
        self.indicators = EnhancedIndicators(self.config)
        self.scoring = SignalScoring()

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals with all indicators and scoring
        Returns DataFrame with signals and all indicator values
        """
        try:
            logger.info(f"Generating enhanced signals for {len(df)} candles")

            # Calculate all indicators
            df['rsi'] = self.indicators.calculate_rsi(df)

            macd, signal, histogram = self.indicators.calculate_macd(df)
            df['macd'] = macd
            df['macd_signal'] = signal
            df['macd_histogram'] = histogram

            adx, plus_di, minus_di = self.indicators.calculate_adx(df)
            df['adx'] = adx
            df['plus_di'] = plus_di
            df['minus_di'] = minus_di

            emas = self.indicators.calculate_emas(df)
            for name, series in emas.items():
                df[name] = series

            df['volume_ratio'] = self.indicators.calculate_volume_ratio(df)

            # Generate signals
            df['signal_type'] = 'hold'
            df['signal_score'] = 0.0

            # Iterate through each row to check entry conditions
            for i in range(self.config.EMA_200, len(df)):
                if self._check_entry_conditions(df, i):
                    df.loc[df.index[i], 'signal_type'] = 'buy'
                    df.loc[df.index[i], 'signal_score'] = self._calculate_signal_score(df, i)

            logger.info(f"Generated {(df['signal_type'] == 'buy').sum()} buy signals")

            return df

        except Exception as e:
            logger.error(f"Error generating signals: {str(e)}")
            return df

    def _check_entry_conditions(self, df: pd.DataFrame, index: int) -> bool:
        """
        Check all entry conditions matching live strategy
        """
        try:
            # Get current and previous values
            current = df.iloc[index]
            prev = df.iloc[index - 1]

            # 1. RSI Scoring
            rsi_momentum = current['rsi'] - prev['rsi']
            rsi_score = self.scoring.calculate_rsi_score(current['rsi'], rsi_momentum)
            is_valid_rsi, _ = self.scoring.is_valid_rsi_setup(rsi_score)

            if not is_valid_rsi:
                return False

            # 2. ADX Scoring
            adx_score = self.scoring.calculate_adx_score(
                current['adx'], current['plus_di'], current['minus_di']
            )
            is_valid_adx, _ = self.scoring.is_valid_adx_setup(adx_score)

            if not is_valid_adx:
                return False

            # 3. MACD Conditions
            macd_crossover = (
                prev['macd'] <= prev['macd_signal'] and
                current['macd'] > current['macd_signal']
            )

            macd_building_momentum = (
                current['macd'] > current['macd_signal'] and
                current['macd'] < 0
            )

            macd_condition = macd_crossover or macd_building_momentum

            if not macd_condition:
                return False

            # 4. Volume Confirmation
            volume_confirmed = (
                current['volume_ratio'] > (1 + self.config.VOLUME_THRESHOLD) or
                current['volume'] > prev['volume']
            )

            if not volume_confirmed:
                return False

            # 5. EMA Trend Alignment (simplified multi-timeframe check)
            ema_aligned = (
                current['ema_fast'] > current['ema_slow'] and
                current['close'] > current['ema_50']
            )

            if not ema_aligned:
                return False

            # All conditions met
            return True

        except Exception as e:
            logger.error(f"Error checking entry conditions at index {index}: {str(e)}")
            return False

    def _calculate_signal_score(self, df: pd.DataFrame, index: int) -> float:
        """
        Calculate overall signal score
        """
        try:
            current = df.iloc[index]
            prev = df.iloc[index - 1]

            # RSI score
            rsi_momentum = current['rsi'] - prev['rsi']
            rsi_score = self.scoring.calculate_rsi_score(current['rsi'], rsi_momentum)

            # ADX score
            adx_score = self.scoring.calculate_adx_score(
                current['adx'], current['plus_di'], current['minus_di']
            )

            # Combined score (max 6: RSI=3, ADX=3)
            total_score = rsi_score['total_score'] + adx_score['total_score']

            return round(total_score, 2)

        except Exception as e:
            logger.error(f"Error calculating signal score: {str(e)}")
            return 0.0


if __name__ == "__main__":
    # Test the enhanced indicators
    print("Enhanced Indicators Module")
    print("Matches live trading strategy from new_multi_indicator.py")
    print("\nIndicator Configuration:")
    config = IndicatorConfig()
    print(f"  RSI Period: {config.RSI_PERIOD}")
    print(f"  MACD: {config.MACD_FAST}/{config.MACD_SLOW}/{config.MACD_SIGNAL}")
    print(f"  ADX Period: {config.ADX_PERIOD}")
    print(f"  EMAs: {config.EMA_FAST}, {config.EMA_SLOW}, {config.EMA_50}, {config.EMA_200}")
