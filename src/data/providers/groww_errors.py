"""Groww provider specific exception hierarchy for SignalForge.

All exceptions inherit from GrowwError. String representations of exceptions
are designed to never leak authentication credentials, tokens, or secrets.
"""

from __future__ import annotations


class GrowwError(Exception):
    """Base exception for all Groww market data provider errors."""


class GrowwAuthenticationError(GrowwError):
    """Raised when authentication against Groww API fails (e.g. 401/403 or missing key)."""


class GrowwRateLimitError(GrowwError):
    """Raised when Groww API rate limits are encountered (e.g. 429 Too Many Requests)."""


class GrowwAPIError(GrowwError):
    """Raised when Groww API responds with a non-success HTTP status code or server error."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class GrowwSymbolMappingError(GrowwError):
    """Raised when an instrument symbol cannot be resolved to a valid Groww instrument."""


class GrowwDataFormatError(GrowwError):
    """Raised when the payload returned by Groww API cannot be parsed or violates schema."""
