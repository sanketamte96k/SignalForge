"""Tests for Phase 10A Provider-Agnostic Market Data Service and Abstraction Layer."""

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from src.data.market_data import (
    CANONICAL_OHLCV_COLUMNS,
    MarketDataProvider,
    MarketDataRequest,
    MarketDataResult,
    normalize_ohlcv_columns,
    validate_normalized_ohlcv,
)
from src.data.market_data_service import (
    MarketDataService,
    ProviderUnavailableError,
    UnknownProviderError,
)
from src.data.providers.local import LocalProvider


# ---------------------------------------------------------------------------
# Helpers & Dummy Providers
# ---------------------------------------------------------------------------


def make_valid_ohlcv_df() -> pd.DataFrame:
    """Create a minimal valid canonical OHLCV DataFrame."""
    idx = pd.to_datetime(
        [
            "2024-01-01 09:15:00",
            "2024-01-01 09:16:00",
            "2024-01-01 09:17:00",
        ]
    )
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [105.0, 106.0, 107.0],
            "Low": [98.0, 99.0, 100.0],
            "Close": [102.0, 103.0, 104.0],
            "Volume": [1000.0, 1500.0, 2000.0],
        },
        index=idx,
    )


class DummyProvider(MarketDataProvider):
    """Configurable dummy provider for isolated service testing."""

    def __init__(
        self,
        name: str = "dummy",
        available: bool = True,
        should_fail: bool = False,
    ) -> None:
        self._name = name
        self._available = available
        self._should_fail = should_fail
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self._available

    def get_historical(self, request: MarketDataRequest) -> MarketDataResult:
        self.call_count += 1
        if self._should_fail:
            raise RuntimeError(f"Provider {self._name} simulated crash")

        df = make_valid_ohlcv_df()
        return MarketDataResult(
            symbol=request.symbol,
            exchange=request.exchange,
            interval=request.interval,
            data=df,
            provider=self.provider_name,
            requested_start=request.start,
            requested_end=request.end,
            metadata={"source": "dummy_test", "custom_key": 42},
        )


# ---------------------------------------------------------------------------
# 1. MarketDataRequest Validation Tests
# ---------------------------------------------------------------------------


def test_valid_request_construction():
    """Verify normal construction and normalization of MarketDataRequest."""
    req = MarketDataRequest(
        symbol="infy",
        exchange="nse",
        interval="5m",
        start="2024-01-01",
        end="2024-01-05",
        adjusted=True,
    )
    assert req.symbol == "INFY"
    assert req.exchange == "NSE"
    assert req.interval == "5m"
    assert req.start == "2024-01-01"
    assert req.end == "2024-01-05"
    assert req.adjusted is True


@pytest.mark.parametrize("invalid_symbol", ["", "   ", None, 123])
def test_invalid_symbol_rejection(invalid_symbol):
    """Reject empty, whitespace, non-string, or None symbols."""
    with pytest.raises((ValueError, TypeError)):
        MarketDataRequest(symbol=invalid_symbol)


@pytest.mark.parametrize("invalid_interval", ["", "1x", "daily", "abc", 15])
def test_invalid_interval_rejection(invalid_interval):
    """Reject invalid or unsupported interval formats."""
    with pytest.raises((ValueError, TypeError)):
        MarketDataRequest(symbol="TCS", interval=invalid_interval)


def test_invalid_date_range_rejection():
    """Reject requests where start date is strictly after end date."""
    with pytest.raises(ValueError, match="must be before or equal to end date"):
        MarketDataRequest(
            symbol="TCS",
            start="2024-05-10",
            end="2024-05-01",
        )


def test_invalid_date_format_rejection():
    """Reject requests where date strings are unparseable."""
    with pytest.raises(ValueError, match="Failed to parse"):
        MarketDataRequest(
            symbol="TCS",
            start="not-a-date",
            end="2024-05-01",
        )


# ---------------------------------------------------------------------------
# 2. Canonical OHLCV Contract Validation Tests
# ---------------------------------------------------------------------------


def test_validate_normalized_ohlcv_success():
    """Verify valid DataFrame passes canonical validation."""
    df = make_valid_ohlcv_df()
    validate_normalized_ohlcv(df)


def test_validate_rejects_empty():
    """Reject empty DataFrame."""
    df = pd.DataFrame()
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_normalized_ohlcv(df)


def test_validate_rejects_non_datetime_index():
    """Reject DataFrame lacking a DatetimeIndex."""
    df = make_valid_ohlcv_df()
    df.index = [1, 2, 3]
    with pytest.raises(TypeError, match="DatetimeIndex"):
        validate_normalized_ohlcv(df)


def test_validate_rejects_nat_index():
    """Reject DataFrame containing NaT in index."""
    df = make_valid_ohlcv_df()
    new_index = list(df.index)
    new_index[1] = pd.NaT
    df.index = pd.DatetimeIndex(new_index)
    with pytest.raises(ValueError, match="contains NaT"):
        validate_normalized_ohlcv(df)


def test_validate_rejects_duplicate_timestamps():
    """Reject DataFrame with duplicate index entries."""
    idx = pd.to_datetime(
        ["2024-01-01 09:15:00", "2024-01-01 09:15:00", "2024-01-01 09:16:00"]
    )
    df = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 101.0],
            "High": [105.0, 105.0, 106.0],
            "Low": [98.0, 98.0, 99.0],
            "Close": [102.0, 102.0, 103.0],
            "Volume": [1000.0, 1000.0, 1500.0],
        },
        index=idx,
    )
    with pytest.raises(ValueError, match="duplicate timestamps"):
        validate_normalized_ohlcv(df)


def test_validate_rejects_non_monotonic_timestamps():
    """Reject DataFrame whose timestamps are not strictly ascending."""
    idx = pd.to_datetime(
        ["2024-01-01 09:17:00", "2024-01-01 09:15:00", "2024-01-01 09:16:00"]
    )
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [105.0, 106.0, 107.0],
            "Low": [98.0, 99.0, 100.0],
            "Close": [102.0, 103.0, 104.0],
            "Volume": [1000.0, 1500.0, 2000.0],
        },
        index=idx,
    )
    with pytest.raises(ValueError, match="sorted in ascending order"):
        validate_normalized_ohlcv(df)


def test_validate_rejects_missing_columns():
    """Reject DataFrame missing canonical OHLCV columns."""
    df = make_valid_ohlcv_df().drop(columns=["Volume"])
    with pytest.raises(ValueError, match="Missing required canonical columns"):
        validate_normalized_ohlcv(df)


def test_validate_rejects_nan_values():
    """Reject DataFrame containing NaN in OHLCV columns."""
    df = make_valid_ohlcv_df()
    df.iloc[1, 0] = float("nan")
    with pytest.raises(ValueError, match="contains NaN OHLCV values"):
        validate_normalized_ohlcv(df)


def test_validate_rejects_invalid_high_low():
    """Reject DataFrame with High < Open, High < Close, Low > Open, or Low > Close."""
    # High < Open
    df_bad_high = make_valid_ohlcv_df()
    df_bad_high.iloc[0, 1] = 90.0  # High=90 while Open=100
    with pytest.raises(ValueError, match="invalid High values"):
        validate_normalized_ohlcv(df_bad_high)

    # Low > Close
    df_bad_low = make_valid_ohlcv_df()
    df_bad_low.iloc[0, 2] = 104.0  # Low=104 while Close=102
    with pytest.raises(ValueError, match="invalid Low values"):
        validate_normalized_ohlcv(df_bad_low)


def test_validate_rejects_negative_volume():
    """Reject DataFrame with negative volume."""
    df = make_valid_ohlcv_df()
    df.iloc[0, 4] = -100.0
    with pytest.raises(ValueError, match="negative volume"):
        validate_normalized_ohlcv(df)


def test_normalize_ohlcv_columns():
    """Verify column normalization to Title Case."""
    raw = pd.DataFrame(
        {
            "open": [100.0],
            "HIGH": [105.0],
            "Low": [98.0],
            "Close": [102.0],
            "volume": [1000.0],
        }
    )
    normalized = normalize_ohlcv_columns(raw)
    assert list(normalized.columns) == list(CANONICAL_OHLCV_COLUMNS)


# ---------------------------------------------------------------------------
# 3. MarketDataService Registration & Routing Tests
# ---------------------------------------------------------------------------


def test_provider_registration_and_listing():
    """Register providers and verify provider listing."""
    service = MarketDataService(auto_register_local=False)
    p1 = DummyProvider("mock_a")
    p2 = DummyProvider("mock_b")

    service.register_provider(p1)
    service.register_provider(p2)

    assert service.list_providers() == ["mock_a", "mock_b"]
    assert service.get_provider("mock_a") is p1
    assert service.get_provider("MOCK_B") is p2


def test_default_provider():
    """Test default provider assignment and query fallback."""
    service = MarketDataService(auto_register_local=False)
    p1 = DummyProvider("alpha")
    p2 = DummyProvider("beta")

    service.register_provider(p1)
    assert service.default_provider == "alpha"

    service.register_provider(p2, set_as_default=True)
    assert service.default_provider == "beta"

    req = MarketDataRequest("INFY")
    res = service.get_historical(req)
    assert res.provider == "beta"
    assert p2.call_count == 1
    assert p1.call_count == 0


def test_explicit_provider_selection():
    """Explicitly selecting a provider queries only that provider."""
    service = MarketDataService(auto_register_local=False)
    p1 = DummyProvider("alpha")
    p2 = DummyProvider("beta")
    service.register_provider(p1, set_as_default=True)
    service.register_provider(p2)

    req = MarketDataRequest("TCS")
    res = service.get_historical(req, provider_name="beta")
    assert res.provider == "beta"
    assert p2.call_count == 1
    assert p1.call_count == 0


def test_unknown_provider_failure():
    """Querying or setting an unknown provider fails with UnknownProviderError."""
    service = MarketDataService(auto_register_local=False)
    service.register_provider(DummyProvider("alpha"))

    with pytest.raises(UnknownProviderError, match="not registered"):
        service.get_historical(MarketDataRequest("TCS"), provider_name="nonexistent")

    with pytest.raises(UnknownProviderError, match="Cannot set default"):
        service.set_default_provider("nonexistent")


def test_provider_availability():
    """Verify provider availability checks and error on unavailable provider."""
    service = MarketDataService(auto_register_local=False)
    p_avail = DummyProvider("online", available=True)
    p_unavail = DummyProvider("offline", available=False)

    service.register_provider(p_avail)
    service.register_provider(p_unavail)

    status = service.get_provider_status()
    assert status == {"online": True, "offline": False}
    assert service.get_provider_status("online") == {"online": True}

    with pytest.raises(ProviderUnavailableError, match="currently unavailable"):
        service.get_historical(MarketDataRequest("TCS"), provider_name="offline")


def test_service_never_silently_falls_back():
    """If the selected provider crashes, service propagates error without fallback."""
    service = MarketDataService(auto_register_local=False)
    crashing_provider = DummyProvider("fragile", should_fail=True)
    backup_provider = DummyProvider("backup", should_fail=False)

    service.register_provider(crashing_provider, set_as_default=True)
    service.register_provider(backup_provider)

    req = MarketDataRequest("RELIANCE")
    with pytest.raises(RuntimeError, match="simulated crash"):
        service.get_historical(req, provider_name="fragile")

    # Verify backup was NEVER called
    assert backup_provider.call_count == 0
    assert crashing_provider.call_count == 1


def test_provider_metadata_preserved():
    """Verify provider metadata is preserved in MarketDataResult."""
    service = MarketDataService(auto_register_local=False)
    provider = DummyProvider("meta_tester")
    service.register_provider(provider)

    res = service.get_historical(MarketDataRequest("INFY"))
    assert res.metadata.get("source") == "dummy_test"
    assert res.metadata.get("custom_key") == 42


# ---------------------------------------------------------------------------
# 4. LocalProvider Tests (Isolated with Temporary Directory)
# ---------------------------------------------------------------------------


def test_local_provider_returns_normalized_ohlcv(tmp_path: Path):
    """LocalProvider reads valid CSV, normalizes columns, and validates OHLCV."""
    csv_file = tmp_path / "SAMPLE_1m.csv"
    csv_content = (
        "timestamp,open,high,low,close,volume\n"
        "2024-01-01 09:15:00,100.0,105.0,98.0,102.0,1000\n"
        "2024-01-01 09:16:00,102.0,106.0,101.0,104.0,1500\n"
    )
    csv_file.write_text(csv_content, encoding="utf-8")

    provider = LocalProvider(data_directory=tmp_path)
    assert provider.is_available() is True

    service = MarketDataService(auto_register_local=False)
    service.register_provider(provider)

    req = MarketDataRequest(
        symbol="SAMPLE",
        interval="1m",
        start="2024-01-01 09:15:00",
        end="2024-01-01 09:16:00",
    )
    result = service.get_historical(req)

    assert result.symbol == "SAMPLE"
    assert result.provider == "local"
    assert list(result.data.columns) == list(CANONICAL_OHLCV_COLUMNS)
    assert len(result.data) == 2
    assert "file_checksum" in result.metadata
    assert result.metadata["row_count"] == 2


def test_local_provider_rejects_missing_file(tmp_path: Path):
    """LocalProvider raises FileNotFoundError when target dataset is missing."""
    provider = LocalProvider(data_directory=tmp_path)
    req = MarketDataRequest("MISSING_TICKER")
    with pytest.raises(FileNotFoundError, match="Local market data not found"):
        provider.get_historical(req)


def test_local_provider_rejects_malformed_data(tmp_path: Path):
    """LocalProvider rejects CSV missing required columns."""
    csv_file = tmp_path / "BADCOL_1m.csv"
    csv_file.write_text("timestamp,open,close\n2024-01-01 09:15:00,100,102\n")
    provider = LocalProvider(data_directory=tmp_path)

    with pytest.raises(ValueError, match="Missing required canonical columns"):
        provider.get_historical(MarketDataRequest("BADCOL"))


def test_local_provider_rejects_duplicate_timestamps(tmp_path: Path):
    """LocalProvider rejects CSV with duplicate timestamps."""
    csv_file = tmp_path / "DUP_1m.csv"
    csv_content = (
        "timestamp,open,high,low,close,volume\n"
        "2024-01-01 09:15:00,100,105,98,102,1000\n"
        "2024-01-01 09:15:00,100,105,98,102,1000\n"
    )
    csv_file.write_text(csv_content)
    provider = LocalProvider(data_directory=tmp_path)

    with pytest.raises(ValueError, match="duplicate timestamps"):
        provider.get_historical(MarketDataRequest("DUP"))


def test_local_provider_rejects_non_monotonic_timestamps(tmp_path: Path):
    """LocalProvider rejects CSV with non-monotonic timestamps."""
    csv_file = tmp_path / "NONMONO_1m.csv"
    csv_content = (
        "timestamp,open,high,low,close,volume\n"
        "2024-01-01 09:16:00,100,105,98,102,1000\n"
        "2024-01-01 09:15:00,100,105,98,102,1000\n"
    )
    csv_file.write_text(csv_content)
    provider = LocalProvider(data_directory=tmp_path)

    with pytest.raises(ValueError, match="sorted in ascending order"):
        provider.get_historical(MarketDataRequest("NONMONO"))


def test_local_provider_rejects_nan_values(tmp_path: Path):
    """LocalProvider rejects CSV with NaN values in OHLCV."""
    csv_file = tmp_path / "NAN_1m.csv"
    csv_content = (
        "timestamp,open,high,low,close,volume\n"
        "2024-01-01 09:15:00,100,,98,102,1000\n"
    )
    csv_file.write_text(csv_content)
    provider = LocalProvider(data_directory=tmp_path)

    with pytest.raises(ValueError, match="contains NaN OHLCV values"):
        provider.get_historical(MarketDataRequest("NAN"))


def test_local_provider_rejects_invalid_ohlc(tmp_path: Path):
    """LocalProvider rejects CSV with invalid OHLC relationship (High < Low)."""
    csv_file = tmp_path / "BADOHLC_1m.csv"
    csv_content = (
        "timestamp,open,high,low,close,volume\n"
        "2024-01-01 09:15:00,100,95,102,96,1000\n"
    )
    csv_file.write_text(csv_content)
    provider = LocalProvider(data_directory=tmp_path)

    with pytest.raises(ValueError, match="invalid High values"):
        provider.get_historical(MarketDataRequest("BADOHLC"))


def test_local_provider_rejects_negative_volume(tmp_path: Path):
    """LocalProvider rejects CSV with negative volume."""
    csv_file = tmp_path / "NEGVOL_1m.csv"
    csv_content = (
        "timestamp,open,high,low,close,volume\n"
        "2024-01-01 09:15:00,100,105,98,102,-50\n"
    )
    csv_file.write_text(csv_content)
    provider = LocalProvider(data_directory=tmp_path)

    with pytest.raises(ValueError, match="negative volume"):
        provider.get_historical(MarketDataRequest("NEGVOL"))
