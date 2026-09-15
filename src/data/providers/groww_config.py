"""Configuration loader for the Groww Market Data Adapter.

Reads credentials and endpoint parameters strictly from environment variables.
Provides secrets masking in repr to guarantee zero token leakage.
"""

from __future__ import annotations

from dataclasses import dataclass
import os


DEFAULT_GROWW_BASE_URL = "https://api.groww.in/v1"
DEFAULT_GROWW_TIMEOUT = 30.0


@dataclass
class GrowwConfig:
    """Groww Trading API connection configuration."""

    api_key: str | None = None
    api_secret: str | None = None
    base_url: str = DEFAULT_GROWW_BASE_URL
    timeout: float = DEFAULT_GROWW_TIMEOUT

    @classmethod
    def from_env(cls) -> GrowwConfig:
        """Instantiate configuration from system environment variables."""
        api_key = os.environ.get("GROWW_API_KEY")
        if api_key is not None:
            api_key = api_key.strip()
            if not api_key:
                api_key = None

        api_secret = os.environ.get("GROWW_API_SECRET")
        if api_secret is not None:
            api_secret = api_secret.strip()
            if not api_secret:
                api_secret = None

        base_url = os.environ.get("GROWW_API_BASE_URL", DEFAULT_GROWW_BASE_URL).strip()
        if not base_url:
            base_url = DEFAULT_GROWW_BASE_URL

        timeout_str = os.environ.get("GROWW_REQUEST_TIMEOUT", str(DEFAULT_GROWW_TIMEOUT))
        try:
            timeout = float(timeout_str)
        except ValueError:
            timeout = DEFAULT_GROWW_TIMEOUT

        return cls(
            api_key=api_key,
            api_secret=api_secret,
            base_url=base_url.rstrip("/"),
            timeout=timeout,
        )

    @property
    def is_configured(self) -> bool:
        """Return True if required credentials are present."""
        return bool(self.api_key)

    def __repr__(self) -> str:
        """Safe representation masking sensitive credentials."""
        masked_key = "***" if self.api_key else "None"
        masked_secret = "***" if self.api_secret else "None"
        return (
            f"GrowwConfig(api_key={masked_key}, api_secret={masked_secret}, "
            f"base_url='{self.base_url}', timeout={self.timeout})"
        )
