"""
Single source of truth for all configuration and credentials.

Every module reads config through `get_settings()`. Nothing else in the codebase
is allowed to touch `os.environ` for credentials, and no key is ever hardcoded --
that was the single worst defect in the predecessor project, where live Bybit
keys sat in source with `testnet=False`.
"""

from __future__ import annotations

import logging
from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root, resolved from this file so paths work regardless of cwd.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)


class TradingMode(str, Enum):
    """How orders are handled. Ordered from safest to most dangerous."""

    PAPER = "paper"  # Simulated fills against live mainnet prices. No funds at risk.
    TESTNET = "testnet"  # Real orders against Bybit testnet.
    LIVE = "live"  # Real orders, real money.


# Typing this phrase in GO_LIVE_CONFIRMED is the only way to reach LIVE mode.
# A deliberate speed bump: flipping TRADING_MODE alone is not enough.
LIVE_CONFIRMATION_PHRASE = "I_ACCEPT_THE_RISK"


class Settings(BaseSettings):
    """Validated application configuration loaded from `.env` / environment."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Trading mode -------------------------------------------------------
    trading_mode: TradingMode = TradingMode.PAPER
    go_live_confirmed: str = ""

    # ---- Bybit credentials (testnet and live kept strictly separate) --------
    bybit_testnet_api_key: str = ""
    bybit_testnet_api_secret: str = ""
    bybit_live_api_key: str = ""
    bybit_live_api_secret: str = ""

    # ---- LLM providers ------------------------------------------------------
    #: xAI is the only provider with live X/web search, which the Sentiment
    #: Analyst depends on. OpenAI serves the cheap and standard employee tiers.
    xai_api_key: str = ""
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    llm_monthly_budget_usd: float = Field(default=200.0, gt=0)

    # ---- Historical data ----------------------------------------------------
    gcp_project_id: str = "crypto-bot-472419"
    bigquery_dataset: str = "historical_data"
    google_application_credentials: str = ""

    # ---- Storage ------------------------------------------------------------
    database_url: str = "sqlite:///data/firm.db"

    # ---- API ----------------------------------------------------------------
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_token: str = "change-me-to-a-long-random-string"

    # ---- Logging ------------------------------------------------------------
    log_level: str = "INFO"

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------
    @model_validator(mode="after")
    def _guard_live_mode(self) -> "Settings":
        """Refuse to construct a LIVE configuration unless explicitly confirmed."""
        if self.trading_mode is TradingMode.LIVE:
            if self.go_live_confirmed != LIVE_CONFIRMATION_PHRASE:
                raise ValueError(
                    "TRADING_MODE=live requires GO_LIVE_CONFIRMED="
                    f"{LIVE_CONFIRMATION_PHRASE}. Refusing to start."
                )
            if not (self.bybit_live_api_key and self.bybit_live_api_secret):
                raise ValueError(
                    "TRADING_MODE=live requires BYBIT_LIVE_API_KEY and "
                    "BYBIT_LIVE_API_SECRET. Refusing to start."
                )
        return self

    # -----------------------------------------------------------------------
    # Derived accessors
    # -----------------------------------------------------------------------
    @property
    def is_live(self) -> bool:
        return self.trading_mode is TradingMode.LIVE

    @property
    def use_bybit_testnet(self) -> bool:
        """True when the Bybit client should point at the testnet host.

        PAPER mode reads mainnet prices (they are more realistic than testnet's
        thin books) but never submits an order, so it stays on mainnet too.
        """
        return self.trading_mode is TradingMode.TESTNET

    def bybit_credentials(self) -> tuple[str, str]:
        """Return the (key, secret) pair appropriate for the current mode.

        PAPER mode needs no credentials at all: market data endpoints are public
        and no order is ever submitted.
        """
        if self.trading_mode is TradingMode.LIVE:
            return self.bybit_live_api_key, self.bybit_live_api_secret
        if self.trading_mode is TradingMode.TESTNET:
            return self.bybit_testnet_api_key, self.bybit_testnet_api_secret
        return "", ""

    def resolved_database_url(self) -> str:
        """Absolutize relative SQLite paths so cwd cannot change which DB is used."""
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            raw = self.database_url[len(prefix) :]
            path = Path(raw)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            path.parent.mkdir(parents=True, exist_ok=True)
            return f"{prefix}{path}"
        return self.database_url

    @property
    def logs_dir(self) -> Path:
        path = PROJECT_ROOT / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def artifacts_dir(self) -> Path:
        path = PROJECT_ROOT / "research" / "artifacts"
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Call this everywhere instead of reading env vars."""
    return Settings()
