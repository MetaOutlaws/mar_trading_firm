"""
SHORT Strategy Configuration - Scalable Asset Management
Easily add hundreds of assets with asset-specific parameters
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ShortStrategyConfig:
    """Configuration for SHORT strategy per asset"""

    # Asset identification
    symbol: str

    # Timeframe (15min, 1h, 4h, etc.)
    timeframe: str

    # Entry conditions
    rsi_threshold: float  # Minimum RSI for overbought signal
    volume_threshold: float  # Minimum volume ratio

    # Trend filter
    trend_filter: str  # 'in_uptrend', 'death_cross', 'below_ema200', 'none'

    # Risk management
    take_profit_pct: float = 0.05  # 5% TP
    stop_loss_pct: float = 0.05  # 5% SL

    # Performance tracking
    expected_win_rate: Optional[float] = None
    expected_trades_per_quarter: Optional[int] = None
    backtest_return_q1: Optional[float] = None
    backtest_return_q4: Optional[float] = None

    # Status
    enabled: bool = True


class ShortStrategyManager:
    """
    Manages SHORT strategy configurations for all assets
    Scalable to hundreds of assets
    """

    def __init__(self):
        self.configs: Dict[str, ShortStrategyConfig] = {}
        self._load_default_configs()

    def _load_default_configs(self):
        """Load proven SHORT configurations from backtesting"""

        # ═══════════════════════════════════════════════════════════════════════════
        # TIER 1: EXCELLENT PERFORMERS (70%+ Win Rate) - ENABLED
        # Comprehensive optimization across 58 assets (2025-10-26)
        # ═══════════════════════════════════════════════════════════════════════════

        # AVAX - 90.0% WR (BEST PERFORMER)
        self.add_config(ShortStrategyConfig(
            symbol='AVAXUSDT',
            timeframe='4h',
            rsi_threshold=65,
            volume_threshold=1.2,
            trend_filter='in_uptrend',
            take_profit_pct=0.05,
            stop_loss_pct=0.05,
            expected_win_rate=90.0,
            expected_trades_per_quarter=3,
            backtest_return_q1=0.62,
            backtest_return_q4=0.92,
            enabled=True  # Tier 1 - Excellent 90% WR
        ))

        # ADA - 87.5% WR (VALIDATED)
        self.add_config(ShortStrategyConfig(
            symbol='ADAUSDT',
            timeframe='4h',
            rsi_threshold=60,
            volume_threshold=1.5,
            trend_filter='in_uptrend',
            take_profit_pct=0.05,
            stop_loss_pct=0.05,
            expected_win_rate=87.5,
            expected_trades_per_quarter=4,
            backtest_return_q1=1.54,
            backtest_return_q4=2.46,
            enabled=True  # Tier 1 - Proven in Q1 & Q4
        ))

        # SHIB - 81.2% WR
        self.add_config(ShortStrategyConfig(
            symbol='SHIB1000USDT',
            timeframe='4h',
            rsi_threshold=65,
            volume_threshold=1.2,
            trend_filter='in_uptrend',
            take_profit_pct=0.05,
            stop_loss_pct=0.05,
            expected_win_rate=81.2,
            expected_trades_per_quarter=4.5,
            backtest_return_q1=0.32,
            backtest_return_q4=0.32,
            enabled=True  # Tier 1 - Consistent across quarters
        ))

        # PYTH - 75.0% WR
        self.add_config(ShortStrategyConfig(
            symbol='PYTHUSDT',
            timeframe='4h',
            rsi_threshold=60,
            volume_threshold=1.2,
            trend_filter='in_uptrend',
            take_profit_pct=0.05,
            stop_loss_pct=0.05,
            expected_win_rate=75.0,
            expected_trades_per_quarter=3,
            backtest_return_q1=0.31,
            backtest_return_q4=0.31,
            enabled=True  # Tier 1 - Good WR and returns
        ))

        # NEAR - 70.8% WR (HIGH VOLUME)
        self.add_config(ShortStrategyConfig(
            symbol='NEARUSDT',
            timeframe='4h',
            rsi_threshold=60,
            volume_threshold=1.0,
            trend_filter='in_uptrend',
            take_profit_pct=0.05,
            stop_loss_pct=0.05,
            expected_win_rate=70.8,
            expected_trades_per_quarter=10.5,
            backtest_return_q1=1.14,
            backtest_return_q4=1.14,
            enabled=True  # Tier 1 - Most trades, 70%+ WR
        ))

        # ═══════════════════════════════════════════════════════════════════════════
        # TIER 2: GOOD PERFORMERS (60-70% Win Rate) - DISABLED (validate first)
        # ═══════════════════════════════════════════════════════════════════════════

        # BTC - 62.5% WR but breakeven
        self.add_config(ShortStrategyConfig(
            symbol='BTCUSDT',
            timeframe='4h',
            rsi_threshold=65,
            volume_threshold=1.2,
            trend_filter='in_uptrend',
            expected_win_rate=62.5,
            expected_trades_per_quarter=4,
            backtest_return_q1=0.19,
            backtest_return_q4=-0.19,
            enabled=False  # Tier 2 - Breakeven, paper trade first
        ))

        # DOGE - 61.1% WR
        self.add_config(ShortStrategyConfig(
            symbol='DOGEUSDT',
            timeframe='4h',
            rsi_threshold=60,
            volume_threshold=1.2,
            trend_filter='in_uptrend',
            expected_win_rate=61.1,
            expected_trades_per_quarter=6,
            backtest_return_q1=0.79,
            backtest_return_q4=-0.01,
            enabled=False  # Tier 2 - Marginal, validate first
        ))

        # ═══════════════════════════════════════════════════════════════════════════
        # TIER 3: MARGINAL (<60% WR) - DISABLED (not recommended)
        # ═══════════════════════════════════════════════════════════════════════════

        # DOT - 54.2% WR
        self.add_config(ShortStrategyConfig(
            symbol='DOTUSDT',
            timeframe='4h',
            rsi_threshold=65,
            volume_threshold=1.5,
            trend_filter='in_uptrend',
            expected_win_rate=54.2,
            expected_trades_per_quarter=3.5,
            backtest_return_q1=0.42,
            backtest_return_q4=0.74,
            enabled=False  # Tier 3 - Below 60% WR threshold
        ))

        # ═══════════════════════════════════════════════════════════════════════════
        # NEW TIER 1 ADDITIONS - Data-Calibrated from Live Monitoring (2025-10-31)
        # Top 15 high-suitability assets with proven SHORT opportunities
        # Conservative parameters based on 7-day live data analysis
        # ═══════════════════════════════════════════════════════════════════════════

        # GLMUSDT - 33 SHORT opportunities, RSI threshold 61
        self.add_config(ShortStrategyConfig(
            symbol='GLMUSDT',
            timeframe='4h',
            rsi_threshold=61,
            volume_threshold=1.0,
            trend_filter='in_uptrend',
            enabled=True  # New Tier 1
        ))

        # TRUMPUSDT - 43 SHORT opportunities, RSI threshold 63
        self.add_config(ShortStrategyConfig(
            symbol='TRUMPUSDT',
            timeframe='4h',
            rsi_threshold=63,
            volume_threshold=1.0,
            trend_filter='in_uptrend',
            enabled=True  # New Tier 1
        ))

        # SANDUSDT - 15 SHORT opportunities, RSI threshold 60
        self.add_config(ShortStrategyConfig(
            symbol='SANDUSDT',
            timeframe='4h',
            rsi_threshold=60,
            volume_threshold=1.0,
            trend_filter='in_uptrend',
            enabled=True  # New Tier 1
        ))

        # STXUSDT - 8 SHORT opportunities, RSI threshold 60
        self.add_config(ShortStrategyConfig(
            symbol='STXUSDT',
            timeframe='4h',
            rsi_threshold=60,
            volume_threshold=1.0,
            trend_filter='in_uptrend',
            enabled=True  # New Tier 1
        ))

        # RSRUSDT - 21 SHORT opportunities, RSI threshold 64
        self.add_config(ShortStrategyConfig(
            symbol='RSRUSDT',
            timeframe='4h',
            rsi_threshold=64,
            volume_threshold=1.0,
            trend_filter='in_uptrend',
            enabled=True  # New Tier 1
        ))

        # FILUSDT - 23 SHORT opportunities, RSI threshold 62
        self.add_config(ShortStrategyConfig(
            symbol='FILUSDT',
            timeframe='4h',
            rsi_threshold=62,
            volume_threshold=1.0,
            trend_filter='in_uptrend',
            enabled=True  # New Tier 1
        ))

        # FLRUSDT - 11 SHORT opportunities, RSI threshold 62
        self.add_config(ShortStrategyConfig(
            symbol='FLRUSDT',
            timeframe='4h',
            rsi_threshold=62,
            volume_threshold=1.1,
            trend_filter='in_uptrend',
            enabled=True  # New Tier 1
        ))

        # LPTUSDT - Only 1 SHORT opportunity, higher volume threshold
        self.add_config(ShortStrategyConfig(
            symbol='LPTUSDT',
            timeframe='4h',
            rsi_threshold=60,
            volume_threshold=1.5,
            trend_filter='in_uptrend',
            enabled=True  # New Tier 1
        ))

        # POPCATUSDT - 13 SHORT opportunities, RSI threshold 60
        self.add_config(ShortStrategyConfig(
            symbol='POPCATUSDT',
            timeframe='4h',
            rsi_threshold=60,
            volume_threshold=1.0,
            trend_filter='in_uptrend',
            enabled=True  # New Tier 1
        ))

        # XCNUSDT - 6 SHORT opportunities, higher volume threshold
        self.add_config(ShortStrategyConfig(
            symbol='XCNUSDT',
            timeframe='4h',
            rsi_threshold=64,
            volume_threshold=2.1,
            trend_filter='in_uptrend',
            enabled=True  # New Tier 1
        ))

        # MNTUSDT - 3 SHORT opportunities, higher volume threshold
        self.add_config(ShortStrategyConfig(
            symbol='MNTUSDT',
            timeframe='4h',
            rsi_threshold=60,
            volume_threshold=1.8,
            trend_filter='in_uptrend',
            enabled=True  # New Tier 1
        ))

        # ORDIUSDT - 8 SHORT opportunities, RSI threshold 60
        self.add_config(ShortStrategyConfig(
            symbol='ORDIUSDT',
            timeframe='4h',
            rsi_threshold=60,
            volume_threshold=1.0,
            trend_filter='in_uptrend',
            enabled=True  # New Tier 1
        ))

        # LDOUSDT - 10 SHORT opportunities, RSI threshold 60
        self.add_config(ShortStrategyConfig(
            symbol='LDOUSDT',
            timeframe='4h',
            rsi_threshold=60,
            volume_threshold=1.0,
            trend_filter='in_uptrend',
            enabled=True  # New Tier 1
        ))

        # DEXEUSDT - 37 SHORT opportunities (high!), RSI threshold 64
        self.add_config(ShortStrategyConfig(
            symbol='DEXEUSDT',
            timeframe='4h',
            rsi_threshold=64,
            volume_threshold=1.0,
            trend_filter='in_uptrend',
            enabled=True  # New Tier 1
        ))

        # HNTUSDT - 35 SHORT opportunities, RSI threshold 61
        self.add_config(ShortStrategyConfig(
            symbol='HNTUSDT',
            timeframe='4h',
            rsi_threshold=61,
            volume_threshold=1.0,
            trend_filter='in_uptrend',
            enabled=True  # New Tier 1
        ))

    def add_config(self, config: ShortStrategyConfig):
        """Add or update a SHORT strategy configuration"""
        self.configs[config.symbol] = config

    def get_config(self, symbol: str) -> Optional[ShortStrategyConfig]:
        """Get SHORT configuration for a symbol"""
        return self.configs.get(symbol)

    def get_enabled_configs(self) -> Dict[str, ShortStrategyConfig]:
        """Get all enabled SHORT configurations"""
        return {symbol: cfg for symbol, cfg in self.configs.items() if cfg.enabled}

    def enable_asset(self, symbol: str):
        """Enable SHORT trading for an asset"""
        if symbol in self.configs:
            self.configs[symbol].enabled = True

    def disable_asset(self, symbol: str):
        """Disable SHORT trading for an asset"""
        if symbol in self.configs:
            self.configs[symbol].enabled = False

    def get_timeframe_assets(self, timeframe: str) -> Dict[str, ShortStrategyConfig]:
        """Get all enabled assets for a specific timeframe"""
        return {
            symbol: cfg
            for symbol, cfg in self.configs.items()
            if cfg.enabled and cfg.timeframe == timeframe
        }

    def print_summary(self):
        """Print summary of all SHORT configurations"""
        print("\n" + "="*100)
        print("SHORT STRATEGY CONFIGURATION SUMMARY")
        print("="*100)

        enabled = self.get_enabled_configs()
        disabled = {s: c for s, c in self.configs.items() if not c.enabled}

        if enabled:
            print(f"\nENABLED STRATEGIES ({len(enabled)}):")
            print("-"*100)
            print(f"{'Symbol':<12} {'Timeframe':<10} {'RSI':<6} {'Vol':<6} {'Trend Filter':<15} {'Exp WR':<8} {'Trades/Q'}")
            print("-"*100)

            for symbol, cfg in enabled.items():
                print(f"{symbol:<12} {cfg.timeframe:<10} {cfg.rsi_threshold:<6.0f} "
                      f"{cfg.volume_threshold:<6.1f} {cfg.trend_filter:<15} "
                      f"{cfg.expected_win_rate or 0:<7.1f}% {cfg.expected_trades_per_quarter or 0:<8}")
        else:
            print("\nNo enabled SHORT strategies")

        if disabled:
            print(f"\nDISABLED STRATEGIES ({len(disabled)}) - Available for future activation:")
            print("-"*100)
            for symbol, cfg in disabled.items():
                print(f"  {symbol:<12} {cfg.timeframe} - {cfg.expected_win_rate or 0:.1f}% WR "
                      f"(Reason: {cfg.expected_trades_per_quarter or 0} trades/Q)")

        print("\n" + "="*100 + "\n")


# Example: How to add new assets in the future
"""
To add a new SHORT opportunity:

1. Run backtesting optimization for the new asset
2. Find the best parameters (RSI threshold, volume threshold, trend filter)
3. Add configuration:

manager = ShortStrategyManager()
manager.add_config(ShortStrategyConfig(
    symbol='LINKUSDT',
    timeframe='4h',
    rsi_threshold=65,
    volume_threshold=1.3,
    trend_filter='in_uptrend',
    expected_win_rate=72.0,
    expected_trades_per_quarter=5,
    enabled=True
))

This scalability means:
- 100 assets × 4 trades/quarter = 400 SHORT opportunities per quarter
- Each asset validated individually
- Easy to enable/disable based on performance
- Configuration-driven, no code changes needed
"""


if __name__ == "__main__":
    # Demo
    manager = ShortStrategyManager()
    manager.print_summary()

    # Show how to query
    print("4-HOUR TIMEFRAME ASSETS:")
    for symbol, cfg in manager.get_timeframe_assets('4h').items():
        print(f"  {symbol}: RSI{cfg.rsi_threshold}+ Vol>{cfg.volume_threshold}")
