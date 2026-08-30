"""
BigQuery Configuration for Trading Bot
Handles connection settings and authentication for Google BigQuery
"""

import os
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class BigQueryConfig:
    """Configuration for BigQuery connection"""

    # Google Cloud Project Settings
    project_id: str = os.getenv('GCP_PROJECT_ID', '')
    dataset_id: str = os.getenv('BIGQUERY_DATASET', 'trading_data')
    credentials_path: str = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')

    # Table Names
    signals_table: str = 'trading_signals'
    market_conditions_table: str = 'market_conditions'
    backtest_results_table: str = 'backtest_results'
    trades_table: str = 'executed_trades'

    # Query Settings
    max_results: int = 100000  # Maximum rows per query
    timeout: int = 300  # Query timeout in seconds
    use_cache: bool = True  # Use BigQuery query cache

    # Data Processing
    chunk_size: int = 10000  # Process data in chunks
    parallel_queries: int = 4  # Number of parallel query threads

    # Cost Management
    max_bytes_billed: Optional[int] = 10_000_000_000  # 10 GB limit per query

    def __post_init__(self):
        """Validate configuration after initialization"""
        if not self.project_id:
            logger.warning("GCP_PROJECT_ID not set. Please set environment variable.")

        if not self.credentials_path:
            logger.warning(
                "GOOGLE_APPLICATION_CREDENTIALS not set. "
                "BigQuery client will attempt to use default credentials."
            )
        elif not os.path.exists(self.credentials_path):
            logger.error(f"Credentials file not found: {self.credentials_path}")

    @property
    def full_table_name(self) -> str:
        """Returns fully qualified table name"""
        return f"{self.project_id}.{self.dataset_id}.{self.signals_table}"

    def get_table_id(self, table_name: str) -> str:
        """Get fully qualified table ID"""
        return f"{self.project_id}.{self.dataset_id}.{table_name}"

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate configuration
        Returns: (is_valid, list_of_errors)
        """
        errors = []

        if not self.project_id:
            errors.append("Project ID is required")

        if not self.dataset_id:
            errors.append("Dataset ID is required")

        if self.credentials_path and not os.path.exists(self.credentials_path):
            errors.append(f"Credentials file not found: {self.credentials_path}")

        if self.timeout < 60:
            errors.append("Timeout should be at least 60 seconds")

        if self.chunk_size < 1000:
            errors.append("Chunk size should be at least 1000")

        is_valid = len(errors) == 0
        return is_valid, errors


# Singleton instance
_config_instance: Optional[BigQueryConfig] = None


def get_bigquery_config() -> BigQueryConfig:
    """Get or create BigQuery configuration singleton"""
    global _config_instance
    if _config_instance is None:
        _config_instance = BigQueryConfig()
    return _config_instance


def set_bigquery_config(config: BigQueryConfig):
    """Set custom BigQuery configuration"""
    global _config_instance
    _config_instance = config


# Query Templates
class QueryTemplates:
    """Common BigQuery query templates"""

    @staticmethod
    def get_historical_signals(
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str = '15m'
    ) -> str:
        """Query historical trading signals"""
        return f"""
        SELECT
            timestamp,
            symbol,
            timeframe,
            signal_type,
            rsi,
            macd,
            macd_signal,
            macd_histogram,
            adx,
            volume_ratio,
            open,
            high,
            low,
            close,
            volume,
            signal_score,
            signal_strength
        FROM `{{table_id}}`
        WHERE symbol = '{symbol}'
        AND timeframe = '{timeframe}'
        AND timestamp BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY timestamp ASC
        """

    @staticmethod
    def get_trade_performance(
        start_date: str,
        end_date: str,
        min_trades: int = 10
    ) -> str:
        """Query trade performance by symbol"""
        return f"""
        SELECT
            symbol,
            COUNT(*) as total_trades,
            SUM(CASE WHEN trade_outcome = 'win' THEN 1 ELSE 0 END) as winning_trades,
            SUM(CASE WHEN trade_outcome = 'loss' THEN 1 ELSE 0 END) as losing_trades,
            ROUND(AVG(CASE WHEN trade_outcome = 'win' THEN pnl_percentage ELSE NULL END), 2) as avg_win_pct,
            ROUND(AVG(CASE WHEN trade_outcome = 'loss' THEN pnl_percentage ELSE NULL END), 2) as avg_loss_pct,
            ROUND(SUM(pnl), 2) as total_pnl,
            ROUND(AVG(signal_score), 2) as avg_signal_score,
            ROUND(AVG(holding_period_minutes), 0) as avg_holding_minutes
        FROM `{{table_id}}`
        WHERE timestamp BETWEEN '{start_date}' AND '{end_date}'
        AND trade_outcome IS NOT NULL
        GROUP BY symbol
        HAVING COUNT(*) >= {min_trades}
        ORDER BY total_pnl DESC
        """

    @staticmethod
    def get_indicator_performance(
        start_date: str,
        end_date: str
    ) -> str:
        """Analyze which indicator ranges perform best"""
        return f"""
        WITH trades AS (
            SELECT
                CASE
                    WHEN rsi < 30 THEN 'oversold'
                    WHEN rsi > 70 THEN 'overbought'
                    ELSE 'neutral'
                END as rsi_zone,
                CASE
                    WHEN adx < 20 THEN 'weak'
                    WHEN adx < 40 THEN 'moderate'
                    ELSE 'strong'
                END as adx_strength,
                CASE
                    WHEN volume_ratio < 1.0 THEN 'low'
                    WHEN volume_ratio < 1.5 THEN 'normal'
                    ELSE 'high'
                END as volume_level,
                trade_outcome,
                pnl
            FROM `{{table_id}}`
            WHERE timestamp BETWEEN '{start_date}' AND '{end_date}'
            AND trade_outcome IS NOT NULL
        )
        SELECT
            rsi_zone,
            adx_strength,
            volume_level,
            COUNT(*) as trades,
            SUM(CASE WHEN trade_outcome = 'win' THEN 1 ELSE 0 END) as wins,
            ROUND(AVG(CASE WHEN trade_outcome = 'win' THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
            ROUND(SUM(pnl), 2) as total_pnl
        FROM trades
        GROUP BY rsi_zone, adx_strength, volume_level
        HAVING COUNT(*) >= 5
        ORDER BY win_rate DESC, total_pnl DESC
        """

    @staticmethod
    def get_losing_patterns(
        start_date: str,
        end_date: str,
        min_losses: int = 3
    ) -> str:
        """Identify common losing trade patterns"""
        return f"""
        WITH losing_trades AS (
            SELECT
                symbol,
                timestamp,
                rsi,
                adx,
                volume_ratio,
                signal_score,
                signal_strength,
                pnl,
                pnl_percentage
            FROM `{{table_id}}`
            WHERE timestamp BETWEEN '{start_date}' AND '{end_date}'
            AND trade_outcome = 'loss'
        )
        SELECT
            symbol,
            COUNT(*) as loss_count,
            ROUND(AVG(rsi), 1) as avg_rsi,
            ROUND(AVG(adx), 1) as avg_adx,
            ROUND(AVG(volume_ratio), 2) as avg_volume,
            ROUND(AVG(signal_score), 2) as avg_score,
            ROUND(SUM(pnl), 2) as total_loss,
            ROUND(AVG(pnl_percentage), 2) as avg_loss_pct
        FROM losing_trades
        GROUP BY symbol
        HAVING COUNT(*) >= {min_losses}
        ORDER BY total_loss ASC
        """

    @staticmethod
    def get_time_based_performance(
        start_date: str,
        end_date: str
    ) -> str:
        """Analyze performance by time of day/week"""
        return f"""
        SELECT
            EXTRACT(DAYOFWEEK FROM timestamp) as day_of_week,
            EXTRACT(HOUR FROM timestamp) as hour_of_day,
            COUNT(*) as trades,
            SUM(CASE WHEN trade_outcome = 'win' THEN 1 ELSE 0 END) as wins,
            ROUND(AVG(CASE WHEN trade_outcome = 'win' THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
            ROUND(SUM(pnl), 2) as total_pnl
        FROM `{{table_id}}`
        WHERE timestamp BETWEEN '{start_date}' AND '{end_date}'
        AND trade_outcome IS NOT NULL
        GROUP BY day_of_week, hour_of_day
        HAVING COUNT(*) >= 5
        ORDER BY win_rate DESC
        """


if __name__ == "__main__":
    # Test configuration
    config = get_bigquery_config()
    is_valid, errors = config.validate()

    print("BigQuery Configuration:")
    print(f"  Project ID: {config.project_id or 'NOT SET'}")
    print(f"  Dataset: {config.dataset_id}")
    print(f"  Credentials: {config.credentials_path or 'Using default'}")
    print(f"  Valid: {is_valid}")

    if errors:
        print("\nConfiguration Errors:")
        for error in errors:
            print(f"  - {error}")

    print("\nTo setup BigQuery:")
    print("1. Set environment variable: export GCP_PROJECT_ID='your-project-id'")
    print("2. Set environment variable: export BIGQUERY_DATASET='trading_data'")
    print("3. Set environment variable: export GOOGLE_APPLICATION_CREDENTIALS='/path/to/key.json'")
