"""Comprehensive mock-based tests for Phase 10B Groww Market Data Provider.

Zero external HTTP calls are performed.
Zero real credentials are used or logged.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock
import httpx
import pandas as pd
import pytest

from src.data.market_data import CANONICAL_OHLCV_COLUMNS, MarketDataRequest
from src.data.market_data_service import MarketDataService
from src.data.providers.groww import (
    DEFAULT_SYMBOL_MAP,
    GrowwProvider,
)
from src.data.providers.groww_config import GrowwConfig
from src.data.providers.groww_errors import (
    GrowwAPIError,
    GrowwAuthenticationError,
    GrowwDataFormatError,
    GrowwError,
    GrowwRateLimitError,
    GrowwSymbolMappingError,
)
from src.data.providers.local import LocalProvider


# ---------------------------------------------------------------------------
# Test Helpers & Mock Client
# ---------------------------------------------------------------------------

SECRET_TOKEN = "TEST_GROWW_TOKEN_DO_NOT_LEAK_98765"


def create_mock_response(status_code: int, payload: dict | list | str) -> httpx.Response:
    """Create a mock httpx.Response with json content."""
    if isinstance(payload, (dict, list)):
        content = json.dumps(payload).encode("utf-8")
    else:
        content = str(payload).encode("utf-8")
    return httpx.Response(status_code=status_code, content=content)


def sample_groww_payload(candles: list | None = None) -> dict:
    """Standard success payload structure from Groww historical candles API."""
    if candles is None:
        # Default 2 valid candles:
        # 1704080700: 2024-01-01 09:15:00 IST
        # 1704080760: 2024-01-01 09:16:00 IST
        candles = [
            [1704080700, 100.0, 105.0, 98.0, 102.0, 1500],
            [1704080760, 102.0, 106.0, 101.0, 104.0, 1200],
        ]
    return {
        "status": "SUCCESS",
        "payload": {
            "candles": candles,
            "start_time": "2024-01-01 09:15:00",
            "end_time": "2024-01-01 09:16:00",
            "interval_in_minutes": 1,
        },
    }


# ---------------------------------------------------------------------------
# 1. Configuration & Secrets Safety Tests
# ---------------------------------------------------------------------------


def test_groww_config_from_env(monkeypatch):
    """Verify GrowwConfig reads environment variables cleanly."""
    monkeypatch.setenv("GROWW_API_KEY", SECRET_TOKEN)
    monkeypatch.setenv("GROWW_API_SECRET", "MY_SECRET")
    monkeypatch.setenv("GROWW_API_BASE_URL", "https://custom.api.groww.in/v1")
    monkeypatch.setenv("GROWW_REQUEST_TIMEOUT", "45.5")

    cfg = GrowwConfig.from_env()
    assert cfg.api_key == SECRET_TOKEN
    assert cfg.api_secret == "MY_SECRET"
    assert cfg.base_url == "https://custom.api.groww.in/v1"
    assert cfg.timeout == 45.5
    assert cfg.is_configured is True


def test_groww_config_missing_env(monkeypatch):
    """Verify GrowwConfig is unconfigured when env var is empty."""
    monkeypatch.delenv("GROWW_API_KEY", raising=False)
    monkeypatch.delenv("GROWW_API_SECRET", raising=False)

    cfg = GrowwConfig.from_env()
    assert cfg.api_key is None
    assert cfg.is_configured is False


def test_secrets_safety_in_repr():
    """Ensure API key and secret are NEVER exposed in repr."""
    cfg = GrowwConfig(api_key=SECRET_TOKEN, api_secret="SUPER_SECRET")
    repr_str = repr(cfg)
    assert SECRET_TOKEN not in repr_str
    assert "SUPER_SECRET" not in repr_str
    assert "***" in repr_str


# ---------------------------------------------------------------------------
# 2. Provider Construction & Availability
# ---------------------------------------------------------------------------


def test_provider_availability():
    """is_available() reflects presence of API credentials."""
    unavail_provider = GrowwProvider(config=GrowwConfig(api_key=None))
    assert unavail_provider.is_available() is False

    avail_provider = GrowwProvider(config=GrowwConfig(api_key=SECRET_TOKEN))
    assert avail_provider.is_available() is True
    assert avail_provider.provider_name == "groww"


def test_unconfigured_provider_raises():
    """Querying unconfigured provider raises GrowwAuthenticationError."""
    provider = GrowwProvider(config=GrowwConfig(api_key=None))
    req = MarketDataRequest("TCS")
    with pytest.raises(GrowwAuthenticationError, match="Groww credentials are not configured"):
        provider.get_historical(req)


# ---------------------------------------------------------------------------
# 3. Symbol Mapping & Interval Validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "symbol,expected_groww_symbol",
    [
        ("RELIANCE", "NSE-RELIANCE"),
        ("TCS", "NSE-TCS"),
        ("INFY", "NSE-INFY"),
        ("HDFCBANK", "NSE-HDFCBANK"),
        ("SBIN", "NSE-SBIN"),
        ("CustomStock", "NSE-CUSTOMSTOCK"),
    ],
)
def test_symbol_mapping(symbol, expected_groww_symbol):
    """Verify default symbol mapping matches Groww instrument convention."""
    provider = GrowwProvider(config=GrowwConfig(api_key=SECRET_TOKEN))
    assert provider.resolve_groww_symbol(symbol, "NSE") == expected_groww_symbol


def test_custom_symbol_map_override():
    """Verify custom symbol mappings override default behavior."""
    provider = GrowwProvider(
        config=GrowwConfig(api_key=SECRET_TOKEN),
        symbol_map={"CUSTOM": "SPECIAL_GROWW_INSTRUMENT"},
    )
    assert provider.resolve_groww_symbol("CUSTOM") == "SPECIAL_GROWW_INSTRUMENT"


def test_unsupported_interval_rejected():
    """Unsupported intervals like 45m or 1wk are rejected."""
    provider = GrowwProvider(config=GrowwConfig(api_key=SECRET_TOKEN))
    req = MarketDataRequest(symbol="TCS", interval="45m")
    with pytest.raises(ValueError, match="Interval '45m' is not supported by Groww"):
        provider.get_historical(req)


# ---------------------------------------------------------------------------
# 4. Successful Historical Response & Normalization
# ---------------------------------------------------------------------------


def test_successful_response_and_normalization():
    """Verify valid response is converted to canonical OHLCV with IST DatetimeIndex."""
    mock_client = MagicMock()
    mock_client.get.return_value = create_mock_response(200, sample_groww_payload())

    provider = GrowwProvider(
        config=GrowwConfig(api_key=SECRET_TOKEN),
        http_client=mock_client,
    )

    req = MarketDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        interval="1m",
        start="2024-01-01 09:15:00",
        end="2024-01-01 09:16:00",
    )
    res = provider.get_historical(req)

    assert res.symbol == "RELIANCE"
    assert res.exchange == "NSE"
    assert res.provider == "groww"
    assert list(res.data.columns) == list(CANONICAL_OHLCV_COLUMNS)
    assert len(res.data) == 2

    # Check timestamps: 1704080700 -> 2024-01-01 09:15:00
    expected_start_ts = pd.Timestamp("2024-01-01 09:15:00")
    assert res.data.index[0] == expected_start_ts
    assert res.data.index.tz is None  # Canonical format is timezone-naive local IST

    # Check metadata & secrets safety
    assert res.metadata["source"] == "groww"
    assert res.metadata["groww_symbol"] == "NSE-RELIANCE"
    assert res.metadata["row_count"] == 2
    assert SECRET_TOKEN not in str(res.metadata)


# ---------------------------------------------------------------------------
# 5. Data Invariant & Rejection Tests
# ---------------------------------------------------------------------------


def test_reject_invalid_ohlc_relationships():
    """Reject response where High < Open or Low > Close."""
    # High = 90 while Open = 100
    bad_candles = [[1704080700, 100.0, 90.0, 85.0, 95.0, 1000]]
    mock_client = MagicMock()
    mock_client.get.return_value = create_mock_response(200, sample_groww_payload(bad_candles))

    provider = GrowwProvider(config=GrowwConfig(api_key=SECRET_TOKEN), http_client=mock_client)
    with pytest.raises(ValueError, match="invalid High values"):
        provider.get_historical(MarketDataRequest("TCS"))


def test_reject_negative_volume():
    """Reject response containing negative volume."""
    bad_candles = [[1704080700, 100.0, 105.0, 95.0, 102.0, -500]]
    mock_client = MagicMock()
    mock_client.get.return_value = create_mock_response(200, sample_groww_payload(bad_candles))

    provider = GrowwProvider(config=GrowwConfig(api_key=SECRET_TOKEN), http_client=mock_client)
    with pytest.raises(ValueError, match="negative volume"):
        provider.get_historical(MarketDataRequest("TCS"))


def test_reject_non_positive_low():
    """Reject response containing zero or negative low price."""
    bad_candles = [[1704080700, 100.0, 105.0, 0.0, 102.0, 500]]
    mock_client = MagicMock()
    mock_client.get.return_value = create_mock_response(200, sample_groww_payload(bad_candles))

    provider = GrowwProvider(config=GrowwConfig(api_key=SECRET_TOKEN), http_client=mock_client)
    with pytest.raises(ValueError, match="non-positive Low values"):
        provider.get_historical(MarketDataRequest("TCS"))


def test_reject_nan_values():
    """Reject response containing NaN in OHLCV fields."""
    bad_candles = [[1704080700, None, 105.0, 95.0, 102.0, 500]]
    mock_client = MagicMock()
    mock_client.get.return_value = create_mock_response(200, sample_groww_payload(bad_candles))

    provider = GrowwProvider(config=GrowwConfig(api_key=SECRET_TOKEN), http_client=mock_client)
    with pytest.raises(ValueError, match="contains NaN OHLCV values"):
        provider.get_historical(MarketDataRequest("TCS"))


# ---------------------------------------------------------------------------
# 6. HTTP & API Failure Tests
# ---------------------------------------------------------------------------


def test_authentication_failure_401():
    """HTTP 401 raises GrowwAuthenticationError without leaking token."""
    mock_client = MagicMock()
    mock_client.get.return_value = create_mock_response(401, {"message": "Invalid token"})

    provider = GrowwProvider(config=GrowwConfig(api_key=SECRET_TOKEN), http_client=mock_client)
    with pytest.raises(GrowwAuthenticationError) as exc_info:
        provider.get_historical(MarketDataRequest("TCS"))

    assert SECRET_TOKEN not in str(exc_info.value)


def test_rate_limit_failure_429():
    """HTTP 429 raises GrowwRateLimitError."""
    mock_client = MagicMock()
    mock_client.get.return_value = create_mock_response(429, {"message": "Rate limit exceeded"})

    provider = GrowwProvider(config=GrowwConfig(api_key=SECRET_TOKEN), http_client=mock_client)
    with pytest.raises(GrowwRateLimitError, match="rate limit exceeded"):
        provider.get_historical(MarketDataRequest("TCS"))


def test_server_error_500():
    """HTTP 500 raises GrowwAPIError."""
    mock_client = MagicMock()
    mock_client.get.return_value = create_mock_response(500, "Internal Server Error")

    provider = GrowwProvider(config=GrowwConfig(api_key=SECRET_TOKEN), http_client=mock_client)
    with pytest.raises(GrowwAPIError, match="error status 500"):
        provider.get_historical(MarketDataRequest("TCS"))


def test_malformed_json_response():
    """Non-JSON response raises GrowwDataFormatError."""
    mock_client = MagicMock()
    mock_client.get.return_value = create_mock_response(200, "NOT_JSON")

    provider = GrowwProvider(config=GrowwConfig(api_key=SECRET_TOKEN), http_client=mock_client)
    with pytest.raises(GrowwDataFormatError, match="Failed to parse JSON"):
        provider.get_historical(MarketDataRequest("TCS"))


def test_empty_response():
    """Response with empty candles list raises ValueError."""
    mock_client = MagicMock()
    mock_client.get.return_value = create_mock_response(200, sample_groww_payload([]))

    provider = GrowwProvider(config=GrowwConfig(api_key=SECRET_TOKEN), http_client=mock_client)
    with pytest.raises(ValueError, match="No market data returned by Groww"):
        provider.get_historical(MarketDataRequest("TCS"))


# ---------------------------------------------------------------------------
# 7. Bounded Chunking & Boundary Overlap Tests
# ---------------------------------------------------------------------------


def test_chunking_for_large_date_range():
    """Range exceeding 30 days for 1m is chunked deterministically and deduplicated."""
    # 45-day request
    start = "2024-01-01 09:15:00"
    end = "2024-02-15 15:30:00"

    # Chunk 1: covers Jan 1 to Jan 31
    chunk1_candles = [
        [1704080700, 100.0, 105.0, 98.0, 102.0, 1000],  # Jan 1 09:15
        [1706673600, 102.0, 106.0, 100.0, 104.0, 1200],  # Jan 31 09:20
    ]
    # Chunk 2: covers Jan 31 to Feb 15 (includes duplicate boundary candle Jan 31 09:20)
    chunk2_candles = [
        [1706673600, 102.0, 106.0, 100.0, 104.0, 1200],  # DUPLICATE boundary candle
        [1707991200, 104.0, 108.0, 103.0, 107.0, 1400],  # Feb 15 15:20
    ]

    mock_client = MagicMock()
    mock_client.get.side_effect = [
        create_mock_response(200, sample_groww_payload(chunk1_candles)),
        create_mock_response(200, sample_groww_payload(chunk2_candles)),
    ]

    provider = GrowwProvider(config=GrowwConfig(api_key=SECRET_TOKEN), http_client=mock_client)
    req = MarketDataRequest("TCS", interval="1m", start=start, end=end)
    result = provider.get_historical(req)

    # 2 HTTP calls must have been made
    assert mock_client.get.call_count == 2
    # Duplicate boundary candle must have been stripped: exactly 3 distinct rows
    assert len(result.data) == 3
    assert result.data.index.is_monotonic_increasing
    assert not result.data.index.has_duplicates
    assert result.metadata["chunks_count"] == 2


# ---------------------------------------------------------------------------
# 8. Service Integration & Zero Silent Fallback
# ---------------------------------------------------------------------------


def test_service_routes_to_groww():
    """MarketDataService successfully routes request to GrowwProvider."""
    mock_client = MagicMock()
    mock_client.get.return_value = create_mock_response(200, sample_groww_payload())

    groww_provider = GrowwProvider(
        config=GrowwConfig(api_key=SECRET_TOKEN),
        http_client=mock_client,
    )
    service = MarketDataService(auto_register_local=False)
    service.register_provider(groww_provider, set_as_default=True)

    res = service.get_historical(MarketDataRequest("INFY"))
    assert res.provider == "groww"
    assert res.symbol == "INFY"


def test_service_never_silently_falls_back_from_groww(tmp_path):
    """If Groww fails, service raises Groww error and NEVER falls back to local."""
    # Create local provider with local file
    local_file = tmp_path / "INFY_1m.csv"
    local_file.write_text(
        "timestamp,open,high,low,close,volume\n2024-01-01 09:15:00,100,105,98,102,1000\n"
    )
    local_provider = LocalProvider(data_directory=tmp_path)

    # Groww provider configured to fail (e.g. 401 error)
    mock_client = MagicMock()
    mock_client.get.return_value = create_mock_response(401, {"message": "Invalid token"})
    failing_groww = GrowwProvider(
        config=GrowwConfig(api_key=SECRET_TOKEN),
        http_client=mock_client,
    )

    service = MarketDataService(auto_register_local=False)
    service.register_provider(local_provider)
    service.register_provider(failing_groww, set_as_default=True)

    # When querying groww, error must be raised directly without falling back to local
    with pytest.raises(GrowwAuthenticationError):
        service.get_historical(MarketDataRequest("INFY"), provider_name="groww")
