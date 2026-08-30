"""
LONG Strategy Configuration - Scalable Asset Management
Easily add hundreds of assets with asset-specific parameters
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class LongStrategyConfig:
    """Configuration for LONG strategy per asset"""

    # Asset identification
    symbol: str

    # Timeframe (15min default)
    timeframe: str

    # Entry conditions
    rsi_min: float  # Minimum RSI for oversold signal
    rsi_max: float  # Maximum RSI for oversold signal
    volume_threshold: float  # Minimum volume ratio

    # Trend filter (always Golden Cross for longs)
    trend_filter: str = 'golden_cross'  # EMA50 > EMA200

    # Risk management
    take_profit_pct: float = 0.05  # 5% TP
    stop_loss_pct: float = 0.05  # 5% SL

    # Performance tracking
    expected_win_rate: Optional[float] = None
    expected_trades_per_quarter: Optional[int] = None
    backtest_return_q1: Optional[float] = None
    backtest_return_q4: Optional[float] = None
    profit_factor: Optional[float] = None

    # Status
    enabled: bool = True


class LongStrategyManager:
    """
    Manages LONG strategy configurations for all assets
    Scalable to hundreds of assets
    """

    def __init__(self):
        self.configs: Dict[str, LongStrategyConfig] = {}
        self._load_default_configs()

    def _load_default_configs(self):
        """Load proven LONG configurations from backtesting"""

        # ═══════════════════════════════════════════════════════════════════════════
        # TIER 1: EXCELLENT PERFORMERS (80%+ Win Rate or 3.0+ PF) - ENABLED
        # Comprehensive optimization across 58 assets (2025-10-27)
        # Golden Cross + RSI Oversold + Volume strategy
        # ═══════════════════════════════════════════════════════════════════════════

        # BTC - 90.0% WR, 4.94 PF (BEST WIN RATE)
        self.add_config(LongStrategyConfig(
            symbol='BTCUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.2,
            expected_win_rate=90.0,
            expected_trades_per_quarter=11,
            profit_factor=4.94,
            backtest_return_q1=2.53,
            backtest_return_q4=3.10,
            enabled=True  # Tier 1 - Best WR, 100% in Q1!
        ))

        # ETH - 85.4% WR, 11.54 PF (BEST PROFIT FACTOR)
        self.add_config(LongStrategyConfig(
            symbol='ETHUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.1,
            expected_win_rate=85.4,
            expected_trades_per_quarter=17,
            profit_factor=11.54,
            backtest_return_q1=3.80,
            backtest_return_q4=4.67,
            enabled=True  # Tier 1 - Exceptional PF
        ))

        # ALGO - 83.9% WR, 5.47 PF
        self.add_config(LongStrategyConfig(
            symbol='ALGOUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.1,
            expected_win_rate=83.9,
            expected_trades_per_quarter=12,
            profit_factor=5.47,
            backtest_return_q1=3.75,
            backtest_return_q4=2.95,
            enabled=True  # Tier 1 - Consistent performer
        ))

        # APT - 81.2% WR, 4.01 PF
        self.add_config(LongStrategyConfig(
            symbol='APTUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.3,
            expected_win_rate=81.2,
            expected_trades_per_quarter=6,
            profit_factor=4.01,
            backtest_return_q1=0.79,
            backtest_return_q4=3.05,
            enabled=True  # Tier 1 - Strong Q4 performance
        ))

        # FLOKI - 79.8% WR, 4.65 PF
        self.add_config(LongStrategyConfig(
            symbol='1000FLOKIUSDT',
            timeframe='15min',
            rsi_min=35,
            rsi_max=45,
            volume_threshold=1.5,
            expected_win_rate=79.8,
            expected_trades_per_quarter=16.5,
            profit_factor=4.65,
            backtest_return_q1=4.73,
            backtest_return_q4=5.09,
            enabled=True  # Tier 1 - Good volume
        ))

        # AVAX - 78.6% WR, 4.11 PF
        self.add_config(LongStrategyConfig(
            symbol='AVAXUSDT',
            timeframe='15min',
            rsi_min=35,
            rsi_max=45,
            volume_threshold=1.5,
            expected_win_rate=78.6,
            expected_trades_per_quarter=17.5,
            profit_factor=4.11,
            backtest_return_q1=1.60,
            backtest_return_q4=5.43,
            enabled=True  # Tier 1 - High volume
        ))

        # TRX - 78.0% WR, 4.07 PF
        self.add_config(LongStrategyConfig(
            symbol='TRXUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.0,
            expected_win_rate=78.0,
            expected_trades_per_quarter=10,
            profit_factor=4.07,
            backtest_return_q1=1.45,
            backtest_return_q4=1.45,
            enabled=True  # Tier 1 - Consistent
        ))

        # IMX - 77.8% WR, 29.05 PF (EXCEPTIONAL PF)
        self.add_config(LongStrategyConfig(
            symbol='IMXUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.2,
            expected_win_rate=77.8,
            expected_trades_per_quarter=9,
            profit_factor=29.05,
            backtest_return_q1=3.74,
            backtest_return_q4=1.47,
            enabled=True  # Tier 1 - Exceptional PF
        ))

        # HBAR - 77.5% WR, 8.74 PF
        self.add_config(LongStrategyConfig(
            symbol='HBARUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.0,
            expected_win_rate=77.5,
            expected_trades_per_quarter=15.5,
            profit_factor=8.74,
            backtest_return_q1=4.08,
            backtest_return_q4=5.83,
            enabled=True  # Tier 1 - High PF
        ))

        # DOT - 76.9% WR, 9.45 PF (VALIDATED - Already in live bot)
        self.add_config(LongStrategyConfig(
            symbol='DOTUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.2,
            expected_win_rate=76.9,
            expected_trades_per_quarter=13,
            profit_factor=9.45,
            backtest_return_q1=1.44,
            backtest_return_q4=7.20,
            enabled=True  # Tier 1 - 93.8% WR in Q4!
        ))

        # OP - 76.4% WR, 6.78 PF
        self.add_config(LongStrategyConfig(
            symbol='OPUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.0,
            expected_win_rate=76.4,
            expected_trades_per_quarter=15,
            profit_factor=6.78,
            backtest_return_q1=4.38,
            backtest_return_q4=4.38,
            enabled=True  # Tier 1 - 94.4% WR in Q4
        ))

        # NEAR - 75.0% WR, 7.70 PF
        self.add_config(LongStrategyConfig(
            symbol='NEARUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.3,
            expected_win_rate=75.0,
            expected_trades_per_quarter=7.5,
            profit_factor=7.70,
            backtest_return_q1=2.59,
            backtest_return_q4=2.59,
            enabled=True  # Tier 1 - 90% WR in Q4
        ))

        # TIA - 75.0% WR, 3.54 PF
        self.add_config(LongStrategyConfig(
            symbol='TIAUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.2,
            expected_win_rate=75.0,
            expected_trades_per_quarter=6,
            profit_factor=3.54,
            backtest_return_q1=1.19,
            backtest_return_q4=1.19,
            enabled=True  # Tier 1 - Solid performer
        ))

        # SEI - 73.9% WR, 4.93 PF
        self.add_config(LongStrategyConfig(
            symbol='SEIUSDT',
            timeframe='15min',
            rsi_min=35,
            rsi_max=45,
            volume_threshold=1.3,
            expected_win_rate=73.9,
            expected_trades_per_quarter=24,
            profit_factor=4.93,
            backtest_return_q1=5.89,
            backtest_return_q4=5.89,
            enabled=True  # Tier 1 - High volume
        ))

        # GRT - 73.9% WR, 3.02 PF
        self.add_config(LongStrategyConfig(
            symbol='GRTUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.2,
            expected_win_rate=73.9,
            expected_trades_per_quarter=9.5,
            profit_factor=3.02,
            backtest_return_q1=2.27,
            backtest_return_q4=2.20,
            enabled=True  # Tier 1 - Consistent
        ))

        # UNI - 72.1% WR, 3.57 PF (HIGH VOLUME)
        self.add_config(LongStrategyConfig(
            symbol='UNIUSDT',
            timeframe='15min',
            rsi_min=35,
            rsi_max=45,
            volume_threshold=1.2,
            expected_win_rate=72.1,
            expected_trades_per_quarter=35,
            profit_factor=3.57,
            backtest_return_q1=7.52,
            backtest_return_q4=7.52,
            enabled=True  # Tier 1 - Most trades
        ))

        # TON - 70.6% WR, 3.34 PF
        self.add_config(LongStrategyConfig(
            symbol='TONUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.3,
            expected_win_rate=70.6,
            expected_trades_per_quarter=8,
            profit_factor=3.34,
            backtest_return_q1=1.18,
            backtest_return_q4=1.18,
            enabled=True  # Tier 1 - Threshold
        ))

        # RUNE - 70.1% WR, 3.13 PF
        self.add_config(LongStrategyConfig(
            symbol='RUNEUSDT',
            timeframe='15min',
            rsi_min=35,
            rsi_max=45,
            volume_threshold=1.2,
            expected_win_rate=70.1,
            expected_trades_per_quarter=27.5,
            profit_factor=3.13,
            backtest_return_q1=3.01,
            backtest_return_q4=3.01,
            enabled=True  # Tier 1 - Good volume
        ))

        # BONK - 69.4% WR, 3.25 PF
        self.add_config(LongStrategyConfig(
            symbol='BONKUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.2,
            expected_win_rate=69.4,
            expected_trades_per_quarter=7.5,
            profit_factor=3.25,
            backtest_return_q1=1.56,
            backtest_return_q4=0.91,
            enabled=False  # Tier 1 but borderline - validate first
        ))

        # ARB - 68.8% WR, 4.19 PF
        self.add_config(LongStrategyConfig(
            symbol='ARBUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.3,
            expected_win_rate=68.8,
            expected_trades_per_quarter=6,
            profit_factor=4.19,
            backtest_return_q1=0.15,
            backtest_return_q4=3.20,
            enabled=False  # Tier 1 but Q1 weak - validate
        ))

        # BCH - 68.3% WR, 3.52 PF (HIGH VOLUME)
        self.add_config(LongStrategyConfig(
            symbol='BCHUSDT',
            timeframe='15min',
            rsi_min=35,
            rsi_max=45,
            volume_threshold=1.1,
            expected_win_rate=68.3,
            expected_trades_per_quarter=36.5,
            profit_factor=3.52,
            backtest_return_q1=8.66,
            backtest_return_q4=8.79,
            enabled=True  # Tier 1 - Highest volume, great returns
        ))

        # SOL - 63.9% WR, 8.04 PF
        self.add_config(LongStrategyConfig(
            symbol='SOLUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.3,
            expected_win_rate=63.9,
            expected_trades_per_quarter=5.5,
            profit_factor=8.04,
            backtest_return_q1=1.12,
            backtest_return_q4=1.12,
            enabled=False  # Tier 1 (by PF) but low WR - validate
        ))

        # KAS - 58.1% WR, 47.15 PF (EXTREME PF but unstable)
        self.add_config(LongStrategyConfig(
            symbol='KASUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.1,
            expected_win_rate=58.1,
            expected_trades_per_quarter=10,
            profit_factor=47.15,
            backtest_return_q1=3.52,
            backtest_return_q4=-2.90,
            enabled=False  # Tier 1 (by PF) but Q4 negative - DO NOT enable
        ))

        # ═══════════════════════════════════════════════════════════════════════════
        # TIER 2: GOOD PERFORMERS (70%+ WR or 2.0+ PF) - DISABLED (validate first)
        # ═══════════════════════════════════════════════════════════════════════════

        # INJ - 72.9% WR, 2.91 PF
        self.add_config(LongStrategyConfig(
            symbol='INJUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.5,
            expected_win_rate=72.9,
            expected_trades_per_quarter=10,
            profit_factor=2.91,
            backtest_return_q1=1.77,
            backtest_return_q4=1.46,
            enabled=False  # Tier 2 - Validate first
        ))

        # AAVE - 70.3% WR, 1.94 PF
        self.add_config(LongStrategyConfig(
            symbol='AAVEUSDT',
            timeframe='15min',
            rsi_min=35,
            rsi_max=45,
            volume_threshold=1.0,
            expected_win_rate=70.3,
            expected_trades_per_quarter=35,
            profit_factor=1.94,
            backtest_return_q1=2.40,
            backtest_return_q4=6.39,
            enabled=False  # Tier 2 - High volume, validate
        ))

        # DYDX - 68.9% WR, 2.15 PF
        self.add_config(LongStrategyConfig(
            symbol='DYDXUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.0,
            expected_win_rate=68.9,
            expected_trades_per_quarter=14.5,
            profit_factor=2.15,
            backtest_return_q1=1.47,
            backtest_return_q4=1.31,
            enabled=False  # Tier 2
        ))

        # SUI - 67.9% WR, 2.71 PF
        self.add_config(LongStrategyConfig(
            symbol='SUIUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.1,
            expected_win_rate=67.9,
            expected_trades_per_quarter=10.5,
            profit_factor=2.71,
            backtest_return_q1=0.50,
            backtest_return_q4=0.50,
            enabled=False  # Tier 2
        ))

        # DOGE - 67.7% WR, 2.69 PF
        self.add_config(LongStrategyConfig(
            symbol='DOGEUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.2,
            expected_win_rate=67.7,
            expected_trades_per_quarter=10.5,
            profit_factor=2.69,
            backtest_return_q1=-0.20,
            backtest_return_q4=2.63,
            enabled=False  # Tier 2 - Q1 negative
        ))

        # LDO - 67.4% WR, 2.90 PF
        self.add_config(LongStrategyConfig(
            symbol='LDOUSDT',
            timeframe='15min',
            rsi_min=35,
            rsi_max=45,
            volume_threshold=1.3,
            expected_win_rate=67.4,
            expected_trades_per_quarter=23,
            profit_factor=2.90,
            backtest_return_q1=4.23,
            backtest_return_q4=4.23,
            enabled=False  # Tier 2 - Good volume
        ))

        # SHIB - 67.1% WR, 2.24 PF
        self.add_config(LongStrategyConfig(
            symbol='SHIB1000USDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.1,
            expected_win_rate=67.1,
            expected_trades_per_quarter=12,
            profit_factor=2.24,
            backtest_return_q1=2.04,
            backtest_return_q4=2.04,
            enabled=False  # Tier 2
        ))

        # ADA - 66.4% WR, 2.06 PF
        self.add_config(LongStrategyConfig(
            symbol='ADAUSDT',
            timeframe='15min',
            rsi_min=35,
            rsi_max=45,
            volume_threshold=1.5,
            expected_win_rate=66.4,
            expected_trades_per_quarter=22,
            profit_factor=2.06,
            backtest_return_q1=0.95,
            backtest_return_q4=5.88,
            enabled=False  # Tier 2 - Good volume
        ))

        # PEPE - 64.1% WR, 2.47 PF (HIGHEST VOLUME)
        self.add_config(LongStrategyConfig(
            symbol='PEPEUSDT',
            timeframe='15min',
            rsi_min=35,
            rsi_max=45,
            volume_threshold=1.0,
            expected_win_rate=64.1,
            expected_trades_per_quarter=39,
            profit_factor=2.47,
            backtest_return_q1=7.02,
            backtest_return_q4=7.02,
            enabled=False  # Tier 2 - Most trades, validate
        ))

        # LINK - 62.5% WR, 2.72 PF
        self.add_config(LongStrategyConfig(
            symbol='LINKUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.0,
            expected_win_rate=62.5,
            expected_trades_per_quarter=12,
            profit_factor=2.72,
            backtest_return_q1=2.28,
            backtest_return_q4=2.28,
            enabled=False  # Tier 2
        ))

        # XLM - 60.0% WR, 2.27 PF
        self.add_config(LongStrategyConfig(
            symbol='XLMUSDT',
            timeframe='15min',
            rsi_min=35,
            rsi_max=45,
            volume_threshold=1.5,
            expected_win_rate=60.0,
            expected_trades_per_quarter=12,
            profit_factor=2.27,
            backtest_return_q1=1.48,
            backtest_return_q4=1.48,
            enabled=False  # Tier 2 - Borderline
        ))

        # ═══════════════════════════════════════════════════════════════════════════
        # NEW TIER 1 ADDITIONS - Data-Calibrated from Live Monitoring (2025-10-31)
        # Top 15 high-suitability assets with proven trading opportunities
        # Conservative parameters based on 7-day live data analysis
        # ═══════════════════════════════════════════════════════════════════════════

        # GLMUSDT - Suitability: 90, 41% opp rate
        self.add_config(LongStrategyConfig(
            symbol='GLMUSDT',
            timeframe='15min',
            rsi_min=31,
            rsi_max=40,
            volume_threshold=1.0,
            enabled=True  # New Tier 1 - High opportunity rate
        ))

        # TRUMPUSDT - Suitability: 90, 32% opp rate
        self.add_config(LongStrategyConfig(
            symbol='TRUMPUSDT',
            timeframe='15min',
            rsi_min=26,
            rsi_max=36,
            volume_threshold=1.0,
            enabled=True  # New Tier 1
        ))

        # SANDUSDT - Suitability: 85, Max Score 4.00
        self.add_config(LongStrategyConfig(
            symbol='SANDUSDT',
            timeframe='15min',
            rsi_min=28,
            rsi_max=38,
            volume_threshold=1.0,
            enabled=True  # New Tier 1
        ))

        # STXUSDT - Suitability: 85, Max Score 4.00
        self.add_config(LongStrategyConfig(
            symbol='STXUSDT',
            timeframe='15min',
            rsi_min=29,
            rsi_max=39,
            volume_threshold=1.0,
            enabled=True  # New Tier 1
        ))

        # RSRUSDT - Suitability: 85, Max Score 4.00
        self.add_config(LongStrategyConfig(
            symbol='RSRUSDT',
            timeframe='15min',
            rsi_min=29,
            rsi_max=39,
            volume_threshold=1.0,
            enabled=True  # New Tier 1
        ))

        # FILUSDT - Suitability: 85, 33% opp rate
        self.add_config(LongStrategyConfig(
            symbol='FILUSDT',
            timeframe='15min',
            rsi_min=29,
            rsi_max=39,
            volume_threshold=1.0,
            enabled=True  # New Tier 1
        ))

        # FLRUSDT - Suitability: 80, Max Score 4.00
        self.add_config(LongStrategyConfig(
            symbol='FLRUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.0,
            enabled=True  # New Tier 1
        ))

        # LPTUSDT - Suitability: 80, Max Score 4.00
        self.add_config(LongStrategyConfig(
            symbol='LPTUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.0,
            enabled=True  # New Tier 1
        ))

        # POPCATUSDT - Suitability: 80, 30% opp rate
        self.add_config(LongStrategyConfig(
            symbol='POPCATUSDT',
            timeframe='15min',
            rsi_min=31,
            rsi_max=40,
            volume_threshold=1.0,
            enabled=True  # New Tier 1
        ))

        # XCNUSDT - Suitability: 80, Max Score 3.89
        self.add_config(LongStrategyConfig(
            symbol='XCNUSDT',
            timeframe='15min',
            rsi_min=32,
            rsi_max=40,
            volume_threshold=1.0,
            enabled=True  # New Tier 1
        ))

        # MNTUSDT - Suitability: 80, Max Score 3.84
        self.add_config(LongStrategyConfig(
            symbol='MNTUSDT',
            timeframe='15min',
            rsi_min=29,
            rsi_max=39,
            volume_threshold=1.0,
            enabled=True  # New Tier 1
        ))

        # ORDIUSDT - Suitability: 80, 25% opp rate
        self.add_config(LongStrategyConfig(
            symbol='ORDIUSDT',
            timeframe='15min',
            rsi_min=30,
            rsi_max=40,
            volume_threshold=1.0,
            enabled=True  # New Tier 1
        ))

        # LDOUSDT - Suitability: 80, Max Score 3.54
        self.add_config(LongStrategyConfig(
            symbol='LDOUSDT',
            timeframe='15min',
            rsi_min=29,
            rsi_max=39,
            volume_threshold=1.0,
            enabled=True  # New Tier 1
        ))

        # DEXEUSDT - Suitability: 80, 46% opp rate (highest!)
        self.add_config(LongStrategyConfig(
            symbol='DEXEUSDT',
            timeframe='15min',
            rsi_min=31,
            rsi_max=40,
            volume_threshold=1.0,
            enabled=True  # New Tier 1 - Highest opportunity rate
        ))

        # HNTUSDT - Suitability: 80, 32% opp rate
        self.add_config(LongStrategyConfig(
            symbol='HNTUSDT',
            timeframe='15min',
            rsi_min=27,
            rsi_max=37,
            volume_threshold=1.0,
            enabled=True  # New Tier 1
        ))

    def add_config(self, config: LongStrategyConfig):
        """Add or update a LONG strategy configuration"""
        self.configs[config.symbol] = config

    def get_config(self, symbol: str) -> Optional[LongStrategyConfig]:
        """Get LONG configuration for a symbol"""
        return self.configs.get(symbol)

    def get_enabled_configs(self) -> Dict[str, LongStrategyConfig]:
        """Get all enabled LONG configurations"""
        return {symbol: cfg for symbol, cfg in self.configs.items() if cfg.enabled}

    def enable_asset(self, symbol: str):
        """Enable LONG trading for an asset"""
        if symbol in self.configs:
            self.configs[symbol].enabled = True

    def disable_asset(self, symbol: str):
        """Disable LONG trading for an asset"""
        if symbol in self.configs:
            self.configs[symbol].enabled = False

    def get_timeframe_assets(self, timeframe: str) -> Dict[str, LongStrategyConfig]:
        """Get all enabled assets for a specific timeframe"""
        return {
            symbol: cfg
            for symbol, cfg in self.configs.items()
            if cfg.enabled and cfg.timeframe == timeframe
        }

    def print_summary(self):
        """Print summary of all LONG configurations"""
        print("\n" + "="*120)
        print("LONG STRATEGY CONFIGURATION SUMMARY")
        print("="*120)

        enabled = self.get_enabled_configs()
        disabled = {s: c for s, c in self.configs.items() if not c.enabled}

        if enabled:
            print(f"\nENABLED STRATEGIES ({len(enabled)}):")
            print("-"*120)
            print(f"{'Symbol':<12} {'Timeframe':<10} {'RSI Range':<12} {'Vol>':<6} {'Exp WR':<8} {'PF':<8} {'Trades/Q'}")
            print("-"*120)

            for symbol, cfg in enabled.items():
                rsi_range = f"{cfg.rsi_min}-{cfg.rsi_max}"
                print(f"{symbol:<12} {cfg.timeframe:<10} {rsi_range:<12} {cfg.volume_threshold:<6.1f} "
                      f"{cfg.expected_win_rate or 0:<7.1f}% {cfg.profit_factor or 0:<7.2f} {cfg.expected_trades_per_quarter or 0:<8}")
        else:
            print("\nNo enabled LONG strategies")

        if disabled:
            print(f"\nDISABLED STRATEGIES ({len(disabled)}) - Available for future activation:")
            print("-"*120)
            for symbol, cfg in disabled.items():
                print(f"  {symbol:<12} {cfg.timeframe} - {cfg.expected_win_rate or 0:.1f}% WR, "
                      f"{cfg.profit_factor or 0:.2f} PF ({cfg.expected_trades_per_quarter or 0} trades/Q)")

        print("\n" + "="*120 + "\n")


# Example: How to add new assets in the future
"""
To add a new LONG opportunity:

1. Run backtesting optimization for the new asset
2. Find the best parameters (RSI range, volume threshold)
3. Add configuration:

manager = LongStrategyManager()
manager.add_config(LongStrategyConfig(
    symbol='MATICUSDT',
    timeframe='15min',
    rsi_min=30,
    rsi_max=40,
    volume_threshold=1.2,
    expected_win_rate=75.0,
    expected_trades_per_quarter=15,
    profit_factor=3.5,
    enabled=True
))

This scalability means:
- 37 assets × 15 trades/quarter = 555 LONG opportunities per quarter
- Each asset validated individually
- Easy to enable/disable based on performance
- Configuration-driven, no code changes needed
"""


if __name__ == "__main__":
    # Demo
    manager = LongStrategyManager()
    manager.print_summary()

    # Show how to query
    print("\n15-MINUTE TIMEFRAME ASSETS:")
    for symbol, cfg in manager.get_timeframe_assets('15min').items():
        print(f"  {symbol}: RSI{cfg.rsi_min}-{cfg.rsi_max} Vol>{cfg.volume_threshold}")
