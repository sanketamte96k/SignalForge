"""Groww Market Data Provider for SignalForge.

Implements the MarketDataProvider interface for Groww's official Trading API:
- Endpoint: GET https://api.groww.in/v1/historical/candles
- Authentication: Bearer token via GROWW_API_KEY
- Interval mappings: 1m, 5m, 15m, 30m, 1h, 1d with bounded chunking per official limitations
- Canonical OHLCV normalization: Open, High, Low, Close, Volume in Asia/Kolkata wall clock time
- Complete secrets safety: zero leakage of tokens in logs, errors, or metadata
- Zero silent fallback: all failures bubble up immediately
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pandas as pd

from src.data.market_data import (
    CANONICAL_OHLCV_COLUMNS,
    MarketDataProvider,
    MarketDataRequest,
    MarketDataResult,
    validate_normalized_ohlcv,
)
from src.data.providers.groww_auth import GrowwAuthManager
from src.data.providers.groww_config import GrowwConfig
from src.data.providers.groww_errors import (
    GrowwAPIError,
    GrowwAuthenticationError,
    GrowwDataFormatError,
    GrowwError,
    GrowwRateLimitError,
    GrowwSymbolMappingError,
)

logger = logging.getLogger(__name__)

# Groww official duration limits per interval
# 1m - 5m: max 30 days
# 10m - 30m: max 90 days
# 1h - 1mo: max 180 days
SUPPORTED_GROWW_INTERVALS: dict[str, tuple[str, pd.Timedelta]] = {
    "1m": ("1minute", pd.Timedelta(days=30)),
    "2m": ("2minute", pd.Timedelta(days=30)),
    "3m": ("3minute", pd.Timedelta(days=30)),
    "5m": ("5minute", pd.Timedelta(days=30)),
    "10m": ("10minute", pd.Timedelta(days=90)),
    "15m": ("15minute", pd.Timedelta(days=90)),
    "30m": ("30minute", pd.Timedelta(days=90)),
    "1h": ("1hour", pd.Timedelta(days=180)),
    "60m": ("1hour", pd.Timedelta(days=180)),
    "1d": ("1day", pd.Timedelta(days=180)),
}

# Explicit instrument symbol mappings for NSE equities
DEFAULT_SYMBOL_MAP: dict[str, str] = {
    "RELIANCE": "NSE-RELIANCE",
    "TCS": "NSE-TCS",
    "INFY": "NSE-INFY",
    "HDFCBANK": "NSE-HDFCBANK",
    "SBIN": "NSE-SBIN",
}


class GrowwProvider(MarketDataProvider):
    """Production Groww market-data adapter conforming to MarketDataProvider."""

    def __init__(
        self,
        config: GrowwConfig | None = None,
        http_client: httpx.Client | Any | None = None,
        symbol_map: dict[str, str] | None = None,
        auth_manager: GrowwAuthManager | None = None,
    ) -> None:
        self.config = config if config is not None else GrowwConfig.from_env()
        self._http_client = http_client
        self._symbol_map = dict(DEFAULT_SYMBOL_MAP)
        if symbol_map:
            self._symbol_map.update(symbol_map)
        self.auth_manager = auth_manager or GrowwAuthManager(
            config=self.config,
            http_client=self._http_client,
        )

    @property
    def provider_name(self) -> str:
        """Canonical provider identifier."""
        return "groww"

    def is_available(self) -> bool:
        """Check whether required Groww credentials are configured."""
        return self.config.is_configured

    def resolve_groww_symbol(self, symbol: str, exchange: str = "NSE") -> str:
        """Map SignalForge ticker to Groww instrument representation.

        Uses explicit symbol map if configured; otherwise defaults to standard
        Groww convention: '{EXCHANGE}-{SYMBOL}' (e.g. 'NSE-RELIANCE').
        """
        clean_symbol = symbol.strip().upper()
        if clean_symbol in self._symbol_map:
            return self._symbol_map[clean_symbol]

        clean_exchange = exchange.strip().upper()
        if not clean_symbol:
            raise GrowwSymbolMappingError("Symbol must not be empty.")

        return f"{clean_exchange}-{clean_symbol}"

    def get_historical(self, request: MarketDataRequest) -> MarketDataResult:
        """Fetch and normalize historical data from Groww Trading API.

        Parameters
        ----------
        request:
            The validated MarketDataRequest.

        Returns
        -------
        MarketDataResult
            Envelope containing canonical OHLCV DataFrame and metadata.
        """
        if not self.is_available():
            raise GrowwAuthenticationError(
                "Groww credentials are not configured. "
                "Set GROWW_API_KEY and GROWW_API_SECRET environment variables."
            )

        interval_key = request.interval.lower()
        if interval_key not in SUPPORTED_GROWW_INTERVALS:
            raise ValueError(
                f"Interval '{request.interval}' is not supported by Groww. "
                f"Supported intervals: {sorted(SUPPORTED_GROWW_INTERVALS.keys())}"
            )

        groww_interval, max_chunk_duration = SUPPORTED_GROWW_INTERVALS[interval_key]
        groww_symbol = self.resolve_groww_symbol(request.symbol, request.exchange)

        # Parse request boundaries or defaults
        start_ts = (
            pd.Timestamp(request.start)
            if request.start is not None
            else pd.Timestamp.now(tz="Asia/Kolkata") - max_chunk_duration
        )
        end_ts = (
            pd.Timestamp(request.end)
            if request.end is not None
            else pd.Timestamp.now(tz="Asia/Kolkata")
        )

        # Ensure tz-aware for comparison if one is tz-aware
        if start_ts.tz is None and end_ts.tz is not None:
            start_ts = start_ts.tz_localize(end_ts.tz)
        elif start_ts.tz is not None and end_ts.tz is None:
            end_ts = end_ts.tz_localize(start_ts.tz)

        if start_ts > end_ts:
            raise ValueError(
                f"Start date ({start_ts}) must be before or equal to end date ({end_ts})."
            )

        # Build bounded chunks to comply with Groww API single-request limits
        chunks = self._generate_chunks(start_ts, end_ts, max_chunk_duration)

        chunk_dfs: list[pd.DataFrame] = []
        for c_start, c_end in chunks:
            chunk_df = self._fetch_chunk(
                groww_symbol=groww_symbol,
                exchange=request.exchange,
                candle_interval=groww_interval,
                start_time=c_start,
                end_time=c_end,
            )
            if not chunk_df.empty:
                chunk_dfs.append(chunk_df)

        if not chunk_dfs:
            raise ValueError(
                f"No market data returned by Groww for symbol '{request.symbol}' "
                f"in range [{start_ts}, {end_ts}]."
            )

        # Combine chunks and resolve boundary overlaps
        combined = pd.concat(chunk_dfs, axis=0)
        combined = combined.sort_index()
        combined = combined[~combined.index.duplicated(keep="last")]

        # Apply strict date filtering matching original request
        if request.start is not None:
            combined = combined[combined.index >= pd.Timestamp(request.start).tz_localize(None)]
        if request.end is not None:
            combined = combined[combined.index <= pd.Timestamp(request.end).tz_localize(None)]

        if combined.empty:
            raise ValueError(
                f"Filtered market data is empty for '{request.symbol}' "
                f"in range [{request.start}, {request.end}]."
            )

        # Validate canonical OHLCV invariants
        validate_normalized_ohlcv(combined)

        # Strict check: Low must be strictly positive
        if (combined["Low"] <= 0).any():
            raise ValueError("Market data contains non-positive Low values (Low <= 0).")

        metadata: dict[str, Any] = {
            "source": "groww",
            "groww_symbol": groww_symbol,
            "candle_interval": groww_interval,
            "row_count": len(combined),
            "chunks_count": len(chunks),
        }

        return MarketDataResult(
            symbol=request.symbol,
            exchange=request.exchange,
            interval=request.interval,
            data=combined,
            provider=self.provider_name,
            requested_start=request.start,
            requested_end=request.end,
            metadata=metadata,
        )

    def _generate_chunks(
        self,
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp,
        max_duration: pd.Timedelta,
    ) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
        """Slice date range into deterministic sub-intervals <= max_duration."""
        chunks: list[tuple[pd.Timestamp, pd.Timestamp]] = []
        curr_start = start_ts
        while curr_start < end_ts:
            curr_end = min(curr_start + max_duration, end_ts)
            chunks.append((curr_start, curr_end))
            if curr_end >= end_ts:
                break
            curr_start = curr_end
        return chunks

    def _fetch_chunk(
        self,
        groww_symbol: str,
        exchange: str,
        candle_interval: str,
        start_time: pd.Timestamp,
        end_time: pd.Timestamp,
    ) -> pd.DataFrame:
        """Call Groww historical candle endpoint for a single chunk."""
        url = f"{self.config.base_url}/historical/candles"
        params = {
            "exchange": exchange.strip().upper(),
            "segment": "CASH",
            "groww_symbol": groww_symbol,
            "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "candle_interval": candle_interval,
        }
        access_token = self.auth_manager.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-API-VERSION": "1.0",
            "Accept": "application/json",
        }

        try:
            if self._http_client is not None:
                response = self._http_client.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.config.timeout,
                )
            else:
                with httpx.Client(timeout=self.config.timeout) as client:
                    response = client.get(url, params=params, headers=headers)
        except httpx.RequestError as exc:
            # Strip potential secrets from request error
            raise GrowwAPIError(f"Network error communicating with Groww API: {type(exc).__name__}") from exc

        # Handle HTTP status codes
        if response.status_code in (401, 403):
            raise GrowwAuthenticationError(
                "Authentication failed with Groww API (HTTP "
                f"{response.status_code}). Check GROWW_API_KEY and GROWW_API_SECRET."
            )
        if response.status_code == 429:
            raise GrowwRateLimitError("Groww API rate limit exceeded (HTTP 429).")
        if response.status_code >= 400:
            raise GrowwAPIError(
                f"Groww API returned error status {response.status_code}",
                status_code=response.status_code,
            )

        # Parse JSON response
        try:
            payload = response.json()
        except Exception as exc:
            raise GrowwDataFormatError(f"Failed to parse JSON response: {exc}") from exc

        if not isinstance(payload, dict):
            raise GrowwDataFormatError("Groww API response is not a JSON object.")

        status = payload.get("status")
        if status in ("FAILURE", "ERROR"):
            msg = payload.get("message", "Unknown Groww API failure")
            raise GrowwAPIError(f"Groww API reported error: {msg}")

        # Extract candles array
        candles = (
            payload.get("payload", {}).get("candles")
            if "payload" in payload and isinstance(payload.get("payload"), dict)
            else payload.get("candles")
        )

        if candles is None:
            raise GrowwDataFormatError("Groww response missing 'candles' field.")

        if not candles:
            return pd.DataFrame(columns=list(CANONICAL_OHLCV_COLUMNS))

        return self._parse_candles(candles)

    def _parse_candles(self, candles: list[Any]) -> pd.DataFrame:
        """Parse raw candle array into canonical DataFrame."""
        if not isinstance(candles, list):
            raise GrowwDataFormatError("Expected candles to be a list.")

        timestamps = []
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []

        for row in candles:
            if not isinstance(row, (list, tuple)) or len(row) < 6:
                raise GrowwDataFormatError(f"Malformed candle row structure: {row}")

            ts, o, h, l, c, v = row[0], row[1], row[2], row[3], row[4], row[5]
            timestamps.append(ts)
            opens.append(o)
            highs.append(h)
            lows.append(l)
            closes.append(c)
            volumes.append(v)

        # Convert epoch seconds to Indian Standard Time (Asia/Kolkata), then strip tz
        dt_index = pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(
            "Asia/Kolkata"
        ).tz_localize(None)

        df = pd.DataFrame(
            {
                "Open": pd.to_numeric(opens, errors="coerce"),
                "High": pd.to_numeric(highs, errors="coerce"),
                "Low": pd.to_numeric(lows, errors="coerce"),
                "Close": pd.to_numeric(closes, errors="coerce"),
                "Volume": pd.to_numeric(volumes, errors="coerce"),
            },
            index=dt_index,
        )
        df.index.name = None

        return df
