"""Market Data Service orchestrator for SignalForge.

This service acts as the provider-agnostic gateway for querying market data.
It enforces strict architectural principles:
- Explicit provider registration and selection.
- Default provider configuration.
- Strict rejection of unknown or unavailable providers.
- Zero silent fallback: if a provider fails or is unavailable, never silently switch.
- Complete absence of network/downloader logic within the service layer.
- Enforced verification of the canonical OHLCV normalization contract.
"""

from __future__ import annotations

import logging
from typing import Any

from src.data.market_data import (
    MarketDataProvider,
    MarketDataRequest,
    MarketDataResult,
    validate_normalized_ohlcv,
)
from src.data.providers.local import LocalProvider

logger = logging.getLogger(__name__)


class UnknownProviderError(ValueError):
    """Raised when an unregistered provider is requested."""


class ProviderUnavailableError(RuntimeError):
    """Raised when a requested provider reports is_available() == False."""


class MarketDataService:
    """Provider-agnostic market data service coordinating registered providers."""

    def __init__(
        self,
        providers: list[MarketDataProvider] | None = None,
        default_provider: str | None = None,
        auto_register_local: bool = True,
    ) -> None:
        self._providers: dict[str, MarketDataProvider] = {}
        self._default_provider: str | None = None

        if auto_register_local:
            local = LocalProvider()
            self.register_provider(local, set_as_default=True)

        if providers:
            for p in providers:
                self.register_provider(p)

        if default_provider is not None:
            self.set_default_provider(default_provider)

    @property
    def default_provider(self) -> str | None:
        """Return the name of the currently configured default provider."""
        return self._default_provider

    def register_provider(
        self,
        provider: MarketDataProvider,
        set_as_default: bool = False,
    ) -> None:
        """Register a new market data provider instance.

        Parameters
        ----------
        provider:
            Instance implementing MarketDataProvider.
        set_as_default:
            Whether to make this provider the default provider.
        """
        if not isinstance(provider, MarketDataProvider):
            raise TypeError("provider must implement MarketDataProvider.")

        name = provider.provider_name.strip().lower()
        if not name:
            raise ValueError("Provider name must not be empty.")

        self._providers[name] = provider

        if set_as_default or self._default_provider is None:
            self._default_provider = name

    def set_default_provider(self, name: str) -> None:
        """Set the default provider by name."""
        norm_name = name.strip().lower()
        if norm_name not in self._providers:
            raise UnknownProviderError(
                f"Cannot set default provider to '{name}'. "
                f"Registered providers: {self.list_providers()}"
            )
        self._default_provider = norm_name

    def get_provider(self, name: str) -> MarketDataProvider:
        """Retrieve a registered provider by name."""
        norm_name = name.strip().lower()
        if norm_name not in self._providers:
            raise UnknownProviderError(
                f"Provider '{name}' is not registered. "
                f"Available providers: {self.list_providers()}"
            )
        return self._providers[norm_name]

    def list_providers(self) -> list[str]:
        """Return a sorted list of registered provider names."""
        return sorted(self._providers.keys())

    def get_provider_status(self, name: str | None = None) -> dict[str, bool]:
        """Return availability status for one or all registered providers.

        Parameters
        ----------
        name:
            Optional provider name. If omitted, returns status for all providers.
        """
        if name is not None:
            provider = self.get_provider(name)
            return {provider.provider_name: provider.is_available()}

        return {
            p_name: p.is_available()
            for p_name, p in self._providers.items()
        }

    def get_historical(
        self,
        request: MarketDataRequest,
        provider_name: str | None = None,
    ) -> MarketDataResult:
        """Query historical market data through an explicit or default provider.

        Parameters
        ----------
        request:
            Standardized MarketDataRequest.
        provider_name:
            Explicit provider to query. If None, uses default_provider.

        Returns
        -------
        MarketDataResult
            Normalized result meeting SignalForge OHLCV invariants.

        Raises
        ------
        TypeError:
            If request is not a MarketDataRequest.
        UnknownProviderError:
            If the requested provider is not registered.
        ProviderUnavailableError:
            If the selected provider is unavailable.
        """
        if not isinstance(request, MarketDataRequest):
            raise TypeError("request must be an instance of MarketDataRequest.")

        if provider_name is not None:
            selected_name = provider_name.strip().lower()
        elif self._default_provider is not None:
            selected_name = self._default_provider
        else:
            raise ValueError(
                "No provider specified and no default provider is configured."
            )

        if selected_name not in self._providers:
            raise UnknownProviderError(
                f"Provider '{selected_name}' is not registered. "
                f"Available providers: {self.list_providers()}"
            )

        provider = self._providers[selected_name]

        if not provider.is_available():
            raise ProviderUnavailableError(
                f"Market data provider '{selected_name}' is currently unavailable."
            )

        # Execute provider fetch without silent fallbacks.
        # Any provider failure must bubble up to the caller.
        result = provider.get_historical(request)

        if not isinstance(result, MarketDataResult):
            raise TypeError(
                f"Provider '{selected_name}' returned invalid result type: {type(result)}"
            )

        # Enforce canonical validation on returned DataFrame
        validate_normalized_ohlcv(result.data)

        return result
