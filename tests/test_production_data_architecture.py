"""Unit tests for Phase 7 Production Data Acquisition Architecture.

Verifies the state machine, dataset manifest, cryptographic checksums,
directory contracts, corporate action symbol mappings, and data integrity
validators using isolated synthetic test fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import pandas as pd

from src.data.acquisition import (
    DataDirectoryContract,
    DataIntegrityValidator,
    DatasetManifest,
    IngestionState,
    InvalidStateTransitionError,
    SymbolMappingRegistry,
    compute_checksum,
    validate_state_transition,
)


def _build_synthetic_df(
    bars: int = 5,
    start: str = "2015-01-01 09:15:00",
) -> pd.DataFrame:
    """Create a minimal synthetically valid OHLCV DataFrame."""
    index = pd.date_range(start=start, periods=bars, freq="min")
    return pd.DataFrame(
        {
            "open": [100.0] * bars,
            "high": [105.0] * bars,
            "low": [95.0] * bars,
            "close": [102.0] * bars,
            "volume": [1000.0] * bars,
        },
        index=index,
    )


# ---------------------------------------------------------------------------
# 1. Valid Manifest Creation
# ---------------------------------------------------------------------------


def test_valid_manifest_creation() -> None:
    """DatasetManifest instantiates with valid parameters and defaults."""
    manifest = DatasetManifest(
        dataset_id="DS-RELIANCE-2015-Q1",
        source="TickData",
        source_file="data/historical/raw/RELIANCE/reliance_1m.csv",
        symbol="RELIANCE",
        historical_symbol="RELIANCE",
        requested_start="2015-01-01 00:00:00",
        requested_end="2024-03-26 15:29:00",
        actual_start="2015-01-01 09:15:00",
        actual_end="2024-03-26 15:29:00",
        interval="1m",
        timezone="Asia/Kolkata",
        row_count=845625,
        checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        validation_status=IngestionState.RECEIVED,
    )

    assert manifest.dataset_id == "DS-RELIANCE-2015-Q1"
    assert manifest.symbol == "RELIANCE"
    assert manifest.historical_symbol == "RELIANCE"
    assert manifest.row_count == 845625
    assert manifest.validation_status == IngestionState.RECEIVED
    assert manifest.validation_errors == []
    assert manifest.ingested_at is not None


# ---------------------------------------------------------------------------
# 2. Deterministic Checksum
# ---------------------------------------------------------------------------


def test_deterministic_checksum() -> None:
    """compute_checksum produces the mathematically expected SHA-256 digest."""
    content = "SignalForge-MarketData-Contract"
    expected = "a718467bef5c76252728dce9152c5665083ef5c52c1fccb864e60e99bdced364"
    digest = compute_checksum(content)
    assert digest == expected


# ---------------------------------------------------------------------------
# 3. Repeated Checksum Consistency
# ---------------------------------------------------------------------------


def test_repeated_checksum_consistency(tmp_path: Path) -> None:
    """Repeated checksum calculations across string, bytes, and file are identical."""
    raw_bytes = b"OHLCV,100,105,95,102,1000\n"
    file_path = tmp_path / "sample_test.csv"
    file_path.write_bytes(raw_bytes)

    hash_str = compute_checksum(raw_bytes.decode("utf-8"))
    hash_bytes = compute_checksum(raw_bytes)
    hash_file = compute_checksum(file_path)

    assert hash_str == hash_bytes
    assert hash_bytes == hash_file


# ---------------------------------------------------------------------------
# 4. Invalid OHLC Rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "open_p,high_p,low_p,close_p,error_substr",
    [
        (100.0, 90.0, 80.0, 95.0, "invalid high values"),   # High < Open (90 < 100)
        (100.0, 95.0, 80.0, 98.0, "invalid high values"),   # High < Close (95 < 98)
        (100.0, 110.0, 105.0, 108.0, "invalid low values"), # Low > Open (105 > 100)
        (100.0, 110.0, 105.0, 102.0, "invalid low values"), # Low > Close (105 > 102)
    ],
)
def test_invalid_ohlc_rejection(
    open_p: float,
    high_p: float,
    low_p: float,
    close_p: float,
    error_substr: str,
) -> None:
    """DataIntegrityValidator rejects OHLC invariant violations."""
    df = pd.DataFrame(
        {
            "open": [open_p],
            "high": [high_p],
            "low": [low_p],
            "close": [close_p],
            "volume": [1000.0],
        },
        index=pd.date_range("2015-01-01 09:15:00", periods=1, freq="min"),
    )

    with pytest.raises(ValueError, match=error_substr):
        DataIntegrityValidator.validate_ohlcv_dataframe(df)


# ---------------------------------------------------------------------------
# 5. Negative Volume Rejection
# ---------------------------------------------------------------------------


def test_negative_volume_rejection() -> None:
    """Negative trade volumes are rejected immediately."""
    df = _build_synthetic_df(bars=3)
    df.iloc[1, df.columns.get_loc("volume")] = -1.0

    with pytest.raises(ValueError, match="negative volume"):
        DataIntegrityValidator.validate_ohlcv_dataframe(df)


# ---------------------------------------------------------------------------
# 6. Duplicate Timestamp Rejection
# ---------------------------------------------------------------------------


def test_duplicate_timestamp_rejection() -> None:
    """Duplicate timestamps in the index trigger a ValueError."""
    ts = pd.Timestamp("2015-01-01 09:15:00")
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [105.0, 106.0],
            "low": [95.0, 96.0],
            "close": [102.0, 103.0],
            "volume": [1000.0, 1000.0],
        },
        index=pd.DatetimeIndex([ts, ts]),
    )

    with pytest.raises(ValueError, match="duplicate timestamps"):
        DataIntegrityValidator.validate_ohlcv_dataframe(df)


# ---------------------------------------------------------------------------
# 7. Malformed Timestamp Rejection
# ---------------------------------------------------------------------------


def test_malformed_timestamp_rejection() -> None:
    """DatetimeIndex containing NaT values is rejected."""
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [105.0, 106.0],
            "low": [95.0, 96.0],
            "close": [102.0, 103.0],
            "volume": [1000.0, 1000.0],
        },
        index=pd.DatetimeIndex([pd.Timestamp("2015-01-01 09:15:00"), pd.NaT]),
    )

    with pytest.raises(ValueError, match="NaT|malformed timestamp"):
        DataIntegrityValidator.validate_ohlcv_dataframe(df)


# ---------------------------------------------------------------------------
# 8. Legal State Transitions
# ---------------------------------------------------------------------------


def test_legal_state_transitions() -> None:
    """The standard happy path through the state machine succeeds."""
    path = [
        IngestionState.RECEIVED,
        IngestionState.SCHEMA_VALID,
        IngestionState.NORMALIZED,
        IngestionState.QUALITY_VALID,
        IngestionState.SESSION_VALID,
        IngestionState.COVERAGE_VALID,
        IngestionState.READY_FOR_PRODUCTION,
    ]

    for current, target in zip(path[:-1], path[1:]):
        validate_state_transition(current, target)

    # Rejection transition
    validate_state_transition(IngestionState.RECEIVED, IngestionState.REJECTED)
    validate_state_transition(IngestionState.REJECTED, IngestionState.QUARANTINED)


# ---------------------------------------------------------------------------
# 9. Invalid State Transition Rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "current,target",
    [
        (IngestionState.RECEIVED, IngestionState.READY_FOR_PRODUCTION),
        (IngestionState.RECEIVED, IngestionState.NORMALIZED),
        (IngestionState.SCHEMA_VALID, IngestionState.QUALITY_VALID),
        (IngestionState.READY_FOR_PRODUCTION, IngestionState.RECEIVED),
        (IngestionState.QUARANTINED, IngestionState.READY_FOR_PRODUCTION),
        (IngestionState.REJECTED, IngestionState.READY_FOR_PRODUCTION),
    ],
)
def test_invalid_state_transition_rejection(
    current: IngestionState,
    target: IngestionState,
) -> None:
    """Illegal or skipped state transitions raise InvalidStateTransitionError."""
    with pytest.raises(InvalidStateTransitionError):
        validate_state_transition(current, target)


# ---------------------------------------------------------------------------
# 10. Quarantine Path Generation
# ---------------------------------------------------------------------------


def test_quarantine_path_generation(tmp_path: Path) -> None:
    """Quarantine path is deterministically formatted with symbol and reason."""
    contract = DataDirectoryContract(base_dir=tmp_path)
    contract.ensure_directories()

    qpath = contract.quarantine_path(
        symbol="RELIANCE",
        filename="reliance_sample.csv",
        reason="Negative Volume Detected",
    )

    assert qpath.name == "reliance_sample.csv"
    assert "RELIANCE" in str(qpath)
    assert "negative_volume_detected" in str(qpath)
    assert contract.quarantine_dir in qpath.parents


# ---------------------------------------------------------------------------
# 11. Explicit Legacy Symbol Mapping
# ---------------------------------------------------------------------------


def test_explicit_legacy_symbol_mapping() -> None:
    """Registry returns authoritative predecessor symbols for corporate actions."""
    assert SymbolMappingRegistry.get_historical_symbol("TMPV") == "TATAMOTORS"
    assert SymbolMappingRegistry.get_historical_symbol("SHRIRAMFIN") == "SRTRANSFIN"
    assert SymbolMappingRegistry.get_historical_symbol("TATACONSUM") == "TATAGLOBAL"
    assert SymbolMappingRegistry.get_historical_symbol("ETERNAL") == "ZOMATO"

    # Unmapped standard stock returns self
    assert SymbolMappingRegistry.get_historical_symbol("RELIANCE") == "RELIANCE"
    assert SymbolMappingRegistry.get_historical_symbol("TCS") == "TCS"

    # Detailed mapping object properties
    mapping = SymbolMappingRegistry.get_mapping("TMPV")
    assert mapping is not None
    assert mapping.historical_symbol == "TATAMOTORS"
    assert mapping.confidence == 1.0
    assert "demerger" in mapping.mapping_reason


# ---------------------------------------------------------------------------
# 12. Listing-Constrained Symbol Behavior
# ---------------------------------------------------------------------------


def test_listing_constrained_symbol_behavior() -> None:
    """Registry correctly identifies post-2015 IPO stocks and rejects fake pre-listing history."""
    constrained = ["HDFCLIFE", "SBILIFE", "INDIGO", "JIOFIN", "MAXHEALTH"]

    for symbol in constrained:
        assert SymbolMappingRegistry.is_listing_constrained(symbol) is True
        constraint = SymbolMappingRegistry.get_listing_constraint(symbol)
        assert constraint is not None

    # HDFCLIFE listed on 2017-11-17
    # Pre-listing candle must be rejected
    assert (
        SymbolMappingRegistry.validate_listing_boundary(
            "HDFCLIFE", "2015-01-01 09:15:00"
        )
        is False
    )
    # On or post-listing candle must be accepted
    assert (
        SymbolMappingRegistry.validate_listing_boundary(
            "HDFCLIFE", "2017-11-17 09:44:00"
        )
        is True
    )

    # Standard stock not listing constrained
    assert SymbolMappingRegistry.is_listing_constrained("RELIANCE") is False
    assert (
        SymbolMappingRegistry.validate_listing_boundary(
            "RELIANCE", "2015-01-01 09:15:00"
        )
        is True
    )


# ---------------------------------------------------------------------------
# 13. Idempotent Ingestion Behavior
# ---------------------------------------------------------------------------


def test_idempotent_ingestion_behavior(tmp_path: Path) -> None:
    """Re-ingesting an identical file detects matching checksums."""
    contract = DataDirectoryContract(base_dir=tmp_path)
    contract.ensure_directories()

    content = b"timestamp,open,high,low,close,volume\n2015-01-01 09:15:00,100,105,95,102,1000\n"
    raw_file = contract.raw_dir / "RELIANCE" / "reliance_1m.csv"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_bytes(content)

    checksum1 = compute_checksum(raw_file)

    # Simulate re-arrival of exact same file
    checksum2 = compute_checksum(raw_file)
    assert checksum1 == checksum2

    # Manifest retains identical checksum fingerprint
    manifest = DatasetManifest(
        dataset_id="DS-RELIANCE-TEST",
        source="TickData",
        source_file=str(raw_file),
        symbol="RELIANCE",
        historical_symbol="RELIANCE",
        requested_start="2015-01-01 00:00:00",
        requested_end="2024-03-26 15:29:00",
        actual_start="2015-01-01 09:15:00",
        actual_end="2015-01-01 09:15:00",
        interval="1m",
        timezone="Asia/Kolkata",
        row_count=1,
        checksum=checksum1,
        validation_status=IngestionState.READY_FOR_PRODUCTION,
    )

    # Re-checking checksum against manifest
    assert manifest.checksum == checksum2


# ---------------------------------------------------------------------------
# 14. Manifest Serialization and Deserialization
# ---------------------------------------------------------------------------


def test_manifest_serialization_deserialization() -> None:
    """Manifest cleanly round-trips to dict and JSON preserving types and enums."""
    original = DatasetManifest(
        dataset_id="DS-TCS-2015",
        source="TickData",
        source_file="data/historical/raw/TCS/tcs_1m.csv",
        symbol="TCS",
        historical_symbol="TCS",
        requested_start="2015-01-01 00:00:00",
        requested_end="2024-03-26 15:29:00",
        actual_start="2015-01-01 09:15:00",
        actual_end="2024-03-26 15:29:00",
        interval="1m",
        timezone="Asia/Kolkata",
        row_count=500000,
        checksum="abcdef1234567890",
        validation_status=IngestionState.QUALITY_VALID,
        validation_errors=["Warning: partial session on 2015-11-11"],
    )

    # Dict round-trip
    as_dict = original.to_dict()
    assert as_dict["validation_status"] == "QUALITY_VALID"
    from_dict = DatasetManifest.from_dict(as_dict)
    assert from_dict.validation_status == IngestionState.QUALITY_VALID
    assert from_dict.dataset_id == original.dataset_id

    # JSON round-trip
    as_json = original.to_json()
    from_json = DatasetManifest.from_json(as_json)
    assert from_json.validation_status == IngestionState.QUALITY_VALID
    assert from_json.checksum == original.checksum
    assert from_json.validation_errors == original.validation_errors
