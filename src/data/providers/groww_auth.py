"""Groww API authentication manager for SignalForge.

Implements the official Groww API authentication flow:
- Endpoint: POST https://api.groww.in/v1/token/api/access
- Checksum: SHA-256(GROWW_API_SECRET + timestamp)
- Header: Authorization: Bearer <GROWW_API_KEY>
- Body: {"key_type": "approval", "checksum": <checksum>, "timestamp": <epoch_seconds>}
- Returns access token used for subsequent API requests.
- Strict secrets safety: zero leakage of API key, secret, checksum, or token in logs/errors.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

import httpx

from src.data.providers.groww_config import GrowwConfig
from src.data.providers.groww_errors import (
    GrowwAPIError,
    GrowwAuthenticationError,
    GrowwDataFormatError,
    GrowwRateLimitError,
)


class GrowwAuthManager:
    """Manages Groww Trading API token generation and lifecycle."""

    def __init__(
        self,
        config: GrowwConfig,
        http_client: httpx.Client | Any | None = None,
    ) -> None:
        self.config = config
        self._http_client = http_client
        self._access_token: str | None = None

    @staticmethod
    def generate_checksum(api_secret: str, timestamp: str) -> str:
        """Compute SHA-256 checksum over secret + timestamp.

        Parameters
        ----------
        api_secret:
            The GROWW_API_SECRET.
        timestamp:
            Current epoch timestamp as a string.

        Returns
        -------
        str
            Hexadecimal SHA-256 checksum digest.
        """
        if not api_secret:
            raise ValueError("api_secret must not be empty.")
        if not timestamp:
            raise ValueError("timestamp must not be empty.")
        message = f"{api_secret}{timestamp}".encode("utf-8")
        return hashlib.sha256(message).hexdigest()

    def authenticate(self) -> str:
        """Execute authentication handshake with Groww API to obtain an access token.

        Returns
        -------
        str
            The generated Groww access token.

        Raises
        ------
        GrowwAuthenticationError:
            If credentials are not configured or HTTP 401/403 is received.
        GrowwRateLimitError:
            If HTTP 429 rate limit is encountered.
        GrowwAPIError:
            If server returns a non-200 HTTP status code.
        GrowwDataFormatError:
            If response structure is invalid or lacks the token field.
        """
        if not self.config.is_configured:
            missing = []
            if not self.config.api_key:
                missing.append("GROWW_API_KEY")
            if not self.config.api_secret:
                missing.append("GROWW_API_SECRET")
            raise GrowwAuthenticationError(
                f"Groww credentials incomplete. Missing: {', '.join(missing)}."
            )

        timestamp = str(int(time.time()))
        # api_secret is guaranteed non-None by is_configured check
        checksum = self.generate_checksum(self.config.api_secret, timestamp)  # type: ignore[arg-type]

        url = f"{self.config.base_url}/token/api/access"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-VERSION": "1.0",
        }
        body = {
            "key_type": "approval",
            "checksum": checksum,
            "timestamp": timestamp,
        }

        try:
            if self._http_client is not None:
                response = self._http_client.post(
                    url,
                    json=body,
                    headers=headers,
                    timeout=self.config.timeout,
                )
            else:
                with httpx.Client(timeout=self.config.timeout) as client:
                    response = client.post(url, json=body, headers=headers)
        except httpx.RequestError as exc:
            raise GrowwAPIError(
                f"Network error communicating with Groww token endpoint: {type(exc).__name__}"
            ) from exc

        if response.status_code in (401, 403):
            raise GrowwAuthenticationError(
                f"Authentication failed during Groww token generation (HTTP {response.status_code}). "
                "Check GROWW_API_KEY and GROWW_API_SECRET."
            )
        if response.status_code == 429:
            raise GrowwRateLimitError(
                "Groww rate limit exceeded during token generation (HTTP 429)."
            )
        if response.status_code >= 400:
            raise GrowwAPIError(
                f"Groww token endpoint returned error status {response.status_code}",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except Exception as exc:
            raise GrowwDataFormatError(
                f"Failed to parse JSON response from Groww token endpoint: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise GrowwDataFormatError("Groww token endpoint response is not a JSON object.")

        status = payload.get("status")
        if status in ("FAILURE", "ERROR"):
            msg = payload.get("message", "Token generation failed")
            raise GrowwAPIError(f"Groww token endpoint reported error: {msg}")

        token = (
            payload.get("token")
            or (payload.get("payload", {}).get("token") if isinstance(payload.get("payload"), dict) else None)
            or (payload.get("data", {}).get("token") if isinstance(payload.get("data"), dict) else None)
        )

        if not token or not isinstance(token, str):
            raise GrowwDataFormatError(
                "Groww authentication response missing valid 'token' field."
            )

        self._access_token = token
        return token

    def get_access_token(self, force_refresh: bool = False) -> str:
        """Return a valid cached access token or authenticate to acquire one."""
        if self._access_token is None or force_refresh:
            return self.authenticate()
        return self._access_token

    def __repr__(self) -> str:
        """Safe representation hiding token and secret details."""
        token_status = "present" if self._access_token else "none"
        return f"GrowwAuthManager(access_token={token_status})"
