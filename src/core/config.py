"""
SignalForge — Centralized Application Settings & Environment Configuration
===========================================================================
Defines unified application configuration using Pydantic v2 models.
Guarantees:
1. Clear development defaults (127.0.0.1:8000, local data directories).
2. Safe production defaults without fabricated credentials.
3. Clean environment variable overrides (APP_ENV, API_HOST, API_PORT, CORS_ORIGINS, etc.).
4. Strict secrets masking in string representation (zero token leakage in logs).
5. Seamless backward compatibility with existing GrowwConfig consumers.
"""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class SignalForgeSettings(BaseModel):
    """
    Centralized SignalForge configuration schema.
    """

    app_env: str = Field(
        default="development",
        description="Application runtime environment (development, staging, production, testing).",
    )
    api_host: str = Field(
        default="127.0.0.1",
        description="Network host interface to bind the API server.",
    )
    api_port: int = Field(
        default=8000,
        description="Port number for the API server.",
    )
    cors_origins: List[str] = Field(
        default=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:5175",
            "http://127.0.0.1:5175",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        description="Permitted origins for Cross-Origin Resource Sharing (CORS).",
    )
    data_root_dir: Path = Field(
        default=Path("data"),
        description="Root directory for application market data and persistent storage.",
    )
    historical_data_dir: Path = Field(
        default=Path("data/historical"),
        description="Directory containing historical market datasets.",
    )
    stocks_data_dir: Path = Field(
        default=Path("data/historical/stocks"),
        description="Directory containing 1-minute stock OHLCV CSV candles.",
    )
    paper_trading_dir: Path = Field(
        default=Path("data/paper_trading"),
        description="Directory containing interactive paper trading session ledgers.",
    )
    universe_registry_path: Path = Field(
        default=Path("data/universe_registry.json"),
        description="Path to the primary stock universe registry JSON file.",
    )
    log_level: str = Field(
        default="INFO",
        description="Standard logging severity level (DEBUG, INFO, WARNING, ERROR).",
    )
    serve_static_frontend: bool = Field(
        default=False,
        description="Whether the FastAPI backend should mount and serve compiled frontend static assets.",
    )

    # Groww API configuration (strictly loaded from environment, default None)
    groww_api_key: Optional[str] = Field(
        default=None,
        description="Groww Trading API key.",
    )
    groww_api_secret: Optional[str] = Field(
        default=None,
        description="Groww Trading API secret.",
    )
    groww_base_url: str = Field(
        default="https://api.groww.in/v1",
        description="Groww Trading API base endpoint URL.",
    )
    groww_request_timeout: float = Field(
        default=30.0,
        description="HTTP request timeout in seconds for Groww API calls.",
    )

    def __repr__(self) -> str:
        """Mask credentials to prevent accidental log exposure."""
        masked_key = "***" if self.groww_api_key else None
        masked_sec = "***" if self.groww_api_secret else None
        return (
            f"SignalForgeSettings("
            f"app_env='{self.app_env}', "
            f"api_host='{self.api_host}', "
            f"api_port={self.api_port}, "
            f"data_root_dir='{self.data_root_dir}', "
            f"groww_api_key={masked_key}, "
            f"groww_api_secret={masked_sec})"
        )

    def __str__(self) -> str:
        return self.__repr__()

    @classmethod
    def from_env(cls) -> SignalForgeSettings:
        """
        Instantiate settings from system environment variables and local .env file.
        """
        # Safely try loading dotenv if present
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        app_env = os.getenv("APP_ENV", "development").strip().lower()
        api_host = os.getenv("API_HOST", "127.0.0.1").strip()

        # Parse port safely
        try:
            api_port = int(os.getenv("API_PORT", "8000"))
        except ValueError:
            api_port = 8000

        # Parse CORS origins (support comma-delimited strings)
        raw_cors = os.getenv("CORS_ORIGINS")
        if raw_cors:
            cors_origins = [o.strip() for o in raw_cors.split(",") if o.strip()]
        else:
            cors_origins = [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:5174",
                "http://127.0.0.1:5174",
                "http://localhost:5175",
                "http://127.0.0.1:5175",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ]

        data_root = Path(os.getenv("DATA_ROOT_DIR", "data"))
        historical_dir = Path(os.getenv("HISTORICAL_DATA_DIR", str(data_root / "historical")))
        stocks_dir = Path(os.getenv("STOCKS_DATA_DIR", str(historical_dir / "stocks")))
        paper_dir = Path(os.getenv("PAPER_TRADING_DIR", str(data_root / "paper_trading")))
        universe_path = Path(os.getenv("UNIVERSE_REGISTRY_PATH", str(data_root / "universe_registry.json")))

        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        serve_static = os.getenv("SERVE_STATIC_FRONTEND", "false").strip().lower() in ("true", "1", "yes")

        # Groww credentials
        groww_key = os.getenv("GROWW_API_KEY")
        if groww_key:
            groww_key = groww_key.strip() or None

        groww_sec = os.getenv("GROWW_API_SECRET")
        if groww_sec:
            groww_sec = groww_sec.strip() or None

        groww_base = os.getenv("GROWW_API_BASE_URL", "https://api.groww.in/v1").strip()
        if not groww_base:
            groww_base = "https://api.groww.in/v1"

        try:
            groww_timeout = float(os.getenv("GROWW_REQUEST_TIMEOUT", "30.0"))
        except ValueError:
            groww_timeout = 30.0

        return cls(
            app_env=app_env,
            api_host=api_host,
            api_port=api_port,
            cors_origins=cors_origins,
            data_root_dir=data_root,
            historical_data_dir=historical_dir,
            stocks_data_dir=stocks_dir,
            paper_trading_dir=paper_dir,
            universe_registry_path=universe_path,
            log_level=log_level,
            serve_static_frontend=serve_static,
            groww_api_key=groww_key,
            groww_api_secret=groww_sec,
            groww_base_url=groww_base,
            groww_request_timeout=groww_timeout,
        )


@lru_cache(maxsize=1)
def get_settings() -> SignalForgeSettings:
    """
    Return cached application settings singleton.
    Use get_settings.cache_clear() in tests to force reload.
    """
    return SignalForgeSettings.from_env()
