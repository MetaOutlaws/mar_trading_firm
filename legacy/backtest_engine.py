"""
Backtesting Engine for Trading Strategy
Simulates historical trading to evaluate strategy performance
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"


@dataclass
class Trade:
    """Represents a single trade"""
    entry_time: datetime
    exit_time: Optional[datetime] = None
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    entry_price: float = 0.0
    exit_price: float = 0.0
    position_size: float = 0.0
    pnl: float = 0.0
    pnl_percentage: float = 0.0
    fees: float = 0.0

    # Signal information
    entry_signal_score: float = 0.0
    entry_rsi: float = 0.0
    entry_adx: float = 0.0
    entry_macd: float = 0.0
    entry_volume: float = 0.0

    # Exit reason
    exit_reason: str = ""  # 'take_profit', 'stop_loss', 'signal', 'timeout'
    holding_period_minutes: int = 0

    # Trade outcome
    is_win: bool = False
    risk_reward_ratio: float = 0.0


@dataclass
class BacktestConfig:
    """Configuration for backtest"""
    initial_capital: float = 10000.0
    risk_per_trade: float = 0.02  # 2% risk per trade
    max_position_size: float = 0.1  # 10% of capital

    # Order execution
    slippage: float = 0.001  # 0.1% slippage
    maker_fee: float = 0.0002  # 0.02% maker fee
    taker_fee: float = 0.0006  # 0.06% taker fee

    # Strategy parameters
    take_profit_pct: float = 0.03  # 3% take profit
    stop_loss_pct: float = 0.015  # 1.5% stop loss
    max_holding_hours: int = 24  # Maximum holding period

    # Entry filters
    min_signal_score: float = 3.0
    min_adx: float = 20.0
    min_volume_ratio: float = 1.0

    # RSI filters
    rsi_oversold: float = 35.0
    rsi_overbought: float = 70.0

    # Risk management
    max_concurrent_trades: int = 5
    max_daily_loss: float = 0.05  # 5% max daily loss

    # Backtest settings
    use_realistic_execution: bool = True  # Simulate market orders, slippage
    compound_returns: bool = True  # Reinvest profits


@dataclass
class BacktestResults:
    """Results from a backtest"""
    # Overall performance
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0

    # P&L metrics
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0

    # Performance ratios
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    risk_reward_ratio: float = 0.0

    # Risk metrics
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0

    # Trade statistics
    avg_holding_minutes: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # Equity curve
    equity_curve: List[float] = field(default_factory=list)
    equity_timestamps: List[datetime] = field(default_factory=list)

    # Trade log
    trades: List[Trade] = field(default_factory=list)

    # Additional stats
    total_fees: float = 0.0
    execution_quality: float = 0.0  # % of intended price achieved

    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary"""
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': round(self.win_rate, 2),
            'profit_factor': round(self.profit_factor, 2),
            'total_pnl': round(self.total_pnl, 2),
            'total_pnl_pct': round(self.total_pnl_pct, 2),
            'max_drawdown_pct': round(self.max_drawdown_pct, 2),
            'sharpe_ratio': round(self.sharpe_ratio, 2),
            'avg_win_pct': round(self.avg_win_pct, 2),
            'avg_loss_pct': round(self.avg_loss_pct, 2),
            'risk_reward_ratio': round(self.risk_reward_ratio, 2),
        }


class BacktestEngine:
    """
    Core backtesting engine for strategy evaluation
    """

    def __init__(self, config: BacktestConfig = None):
        """
        Initialize backtest engine

        Args:
            config: Backtest configuration
        """
        self.config = config or BacktestConfig()
        self.reset()

    def reset(self):
        """Reset backtest state"""
        self.capital = self.config.initial_capital
        self.equity = self.config.initial_capital
        self.peak_equity = self.config.initial_capital

        self.open_trades: List[Trade] = []
        self.closed_trades: List[Trade] = []

        self.equity_curve = [self.config.initial_capital]
        self.equity_timestamps = []

        self.daily_pnl = {}
        self.current_day = None

    def run_backtest(
        self,
        signals_df: pd.DataFrame,
        price_data: Optional[pd.DataFrame] = None
    ) -> BacktestResults:
        """
        Run backtest on historical signals

        Args:
            signals_df: DataFrame with trading signals
                Required columns: timestamp, symbol, signal_type, close,
                                 rsi, adx, volume_ratio, signal_score
            price_data: Optional high-resolution price data for realistic execution

        Returns:
            BacktestResults object
        """
        logger.info(f"Starting backtest with {len(signals_df)} signals")
        logger.info(f"Initial capital: ${self.config.initial_capital:,.2f}")

        self.reset()

        # Sort by timestamp
        signals_df = signals_df.sort_values('timestamp').reset_index(drop=True)

        # Process each signal
        for idx, row in signals_df.iterrows():
            timestamp = row['timestamp']

            # Update current day for daily loss tracking
            current_date = timestamp.date()
            if self.current_day != current_date:
                self.current_day = current_date
                self.daily_pnl[current_date] = 0.0

            # Check if daily loss limit exceeded
            if self.daily_pnl[current_date] < -self.config.max_daily_loss * self.capital:
                logger.debug(f"Daily loss limit reached on {current_date}")
                continue

            # Update open trades (check for exits)
            self._update_open_trades(row, price_data)

            # Check for new entry signals
            if row['signal_type'] == 'buy':
                self._process_buy_signal(row)
            elif row['signal_type'] == 'sell':  # SHORT entry
                self._process_sell_signal(row)

            # Update equity curve
            self._update_equity(timestamp)

            # Log progress
            if idx % 1000 == 0:
                logger.info(f"Processed {idx}/{len(signals_df)} signals, Equity: ${self.equity:,.2f}")

        # Close any remaining open trades
        final_row = signals_df.iloc[-1]
        self._close_all_trades(final_row, reason='backtest_end')

        # Calculate results
        results = self._calculate_results()

        logger.info(f"Backtest complete: {results.total_trades} trades, "
                   f"Win rate: {results.win_rate:.1f}%, "
                   f"Total P&L: ${results.total_pnl:,.2f}")

        return results

    def _process_buy_signal(self, signal: pd.Series):
        """Process a buy signal"""
        # Check if we can open new trade
        if len(self.open_trades) >= self.config.max_concurrent_trades:
            return

        # Apply entry filters
        if signal['signal_score'] < self.config.min_signal_score:
            return

        if signal['adx'] < self.config.min_adx:
            return

        if signal['volume_ratio'] < self.config.min_volume_ratio:
            return

        if signal['rsi'] > self.config.rsi_overbought:
            return

        # Calculate position size
        position_value = min(
            self.equity * self.config.risk_per_trade / self.config.stop_loss_pct,
            self.equity * self.config.max_position_size
        )

        # Apply slippage
        entry_price = signal['close'] * (1 + self.config.slippage)
        position_size = position_value / entry_price

        # Calculate fees
        fees = position_value * self.config.taker_fee

        # Create trade
        trade = Trade(
            entry_time=signal['timestamp'],
            symbol=signal['symbol'],
            side=OrderSide.BUY,
            entry_price=entry_price,
            position_size=position_size,
            entry_signal_score=signal['signal_score'],
            entry_rsi=signal['rsi'],
            entry_adx=signal['adx'],
            entry_volume=signal['volume_ratio'],
            fees=fees
        )

        self.open_trades.append(trade)
        self.capital -= (position_value + fees)

        logger.debug(f"Opened LONG trade: {signal['symbol']} @ ${entry_price:.2f}, "
                    f"Size: {position_size:.4f}, Score: {signal['signal_score']:.2f}")

    def _process_sell_signal(self, signal: pd.Series):
        """Process a sell signal (SHORT entry)"""
        # Check if we can open new trade
        if len(self.open_trades) >= self.config.max_concurrent_trades:
            return

        # Apply entry filters (inverted for shorts)
        if signal['signal_score'] < self.config.min_signal_score:
            return

        if signal['adx'] < self.config.min_adx:
            return

        if signal['volume_ratio'] < self.config.min_volume_ratio:
            return

        if signal['rsi'] < self.config.rsi_oversold:  # For shorts, check if not too oversold
            return

        # Calculate position size
        position_value = min(
            self.equity * self.config.risk_per_trade / self.config.stop_loss_pct,
            self.equity * self.config.max_position_size
        )

        # Apply slippage (worse for shorts)
        entry_price = signal['close'] * (1 - self.config.slippage)
        position_size = position_value / entry_price

        # Calculate fees
        fees = position_value * self.config.taker_fee

        # Create SHORT trade
        trade = Trade(
            entry_time=signal['timestamp'],
            symbol=signal['symbol'],
            side=OrderSide.SELL,  # SHORT position
            entry_price=entry_price,
            position_size=position_size,
            entry_signal_score=signal['signal_score'],
            entry_rsi=signal['rsi'],
            entry_adx=signal['adx'],
            entry_volume=signal['volume_ratio'],
            fees=fees
        )

        self.open_trades.append(trade)
        self.capital -= (position_value + fees)

        logger.debug(f"Opened SHORT trade: {signal['symbol']} @ ${entry_price:.2f}, "
                    f"Size: {position_size:.4f}, Score: {signal['signal_score']:.2f}")

    def _update_open_trades(self, current_signal: pd.Series, price_data: Optional[pd.DataFrame]):
        """Update open trades and check for exits"""
        trades_to_close = []

        for trade in self.open_trades:
            # Skip trades for different symbols
            if trade.symbol != current_signal['symbol']:
                continue

            current_price = current_signal['close']
            current_time = current_signal['timestamp']

            # Calculate unrealized P&L (different for LONG vs SHORT)
            if trade.side == OrderSide.BUY:  # LONG position
                pnl_pct = (current_price - trade.entry_price) / trade.entry_price
            else:  # SHORT position (OrderSide.SELL)
                pnl_pct = (trade.entry_price - current_price) / trade.entry_price

            # Check take profit
            if pnl_pct >= self.config.take_profit_pct:
                trades_to_close.append((trade, current_price, 'take_profit'))
                continue

            # Check stop loss
            if pnl_pct <= -self.config.stop_loss_pct:
                trades_to_close.append((trade, current_price, 'stop_loss'))
                continue

            # Check timeout
            holding_minutes = (current_time - trade.entry_time).total_seconds() / 60
            if holding_minutes > self.config.max_holding_hours * 60:
                trades_to_close.append((trade, current_price, 'timeout'))
                continue

            # Check sell signal
            if current_signal['signal_type'] == 'sell':
                trades_to_close.append((trade, current_price, 'signal'))
                continue

        # Close marked trades
        for trade, exit_price, reason in trades_to_close:
            self._close_trade(trade, exit_price, current_signal['timestamp'], reason)

    def _close_trade(self, trade: Trade, exit_price: float, exit_time: datetime, reason: str):
        """Close a trade"""
        # Apply slippage (direction depends on LONG vs SHORT)
        if trade.side == OrderSide.BUY:  # LONG exit
            exit_price = exit_price * (1 - self.config.slippage)
        else:  # SHORT exit (buy to cover)
            exit_price = exit_price * (1 + self.config.slippage)

        # Calculate P&L (different for LONG vs SHORT)
        position_value = trade.position_size * exit_price
        entry_value = trade.position_size * trade.entry_price

        if trade.side == OrderSide.BUY:  # LONG position
            pnl = position_value - entry_value  # Profit if price went up
        else:  # SHORT position
            pnl = entry_value - position_value  # Profit if price went down

        # Apply exit fees
        exit_fees = position_value * self.config.taker_fee
        trade.fees += exit_fees
        pnl -= (trade.fees)

        # Update trade
        trade.exit_price = exit_price
        trade.exit_time = exit_time
        trade.pnl = pnl
        trade.pnl_percentage = (pnl / entry_value) * 100
        trade.exit_reason = reason
        trade.holding_period_minutes = int((exit_time - trade.entry_time).total_seconds() / 60)
        trade.is_win = pnl > 0
        trade.risk_reward_ratio = abs(pnl / entry_value)

        # Update capital
        self.capital += position_value - exit_fees

        # Update daily P&L
        current_date = exit_time.date()
        if current_date in self.daily_pnl:
            self.daily_pnl[current_date] += pnl

        # Move to closed trades
        self.open_trades.remove(trade)
        self.closed_trades.append(trade)

        logger.debug(f"Closed trade: {trade.symbol}, P&L: ${pnl:.2f} ({trade.pnl_percentage:.2f}%), "
                    f"Reason: {reason}")

    def _close_all_trades(self, final_signal: pd.Series, reason: str):
        """Close all remaining open trades"""
        for trade in self.open_trades.copy():
            self._close_trade(trade, final_signal['close'], final_signal['timestamp'], reason)

    def _update_equity(self, timestamp: datetime):
        """Update equity curve"""
        # Calculate unrealized P&L
        unrealized_pnl = sum(
            (trade.position_size * trade.entry_price * 0.98)  # Estimate with slight discount
            for trade in self.open_trades
        )

        self.equity = self.capital + unrealized_pnl
        self.peak_equity = max(self.peak_equity, self.equity)

        self.equity_curve.append(self.equity)
        self.equity_timestamps.append(timestamp)

    def _calculate_results(self) -> BacktestResults:
        """Calculate backtest results"""
        results = BacktestResults()

        results.trades = self.closed_trades
        results.total_trades = len(self.closed_trades)

        if results.total_trades == 0:
            logger.warning("No trades executed in backtest")
            return results

        # Count wins/losses
        results.winning_trades = sum(1 for t in self.closed_trades if t.is_win)
        results.losing_trades = sum(1 for t in self.closed_trades if not t.is_win and t.pnl < 0)
        results.breakeven_trades = results.total_trades - results.winning_trades - results.losing_trades

        # P&L metrics
        results.total_pnl = sum(t.pnl for t in self.closed_trades)
        results.total_pnl_pct = (results.total_pnl / self.config.initial_capital) * 100
        results.gross_profit = sum(t.pnl for t in self.closed_trades if t.pnl > 0)
        results.gross_loss = abs(sum(t.pnl for t in self.closed_trades if t.pnl < 0))

        # Performance ratios
        results.win_rate = (results.winning_trades / results.total_trades) * 100
        results.profit_factor = results.gross_profit / results.gross_loss if results.gross_loss > 0 else 0

        wins = [t.pnl for t in self.closed_trades if t.is_win]
        losses = [t.pnl for t in self.closed_trades if not t.is_win and t.pnl < 0]

        results.avg_win = np.mean(wins) if wins else 0
        results.avg_loss = abs(np.mean(losses)) if losses else 0
        results.avg_win_pct = np.mean([t.pnl_percentage for t in self.closed_trades if t.is_win]) if wins else 0
        results.avg_loss_pct = abs(np.mean([t.pnl_percentage for t in self.closed_trades if not t.is_win])) if losses else 0
        results.risk_reward_ratio = results.avg_win / results.avg_loss if results.avg_loss > 0 else 0

        # Risk metrics
        drawdowns = []
        peak = self.config.initial_capital
        for equity in self.equity_curve:
            peak = max(peak, equity)
            drawdown = peak - equity
            drawdowns.append(drawdown)

        results.max_drawdown = max(drawdowns) if drawdowns else 0
        results.max_drawdown_pct = (results.max_drawdown / self.config.initial_capital) * 100

        # Sharpe ratio (simplified - assuming daily returns)
        returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
        if len(returns) > 0 and np.std(returns) > 0:
            results.sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)  # Annualized

        # Trade statistics
        results.avg_holding_minutes = np.mean([t.holding_period_minutes for t in self.closed_trades])

        # Consecutive wins/losses
        max_consec_wins = 0
        max_consec_losses = 0
        current_consec = 0
        last_was_win = None

        for trade in self.closed_trades:
            if trade.is_win:
                if last_was_win:
                    current_consec += 1
                else:
                    current_consec = 1
                max_consec_wins = max(max_consec_wins, current_consec)
                last_was_win = True
            else:
                if last_was_win == False:
                    current_consec += 1
                else:
                    current_consec = 1
                max_consec_losses = max(max_consec_losses, current_consec)
                last_was_win = False

        results.max_consecutive_wins = max_consec_wins
        results.max_consecutive_losses = max_consec_losses

        # Equity curve
        results.equity_curve = self.equity_curve
        results.equity_timestamps = self.equity_timestamps

        # Fees
        results.total_fees = sum(t.fees for t in self.closed_trades)

        return results


if __name__ == "__main__":
    # Example usage
    print("Backtesting Engine - Example Usage")
    print("=" * 50)

    # This would normally come from BigQuery
    sample_data = {
        'timestamp': pd.date_range('2024-01-01', periods=100, freq='15min'),
        'symbol': ['BTCUSDT'] * 100,
        'signal_type': ['buy' if i % 10 == 0 else 'hold' for i in range(100)],
        'close': np.random.randn(100).cumsum() + 50000,
        'rsi': np.random.uniform(30, 70, 100),
        'adx': np.random.uniform(20, 40, 100),
        'volume_ratio': np.random.uniform(0.8, 2.0, 100),
        'signal_score': np.random.uniform(2.5, 4.5, 100),
    }

    signals_df = pd.DataFrame(sample_data)

    # Run backtest
    config = BacktestConfig(
        initial_capital=10000,
        risk_per_trade=0.02,
        take_profit_pct=0.03,
        stop_loss_pct=0.015
    )

    engine = BacktestEngine(config)
    results = engine.run_backtest(signals_df)

    # Print results
    print("\nBacktest Results:")
    print(f"Total Trades: {results.total_trades}")
    print(f"Win Rate: {results.win_rate:.2f}%")
    print(f"Profit Factor: {results.profit_factor:.2f}")
    print(f"Total P&L: ${results.total_pnl:,.2f} ({results.total_pnl_pct:.2f}%)")
    print(f"Max Drawdown: {results.max_drawdown_pct:.2f}%")
    print(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")
