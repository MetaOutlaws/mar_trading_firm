"""
BigQuery Connector for Trading Bot
Handles data fetching and querying from Google BigQuery
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import pandas as pd
from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.bigquery_config import get_bigquery_config, QueryTemplates

logger = logging.getLogger(__name__)


class BigQueryConnector:
    """
    Connector class for fetching trading data from BigQuery
    """

    def __init__(self, config=None):
        """
        Initialize BigQuery connector

        Args:
            config: BigQueryConfig instance (uses default if None)
        """
        self.config = config or get_bigquery_config()
        self.client: Optional[bigquery.Client] = None
        self._connection_tested = False

    def connect(self) -> bool:
        """
        Establish connection to BigQuery

        Returns:
            bool: True if connection successful
        """
        try:
            # Validate configuration
            is_valid, errors = self.config.validate()
            if not is_valid:
                logger.error(f"Invalid configuration: {errors}")
                return False

            # Create BigQuery client
            if self.config.credentials_path and os.path.exists(self.config.credentials_path):
                self.client = bigquery.Client.from_service_account_json(
                    self.config.credentials_path,
                    project=self.config.project_id
                )
                logger.info(f"Connected to BigQuery using service account")
            else:
                self.client = bigquery.Client(project=self.config.project_id)
                logger.info(f"Connected to BigQuery using default credentials")

            # Test connection
            self._test_connection()
            self._connection_tested = True

            return True

        except GoogleCloudError as e:
            logger.error(f"Failed to connect to BigQuery: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to BigQuery: {e}")
            return False

    def _test_connection(self):
        """Test BigQuery connection with a simple query"""
        try:
            query = f"""
            SELECT COUNT(*) as table_count
            FROM `{self.config.project_id}.{self.config.dataset_id}.INFORMATION_SCHEMA.TABLES`
            """
            result = list(self.client.query(query).result())
            logger.info(f"Connection test successful. Found {result[0].table_count} tables in dataset.")
        except Exception as e:
            logger.warning(f"Connection test query failed: {e}")

    def query(
        self,
        query_string: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> Optional[pd.DataFrame]:
        """
        Execute a query and return results as DataFrame

        Args:
            query_string: SQL query to execute
            params: Query parameters for parameterized queries
            timeout: Query timeout in seconds (uses config default if None)

        Returns:
            DataFrame with query results or None if error
        """
        if not self.client:
            if not self.connect():
                logger.error("Cannot execute query: Not connected to BigQuery")
                return None

        try:
            # Replace table placeholders
            query_string = query_string.replace(
                '{table_id}',
                self.config.get_table_id(self.config.signals_table)
            )

            # Configure query job
            job_config = bigquery.QueryJobConfig()

            if params:
                job_config.query_parameters = [
                    bigquery.ScalarQueryParameter(k, "STRING", v)
                    for k, v in params.items()
                ]

            if self.config.max_bytes_billed:
                job_config.maximum_bytes_billed = self.config.max_bytes_billed

            job_config.use_query_cache = self.config.use_cache

            # Execute query
            timeout_seconds = timeout or self.config.timeout
            logger.info(f"Executing query (timeout: {timeout_seconds}s)...")

            query_job = self.client.query(query_string, job_config=job_config)
            results = query_job.result(timeout=timeout_seconds)

            # Convert to DataFrame
            df = results.to_dataframe()

            # Log query stats
            if query_job.total_bytes_processed:
                gb_processed = query_job.total_bytes_processed / (1024**3)
                logger.info(
                    f"Query completed: {len(df)} rows, "
                    f"{gb_processed:.3f} GB processed, "
                    f"{query_job.total_bytes_billed / (1024**3):.3f} GB billed"
                )

            return df

        except GoogleCloudError as e:
            logger.error(f"BigQuery error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error executing query: {e}")
            return None

    def get_historical_signals(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str = '15m'
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical trading signals for a symbol

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            start_date: Start of date range
            end_date: End of date range
            timeframe: Candle timeframe (e.g., '15m', '1h', '4h')

        Returns:
            DataFrame with historical signals
        """
        query = QueryTemplates.get_historical_signals(
            symbol=symbol,
            start_date=start_date.strftime('%Y-%m-%d %H:%M:%S'),
            end_date=end_date.strftime('%Y-%m-%d %H:%M:%S'),
            timeframe=timeframe
        )

        df = self.query(query)

        if df is not None and not df.empty:
            logger.info(
                f"Fetched {len(df)} signals for {symbol} "
                f"from {start_date} to {end_date}"
            )

        return df

    def get_trade_performance(
        self,
        start_date: datetime,
        end_date: datetime,
        min_trades: int = 10
    ) -> Optional[pd.DataFrame]:
        """
        Get trade performance summary by symbol

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            min_trades: Minimum trades required per symbol

        Returns:
            DataFrame with performance metrics per symbol
        """
        query = QueryTemplates.get_trade_performance(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            min_trades=min_trades
        )

        df = self.query(query)

        if df is not None:
            # Calculate additional metrics
            if not df.empty:
                df['win_rate'] = (df['winning_trades'] / df['total_trades'] * 100).round(2)
                df['profit_factor'] = (
                    (df['winning_trades'] * df['avg_win_pct'].abs()) /
                    (df['losing_trades'] * df['avg_loss_pct'].abs())
                ).round(2)

            logger.info(f"Analyzed performance for {len(df)} symbols")

        return df

    def get_indicator_performance(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Analyze which indicator combinations perform best

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period

        Returns:
            DataFrame with indicator performance analysis
        """
        query = QueryTemplates.get_indicator_performance(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )

        df = self.query(query)

        if df is not None and not df.empty:
            logger.info(f"Analyzed {len(df)} indicator combinations")

        return df

    def get_losing_patterns(
        self,
        start_date: datetime,
        end_date: datetime,
        min_losses: int = 3
    ) -> Optional[pd.DataFrame]:
        """
        Identify common patterns in losing trades

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            min_losses: Minimum losses required to include symbol

        Returns:
            DataFrame with losing trade patterns
        """
        query = QueryTemplates.get_losing_patterns(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            min_losses=min_losses
        )

        df = self.query(query)

        if df is not None and not df.empty:
            logger.info(f"Identified losing patterns for {len(df)} symbols")

        return df

    def get_time_based_performance(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Analyze performance by time of day and day of week

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period

        Returns:
            DataFrame with time-based performance
        """
        query = QueryTemplates.get_time_based_performance(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )

        df = self.query(query)

        if df is not None and not df.empty:
            # Add readable day names
            day_map = {1: 'Sunday', 2: 'Monday', 3: 'Tuesday', 4: 'Wednesday',
                      5: 'Thursday', 6: 'Friday', 7: 'Saturday'}
            df['day_name'] = df['day_of_week'].map(day_map)
            logger.info(f"Analyzed performance across {len(df)} time periods")

        return df

    def get_data_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics about available data

        Returns:
            Dictionary with data summary
        """
        if not self.client:
            if not self.connect():
                return {}

        try:
            table_id = self.config.get_table_id(self.config.signals_table)

            query = f"""
            SELECT
                MIN(timestamp) as earliest_date,
                MAX(timestamp) as latest_date,
                COUNT(*) as total_records,
                COUNT(DISTINCT symbol) as unique_symbols,
                COUNT(DISTINCT DATE(timestamp)) as trading_days,
                SUM(CASE WHEN trade_outcome = 'win' THEN 1 ELSE 0 END) as total_wins,
                SUM(CASE WHEN trade_outcome = 'loss' THEN 1 ELSE 0 END) as total_losses
            FROM `{table_id}`
            """

            result = list(self.client.query(query).result())[0]

            summary = {
                'earliest_date': result.earliest_date,
                'latest_date': result.latest_date,
                'total_records': result.total_records,
                'unique_symbols': result.unique_symbols,
                'trading_days': result.trading_days,
                'total_wins': result.total_wins or 0,
                'total_losses': result.total_losses or 0,
                'overall_win_rate': (
                    result.total_wins / (result.total_wins + result.total_losses) * 100
                    if (result.total_wins + result.total_losses) > 0 else 0
                )
            }

            logger.info(f"Data summary retrieved: {summary['total_records']} total records")
            return summary

        except Exception as e:
            logger.error(f"Failed to get data summary: {e}")
            return {}

    def close(self):
        """Close BigQuery connection"""
        if self.client:
            self.client.close()
            logger.info("BigQuery connection closed")


# Utility function for quick data access
def quick_query(query: str) -> Optional[pd.DataFrame]:
    """
    Execute a quick query without managing connection

    Args:
        query: SQL query string

    Returns:
        DataFrame with results
    """
    connector = BigQueryConnector()
    try:
        return connector.query(query)
    finally:
        connector.close()


if __name__ == "__main__":
    # Test the connector
    print("Testing BigQuery Connector...")

    connector = BigQueryConnector()

    if connector.connect():
        print("✓ Connection successful")

        # Get data summary
        summary = connector.get_data_summary()
        if summary:
            print("\nData Summary:")
            for key, value in summary.items():
                print(f"  {key}: {value}")

        # Test query
        print("\nTesting sample query...")
        df = connector.get_trade_performance(
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
            min_trades=5
        )

        if df is not None and not df.empty:
            print(f"✓ Query successful: {len(df)} results")
            print(df.head())
        else:
            print("✗ Query returned no results")

        connector.close()
    else:
        print("✗ Connection failed")
        print("\nSetup instructions:")
        print("1. Install: pip install google-cloud-bigquery pandas-gbq")
        print("2. Set GCP_PROJECT_ID environment variable")
        print("3. Set GOOGLE_APPLICATION_CREDENTIALS to your service account key path")
