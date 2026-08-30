# BEGIN SECTION 1: Core Components and Setup
from symtable import Symbol
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime
import io
import sys
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pybit.unified_trading import HTTP
import traceback
from collections import defaultdict
import json
import os
import requests.exceptions
from functools import wraps
import concurrent.futures
from python_db_connector import TradingDatabaseConnector
from concurrent.futures import TimeoutError
from typing import Optional, Any  # Add this import at the top of file

# Import strategy configuration managers
from long_strategy_config import LongStrategyManager
from short_strategy_config import ShortStrategyManager

# Logging Setup with Enhanced Configuration
logging.getLogger('urllib3').setLevel(logging.WARNING)  # Reduce external library noise
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')),
        logging.FileHandler("trading_bot_2.log", encoding="utf-8", mode='a')
    ]
)
logger = logging.getLogger("TradingSystem")

# Add this timeout decorator
def timeout_handler(timeout_duration=30):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=timeout_duration)
                except TimeoutError:
                    logger.error(f"Operation timed out after {timeout_duration} seconds")
                    raise TimeoutError(f"Operation timed out after {timeout_duration} seconds")
        return wrapper
    return decorator

# Error Management System
class ErrorType:
    API_ERROR = "api_error"
    EXECUTION_ERROR = "exec_error"
    VALIDATION_ERROR = "valid_error"
    MARKET_ERROR = "market_error"
    CALCULATION_ERROR = "calc_error"  # Added for indicator calculations
    RATE_LIMIT_ERROR = "rate_limit_error"  # Add this

class ErrorManager:
    def __init__(self):
        self.error_counts = {}
        self.thresholds = {
            ErrorType.API_ERROR: {'count': 30, 'window': 700, 'cooldown': 600},
            ErrorType.EXECUTION_ERROR: {'count': 30, 'window': 3600, 'cooldown': 1800},
            ErrorType.VALIDATION_ERROR: {'count': 30, 'window': 700, 'cooldown': 300},
            ErrorType.MARKET_ERROR: {'count': 30, 'window': 3600, 'cooldown': 900},
            ErrorType.CALCULATION_ERROR: {'count': 30, 'window': 700, 'cooldown': 300}
        }
        self.error_history = {}
        self.cycle_duration = 900  # 15 minutes
        self.last_cycle_time = time.time()

    def record_error(self, symbol: str, error: Exception, context: dict = None) -> bool:
        try:
            if self.new_cycle_started():
                self.cleanup_error_history()
            
            current_time = time.time()
            error_type = self.classify_error(error)
            
            # Initialize if needed
            if symbol not in self.error_history:
                self.error_history[symbol] = {}
            if error_type not in self.error_history[symbol]:
                self.error_history[symbol][error_type] = []
            
            # Record error with detailed context
            error_details = {
                'timestamp': current_time,
                'error_message': str(error),
                'error_type': error_type,
                'context': context,
                'traceback': traceback.format_exc()
            }
            
            self.error_history[symbol][error_type].append(error_details)
            error_count = len(self.error_history[symbol][error_type])
            threshold = self.thresholds[error_type]['count']
            
            logger.warning(f"{symbol} {error_type} count: {error_count}/{threshold}")
            logger.error(f"Error details: {str(error)}")
            if context:
                logger.error(f"Error context: {context}")
                
            return error_count >= threshold
            
        except Exception as e:
            logger.critical(f"Error in error handling system: {str(e)}")
            return True

    def classify_error(self, error: Exception) -> str:
        error_str = str(error).lower()
        if 'calculation' in error_str or 'math' in error_str:
            return ErrorType.CALCULATION_ERROR
        if 'api' in error_str or 'request' in error_str:
            return ErrorType.API_ERROR
        if 'execution' in error_str or 'order' in error_str:
            return ErrorType.EXECUTION_ERROR
        if 'invalid' in error_str or 'validation' in error_str:
            return ErrorType.VALIDATION_ERROR
        if 'market' in error_str:
            return ErrorType.MARKET_ERROR
        return ErrorType.API_ERROR

    def should_cool_down(self, symbol: str, error_type: str) -> bool:
        try:
            if symbol not in self.error_history or error_type not in self.error_history[symbol]:
                return False
                
            current_time = time.time()
            window = self.thresholds[error_type]['window']
            
            # Access timestamp from error details dictionary
            errors_in_window = [
                error['timestamp'] for error in self.error_history[symbol][error_type] 
                if current_time - error['timestamp'] <= window
            ]
            
            return len(errors_in_window) >= self.thresholds[error_type]['count']
        except Exception as e:
            logger.error(f"Error checking cooldown status: {str(e)}")
            return False

    def new_cycle_started(self) -> bool:
        current_time = time.time()
        if current_time - self.last_cycle_time >= self.cycle_duration:
            self.last_cycle_time = current_time
            return True
        return False

    def cleanup_error_history(self):
        try:
            current_time = time.time()
            for symbol in list(self.error_history.keys()):
                for error_type in list(self.error_history[symbol].keys()):
                    window = self.thresholds[error_type]['window']
                    self.error_history[symbol][error_type] = [
                        t for t in self.error_history[symbol][error_type]
                        if current_time - t <= window
                    ]
                    if not self.error_history[symbol][error_type]:
                        del self.error_history[symbol][error_type]
                if not self.error_history[symbol]:
                    del self.error_history[symbol]
                    
        except Exception as e:
            logger.error(f"Error cleaning up error history: {str(e)}")

    def get_error_metrics(self) -> dict:
        metrics = {
            'total_errors': sum(len(errors) for errors in self.error_history.values()),
            'errors_by_type': defaultdict(int),
            'cooldown_pairs': set()
        }
        
        for symbol, errors in self.error_history.items():
            for error_type, timestamps in errors.items():
                metrics['errors_by_type'][error_type] += len(timestamps)
                if self.should_cool_down(symbol, error_type):
                    metrics['cooldown_pairs'].add(symbol)
                    
        return metrics

    def log_error_metrics(self):
        metrics = self.get_error_metrics()
        logger.info(f"Error Metrics Summary:")
        logger.info(f"Total Errors: {metrics['total_errors']}")
        logger.info(f"Errors by Type: {dict(metrics['errors_by_type'])}")
        logger.info(f"Pairs in Cooldown: {metrics['cooldown_pairs']}")

class PybitMetrics:
    def __init__(self):
        self.kline_requests = 0
        self.successful_klines = 0
        self.failed_klines = 0
        self.response_times = []
        self.rate_limit_hits = 0
        self.data_validation_errors = 0
        self.metrics_by_symbol = {}  # Add per-symbol tracking
        
    def log_kline_request(self, symbol: str, success: bool, response_time: float, rate_limited: bool = False):
        # Update global counters
        self.kline_requests += 1
        if success:
            self.successful_klines += 1
            self.response_times.append(response_time)
        else:
            self.failed_klines += 1
        if rate_limited:
            self.rate_limit_hits += 1
            
        # Update per-symbol metrics
        if symbol not in self.metrics_by_symbol:
            self.metrics_by_symbol[symbol] = {
                'requests': 0,
                'successes': 0,
                'failures': 0,
                'rate_limits': 0,
                'response_times': []
            }
            
        symbol_metrics = self.metrics_by_symbol[symbol]
        symbol_metrics['requests'] += 1
        if success:
            symbol_metrics['successes'] += 1
            symbol_metrics['response_times'].append(response_time)
        else:
            symbol_metrics['failures'] += 1
        if rate_limited:
            symbol_metrics['rate_limits'] += 1
            
        # Log metrics every 100 requests
        if self.kline_requests % 100 == 0:
            self._log_metrics_summary()
            
    def _log_metrics_summary(self):
        try:
            # Global metrics with explicit debug statements
            logger.debug("=== PybitMetrics Summary Start ===")
            logger.info(f"Total API Requests: {self.kline_requests}")
            logger.info(f"Rate Limit Hits: {self.rate_limit_hits}")
            logger.info(f"API Errors: {self.failed_klines}")
            
            # Success rate calculation
            if self.kline_requests > 0:
                success_rate = (self.successful_klines / self.kline_requests) * 100
                logger.info(f"Overall Success Rate: {success_rate:.2f}%")
            
            # Rate limiting details
            if self.rate_limit_hits > 0:
                logger.warning(f"Rate Limit Alert: {self.rate_limit_hits} hits detected")
                
            # Performance metrics
            if self.response_times:
                avg_time = sum(self.response_times) / len(self.response_times)
                max_time = max(self.response_times)
                logger.info(f"Average Response Time: {avg_time:.3f}s")
                logger.info(f"Max Response Time: {max_time:.3f}s")
                
            # Per-symbol breakdown
            logger.info("=== Per-Symbol Metrics ===")
            for symbol, metrics in self.metrics_by_symbol.items():
                if metrics['requests'] > 0:
                    symbol_success_rate = (metrics['successes'] / metrics['requests']) * 100
                    avg_response_time = (
                        sum(metrics['response_times']) / len(metrics['response_times'])
                        if metrics['response_times']
                        else 0
                    )
                    logger.info(f"Symbol: {symbol}")
                    logger.info(f"  Requests: {metrics['requests']}")
                    logger.info(f"  Successes: {metrics['successes']}")
                    logger.info(f"  Success Rate: {symbol_success_rate:.2f}%")
                    logger.info(f"  Average Response Time: {avg_response_time:.3f}s")

            logger.debug("=== PybitMetrics Summary End ===")
        except Exception as e:
            logger.error(f"Error in logging metrics summary: {e}")

# Configuration Classes
class IndicatorConfig:
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
        # Short-term EMAs for quick signals
        self.EMA_FAST = 5          # 5-period fast EMA
        self.EMA_SLOW = 10         # 10-period slow EMA

        # Long-term EMAs for trend identification  
        self.EMA_50 = 50          # 50-period EMA for medium trend
        self.EMA_200 = 200        # 200-period EMA for long trend
        
        # Volume Configuration
        self.VOLUME_MA_PERIOD = 20
        self.VOLUME_THRESHOLD = 0.05

        # OPTIMIZED: Load asset-specific configurations from strategy managers
        # Based on comprehensive Q1/Q4 2024 optimization across 58 assets
        self._load_asset_configurations()
        
        # ADX Configuration
        self.ADX_PERIOD = 14
        self.ADX_THRESHOLD = 20
        
        # Validation Constants
        self.MIN_REQUIRED_CANDLES = 200
        self.WARMUP_CANDLES = 50

    def _load_asset_configurations(self):
        """Load asset-specific configurations from LONG and SHORT strategy managers"""
        # Initialize configuration managers
        long_mgr = LongStrategyManager()
        short_mgr = ShortStrategyManager()

        # Get enabled configurations
        long_configs = long_mgr.get_enabled_configs()
        short_configs = short_mgr.get_enabled_configs()

        # Initialize asset parameter dictionaries
        self.ASSET_VOLUME_THRESHOLDS = {}
        self.ASSET_RSI_RANGES = {}
        self.ASSET_STRATEGIES = {}  # 'LONG', 'SHORT', or 'BOTH'
        self.TRADING_ENABLED = set()  # Track which assets can execute trades

        # Load LONG configurations
        for symbol, config in long_configs.items():
            self.ASSET_VOLUME_THRESHOLDS[symbol] = config.volume_threshold
            self.ASSET_RSI_RANGES[symbol] = {
                'min': config.rsi_min,
                'max': config.rsi_max
            }
            self.ASSET_STRATEGIES[symbol] = 'LONG'
            self.TRADING_ENABLED.add(symbol)  # Mark as trading-enabled

        # Load SHORT configurations (some assets may have both LONG and SHORT)
        for symbol, config in short_configs.items():
            self.ASSET_VOLUME_THRESHOLDS[symbol] = config.volume_threshold
            self.ASSET_RSI_RANGES[symbol] = {
                'min': config.rsi_threshold,  # For shorts, this is the overbought level
                'max': 100  # Shorts look for RSI >= threshold
            }

            # Mark as BOTH if already has LONG strategy
            if symbol in self.ASSET_STRATEGIES:
                self.ASSET_STRATEGIES[symbol] = 'BOTH'
            else:
                self.ASSET_STRATEGIES[symbol] = 'SHORT'

            self.TRADING_ENABLED.add(symbol)  # Mark as trading-enabled

        logger.info(f"Loaded configurations for {len(self.ASSET_VOLUME_THRESHOLDS)} enabled assets")
        logger.info(f"  - LONG only: {list(self.ASSET_STRATEGIES.values()).count('LONG')} assets")
        logger.info(f"  - SHORT only: {list(self.ASSET_STRATEGIES.values()).count('SHORT')} assets")
        logger.info(f"  - BOTH: {list(self.ASSET_STRATEGIES.values()).count('BOTH')} assets")
        logger.info(f"  - Trading-enabled: {len(self.TRADING_ENABLED)} assets")

class TradingConfig:
    def __init__(self):
        # Position Management
        self.LONG_TP_PERCENTAGE = 5.0
        self.LONG_SL_PERCENTAGE = 5.0
        self.SHORT_TP_PERCENTAGE = 3.0
        self.SHORT_SL_PERCENTAGE = 2.0
        self.USDT_VALUE = 500  # Position size per trade in USDT
        self.TRAILING_STOP_PERCENTAGE = 1.0
        
        # Timeframe Configuration
        self.MIN_4H_CANDLES = 50
        
        # Order Management
        self.MAX_ORDER_RETRIES = 3
        self.RETRY_DELAY = 2
        
        # Risk Management
        self.MAX_POSITIONS = 5
        self.MAX_DAILY_TRADES = 30
        
        # Data Validation
        self.RSI_VALIDATION_CONSTANTS = {
            'WARMUP_PERIOD': 14,
            'MIN_VALID_RSI': 0,
            'MAX_VALID_RSI': 100,
            'EPSILON': 0.0001,
            'MAX_EXTREME_VALUES_PCT': 0.05,
            'MIN_VALID_VALUES_PCT': 0.90
        }

class TimeoutConfig:
    def __init__(self):
        self.initial_timeout = 30
        self.max_timeout = 90
        self.backoff_factor = 1.5
        self.max_retries = 3
        self.chunk_timeout = 10  # Add timeout for individual chunks

    def get_timeout(self, retry_count: int) -> int:
        return min(self.initial_timeout * (self.backoff_factor ** retry_count), self.max_timeout)

# Position Tracking
@dataclass
class Position:
    symbol: str
    entry_price: float
    quantity: float
    side: str
    entry_time: datetime
    order_id: str
    tp_price: Optional[float] = None
    sl_price: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Convert position to dictionary for logging"""
        return {
            'symbol': self.symbol,
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'side': self.side,
            'entry_time': self.entry_time.isoformat(),
            'order_id': self.order_id,
            'tp_price': self.tp_price,
            'sl_price': self.sl_price
        }

# END SECTION 1

# BEGIN SECTION 2: Price Validation and Data Processing

class PriceValidation:
    def __init__(self, session, error_manager: ErrorManager):
        self.session = session
        self.error_manager = error_manager
        self._instrument_cache = {}
        self._cache_expiry = {}
        self.CACHE_DURATION = 300

    def get_instrument_info(self, symbol: str) -> Optional[dict]:
        try:
            current_time = time.time()
            
            # Check cache
            if (symbol in self._instrument_cache and 
                current_time - self._cache_expiry.get(symbol, 0) < self.CACHE_DURATION):
                logger.debug(f"Using cached instrument info for {symbol}")
                return self._instrument_cache[symbol]
                
            # Fetch new data
            response = self.session.get_instruments_info(
                category="linear",
                symbol=symbol
            )
            
            if response.get('retCode') == 0 and response['result']['list']:
                self._instrument_cache[symbol] = response['result']['list'][0]
                self._cache_expiry[symbol] = current_time
                return self._instrument_cache[symbol]
                
            logger.error(f"Failed to get instrument info: {response.get('retMsg', 'Unknown error')}")
            return None
            
        except Exception as e:
            self.error_manager.record_error(symbol, e, {'context': 'get_instrument_info'})
            return None

    def validate_entry_price(self, symbol: str, price: float) -> Tuple[bool, str, dict]:
        try:
            instrument = self.get_instrument_info(symbol)
            if not instrument:
                return False, "Failed to get instrument info", {}
                
            price_filter = instrument['priceFilter']
            tick_size = float(price_filter['tickSize'])
            min_price = float(price_filter['minPrice'])
            max_price = float(price_filter['maxPrice'])
            
            # Round to valid tick size
            valid_price = round(price / tick_size) * tick_size
            valid_price = round(valid_price, 8)  # Ensure no floating point issues
            
            if not (min_price <= valid_price <= max_price):
                return False, f"Price {valid_price} outside range [{min_price}, {max_price}]", {}
                
            return True, str(valid_price), {
                'tick_size': tick_size,
                'min_price': min_price,
                'max_price': max_price
            }
            
        except Exception as e:
            self.error_manager.record_error(symbol, e, {'context': 'validate_entry_price', 'price': price})
            return False, str(e), {}

    def validate_mark_price(self, symbol: str) -> Tuple[bool, float, str]:
        try:
            response = self.session.get_positions(
                category="linear",
                symbol=symbol
            )
            
            if response.get('retCode') == 0 and response['result']['list']:
                mark_price = float(response['result']['list'][0]['markPrice'])
                return True, mark_price, ""
                
            return False, 0, "Failed to get mark price"
            
        except Exception as e:
            self.error_manager.record_error(symbol, e, {'context': 'validate_mark_price'})
            return False, 0, str(e)

class DataProcessor:
    def __init__(self, indicator_config: IndicatorConfig, error_manager: ErrorManager):
        self.config = indicator_config
        self.error_manager = error_manager
        self.required_fields = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        self.max_future_time = 300  # 5 minutes allowance for time sync issues

    def validate_timestamp(self, timestamp: Any, symbol: str) -> Optional[int]:
        """
        Enhanced timestamp validation with comprehensive checks
        """
        try:
            if timestamp is None:
                logger.error(f"{symbol}: Null timestamp received")
                return None
                
            # Convert to int if string
            if isinstance(timestamp, str):
                timestamp = int(timestamp)
            elif not isinstance(timestamp, (int, float)):
                logger.error(f"{symbol}: Invalid timestamp type: {type(timestamp)}")
                return None
            
            # Normalize to milliseconds
            if timestamp < 1e12:  # If in seconds, convert to milliseconds
                timestamp = timestamp * 1000
                
            # Validate timestamp range
            current_time = int(time.time() * 1000)  # Current time in ms
            if timestamp > current_time + (self.max_future_time * 1000):
                logger.error(f"{symbol}: Future timestamp detected: {timestamp}")
                return None
                
            return int(timestamp)
            
        except Exception as e:
            logger.error(f"{symbol}: Timestamp validation error: {str(e)}")
            return None
    
    def validate_klines_data(self, klines: list, symbol: str) -> bool:
        """
        Comprehensive klines data validation
        """
        try:
            if not klines:
                logger.error(f"{symbol}: Empty klines data received")
                return False
                
            # Check data structure
            if not isinstance(klines, list):
                logger.error(f"{symbol}: Invalid klines type: {type(klines)}")
                return False
                
            # Validate each kline
            for i, kline in enumerate(klines):
                # Check length
                if len(kline) < 6:  # Minimum required fields
                    logger.error(f"{symbol}: Invalid kline length at index {i}: {len(kline)}")
                    return False
                    
                # Validate timestamp
                timestamp = self.validate_timestamp(kline[0], symbol)
                if timestamp is None:
                    logger.error(f"{symbol}: Invalid timestamp in kline at index {i}")
                    return False
                    
                # Validate numeric values
                try:
                    numeric_values = [float(kline[j]) for j in range(1, 6)]  # open, high, low, close, volume
                    
                    # Price validation
                    open_price, high_price, low_price, close_price = numeric_values[:4]
                    if not (low_price <= open_price <= high_price and 
                           low_price <= close_price <= high_price):
                        logger.error(f"{symbol}: Invalid OHLC values at index {i}")
                        return False
                        
                    # Volume validation
                    if numeric_values[4] < 0:
                        logger.error(f"{symbol}: Negative volume at index {i}")
                        return False
                        
                except ValueError:
                    logger.error(f"{symbol}: Non-numeric values in kline at index {i}")
                    return False
            
            # Validate timestamp sequence (should be in descending order)
            timestamps = [int(k[0]) for k in klines]
            if not all(timestamps[i] > timestamps[i+1] for i in range(len(timestamps)-1)):
                logger.error(f"{symbol}: Timestamps not in descending order")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"{symbol}: Klines validation error: {str(e)}")

    def validate_and_prepare_data(self, df: pd.DataFrame, symbol: str) -> Optional[pd.DataFrame]:
        """Comprehensive data validation and preparation"""
        try:
            # Make copy to avoid modifying original data
            df = df.copy()
            
            # Enhanced basic validation
            if df is None or df.empty:
                self.error_manager.record_error(
                    symbol, 
                    ValueError("Empty DataFrame"), 
                    {'context': 'data_validation'}
                )
                logger.error(f"{symbol}: Empty DataFrame received")
                return None
                
            # Ensure chronological order
            df = df.sort_index()
            
            # Check for minimum required data
            if len(df) < self.config.MIN_REQUIRED_CANDLES:
                logger.error(f"{symbol}: Insufficient data points: {len(df)} < {self.config.MIN_REQUIRED_CANDLES}")
                return None
                
            # Validate data types and convert if necessary
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                if col not in df.columns:
                    logger.error(f"{symbol}: Missing required column: {col}")
                    return None
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Check for missing values
            missing_values = df[numeric_columns].isnull().sum()
            if missing_values.any():
                logger.error(f"{symbol}: Missing values detected: {missing_values[missing_values > 0]}")
                return None
            
            # Validate price relationships
            invalid_candles = (
                (df['high'] < df['low']) | 
                (df['high'] < df['open']) | 
                (df['high'] < df['close']) |
                (df['low'] > df['open']) | 
                (df['low'] > df['close'])
            )
            
            if invalid_candles.any():
                logger.error(f"{symbol}: Invalid OHLC relationships detected")
                return None
            
            # Handle time gaps
            time_diff = df.index.to_series().diff()
            expected_diff = pd.Timedelta(minutes=15)
            gaps = time_diff[time_diff > expected_diff]
            
            if not gaps.empty:
                logger.warning(f"{symbol}: Found {len(gaps)} time gaps, attempting to fix...")
                df = self._fix_time_gaps(df, symbol)
                if df is None:
                    return None
            
            # Optimize memory usage
            df = self._optimize_memory(df)
            
            # Add your existing pybit data validation logic here
            expected_columns = {'open', 'high', 'low', 'close', 'volume', 'turnover'}
            if not expected_columns.issubset(df.columns):
                missing = expected_columns - set(df.columns)
                self.error_manager.record_error(
                    symbol, 
                    ValueError(f"Missing columns: {missing}"), 
                    {'context': 'data_validation'}
                )
                return None
            
            logger.info(f"{symbol}: Data preparation completed successfully")
            return df
            
        except Exception as e:
            self.error_manager.record_error(symbol, e, {'context': 'validate_and_prepare_data'})
            return None

    def _fix_time_gaps(self, df: pd.DataFrame, symbol: str) -> Optional[pd.DataFrame]:
        """Handle time gaps in data"""
        try:
            # Resample to regular intervals
            resampled = df.resample('15T').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            })
            
            # Forward fill at most 4 periods (1 hour)
            df_filled = resampled.fillna(method='ffill', limit=4)
            
            # Check if we still have gaps
            remaining_gaps = df_filled.isnull().sum()
            if remaining_gaps.any():
                logger.error(f"{symbol}: Unable to fix all time gaps: {remaining_gaps}")
                return None
                
            return df_filled
            
        except Exception as e:
            self.error_manager.record_error(symbol, e, {'context': '_fix_time_gaps'})
            return None

    def _optimize_memory(self, df: pd.DataFrame) -> pd.DataFrame:
        """Optimize DataFrame memory usage"""
        try:
            # Convert float64 to float32
            float_cols = df.select_dtypes(include=['float64']).columns
            for col in float_cols:
                df[col] = df[col].astype('float32')
                
            return df
            
        except Exception as e:
            logger.warning(f"Memory optimization failed: {str(e)}")
            return df

    def calculate_typical_price(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate typical price and related metrics"""
        try:
            df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
            df['hlc3'] = df['typical_price']  # Common name used in indicators
            df['price_range'] = df['high'] - df['low']
            df['price_range_pct'] = (df['price_range'] / df['close'] * 100).round(4)
            return df
        except Exception as e:
            logger.error(f"Error calculating typical price: {str(e)}")
            return df

# END SECTION 2

# BEGIN SECTION 3: Technical Indicators

class TechnicalIndicators:
    def __init__(self, indicator_config: IndicatorConfig, error_manager: ErrorManager):
        self.indicator_config = indicator_config
        self.error_manager = error_manager
        self.logger = logging.getLogger("TradingSystem")

    def calculate_rsi(self, df: pd.DataFrame, symbol: str) -> Optional[pd.Series]:
        """Calculate RSI with comprehensive NaN handling"""
        try:
            # Validate input
            if 'close' not in df.columns:
                raise ValueError("Close price data required for RSI calculation")

            # Calculate price changes
            delta = df['close'].diff()
            
            # Create separate gain/loss series with proper initialization
            gains = pd.Series(0.0, index=delta.index)
            losses = pd.Series(0.0, index=delta.index)
            
            # Populate gains and losses
            gains[delta > 0] = delta[delta > 0]
            losses[delta < 0] = -delta[delta < 0]
            
            # Initialize with simple moving average
            avg_gain = gains.rolling(
                window=self.indicator_config.RSI_PERIOD,
                min_periods=self.indicator_config.RSI_PERIOD
            ).mean()
            avg_loss = losses.rolling(
                window=self.indicator_config.RSI_PERIOD,
                min_periods=self.indicator_config.RSI_PERIOD
            ).mean()
            
            # Apply Wilder's smoothing
            for i in range(self.indicator_config.RSI_PERIOD, len(gains)):
                avg_gain.iloc[i] = (avg_gain.iloc[i-1] * 
                    (self.indicator_config.RSI_PERIOD-1) + gains.iloc[i]) / self.indicator_config.RSI_PERIOD
                avg_loss.iloc[i] = (avg_loss.iloc[i-1] * 
                    (self.indicator_config.RSI_PERIOD-1) + losses.iloc[i]) / self.indicator_config.RSI_PERIOD
            
            # Handle division by zero
            avg_loss = avg_loss.replace(0, 0.0001)
            
            # Calculate RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            # Validate results
            rsi = rsi.round(4)
            if not self._validate_rsi(rsi, symbol):
                return None
                
            return rsi
            
        except Exception as e:
            self.error_manager.record_error(symbol, e, {'context': 'RSI calculation'})
            return None

    def calculate_macd(self, df: pd.DataFrame, symbol: str) -> Tuple[Optional[pd.Series], Optional[pd.Series]]:
        """Calculate MACD and signal line with enhanced precision and validation"""
        try:
            # Initial data validation
            if len(df) < max(self.indicator_config.MACD_SLOW * 2, self.indicator_config.MACD_SIGNAL * 2):
                logger.warning(f"{symbol}: Insufficient data for reliable MACD calculation")
                return None, None

            # Data preprocessing
            if df['close'].isnull().any():
                df['close'] = df['close'].fillna(method='ffill')
                
            # Log data statistics for debugging
            logger.debug(f"{symbol}: MACD calculation input stats - Min: {df['close'].min():.6f}, Max: {df['close'].max():.6f}")

            # Calculate initial SMAs for better EMA initialization
            fast_sma = df['close'].rolling(
                window=self.indicator_config.MACD_FAST,
                min_periods=1
            ).mean()
            
            slow_sma = df['close'].rolling(
                window=self.indicator_config.MACD_SLOW,
                min_periods=1
            ).mean()

            # Calculate EMAs with proper initialization
            fast_ema = df['close'].ewm(
                span=self.indicator_config.MACD_FAST,
                adjust=False,
                min_periods=1
            ).mean()

            slow_ema = df['close'].ewm(
                span=self.indicator_config.MACD_SLOW,
                adjust=False,
                min_periods=1
            ).mean()

            # Validate EMA calculations
            if fast_ema.isnull().any() or slow_ema.isnull().any():
                logger.error(f"{symbol}: NaN values in EMA calculation")
                return None, None

            # Calculate MACD line with explicit type casting
            macd_line = pd.Series(
                fast_ema - slow_ema,
                index=df.index,
                dtype=np.float64
            )

            # Log MACD line statistics
            logger.debug(f"{symbol}: MACD line stats - Min: {macd_line.min():.6f}, Max: {macd_line.max():.6f}")

            # Calculate signal line
            signal_line = macd_line.ewm(
                span=self.indicator_config.MACD_SIGNAL,
                adjust=False,
                min_periods=1
            ).mean()

            # Validate results before rounding
            if not self._validate_macd(macd_line, signal_line, df, symbol):
                logger.error(f"{symbol}: MACD validation failed")
                return None, None

            # Round to appropriate precision
            macd_line = macd_line.round(6)
            signal_line = signal_line.round(6)

            return macd_line, signal_line

        except Exception as e:
            logger.error(f"{symbol}: Error in MACD calculation: {str(e)}")
            self.error_manager.record_error(symbol, e, {'context': 'MACD calculation'})
            return None, None

    def calculate_emas(self, df: pd.DataFrame, symbol: str) -> Dict[str, pd.Series]:
        """Calculate all required EMAs with enhanced validation and cleaning"""
        try:
            # Input validation
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_columns):
                raise ValueError(f"DataFrame missing required columns: {required_columns}")
                    
            if df.empty:
                self.logger.error(f"{symbol}: Empty DataFrame provided")
                return {}

            # Create working copy
            df_work = df.copy()
            
            # Clean and validate close prices
            close_series = df_work['close']
            
            # Add debug logging for data validation
            self.logger.debug(f"{symbol}: Close price statistics before EMA calculation:")
            self.logger.debug(f"NaN count: {close_series.isnull().sum()}")
            self.logger.debug(f"Range: {close_series.min()} to {close_series.max()}")
            
            # Clean close prices before calculation
            close_series = close_series.replace([np.inf, -np.inf], np.nan)
            close_series = close_series.ffill().bfill()
            
            # Check for any NaN values in close prices
            nan_count = close_series.isnull().sum()
            if nan_count > 0:
                self.logger.warning(f"{symbol}: Found {nan_count} NaN values in close prices")
                # If still have NaNs after filling, we can't proceed
                if close_series.isnull().any():
                    self.logger.error(f"{symbol}: Unable to clean close price data")
                    return {}

            # Update working DataFrame with cleaned prices
            df_work['close'] = close_series

            emas = {}
            
            # 1. Calculate base timeframe EMAs
            self.logger.info(f"{symbol}: Calculating base timeframe EMAs")
            
            # Add debug logging for close prices
            self.logger.debug(f"{symbol}: Close price range - Min: {close_series.min()}, Max: {close_series.max()}")
            
            for period, name in [
                (self.indicator_config.EMA_FAST, 'ema_fast'),
                (self.indicator_config.EMA_SLOW, 'ema_slow'),
                (self.indicator_config.EMA_50, 'ema_50'),
                (self.indicator_config.EMA_200, 'ema_200')
            ]:
                try:
                    # Calculate SMA first for better initialization
                    sma = close_series.rolling(
                        window=period,
                        min_periods=1  # Changed from period to 1 for better handling
                    ).mean()
                    
                    # Initialize EMA series
                    ema = pd.Series(index=close_series.index, dtype=float)
                    ema.iloc[:period] = sma.iloc[:period]
                    
                    # Calculate EMA manually for better control
                    multiplier = 2 / (period + 1)
                    for i in range(period, len(close_series)):
                        ema.iloc[i] = (close_series.iloc[i] * multiplier) + \
                                    (ema.iloc[i-1] * (1 - multiplier))
                    
                    # Validate EMA output
                    if ema.isnull().any():
                        self.logger.error(f"{symbol}: NaN values in {name} calculation")
                        continue
                        
                    emas[name] = ema
                    self.logger.debug(f"{symbol}: {name} calculated successfully - Length: {len(ema)}")
                    
                except Exception as e:
                    self.logger.error(f"{symbol}: Error calculating {name}: {str(e)}")
                    self.error_manager.record_error(symbol, e, {'context': f'{name} calculation'})
            
            # 2. Calculate 4h timeframe EMAs
            try:
                # Ensure index is datetime
                if not isinstance(df_work.index, pd.DatetimeIndex):
                    self.logger.error(f"{symbol}: Index is not DatetimeIndex")
                    return emas
                
                # Resample to 4h timeframe
                df_4h = self._resample_to_4h(df_work, symbol)
                if df_4h is None:
                    self.logger.error(f"{symbol}: Failed to process 4h timeframe data")
                    return emas
                
                # Handle any missing values in resampled data
                df_4h = self._handle_missing_data(df_4h, symbol)
                
                if df_4h is None:
                    self.logger.error(f"{symbol}: Failed to process 4h timeframe data")
                    return emas
                
                self.logger.debug(f"{symbol}: 4h resampling complete, shape: {df_4h.shape}")
                
                # Validate sufficient data
                min_periods = max(self.indicator_config.EMA_50, self.indicator_config.EMA_200)
                if len(df_4h) < min_periods:
                    self.logger.warning(
                        f"{symbol}: Insufficient data for 4h EMAs. "
                        f"Need {min_periods} periods, got {len(df_4h)}"
                    )
                    return emas
                    
                # Calculate 4h EMAs
                close_4h = df_4h['close']
                
                for period, name in [
                    (self.indicator_config.EMA_50, 'ema_50_4h'),
                    (self.indicator_config.EMA_200, 'ema_200_4h')
                ]:
                    try:
                        # Calculate SMA for initialization
                        sma_4h = close_4h.rolling(
                            window=period,
                            min_periods=1  # Changed from period to 1
                        ).mean()
                        
                        # Initialize EMA series
                        ema_4h = pd.Series(index=close_4h.index, dtype=float)
                        ema_4h.iloc[:period] = sma_4h.iloc[:period]
                        
                        # Calculate EMA manually
                        multiplier = 2 / (period + 1)
                        for i in range(period, len(close_4h)):
                            ema_4h.iloc[i] = (close_4h.iloc[i] * multiplier) + \
                                        (ema_4h.iloc[i-1] * (1 - multiplier))
                        
                        # Validate and store
                        if not ema_4h.isnull().any():
                            emas[name] = ema_4h
                            self.logger.debug(f"{symbol}: {name} calculated successfully")
                        else:
                            self.logger.error(f"{symbol}: Invalid {name} calculation")
                            
                    except Exception as e:
                        self.logger.error(f"{symbol}: Error calculating {name}: {str(e)}")
                        self.error_manager.record_error(symbol, e, {'context': f'{name} calculation'})
                        
            except Exception as e:
                self.logger.error(f"{symbol}: Error in 4h EMA calculations: {str(e)}")
                self.error_manager.record_error(symbol, e, {'context': '4h EMA calculation'})
            
            # Final validation
            if not self._validate_emas(emas, symbol):
                return {}
                
            return emas
            
        except Exception as e:
            self.logger.error(f"{symbol}: Critical error in EMA calculations: {str(e)}")
            self.error_manager.record_error(symbol, e, {'context': 'EMA calculation'})
            return {}

    def calculate_adx(self, df: pd.DataFrame, symbol: str) -> Tuple[Optional[pd.Series], Optional[pd.Series], Optional[pd.Series]]:
        """
        Calculate ADX with DI+ and DI- and return all three indicators
        Returns: Tuple of (ADX, DI+, DI-)
        """
        try:
            # Ensure minimum required periods
            if len(df) < self.indicator_config.ADX_PERIOD * 3:
                logger.warning(f"{symbol}: Insufficient data for ADX calculation. Need {self.indicator_config.ADX_PERIOD * 3} periods, got {len(df)}")
                return None, None, None

            # Create copy to avoid modifying original
            df = df.copy()
            
            # Ensure index alignment
            high = pd.Series(df['high'].values, index=df.index)
            low = pd.Series(df['low'].values, index=df.index)
            close = pd.Series(df['close'].values, index=df.index)
            
            # Calculate True Range
            tr1 = pd.Series(high - low)
            tr2 = pd.Series(abs(high - close.shift(1)))
            tr3 = pd.Series(abs(low - close.shift(1)))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # Directional Movement
            up_move = high - high.shift(1)
            down_move = low.shift(1) - low
            
            # Calculate +DM and -DM with proper Series creation
            pos_dm = pd.Series(
                np.where((up_move > down_move) & (up_move > 0), up_move, 0),
                index=df.index
            )
            neg_dm = pd.Series(
                np.where((down_move > up_move) & (down_move > 0), down_move, 0),
                index=df.index
            )
            
            # Calculate smoothed values with index alignment
            period = self.indicator_config.ADX_PERIOD
            tr_smooth = self._smoothen_series(pd.Series(tr, index=df.index), period)
            pos_dm_smooth = self._smoothen_series(pos_dm, period)
            neg_dm_smooth = self._smoothen_series(neg_dm, period)
            
            # Handle potential zero values in TR smooth
            tr_smooth = tr_smooth.replace(0, np.nan).fillna(tr_smooth.mean())
            
            # Calculate DI+ and DI-
            plus_di = pd.Series(100 * (pos_dm_smooth / tr_smooth), index=df.index)
            minus_di = pd.Series(100 * (neg_dm_smooth / tr_smooth), index=df.index)
            
            # Calculate DX with proper index alignment
            dx = pd.Series(
                100 * abs(plus_di - minus_di) / (plus_di + minus_di),
                index=df.index
            )
            
            # Calculate ADX
            adx = self._smoothen_series(dx, period)
            
            # Ensure final index alignment
            adx = pd.Series(adx.values, index=df.index)
            plus_di = pd.Series(plus_di.values, index=df.index)
            minus_di = pd.Series(minus_di.values, index=df.index)
            
            # Final validation
            if not self._validate_adx(adx, symbol):
                logger.error(f"{symbol}: ADX validation failed")
                return None, None, None
            
            logger.info(f"{symbol}: ADX calculation successful")
            # Return all three indicators rounded to 4 decimal places
            return adx.round(4), plus_di.round(4), minus_di.round(4)
            
        except Exception as e:
            logger.error(f"{symbol}: Error in ADX calculation: {str(e)}")
            self.error_manager.record_error(symbol, e, {'context': 'ADX calculation'})
            return None, None, None

    def analyze_volume(self, df: pd.DataFrame, symbol: str) -> Dict[str, pd.Series]:
        """Analyze volume patterns and trends"""
        try:
            results = {}
            
            # Calculate volume moving average
            results['volume_ma'] = df['volume'].rolling(
                window=self.indicator_config.VOLUME_MA_PERIOD, 
                min_periods=1
            ).mean()
            
            # Calculate relative volume
            results['relative_volume'] = df['volume'] / results['volume_ma']
            
            # Identify volume spikes
            results['volume_spikes'] = results['relative_volume'] > self.indicator_config.VOLUME_THRESHOLD
            
            # Calculate volume trend
            results['volume_trend'] = df['volume'].rolling(window=10).mean().pct_change()
            
            # Validate
            if not self._validate_volume(results, symbol):
                return {}
                
            return results
            
        except Exception as e:
            self.error_manager.record_error(symbol, e, {'context': 'Volume analysis'})
            return {}

    def _smoothen_series(self, series: pd.Series, period: int) -> pd.Series:
        """Apply Wilder's smoothing to a series"""
        return series.ewm(alpha=1/period, adjust=False).mean()
    
    def _resample_to_4h(self, df: pd.DataFrame, symbol: str) -> Optional[pd.DataFrame]:
        try:
            # Ensure index is datetime
            if not isinstance(df.index, pd.DatetimeIndex):
                self.logger.error(f"{symbol}: Index is not DatetimeIndex")
                return None
                
            # Resample with proper handling
            df_4h = df.resample('4h').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()  # Remove any NaN rows after resampling
            
            if len(df_4h) < self.indicator_config.MIN_REQUIRED_CANDLES:
                self.logger.error(f"{symbol}: Insufficient 4H candles after resampling")
                return None
                
            return df_4h
            
        except Exception as e:
            self.logger.error(f"{symbol}: Error in 4H resampling: {str(e)}")
            return None

    def _handle_missing_data(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Handle missing data during resampling"""
        try:
            # Remove any rows where all values are NaN
            df = df.dropna(how='all')
            
            # Check for missing values
            missing_values = df.isnull().sum()
            if missing_values.any():
                self.logger.warning(f"{symbol}: Missing values detected in resampled data: {missing_values[missing_values > 0]}")

                # Fill missing values using forward fill first
                df = df.fillna(method='ffill')
                # Then backward fill any remaining NaNs
                df = df.fillna(method='bfill')
                
                # If still have NaNs, drop those rows
                if df.isnull().any().any():
                    df = df.dropna()
                    self.logger.warning(f"{symbol}: Dropped rows with persistent NaN values")

            return df

        except Exception as e:
            self.logger.error(f"{symbol}: Error handling missing data: {str(e)}")
            return df

    def _validate_rsi(self, rsi: pd.Series, symbol: str) -> bool:
        """Validate RSI calculations"""
        try:
            warmup_period = self.indicator_config.RSI_PERIOD
            
            # Allow NaN values during warmup period
            rsi_to_check = rsi.iloc[warmup_period:]
            
            # Check for NaN values after warmup, with some tolerance
            nan_count = rsi_to_check.isnull().sum()
            if nan_count > 0:
                nan_percentage = (nan_count / len(rsi_to_check)) * 100
                # Allow up to 5% NaN values after warmup
                if nan_percentage > 5:
                    self.logger.warning(f"{symbol}: High number of NaN values in RSI: {nan_percentage:.2f}%")
                    return False
            
            # Remove NaN values for range checking
            valid_values = rsi_to_check.dropna()
            if len(valid_values) == 0:
                self.logger.error(f"{symbol}: No valid RSI values after warmup period")
                return False
                
            # More flexible range checking
            if (valid_values < 0).any() or (valid_values > 100).any():
                self.logger.warning(f"{symbol}: RSI values out of range: min={valid_values.min():.4f}, max={valid_values.max():.4f}")
                # Don't fail on slight deviations
                if (valid_values < -1).any() or (valid_values > 101).any():
                    return False
                    
            return True
            
        except Exception as e:
            self.logger.error(f"{symbol}: Error validating RSI: {str(e)}")
            return False

    def _validate_macd(self, macd: pd.Series, signal: pd.Series, df: pd.DataFrame, symbol: str) -> bool:
        """Enhanced MACD validation with comprehensive checks"""
        try:
            # Remove initial warmup period from validation
            warmup_period = max(self.indicator_config.MACD_SLOW, self.indicator_config.MACD_SIGNAL)
            macd_to_check = macd.iloc[warmup_period:]
            signal_to_check = signal.iloc[warmup_period:]

            # Check for NaN values after warmup
            if macd_to_check.isnull().any() or signal_to_check.isnull().any():
                logger.error(f"{symbol}: NaN values in MACD/Signal after warmup period")
                return False

            # Validate value ranges
            close_mean = df['close'].mean()
            max_macd_value = max(abs(macd_to_check.max()), abs(macd_to_check.min()))
            max_signal_value = max(abs(signal_to_check.max()), abs(signal_to_check.min()))

            # MACD should not exceed certain percentage of price
            price_threshold = close_mean * 0.2  # 20% of average price (relaxed from 10% to handle low-priced assets)
            if max_macd_value > price_threshold or max_signal_value > price_threshold:
                logger.warning(f"{symbol}: MACD values too large relative to price")
                logger.debug(f"{symbol}: MACD max: {max_macd_value:.6f}, Signal max: {max_signal_value:.6f}, Threshold: {price_threshold:.6f}")
                return False

            # Check for extreme values
            if max_macd_value < 1e-10 or max_signal_value < 1e-10:
                logger.warning(f"{symbol}: MACD/Signal values too small")
                return False

            # Verify reasonable oscillation
            macd_std = macd_to_check.std()
            if macd_std < 1e-6:
                logger.warning(f"{symbol}: Insufficient MACD variation")
                return False

            return True

        except Exception as e:
            logger.error(f"{symbol}: Error in MACD validation: {str(e)}")
            return False

    def _validate_emas(self, emas: Dict[str, pd.Series], symbol: str) -> bool:
        """Validate EMA calculations"""
        try:
            for name, ema in emas.items():
                if ema.isnull().any():
                    self.logger.error(f"{symbol}: NaN values in {name}")
                    return False
                    
                if (ema <= 0).any():
                    self.logger.error(f"{symbol}: Invalid values in {name}")
                    return False
                    
            return True
            
        except Exception as e:
            self.logger.error(f"{symbol}: Error validating EMAs: {str(e)}")
            return False

    def _validate_adx(self, adx: pd.Series, symbol: str) -> bool:
        """Validate ADX calculations"""
        try:
            warmup_period = self.indicator_config.ADX_PERIOD * 2  # Double period for proper ADX warmup
            
            # Check for NaN values after warmup
            adx_to_check = adx.iloc[warmup_period:]
            nan_count = adx_to_check.isnull().sum()
            
            if nan_count > 0:
                nan_percentage = (nan_count / len(adx_to_check)) * 100
                # Allow up to 5% NaN values after warmup
                if nan_percentage > 5:
                    self.logger.warning(f"{symbol}: High number of NaN values in ADX: {nan_percentage:.2f}%")
                    return False
            
            # Remove NaN values for range checking
            valid_values = adx_to_check.dropna()
            if len(valid_values) == 0:
                self.logger.error(f"{symbol}: No valid ADX values after warmup period")
                return False
            
            # Check value range
            if (valid_values < 0).any():
                self.logger.error(f"{symbol}: ADX values less than 0: {valid_values[valid_values < 0]}")
                return False
                
            if (valid_values > 100).any():
                self.logger.error(f"{symbol}: ADX values greater than 100: {valid_values[valid_values > 100]}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"{symbol}: Error validating ADX: {str(e)}")
            return False

    def _validate_volume(self, volume_data: Dict[str, pd.Series], symbol: str) -> bool:
        """Validate volume analysis"""
        try:
            for name, series in volume_data.items():
                # Check for NaN values
                nan_count = series.isnull().sum()
                if nan_count > 0:
                    nan_percentage = (nan_count / len(series)) * 100
                    if nan_percentage > 5:  # Allow up to 5% NaN values
                        self.logger.error(f"{symbol}: High number of NaN values in {name}: {nan_percentage:.2f}%")
                        return False
                
                # Remove NaN values for validation
                valid_values = series.dropna()
                
                if len(valid_values) == 0:
                    self.logger.error(f"{symbol}: No valid values in {name}")
                    return False
                
                # Specific validation for each volume metric
                if name == 'volume_ma':
                    if (valid_values < 0).any():
                        self.logger.error(f"{symbol}: Negative values in volume MA")
                        return False
                        
                elif name == 'relative_volume':
                    if (valid_values < 0).any():
                        self.logger.error(f"{symbol}: Negative relative volume values")
                        return False
                        
                elif name == 'volume_trend':
                    # Volume trend can be negative (decreasing volume)
                    pass
                    
            return True
            
        except Exception as e:
            self.logger.error(f"{symbol}: Error validating volume analysis: {str(e)}")
            return False

# END SECTION 3

# BEGIN SECTION 4: Multi-Timeframe Trend Validation

class MultiTimeframeTrendValidator:
    def __init__(self, indicator_config: IndicatorConfig, error_manager: ErrorManager):
        self.indicator_config = indicator_config
        self.error_manager = error_manager
        self.logger = logging.getLogger("TradingSystem")
        
        # Configuration for trend validation
        self.config = {
            '4h': {
                'period': 16,  # Number of 15m candles in 4h
                'trend_length': 10,  # Number of periods for trend calculation
                'weight': 0.5  # Weight in final score
            },
            '1h': {
                'period': 4,   # Number of 15m candles in 1h
                'trend_length': 24,
                'weight': 0.3
            },
            '15m': {
                'period': 1,
                'trend_length': 48,
                'weight': 0.2
            }
        }

    def validate_timeframes(self, df: pd.DataFrame, analysis: dict, symbol: str) -> dict:
        """
        Validate trend alignment across multiple timeframes
        Returns a dictionary with detailed scoring and analysis
        """
        try:
            results = {
                'score': 0,
                'alignments': {},
                'momentum': {},
                'is_valid': False,
                'details': {}
            }

            # 1. Resample data to different timeframes
            timeframe_data = self._resample_timeframes(df, symbol)
            if not timeframe_data:
                return results

            # 2. Calculate trends for each timeframe
            for tf, data in timeframe_data.items():
                trend_info = self._calculate_trend_metrics(
                    data, 
                    self.config[tf]['trend_length'],
                    symbol
                )
                
                if trend_info:
                    results['alignments'][tf] = trend_info
                    
                    # Calculate momentum for each timeframe
                    momentum = self._calculate_momentum(
                        data,
                        analysis,
                        tf,
                        symbol
                    )
                    results['momentum'][tf] = momentum

            # 3. Calculate trend alignment score
            alignment_score = self._calculate_alignment_score(results['alignments'])
            results['details']['alignment_score'] = alignment_score

            # 4. Calculate momentum alignment score
            momentum_score = self._calculate_momentum_score(results['momentum'])
            results['details']['momentum_score'] = momentum_score

            # 5. Calculate final score
            final_score = (alignment_score * 0.6) + (momentum_score * 0.4)
            results['score'] = round(final_score, 4)

            # 6. Validate result
            results['is_valid'] = self._validate_trend_setup(results)
            
            # Log detailed results
            self.logger.info(f"{symbol}: Timeframe validation results:")
            self.logger.info(f"Final Score: {results['score']}")
            self.logger.info(f"Alignment Score: {alignment_score}")
            self.logger.info(f"Momentum Score: {momentum_score}")
            self.logger.info(f"Valid Setup: {results['is_valid']}")

            return results

        except Exception as e:
            self.error_manager.record_error(
                symbol, 
                e, 
                {'context': 'timeframe_validation'}
            )
            return results

    def _resample_timeframes(self, df: pd.DataFrame, symbol: str) -> Dict[str, pd.DataFrame]:
        """Resample data to different timeframes with validation"""
        try:
            resampled = {}
            
            for tf, config in self.config.items():
                if tf == '15m':
                    resampled[tf] = df
                    continue

                # Resample to higher timeframe
                period = config['period']
                resampled_df = df.resample(
                    f'{period*15}min',
                    closed='left',
                    label='left'
                ).agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                })

                # Validate resampled data
                if len(resampled_df) < config['trend_length']:
                    self.logger.warning(
                        f"{symbol}: Insufficient {tf} candles: {len(resampled_df)} < {config['trend_length']}"
                    )
                    return {}

                resampled[tf] = resampled_df

            return resampled

        except Exception as e:
            self.logger.error(f"{symbol}: Error in timeframe resampling: {str(e)}")
            return {}

    def _calculate_trend_metrics(self, df: pd.DataFrame, length: int, symbol: str) -> dict:
        """Calculate comprehensive trend metrics"""
        try:
            # Get recent data for trend calculation
            recent_data = df.tail(length)
            
            # Price trends
            close_prices = recent_data['close']
            highs = recent_data['high']
            lows = recent_data['low']
            
            # Calculate linear regression
            x = np.arange(len(close_prices))
            slope, intercept = np.polyfit(x, close_prices, 1)
            
            # Calculate trend strength (R-squared)
            y_pred = slope * x + intercept
            r_squared = 1 - (np.sum((close_prices - y_pred) ** 2) / 
                           np.sum((close_prices - close_prices.mean()) ** 2))
            
            # Calculate higher highs and lower lows
            higher_highs = sum(1 for i in range(1, len(highs)) if highs.iloc[i] > highs.iloc[i-1])
            higher_lows = sum(1 for i in range(1, len(lows)) if lows.iloc[i] > lows.iloc[i-1])
            
            # Determine trend direction and strength
            trend_metrics = {
                'slope': slope,
                'r_squared': r_squared,
                'higher_highs_ratio': higher_highs / (len(highs) - 1),
                'higher_lows_ratio': higher_lows / (len(lows) - 1),
                'strength': abs(slope) * r_squared,
                'direction': 'up' if slope > 0 else 'down'
            }
            
            return trend_metrics
            
        except Exception as e:
            self.logger.error(f"{symbol}: Error calculating trend metrics: {str(e)}")
            return None

    def _calculate_momentum(self, df: pd.DataFrame, analysis: dict, timeframe: str, symbol: str) -> dict:
        """Calculate momentum metrics for each timeframe with enhanced volume calculation"""
        try:
            recent_data = df.tail(self.config[timeframe]['trend_length'])
            
            # RSI momentum
            if 'rsi' in analysis:
                rsi_values = analysis['rsi'].reindex(recent_data.index)
                rsi_momentum = rsi_values.diff().mean()
            else:
                rsi_momentum = 0
                
            # Enhanced volume momentum calculation
            volume_data = recent_data['volume'].replace(0, np.nan)  # Replace zeros with nan
            if len(volume_data.dropna()) < 2:  # Check if we have enough valid volume data
                volume_momentum = 0
            else:
                # Calculate volume SMA with minimal periods required
                volume_sma = volume_data.rolling(
                    window=min(5, len(volume_data)), 
                    min_periods=1
                ).mean()
                
                # Get first and last valid values
                first_valid = volume_sma.first_valid_index()
                last_valid = volume_sma.last_valid_index()
                
                if first_valid is not None and last_valid is not None:
                    volume_momentum = (
                        (volume_sma[last_valid] / volume_sma[first_valid]) - 1
                    ) if volume_sma[first_valid] != 0 else 0
                else:
                    volume_momentum = 0
            
            # Price momentum
            price_momentum = (
                (recent_data['close'].iloc[-1] / recent_data['close'].iloc[0]) - 1
            ) * 100
            
            # Log momentum values for debugging
            self.logger.debug(
                f"{symbol} {timeframe} Momentum - RSI: {rsi_momentum:.4f}, "
                f"Volume: {volume_momentum:.4f}, Price: {price_momentum:.4f}"
            )
            
            return {
                'rsi_momentum': rsi_momentum,
                'volume_momentum': volume_momentum,
                'price_momentum': price_momentum
            }
            
        except Exception as e:
            self.logger.error(f"{symbol}: Error calculating momentum: {str(e)}")
            return {
                'rsi_momentum': 0,
                'volume_momentum': 0,
                'price_momentum': 0
            }

    def _calculate_alignment_score(self, alignments: dict) -> float:
        """Calculate trend alignment score"""
        try:
            if not alignments or len(alignments) < len(self.config):
                return 0
                
            score = 0
            
            # Check trend direction alignment
            directions = [info['direction'] for info in alignments.values()]
            primary_direction = max(set(directions), key=directions.count)
            
            for tf, metrics in alignments.items():
                tf_score = 0
                
                # Direction alignment
                if metrics['direction'] == primary_direction:
                    tf_score += 0.4
                    
                # Trend strength
                tf_score += min(0.3, metrics['strength'])
                
                # R-squared quality
                tf_score += min(0.3, metrics['r_squared'])
                
                # Apply timeframe weight
                score += tf_score * self.config[tf]['weight']
                
            return round(score, 4)
            
        except Exception as e:
            self.logger.error(f"Error calculating alignment score: {str(e)}")
            return 0

    def _calculate_momentum_score(self, momentum_data: dict) -> float:
        """Calculate momentum alignment score across timeframes"""
        try:
            if not momentum_data or len(momentum_data) < len(self.config):
                return 0
                
            score = 0
            
            for tf, metrics in momentum_data.items():
                tf_score = 0
                
                # RSI momentum
                if metrics['rsi_momentum'] > 0:
                    tf_score += 0.4
                    
                # Volume momentum
                if metrics['volume_momentum'] > 0:
                    tf_score += 0.3
                    
                # Price momentum
                if metrics['price_momentum'] > 0:
                    tf_score += 0.3
                    
                # Apply timeframe weight
                score += tf_score * self.config[tf]['weight']
                
            return round(score, 4)
            
        except Exception as e:
            self.logger.error(f"Error calculating momentum score: {str(e)}")
            return 0

    def _analyze_divergences(self, results: dict) -> dict:
        """
        Analyze divergences between timeframes and their significance
        Returns detailed divergence analysis
        """
        try:
            divergence_info = {
                'has_divergence': False,
                'type': None,
                'significance': 0,
                'tradeable': False,
                'details': {}
            }
            
            if not results['alignments']:
                return divergence_info
                
            # Get directions for each timeframe
            h4_direction = results['alignments']['4h']['direction']
            h1_direction = results['alignments']['1h']['direction']
            m15_direction = results['alignments']['15m']['direction']
            
            # Get strength metrics
            h4_strength = results['alignments']['4h']['strength']
            h1_strength = results['alignments']['1h']['strength']
            m15_strength = results['alignments']['15m']['strength']
            
            # Check for divergences
            if h4_direction == h1_direction and h1_direction != m15_direction:
                divergence_info['has_divergence'] = True
                divergence_info['type'] = 'higher_tf_aligned'
                
                # Calculate significance based on strength
                significance = (h4_strength * 0.6 + h1_strength * 0.4) / m15_strength
                divergence_info['significance'] = min(significance, 10)  # Cap at 10
                
                # Determine if divergence is tradeable
                # Criteria: Strong higher timeframe alignment with weak 15m counter-trend
                if (h4_direction == 'up' and
                    h4_strength > 0.7 and
                    h1_strength > 0.5 and
                    m15_strength < 0.3):
                    divergence_info['tradeable'] = True
                    
            elif h4_direction != h1_direction:
                divergence_info['has_divergence'] = True
                divergence_info['type'] = 'major_tf_conflict'
                divergence_info['significance'] = (h4_strength + h1_strength) / 2
                
            # Add detailed metrics
            divergence_info['details'] = {
                '4h': {'direction': h4_direction, 'strength': h4_strength},
                '1h': {'direction': h1_direction, 'strength': h1_strength},
                '15m': {'direction': m15_direction, 'strength': m15_strength}
            }
            
            return divergence_info
            
        except Exception as e:
            self.logger.error(f"Error in divergence analysis: {str(e)}")
            return divergence_info

    def _validate_trend_setup(self, results: dict) -> bool:
        """
        Enhanced validation incorporating divergence analysis
        Returns True if setup is valid for trading
        """
        try:
            # Adjusted minimum score requirements
            MIN_TOTAL_SCORE = 0.55         # Lowered from 0.7 as total includes momentum
            MIN_ALIGNMENT_SCORE = 0.6      # Keep this as is - working well
            MIN_MOMENTUM_SCORE = 0.25      # Lowered from 0.5 - more realistic for choppy markets
            
            # Get base scores
            alignment_score = results['details']['alignment_score']
            momentum_score = results['details']['momentum_score']
            
            # Analyze divergences
            divergence_analysis = self._analyze_divergences(results)
            
            # Log divergence analysis
            self.logger.info(f"Divergence Analysis: {divergence_analysis}")
            
            # Regular validation path
            if results['score'] >= MIN_TOTAL_SCORE:
                if alignment_score >= MIN_ALIGNMENT_SCORE and momentum_score >= MIN_MOMENTUM_SCORE:
                    return True
                    
            # Alternative validation path for tradeable divergences
            if divergence_analysis['has_divergence'] and divergence_analysis['tradeable']:
                # Check if higher timeframes are strongly aligned
                h4_metrics = divergence_analysis['details']['4h']
                h1_metrics = divergence_analysis['details']['1h']
                
                if (h4_metrics['direction'] == 'up' and
                    h1_metrics['direction'] == 'up' and
                    alignment_score >= MIN_ALIGNMENT_SCORE and
                    divergence_analysis['significance'] > 2.0):  # Strong divergence
                    
                    self.logger.info("Valid setup through divergence pattern")
                    return True
                    
            return False
            
        except Exception as e:
            self.logger.error(f"Error validating trend setup: {str(e)}")
            return False

# BEGIN SECTION 5: Trading Strategy and Position Management

class TradingStrategy:
    def __init__(self, 
                 session: HTTP,
                 indicator_config: IndicatorConfig,
                 trading_config: TradingConfig,
                 error_manager: ErrorManager):
        self.session = session
        self.indicator_config = indicator_config
        self.trading_config = trading_config
        self.error_manager = error_manager
        self.timeout_config = TimeoutConfig()  # Add this line
        self.active_positions = {}
        self.metrics = PybitMetrics()
        self.data_cache = {}  # Add caching for rate limit management
        self.last_request_time = {}  # For rate limiting
        self.min_request_interval = 0.2  # 200ms between requests
        self.request_timeout = 30  # Add timeout setting
        self.max_retries = 3      # Add retry setting
        self.request_stats = {
            'total_requests': 0,
            'timeout_counts': 0,
            'average_response_time': 0,
            'slow_requests': []  # Track requests taking > 5s
        }
        
        # Initialize components
        self.price_validator = PriceValidation(session, error_manager)
        self.data_processor = DataProcessor(indicator_config, error_manager)
        self.indicators = TechnicalIndicators(indicator_config, error_manager)
        self.timeframe_validator = MultiTimeframeTrendValidator(indicator_config, error_manager)
        
        # Initialize database connector for saving analysis data
        try:
            self.db_connector = TradingDatabaseConnector()
            logger.info("Trading Strategy initialized with database connector")
        except Exception as e:
            logger.error(f"Failed to initialize database connector: {e}")
            self.db_connector = None

    def check_api_connection(self, symbol: str) -> bool:
        """Test API connection and response times"""
        try:
            start_time = time.time()
            response = self.session.get_server_time()
            latency = time.time() - start_time
            
            logger.info(f"API Connection Test - Latency: {latency:.3f}s")
            logger.info(f"API Status: {response.get('retCode')} - {response.get('retMsg', 'Unknown')}")
            
            return response.get('retCode') == 0
        except Exception as e:
            logger.error(f"API Connection Test Failed: {str(e)}")
            return False    

    @timeout_handler(timeout_duration=60)
    def get_market_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Fetch market data with enhanced chunking, validation, and error handling.
        Implements comprehensive timestamp validation and data quality checks.
        
        Args:
            symbol (str): Trading pair symbol
            
        Returns:
            Optional[pd.DataFrame]: Processed market data or None if error
        """
        try:
            # Initialize tracking variables
            current_time = time.time()
            start_time = current_time
            required_candles = 3500
            processed_klines = []
            total_candles = 0
            last_timestamp = None
            chunk_count = 0
            retry_count = 0
            consecutive_small_chunks = 0
            chunk_size = 1000
            chunk_timestamps = set()  # Track unique timestamps

            # Rate limit check
            if symbol in self.last_request_time:
                time_since_last = current_time - self.last_request_time[symbol]
                if time_since_last < self.min_request_interval:
                    sleep_time = self.min_request_interval - time_since_last
                    time.sleep(sleep_time)

            logger.info(f"{symbol}: Starting data fetch at {datetime.now()}")

            while retry_count < self.timeout_config.max_retries:
                try:
                    timeout = self.timeout_config.get_timeout(retry_count)
                    logger.info(f"{symbol}: Attempt {retry_count + 1} with timeout {timeout}s")

                    while total_candles < required_candles:
                        chunk_start = time.time()
                        chunk_count += 1
                        
                        logger.debug(f"{symbol}: Requesting chunk {chunk_count} - Total candles so far: {total_candles}")
                        
                        # Build request parameters
                        request_params = {
                            'category': 'linear',
                            'symbol': symbol,
                            'interval': 15,
                            'limit': chunk_size,
                            'timeout': timeout
                        }
                        
                        # Add start parameter for pagination if we have a last timestamp
                        if last_timestamp:
                            # Get next chunk's time window
                            window_size = chunk_size * 15 * 60 * 1000  # chunk_size candles * 15 min * 60 sec * 1000 ms
                            request_params['start'] = last_timestamp - window_size
                            request_params['end'] = last_timestamp - 1  # Exclude the last timestamp

                            logger.debug(f"{symbol}: Requesting chunk from {request_params['start']} to {request_params['end']}")
                        
                        try:
                            # Make API request
                            response = self.session.get_kline(**request_params)
                            chunk_time = time.time() - chunk_start
                            
                            logger.debug(f"{symbol}: Chunk {chunk_count} received in {chunk_time:.2f}s")
                            
                            # Validate response
                            if not response or response.get('retCode') != 0:
                                error_msg = response.get('retMsg', 'Unknown error') if response else 'Empty response'
                                logger.error(f"{symbol}: Failed to fetch kline data: {error_msg}")
                                break
                            
                            # Get klines data
                            klines = response['result']['list']

                            # Add chunk boundary validation
                            current_chunk_timestamps = set()
                            for kline in klines:
                                timestamp = kline[0]
                                if timestamp in current_chunk_timestamps:
                                    logger.warning(f"{symbol}: Intra-chunk duplicate detected: {timestamp}")
                                    continue
                                current_chunk_timestamps.add(timestamp)
                            
                            # Handle empty response
                            if not klines:
                                if total_candles >= required_candles * 0.8:  # Allow slight shortfall
                                    logger.info(f"{symbol}: No more data available, but have sufficient candles: {total_candles}")
                                    break
                                else:
                                    logger.error(f"{symbol}: No data received for chunk {chunk_count}")
                                    break

                            # Log received data
                            logger.debug(f"{symbol}: Received {len(klines)} candles in chunk {chunk_count}")
                            
                            # Process and validate each kline
                            valid_klines = []
                            for kline in klines:
                                timestamp = self.data_processor.validate_timestamp(kline[0], symbol)
                                if timestamp is None:
                                    continue
                                    
                                # Check for duplicate timestamps
                                if timestamp in chunk_timestamps:
                                    logger.warning(f"{symbol}: Duplicate timestamp detected: {timestamp}")
                                    continue
                                    
                                # Validate strictly decreasing sequence
                                if last_timestamp is not None:
                                    if timestamp >= last_timestamp:
                                        logger.warning(f"{symbol}: Non-decreasing timestamp detected - Current: {timestamp}, Last: {last_timestamp}")
                                        continue
                                
                                # Additional price and volume validations
                                try:
                                    open_price = float(kline[1])
                                    high_price = float(kline[2])
                                    low_price = float(kline[3])
                                    close_price = float(kline[4])
                                    volume = float(kline[5])
                                    
                                    # Price relationship validation
                                    if not (low_price <= open_price <= high_price and 
                                        low_price <= close_price <= high_price):
                                        logger.warning(f"{symbol}: Invalid OHLC relationships detected")
                                        continue
                                        
                                    # Volume validation
                                    if volume <= 0:
                                        logger.warning(f"{symbol}: Invalid volume detected")
                                        continue
                                        
                                except (ValueError, TypeError) as e:
                                    logger.warning(f"{symbol}: Invalid numeric values in kline")
                                    continue
                                
                                chunk_timestamps.add(timestamp)
                                last_timestamp = timestamp
                                valid_klines.append(kline)

                            # Update processed klines
                            processed_klines.extend(valid_klines)
                            total_candles = len(processed_klines)
                            
                            # Check if we have enough valid candles
                            if total_candles >= required_candles:
                                logger.info(f"{symbol}: Required candles collected: {total_candles}")
                                break
                                
                            # Reset consecutive small chunks counter on successful chunk
                            consecutive_small_chunks = 0
                            
                            # Rate limiting sleep
                            time.sleep(0.1)
                            
                        except Exception as e:
                            error_context = {
                                'stage': 'chunk_processing',
                                'chunk_number': chunk_count,
                                'total_candles': total_candles,
                                'last_timestamp': last_timestamp,
                                'request_params': request_params,
                                'response_time': time.time() - chunk_start
                            }
                            self.error_manager.record_error(symbol, e, error_context)
                            logger.error(f"{symbol}: Error fetching chunk {chunk_count}: {str(e)}")
                            raise

                    # Check if we have sufficient data
                    if total_candles >= required_candles * 0.8:
                        break
                        
                    retry_count += 1
                    if retry_count < self.timeout_config.max_retries:
                        wait_time = 2 ** retry_count
                        logger.warning(f"{symbol}: Retry {retry_count}/{self.timeout_config.max_retries} - waiting {wait_time}s")
                        time.sleep(wait_time)
                        
                except Exception as e:
                    logger.error(f"{symbol}: Error in retry loop: {str(e)}")
                    retry_count += 1
                    if retry_count < self.timeout_config.max_retries:
                        time.sleep(2 ** retry_count)
                    continue

            if not processed_klines:
                logger.error(f"{symbol}: Failed to fetch any data after {self.timeout_config.max_retries} retries")
                return None

            # Create DataFrame from processed klines
            df = self._create_dataframe(processed_klines, symbol)
            if df is None:
                return None
                
            # Process and validate data
            df = self.data_processor.validate_and_prepare_data(df, symbol)
            if df is None:
                return None

            # Update metrics and timing
            total_time = time.time() - start_time
            self.last_request_time[symbol] = time.time()
            self.metrics.log_kline_request(
                symbol=symbol,
                success=True,
                response_time=total_time
            )
            
            logger.info(f"{symbol}: Data fetch completed in {total_time:.2f}s")
            return df
            
        except TimeoutError:
            total_time = time.time() - start_time
            logger.error(f"{symbol}: Request timed out after {total_time:.2f}s")
            error_context = {
                'total_duration': total_time,
                'retry_count': retry_count if 'retry_count' in locals() else 0,
                'last_chunk': chunk_count if 'chunk_count' in locals() else 0,
                'total_candles': total_candles if 'total_candles' in locals() else 0
            }
            self.metrics.log_kline_request(
                symbol=symbol,
                success=False,
                response_time=total_time,
                rate_limited=True
            )
            self.error_manager.record_error(
                symbol,
                TimeoutError("Request timed out"),
                error_context
            )
            return None
            
        except Exception as e:
            total_time = time.time() - start_time
            error_context = {
                'total_duration': total_time,
                'retry_count': retry_count if 'retry_count' in locals() else 0,
                'stage': 'data_fetch',
                'last_chunk': chunk_count if 'chunk_count' in locals() else 0,
                'total_candles': total_candles if 'total_candles' in locals() else 0,
                'last_timestamp': last_timestamp if 'last_timestamp' in locals() else None
            }
            
            # Handle rate limit errors
            if "too many requests" in str(e).lower():
                self.metrics.log_kline_request(
                    symbol=symbol,
                    success=False,
                    response_time=total_time,
                    rate_limited=True
                )
                error_context['error_type'] = 'rate_limit'
            else:
                self.metrics.log_kline_request(
                    symbol=symbol,
                    success=False,
                    response_time=total_time
                )
                error_context['error_type'] = 'general_error'
                
            self.error_manager.record_error(symbol, e, error_context)
            logger.error(f"{symbol}: Error in get_market_data: {str(e)}")
            return None
        
    def _create_dataframe(self, klines: list, symbol: str) -> Optional[pd.DataFrame]:
        """
        Create and validate DataFrame from processed klines
        """
        try:
            if not klines:
                logger.error(f"{symbol}: No valid klines data")
                return None
                
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'
            ])
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp']), unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Sort index to ensure chronological order
            df = df.sort_index(ascending=False)
            
            # Validate no duplicate indices
            if df.index.duplicated().any():
                logger.warning(f"{symbol}: Duplicate timestamps found, keeping first occurrence")
                df = df[~df.index.duplicated(keep='first')]
            
            # Convert columns to numeric
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
            return df
            
        except Exception as e:
            logger.error(f"{symbol}: Error creating DataFrame: {str(e)}")
            return None

    def analyze_market_data(self, df: pd.DataFrame, symbol: str) -> Optional[dict]:
        """Perform comprehensive market analysis"""
        try:
            # Calculate all indicators
            analysis = {}

            # Add close price to analysis
            analysis['close'] = df['close']

            # RSI
            analysis['rsi'] = self.indicators.calculate_rsi(df, symbol)
            if analysis['rsi'] is None:
                return None
                
            # MACD
            analysis['macd'], analysis['signal'] = self.indicators.calculate_macd(df, symbol)
            if analysis['macd'] is None:
                return None
                
            # EMAs
            emas = self.indicators.calculate_emas(df, symbol)
            if not emas:
                return None
            analysis.update(emas)
            
            # ADX with DI+/DI-
            try:
                adx, plus_di, minus_di = self.indicators.calculate_adx(df, symbol)
                if adx is not None and plus_di is not None and minus_di is not None:
                    analysis['adx'] = adx
                    analysis['plus_di'] = plus_di
                    analysis['minus_di'] = minus_di
                    logger.debug(f"{symbol}: ADX calculation successful - ADX: {adx.iloc[-1]:.2f}, DI+: {plus_di.iloc[-1]:.2f}, DI-: {minus_di.iloc[-1]:.2f}")
                else:
                    logger.error(f"{symbol}: ADX calculation returned None values")
                    return None
            except Exception as e:
                logger.error(f"{symbol}: Error calculating ADX: {str(e)}")
                return None
                    
            # Volume
            volume_analysis = self.indicators.analyze_volume(df, symbol)
            if not volume_analysis:
                return None
            analysis.update(volume_analysis)
            
            return analysis
            
        except Exception as e:
            self.error_manager.record_error(symbol, e, {'context': 'market_analysis'})
            return None
        
    def calculate_rsi(self, df: pd.DataFrame, symbol: str) -> Optional[pd.Series]:
        """Calculate RSI with comprehensive NaN handling"""
        try:
            # Validate input
            if 'close' not in df.columns:
                raise ValueError("Close price data required for RSI calculation")

            # Calculate price changes
            delta = df['close'].diff()
            
            # Create separate gain/loss series with proper initialization
            gains = pd.Series(0.0, index=delta.index)
            losses = pd.Series(0.0, index=delta.index)
            
            # Populate gains and losses, handling potential NaN values
            gains[delta > 0] = delta[delta > 0]
            losses[delta < 0] = -delta[delta < 0]
            
            # Initialize with simple moving average
            avg_gain = gains.rolling(
                window=self.indicator_config.RSI_PERIOD,
                min_periods=self.indicator_config.RSI_PERIOD
            ).mean()
            avg_loss = losses.rolling(
                window=self.indicator_config.RSI_PERIOD,
                min_periods=self.indicator_config.RSI_PERIOD
            ).mean()
            
            # Apply Wilder's smoothing after initial period
            for i in range(self.indicator_config.RSI_PERIOD, len(gains)):
                avg_gain.iloc[i] = (avg_gain.iloc[i-1] * 
                    (self.indicator_config.RSI_PERIOD-1) + gains.iloc[i]) / self.indicator_config.RSI_PERIOD
                avg_loss.iloc[i] = (avg_loss.iloc[i-1] * 
                    (self.indicator_config.RSI_PERIOD-1) + losses.iloc[i]) / self.indicator_config.RSI_PERIOD
            
            # Handle division by zero
            avg_loss = avg_loss.replace(0, 0.0001)
            
            # Calculate RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            # Validate results
            rsi = rsi.round(4)
            if not self._validate_rsi(rsi, symbol):
                return None
                
            return rsi
            
        except Exception as e:
            self.error_manager.record_error(symbol, e, {'context': 'RSI calculation'})
            return None
        
    def calculate_rsi_score(self, rsi_value: float, rsi_momentum: float) -> dict:
        """
        Calculate RSI score based on value and momentum
        Returns a dictionary with detailed scoring breakdown
        """
        try:
            score_details = {
                'range_score': 0,
                'momentum_score': 0,
                'total_score': 0,
                'components': {}
            }
            
            # 1. Range Score (0-2 points) - OPTIMIZED: Look for oversold RSI 30-40 for longs
            if 30 <= rsi_value <= 40:
                score_details['range_score'] = 2.0
                score_details['components']['range'] = 'optimal_oversold'
            elif 25 <= rsi_value < 30 or 40 < rsi_value <= 45:
                score_details['range_score'] = 1.0
                score_details['components']['range'] = 'moderate_oversold'
            else:
                score_details['range_score'] = 0
                score_details['components']['range'] = 'out_of_range'
                
            # 2. Momentum Score (0-1 point)
            if rsi_momentum > 0:  # Rising momentum
                score_details['momentum_score'] = 1.0
                score_details['components']['momentum'] = 'rising'
            else:
                score_details['momentum_score'] = 0
                score_details['components']['momentum'] = 'falling'
            
            # Calculate total score
            score_details['total_score'] = score_details['range_score'] + score_details['momentum_score']
            
            # Add metadata
            score_details['components']['rsi_value'] = rsi_value
            score_details['components']['rsi_momentum'] = rsi_momentum
            
            logger.debug(f"RSI Score calculated: {score_details}")
            return score_details
            
        except Exception as e:
            logger.error(f"Error calculating RSI score: {str(e)}")
            return {
                'range_score': 0,
                'momentum_score': 0,
                'total_score': 0,
                'components': {'error': str(e)}
            }

    def is_valid_rsi_setup(self, score_details: dict) -> Tuple[bool, str]:
        """
        Validate if the RSI setup meets minimum criteria for entry
        """
        try:
            min_total_score = 1.0  # Minimum required total score
            
            if score_details['total_score'] < min_total_score:
                return False, f"Total score {score_details['total_score']} below minimum {min_total_score}"
                
            if score_details['range_score'] < 1.0:
                return False, "RSI not in favorable range"
                
            return True, "Valid RSI setup"
            
        except Exception as e:
            logger.error(f"Error validating RSI setup: {str(e)}")
            return False, f"Error in validation: {str(e)}"

    def check_rsi_conditions(self, df: pd.DataFrame, analysis: dict) -> Tuple[bool, dict]:
        """
        Check RSI conditions using the scoring model
        """
        try:
            # Get current and previous RSI values
            current_rsi = analysis['rsi'].iloc[-1]
            prev_rsi = analysis['rsi'].iloc[-2]
            
            # Calculate RSI momentum
            rsi_momentum = current_rsi - prev_rsi
            
            # Calculate RSI score
            score_details = self.calculate_rsi_score(current_rsi, rsi_momentum)
            
            # Validate setup
            is_valid, reason = self.is_valid_rsi_setup(score_details)
            
            # Add validation reason to score details
            score_details['validation'] = {
                'is_valid': is_valid,
                'reason': reason
            }
            
            # Log scoring details
            logger.info(f"RSI Score Details: {score_details}")
            
            return is_valid, score_details
            
        except Exception as e:
            logger.error(f"Error in RSI scoring: {str(e)}")
            return False, {}
        

    def calculate_adx_score(self, df: pd.DataFrame, analysis: dict) -> dict:
        """
        Calculate ADX score with DI+/DI- trend strength filtering
        Returns a comprehensive scoring dictionary
        
        Score Components (Total 3 points):
        - ADX Strength (0-1 point): Based on ADX value
        - Trend Direction (0-1 point): Based on DI+ vs DI- relationship
        - Trend Consistency (0-1 point): Based on DI+/DI- spread
        """
        try:
            # Get current ADX values from analysis
            current_adx = analysis['adx'].iloc[-1]
            current_plus_di = analysis['plus_di'].iloc[-1]
            current_minus_di = analysis['minus_di'].iloc[-1]
            
            score_details = {
                'strength_score': 0,
                'direction_score': 0,
                'consistency_score': 0,
                'total_score': 0,
                'components': {
                    'adx': float(current_adx),
                    'plus_di': float(current_plus_di),
                    'minus_di': float(current_minus_di),
                    'di_spread': float(abs(current_plus_di - current_minus_di))
                }
            }
            
            # 1. ADX Strength Score (0-1 point)
            if current_adx >= 40:
                score_details['strength_score'] = 1.0
                score_details['components']['strength'] = 'very_strong'
            elif current_adx >= 25:
                score_details['strength_score'] = 0.5
                score_details['components']['strength'] = 'strong'
            else:
                score_details['components']['strength'] = 'weak'
                
            # 2. Trend Direction Score (0-1 point)
            di_diff = current_plus_di - current_minus_di
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
            di_spread = abs(current_plus_di - current_minus_di)
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
            
            logger.debug(f"ADX Score calculated: {score_details}")
            return score_details
            
        except Exception as e:
            logger.error(f"Error calculating ADX score: {str(e)}")
            return self._get_default_adx_score()

    def _get_default_adx_score(self) -> dict:
        """Return default ADX score structure"""
        return {
            'strength_score': 0,
            'direction_score': 0,
            'consistency_score': 0,
            'total_score': 0,
            'components': {
                'adx': 0,
                'plus_di': 0,
                'minus_di': 0,
                'di_spread': 0,
                'strength': 'error',
                'direction': 'error',
                'consistency': 'error'
            }
        }

    def is_valid_adx_setup(self, score_details: dict) -> Tuple[bool, str]:
        """
        Validate if the ADX setup meets minimum criteria
        """
        try:
            min_total_score = 1.5  # Minimum required total score
            
            if score_details['total_score'] < min_total_score:
                return False, f"Total score {score_details['total_score']} below minimum {min_total_score}"
                
            if score_details['direction_score'] == 0:
                return False, "Not in bullish trend"
                
            if score_details['strength_score'] == 0:
                return False, "Insufficient trend strength"
                
            return True, "Valid ADX setup"
            
        except Exception as e:
            logger.error(f"Error validating ADX setup: {str(e)}")
            return False, f"Error in validation: {str(e)}"

    def check_adx_conditions(self, df: pd.DataFrame, analysis: dict) -> Tuple[bool, dict]:
        """
        Check ADX conditions using the scoring model
        """
        try:
            # Calculate ADX score
            score_details = self.calculate_adx_score(df, analysis)
            
            # Validate setup
            is_valid, reason = self.is_valid_adx_setup(score_details)
            
            # Add validation reason to score details
            score_details['validation'] = {
                'is_valid': is_valid,
                'reason': reason
            }
            
            # Log scoring details
            logger.info(f"ADX Score Details: {score_details}")
            
            return is_valid, score_details
            
        except Exception as e:
            logger.error(f"Error in ADX scoring: {str(e)}")
            return False, {}

    def check_entry_conditions(self, df: pd.DataFrame, analysis: dict, symbol: str = "") -> Tuple[bool, str]:
        """
        OPTIMIZED STRATEGY: Asset-Specific LONG/SHORT Strategies

        LONG Entry:
        1. RSI in oversold range (asset-specific) + rising
        2. EMA50 > EMA200 (Golden Cross - uptrend confirmation)
        3. Volume Ratio > asset-specific threshold

        SHORT Entry:
        1. RSI >= overbought threshold (asset-specific) + falling
        2. Price > EMA200 (in uptrend - short pullbacks)
        3. Volume Ratio > asset-specific threshold

        Based on comprehensive Q1/Q4 2024 optimization across 58 assets
        """
        try:
            if df.empty or len(df) < 2:
                logger.warning("Insufficient data for entry condition analysis")
                return False, ""

            # Get asset-specific configurations
            volume_threshold = self.indicator_config.ASSET_VOLUME_THRESHOLDS.get(symbol, None)
            rsi_range = self.indicator_config.ASSET_RSI_RANGES.get(symbol, None)
            strategy_type = self.indicator_config.ASSET_STRATEGIES.get(symbol, None)

            # Check if asset is in monitoring-only mode (data collection without trading)
            is_trading_enabled = symbol in self.indicator_config.TRADING_ENABLED

            # If asset not configured at all, skip silently
            if volume_threshold is None or rsi_range is None or strategy_type is None:
                # This is a monitoring-only asset - use default parameters for data collection
                logger.debug(f"{symbol}: Monitoring mode - data collected, no trading signals")
                return False, ""

            # If asset is configured but not enabled for trading, log but don't signal
            if not is_trading_enabled:
                logger.debug(f"{symbol}: MONITORING ONLY - Data collected for market intelligence")
                return False, ""

            # Get current and previous values
            current_rsi = analysis['rsi'].iloc[-1]
            prev_rsi = analysis['rsi'].iloc[-2]
            rsi_momentum = current_rsi - prev_rsi

            # Get EMA values
            current_ema_50 = analysis['ema_50'].iloc[-1]
            current_ema_200 = analysis['ema_200'].iloc[-1]
            current_price = analysis['close'].iloc[-1]

            # Get volume ratio
            current_volume_ratio = analysis['relative_volume'].iloc[-1]

            # Volume confirmation (applies to both LONG and SHORT)
            volume_condition = current_volume_ratio > volume_threshold

            # Initialize variables
            long_signal = False
            short_signal = False

            # ===== CHECK LONG SIGNALS (if enabled for this asset) =====
            if strategy_type in ['LONG', 'BOTH']:
                # LONG CONDITIONS
                rsi_oversold = (rsi_range['min'] <= current_rsi <= rsi_range['max']) and (rsi_momentum > 0)
                golden_cross = current_ema_50 > current_ema_200

                long_signal = rsi_oversold and golden_cross and volume_condition

                if long_signal:
                    logger.info(f"{symbol}: [LONG SIGNAL] RSI{rsi_range['min']}-{rsi_range['max']}+rising, "
                              f"GoldenCross, Vol>{volume_threshold}")
                    logger.info(f"  RSI: {current_rsi:.2f} (momentum: {rsi_momentum:+.2f})")
                    logger.info(f"  EMA50: {current_ema_50:.2f} > EMA200: {current_ema_200:.2f}")
                    logger.info(f"  Volume Ratio: {current_volume_ratio:.2f} > {volume_threshold}")
                    return True, "Buy"

            # ===== CHECK SHORT SIGNALS (if enabled for this asset) =====
            if strategy_type in ['SHORT', 'BOTH']:
                # SHORT CONDITIONS
                rsi_overbought = (current_rsi >= rsi_range['min']) and (rsi_momentum < 0)
                in_uptrend = current_price > current_ema_200  # Short pullbacks in uptrends

                short_signal = rsi_overbought and in_uptrend and volume_condition

                if short_signal:
                    logger.info(f"{symbol}: [SHORT SIGNAL] RSI{rsi_range['min']}+falling, "
                              f"InUptrend, Vol>{volume_threshold}")
                    logger.info(f"  RSI: {current_rsi:.2f} (momentum: {rsi_momentum:+.2f})")
                    logger.info(f"  Price: {current_price:.2f} > EMA200: {current_ema_200:.2f}")
                    logger.info(f"  Volume Ratio: {current_volume_ratio:.2f} > {volume_threshold}")
                    return True, "Sell"

            # No signals met
            logger.debug(f"{symbol}: No entry signals (Type: {strategy_type}, "
                        f"RSI: {current_rsi:.2f}, Vol: {current_volume_ratio:.2f})")
            return False, ""

        except Exception as e:
            logger.error(f"Error checking entry conditions for {symbol}: {str(e)}")
            logger.error(traceback.format_exc())
            return False, ""

    def calculate_position_size(self, symbol: str, current_price: float) -> Optional[float]:
        """Calculate valid position size"""
        try:
            instrument = self.price_validator.get_instrument_info(symbol)
            if not instrument:
                return None

            lot_size_filter = instrument['lotSizeFilter']
            min_qty = float(lot_size_filter['minOrderQty'])
            max_qty = float(lot_size_filter['maxOrderQty'])
            qty_step = float(lot_size_filter['qtyStep'])
            
            # Calculate base quantity
            base_quantity = self.trading_config.USDT_VALUE / current_price
            
            # Round to valid step size
            steps = base_quantity / qty_step
            valid_quantity = float(int(steps)) * qty_step
            
            # Validate against limits
            if valid_quantity < min_qty:
                logger.warning(f"{symbol}: Calculated quantity below minimum")
                return None
            if valid_quantity > max_qty:
                valid_quantity = max_qty
            
            # Validate notional value
            order_value = valid_quantity * current_price
            if order_value < float(lot_size_filter.get('minNotional', 0)):
                logger.warning(f"{symbol}: Order value below minimum notional")
                return None
                
            return round(valid_quantity, 8)
            
        except Exception as e:
            self.error_manager.record_error(symbol, e, {'context': 'position_size_calculation'})
            return None

    def place_order(self, symbol: str, side: str, quantity: float) -> Optional[str]:
        """Place order with retry logic"""
        for attempt in range(self.trading_config.MAX_ORDER_RETRIES):
            try:
                response = self.session.place_order(
                    category="linear",
                    symbol=symbol,
                    side=side,
                    orderType="Market",
                    qty=str(quantity)
                )
                
                if response.get('retCode') == 0:
                    logger.info(f"{symbol}: Order placed successfully on attempt {attempt + 1}")
                    return response['result']['orderId']
                
                error_msg = response.get('retMsg', 'Unknown error')
                logger.error(f"{symbol}: Order placement failed: {error_msg}")
                
                if attempt < self.trading_config.MAX_ORDER_RETRIES - 1:
                    time.sleep(self.trading_config.RETRY_DELAY)
                    continue
                
            except Exception as e:
                self.error_manager.record_error(symbol, e, {'context': 'order_placement'})
                if attempt < self.trading_config.MAX_ORDER_RETRIES - 1:
                    time.sleep(self.trading_config.RETRY_DELAY)
                    continue
                
        return None

    def set_tp_sl(self, symbol: str, position: Position) -> bool:
        """Set Take Profit and Stop Loss"""
        try:
            # Validate mark price
            is_valid, mark_price, error = self.price_validator.validate_mark_price(symbol)
            if not is_valid:
                logger.error(f"{symbol}: Failed to get mark price: {error}")
                return False

            # Calculate TP/SL prices
            if position.side == "Buy":
                tp_price = position.entry_price * (1 + self.trading_config.LONG_TP_PERCENTAGE/100)
                sl_price = position.entry_price * (1 - self.trading_config.LONG_SL_PERCENTAGE/100)
            else:
                tp_price = position.entry_price * (1 - self.trading_config.SHORT_TP_PERCENTAGE/100)
                sl_price = position.entry_price * (1 + self.trading_config.SHORT_SL_PERCENTAGE/100)

            # Place TP/SL orders
            response = self.session.set_trading_stop(
                category="linear",
                symbol=symbol,
                takeProfit=str(round(tp_price, 8)),
                stopLoss=str(round(sl_price, 8)),
                tpTriggerBy="MarkPrice",
                slTriggerBy="MarkPrice",
                positionIdx=0
            )
            
            if response.get('retCode') == 0:
                position.tp_price = tp_price
                position.sl_price = sl_price
                logger.info(f"{symbol}: TP/SL set successfully")
                return True
            
            logger.error(f"{symbol}: Failed to set TP/SL: {response.get('retMsg')}")
            return False

        except Exception as e:
            self.error_manager.record_error(symbol, e, {'context': 'tp_sl_setting'})
            return False

    def monitor_positions(self):
        """Monitor and update active positions"""
        try:
            for symbol in list(self.active_positions.keys()):
                try:
                    response = self.session.get_positions(
                        category="linear",
                        symbol=symbol
                    )

                    if response.get('retCode') != 0:
                        logger.error(f"{symbol}: Failed to get position info")
                        continue

                    position_data = response['result']['list']
                    if not position_data or float(position_data[0]['size']) == 0:
                        logger.info(f"{symbol}: Position closed")
                        del self.active_positions[symbol]
                        continue

                    # Update position information
                    position = self.active_positions[symbol]
                    
                    # Check if TP/SL needs to be updated
                    if not position.tp_price or not position.sl_price:
                        self.set_tp_sl(symbol, position)

                except Exception as e:
                    self.error_manager.record_error(symbol, e, {'context': 'position_monitoring'})

        except Exception as e:
            logger.error(f"Error in position monitoring: {str(e)}")

    def execute_strategy(self, symbol: str):
        """Main strategy execution"""
        try:
            # Skip if in cooldown
            if self.error_manager.should_cool_down(symbol, ErrorType.API_ERROR):
                logger.warning(f"{symbol}: Skipping - In cooldown period")
                return

            # Check active positions
            if symbol in self.active_positions:
                logger.debug(f"{symbol}: Position already exists")
                return

            # Get market data
            logger.info(f"{symbol}: Fetching market data...")  # Added
            df = self.get_market_data(symbol)
            if df is None or df.empty:
                return
                    
            # Analyze market data
            logger.info(f"{symbol}: Starting market analysis...")  # Added
            analysis = self.analyze_market_data(df, symbol)
            if not analysis:
                logger.warning(f"{symbol}: Analysis returned no results")  # Added
                return
            
            # Log analysis results
            logger.debug(f"{symbol}: Analysis results:")  # Added
            logger.debug(f"RSI: {analysis.get('rsi', 'N/A').iloc[-1]:.2f}")  # Added
            logger.debug(f"ADX: {analysis.get('adx', 'N/A').iloc[-1]:.2f}")  # Added
            logger.debug(f"Volume: {analysis.get('relative_volume', 'N/A').iloc[-1]:.2f}x")  # Added
            
            # **SAVE ANALYSIS DATA TO DATABASE**
            if self.db_connector is None:
                logger.warning(f"{symbol}: Database connector not available, skipping data save")
            else:
                try:
                    # Extract indicator values
                    rsi_value = float(analysis['rsi'].iloc[-1]) if 'rsi' in analysis else 50.0
                    adx_value = float(analysis['adx'].iloc[-1]) if 'adx' in analysis else 25.0
                    volume_value = float(analysis['relative_volume'].iloc[-1]) if 'relative_volume' in analysis else 1.0
                    
                    # Calculate score based on indicators
                    score = 0.0
                    if rsi_value < 30:  # Oversold - bullish signal
                        score += 1.5
                    elif rsi_value > 70:  # Overbought - bearish signal  
                        score += 1.0
                    else:
                        score += 0.5
                        
                    if adx_value > 25:  # Strong trend
                        score += 1.0
                    score += min(volume_value / 2.0, 1.5)  # Volume bonus, capped at 1.5
                    
                    # Determine signal type based on indicators
                    if rsi_value < 35 and adx_value > 25:
                        signal_type = 'bullish'
                    elif rsi_value > 65 and adx_value > 25:
                        signal_type = 'bearish'
                    else:
                        signal_type = 'neutral'
                    
                    # Calculate price change estimate
                    current_price = float(df['close'].iloc[-1])
                    price_change = ((current_price - float(df['close'].iloc[-20])) / float(df['close'].iloc[-20])) * 100 if len(df) >= 20 else 0.0
                    
                    # Fetch real-time price data from Bybit
                    try:
                        price_data = self.db_connector.fetch_price_data(symbol)
                        if price_data:
                            current_price_real = price_data['current_price']
                            high_24h = price_data['high_24h']
                            low_24h = price_data['low_24h']
                            price_change_24h = price_data['price_change_24h']
                        else:
                            current_price_real = current_price
                            high_24h = None
                            low_24h = None
                            price_change_24h = None
                    except:
                        current_price_real = current_price
                        high_24h = None
                        low_24h = None
                        price_change_24h = None
                    
                    # Save to database
                    success = self.db_connector.insert_market_distribution(
                        symbol=symbol,
                        rsi=rsi_value,
                        adx=adx_value,
                        volume=volume_value,
                        score=score,
                        signal_type=signal_type,
                        price_change=price_change,
                        current_price=current_price_real,
                        high_24h=high_24h,
                        low_24h=low_24h,
                        price_change_24h=price_change_24h
                    )
                    
                    if success:
                        logger.info(f"{symbol}: ✅ Market data saved to database (Score: {score:.2f}, Type: {signal_type})")
                    else:
                        logger.warning(f"{symbol}: ❌ Failed to save market data to database")
                        
                except Exception as e:
                    logger.error(f"{symbol}: Error saving market data to database: {e}")
            
            # Check entry conditions
            logger.info(f"{symbol}: Checking entry conditions...")  # Added
            should_enter, side = self.check_entry_conditions(df, analysis, symbol)
            logger.info(f"{symbol}: Entry decision - Should enter: {should_enter}, Side: {side}")  # Added

            if not should_enter:
                return

            # Validate entry price
            current_price = float(df['close'].iloc[-1])
            is_valid, price_str, _ = self.price_validator.validate_entry_price(
                symbol, current_price)
            if not is_valid:
                logger.error(f"{symbol}: Invalid entry price: {price_str}")
                return

            # Calculate position size
            quantity = self.calculate_position_size(symbol, current_price)
            if not quantity:
                return

            # Place order
            order_id = self.place_order(symbol, side, quantity)
            if not order_id:
                return

            # Create position object
            position = Position(
                symbol=symbol,
                entry_price=current_price,
                quantity=quantity,
                side=side,
                entry_time=datetime.now(),
                order_id=order_id
            )

            # Set TP/SL
            if not self.set_tp_sl(symbol, position):
                logger.error(f"{symbol}: Failed to set TP/SL")

            # Add to active positions
            self.active_positions[symbol] = position
            logger.info(f"{symbol}: Successfully opened position")

        except Exception as e:
            self.error_manager.record_error(symbol, e, {'context': 'strategy_execution'})

# END SECTION 4

# BEGIN SECTION 5: Main Execution and System Control

class TradingSystem:
    def __init__(self, api_key: str, api_secret: str):
        """Initialize the complete trading system"""
        try:
            logger.info("Initializing Trading System...")
            
            # Initialize session
            self.session = HTTP(
                testnet=False,
                api_key=api_key,
                api_secret=api_secret
            )
            
            # Initialize configurations
            self.indicator_config = IndicatorConfig()
            self.trading_config = TradingConfig()
            self.error_manager = ErrorManager()
            
            # Initialize trading strategy
            self.strategy = TradingStrategy(
                session=self.session,
                indicator_config=self.indicator_config,
                trading_config=self.trading_config,
                error_manager=self.error_manager
            )

            # Initialize state tracking
            self.cycle_state = {
                'cycle_id': None,
                'in_progress': False,
                'last_processed_pair': None,
                'unprocessed_pairs': [],
                'cycle_start_time': None
            }
            
            # Trading pairs configuration
            self.trading_pairs = TRADING_PAIRS
            
            # System state
            self.is_running = False
            self.last_health_check = time.time()
            self.health_check_interval = 300  # 5 minutes
            
            logger.info("Trading System initialized successfully")
            
        except Exception as e:
            logger.critical(f"Failed to initialize Trading System: {str(e)}")
            raise

    def health_check(self) -> bool:
        """Perform system health check"""
        try:
            # Check API connectivity
            status = self.session.get_server_time()
            if status.get('retCode') != 0:
                logger.error("Failed to connect to Bybit API")
                return False
            
            # Check error rates
            error_counts = {
                error_type: sum(len(errors) for errors in 
                self.error_manager.error_history.values())
                for error_type in ErrorType.__dict__.values()
                if isinstance(error_type, str)
            }
            
            high_errors = [k for k, v in error_counts.items() if v > 50]
            if high_errors:
                logger.warning(f"High error counts in: {high_errors}")
            
            # Log system status
            logger.info(f"Health check passed. Active positions: {len(self.strategy.active_positions)}")
            self.last_health_check = time.time()
            
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False
        
    def _save_state(self):
        state = {
            'last_processed_pair': self.last_processed_pair,
            'completed_pairs': list(self.processing_state['completed_pairs']),
            'failed_pairs': self.processing_state['failed_pairs'],
            'timestamp': datetime.now().isoformat()
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f)

    def _load_state(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.last_processed_pair = state['last_processed_pair']
                    self.processing_state['completed_pairs'] = set(state['completed_pairs'])
                    self.processing_state['failed_pairs'] = state['failed_pairs']
        except Exception as e:
            logger.error(f"Error loading state: {e}")

    def _reset_state(self):
        self.processing_state['completed_pairs'].clear()
        self.processing_state['failed_pairs'].clear()
        self.last_processed_pair = None
        if os.path.exists(self.state_file):
            os.remove(self.state_file)

    def run(self):
        """Main entry point for the trading system"""
        logger.info("Starting trading system...")
        self.is_running = True
            
        try:
            while self.is_running:
                current_time = time.time()
                    
                # Check for incomplete previous cycle
                if self._has_incomplete_cycle():
                    logger.info("Resuming incomplete cycle...")
                    self._resume_incomplete_cycle()
                else:
                    # Start new cycle
                    self.cycle_state = {
                        'cycle_id': int(current_time),
                        'in_progress': True,
                        'last_processed_pair': None,
                        'unprocessed_pairs': self.trading_pairs.copy(),
                        'cycle_start_time': current_time
                    }
                    
                try:
                    # Health check
                    if current_time - self.last_health_check >= self.health_check_interval:
                        if not self.health_check():
                            logger.error("Health check failed, pausing for 60 seconds")
                            time.sleep(60)
                            continue

                    # Process trading cycle
                    self._process_cycle()
                        
                    # Log error metrics at cycle end
                    self.error_manager.log_error_metrics()
                        
                    # Calculate sleep time for next cycle
                    cycle_duration = time.time() - self.cycle_state['cycle_start_time']
                    sleep_time = max(0, 900 - cycle_duration)  # 15 minutes
                    logger.info(f"Cycle completed. Sleeping for {sleep_time:.2f}s")
                    time.sleep(sleep_time)
                        
                except Exception as e:
                    logger.error(f"Error during cycle: {str(e)}")
                    self._save_cycle_state()  # Save state for recovery
                    time.sleep(60)  # Wait before retrying
                        
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            self._save_cycle_state()
        except Exception as e:
            logger.critical(f"Critical error: {str(e)}")
            self._save_cycle_state()
        finally:
            self.is_running = False
            self.cleanup()

    def cleanup(self):
        """Cleanup resources and log final status"""
        try:
            logger.info("Starting cleanup process...")
                
            # Log active positions
            for symbol, position in self.strategy.active_positions.items():
                position_info = position.to_dict()
                logger.info(f"Active position for {symbol}: {position_info}")
                
            # Clean up error history
            self.error_manager.cleanup_error_history()
                
            # Log final statistics
            logger.info("Final System Statistics:")
            logger.info(f"Total Active Positions: {len(self.strategy.active_positions)}")
                
            logger.info("Cleanup completed")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    def _process_cycle(self):
        """Process a single trading cycle"""
        try:
            while self.cycle_state['unprocessed_pairs']:
                symbol = self.cycle_state['unprocessed_pairs'][0]
                
                # Log current state before processing
                logger.info(f"Processing pair {symbol}")
                self.error_manager.log_error_metrics()  # Add this line
                
                try:
                    if self.error_manager.should_cool_down(symbol, ErrorType.API_ERROR):
                        logger.info(f"{symbol}: Skipping - In cooldown")
                        self.cycle_state['unprocessed_pairs'].remove(symbol)
                        continue
                    
                    self.strategy.execute_strategy(symbol)
                    self.cycle_state['last_processed_pair'] = symbol
                    self.cycle_state['unprocessed_pairs'].remove(symbol)
                    self._save_cycle_state()
                    
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {str(e)}")
                    self.error_manager.record_error(symbol, e)
                    # Log error metrics after error
                    self.error_manager.log_error_metrics()  # Add this line
                    raise
                    
                time.sleep(1)  # Rate limiting
        except Exception as e:
            logger.error(f"Critical error in processing cycle: {str(e)}")
            self.error_manager.log_error_metrics()  # Add this line
            raise

    def _has_incomplete_cycle(self) -> bool:
        """Check if there's an incomplete cycle that needs to be resumed"""
        try:
            if not os.path.exists('cycle_state.json'):
                return False
                
            with open('cycle_state.json', 'r') as f:
                saved_state = json.load(f)
                
            # Check if saved cycle is still relevant (less than 15 mins old)
            if saved_state['cycle_start_time'] + 900 > time.time():
                self.cycle_state = saved_state
                return bool(saved_state['unprocessed_pairs'])
                
            return False
        except FileNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error checking incomplete cycle: {str(e)}")
            return False

    def _save_cycle_state(self):
        """Save current cycle state to file"""
        try:
            state = {
                'current_pair': self.cycle_state['last_processed_pair'],
                'remaining_pairs': len(self.cycle_state['unprocessed_pairs']),
                'timestamp': datetime.now().isoformat()
            }
            logger.info(f"Cycle State: {state}")  # Add this line
            with open('cycle_state.json', 'w') as f:
                json.dump(self.cycle_state, f)
        except Exception as e:
            logger.error(f"Error saving cycle state: {str(e)}")

    def _resume_incomplete_cycle(self):
        """Resume processing from last saved state"""
        logger.info(f"Resuming cycle {self.cycle_state['cycle_id']} "
                f"with {len(self.cycle_state['unprocessed_pairs'])} remaining pairs")
        self._process_cycle()


    def cleanup(self):
            """Cleanup resources and log final status"""
            try:
                logger.info("Starting cleanup process...")
                
                # Log active positions
                for symbol, position in self.strategy.active_positions.items():
                    position_info = position.to_dict()
                    logger.info(f"Active position for {symbol}: {position_info}")
                
                # Clean up error history
                self.error_manager.cleanup_error_history()
                
                # Log final statistics
                logger.info("Final System Statistics:")
                logger.info(f"Total Active Positions: {len(self.strategy.active_positions)}")
                
                logger.info("Cleanup completed")
                
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")

# ============================================================================
# DUAL-MODE CONFIGURATION: Trading + Monitoring
# ============================================================================
# This system operates in two modes:
# 1. TRADING MODE (22 assets): Full analysis + trade execution with optimized strategies
# 2. MONITORING MODE (~75 assets): Data collection only for market intelligence
# ============================================================================

def get_enabled_trading_pairs():
    """Get list of enabled trading pairs from strategy configurations"""
    long_mgr = LongStrategyManager()
    short_mgr = ShortStrategyManager()

    # Get all enabled asset symbols
    long_assets = set(long_mgr.get_enabled_configs().keys())
    short_assets = set(short_mgr.get_enabled_configs().keys())

    # Combine and return sorted list
    all_assets = long_assets | short_assets
    return sorted(list(all_assets))

def get_monitoring_pairs():
    """
    Get list of assets for monitoring only (data collection, no trading).
    These assets provide market intelligence and help identify new opportunities.
    """
    monitoring_assets = [
        # Solana Ecosystem
        'SOLUSDT', 'SUIUSDT', 'JUPUSDT', 'RAYDIUMUSDT', 'BEAMUSDT',

        # Meme Coins (high volatility, good for monitoring trends)
        'DOGEUSDT', '1000BONKUSDT', 'BOMEUSDT', 'WIFUSDT', 'POPCATUSDT',
        'MEMEUSDT', 'DOGSUSDT', 'GOATUSDT', 'NOTUSDT', 'MEWUSDT',
        'CHILLGUYUSDT', 'FARTCOINUSDT', 'PENGUUSDT',

        # AI/Tech Tokens
        'RENDERUSDT', 'TAOUSDT', 'ARKMUSDT', 'AIOZUSDT', 'ACTUSDT',
        'ASTRUSDT',

        # Gaming/Metaverse
        'SANDUSDT', 'GALAUSDT', 'AXSUSDT', 'APEUSDT', 'ENJUSDT',
        'BEAMUSDT',

        # DeFi Ecosystem
        'PENDLEUSDT', 'QNTUSDT', 'AAVEUSDT', 'COMPUSDT', 'SNXUSDT',
        'CROUSDT', 'INJUSDT', 'DEXEUSDT',

        # Layer 1/Layer 2
        'XRPUSDT', 'ARBUSDT', 'LINKUSDT', 'ICPUSDT',
        'MNTUSDT', 'STXUSDT', 'STRKUSDT', 'KAIAUSDT', 'CFXUSDT',
        'EGLDUSDT', 'FLOWUSDT', 'KSMUSDT', 'MINAUSDT', 'XTZUSDT',

        # Infrastructure/Utility
        'FILUSDT', 'ARUSDT', 'HNTUSDT', 'THETAUSDT', 'ROSEUSDT',
        'LPTUSDT', 'GLMUSDT', 'FLUXUSDT', 'IOTAUSDT', 'VETUSDT',

        # Emerging/New Listings
        'ONDOUSDT', 'VIRTUALUSDT', 'FLRUSDT', 'EIGENUSDT', 'RSRUSDT',
        'GRASSUSDT', 'ORDIUSDT', 'SFPUSDT', 'HYPERUSDT', 'TRUMPUSDT',
        'MOVEUSDT', 'XCNUSDT',

        # Gaming Tokens
        'GMTUSDT', 'KDAUSDT', 'SUPERUSDT', 'SPXUSDT',

        # Other Major Tokens
        'BNBUSDT', 'WLDUSDT', '1000PEPEUSDT', 'LDOUSDT',
        'DYDXUSDT', 'JUPUSDT'  # Note: PYTHUSDT and 1000BONKUSDT already in trading mode
    ]

    # Remove duplicates and assets already in trading mode
    trading_assets = set(get_enabled_trading_pairs())
    monitoring_only = [asset for asset in monitoring_assets if asset not in trading_assets]

    return sorted(list(set(monitoring_only)))

# Load trading and monitoring pairs
TRADING_PAIRS_ENABLED = get_enabled_trading_pairs()
MONITORING_PAIRS = get_monitoring_pairs()
TRADING_PAIRS = sorted(list(set(TRADING_PAIRS_ENABLED + MONITORING_PAIRS)))

logger.info("=" * 80)
logger.info("DUAL-MODE SYSTEM INITIALIZED")
logger.info("=" * 80)
logger.info(f"✓ Trading Mode: {len(TRADING_PAIRS_ENABLED)} assets (will execute trades)")
logger.info(f"  Assets: {TRADING_PAIRS_ENABLED}")
logger.info(f"✓ Monitoring Mode: {len(MONITORING_PAIRS)} assets (data collection only)")
logger.info(f"  Monitoring: {MONITORING_PAIRS[:10]}... (+{len(MONITORING_PAIRS)-10} more)")
logger.info(f"✓ Total Market Coverage: {len(TRADING_PAIRS)} assets")
logger.info("=" * 80)

def main():
    """Main entry point"""
    try:
        # Get API credentials
        api_key = 'YFvx7mzSBIQzyUdGNM'
        api_secret = 'mDvfiwNRXgGLT7DWlAoRVLCoZWyq4WEb9tGM'
        
        # Initialize and run trading system
        trading_system = TradingSystem(api_key, api_secret)
        trading_system.run()
        
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        if 'trading_system' in locals():
            trading_system.cleanup()
    except Exception as e:
        logger.critical(f"Unhandled exception: {str(e)}")
        if 'trading_system' in locals():
            trading_system.cleanup()
    finally:
        logger.info("Program terminated")

if __name__ == "__main__":
    main()

# END SECTION 6