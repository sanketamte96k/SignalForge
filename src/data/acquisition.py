"""Production Data Acquisition & Ingestion Architecture for SignalForge.

This module provides the core data acquisition abstractions:
- IngestionState: Explicit lifecycle states and transition gates.
- DatasetManifest: Immutable provenance and audit record.
- SymbolMapping & SymbolMappingRegistry: Centralized corporate action & listing constraints.
- DataDirectoryContract: Strict directory contract and quarantine path resolver.
- DataIntegrityValidator: Microstructure and OHLCV invariant validation.
- compute_checksum: Deterministic cryptographic SHA-256 fingerprinting.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.validator import REQUIRED_COLUMNS, validate_market_data


class IngestionState(str, Enum):
    """Explicit lifecycle states for dataset acquisition."""

    RECEIVED = "RECEIVED"
    SCHEMA_VALID = "SCHEMA_VALID"
    NORMALIZED = "NORMALIZED"
    QUALITY_VALID = "QUALITY_VALID"
    SESSION_VALID = "SESSION_VALID"
    COVERAGE_VALID = "COVERAGE_VALID"
    READY_FOR_PRODUCTION = "READY_FOR_PRODUCTION"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal state transition is attempted."""


VALID_STATE_TRANSITIONS: dict[IngestionState, set[IngestionState]] = {
    IngestionState.RECEIVED: {
        IngestionState.SCHEMA_VALID,
        IngestionState.REJECTED,
    },
    IngestionState.SCHEMA_VALID: {
        IngestionState.NORMALIZED,
        IngestionState.REJECTED,
    },
    IngestionState.NORMALIZED: {
        IngestionState.QUALITY_VALID,
        IngestionState.REJECTED,
    },
    IngestionState.QUALITY_VALID: {
        IngestionState.SESSION_VALID,
        IngestionState.REJECTED,
    },
    IngestionState.SESSION_VALID: {
        IngestionState.COVERAGE_VALID,
        IngestionState.REJECTED,
    },
    IngestionState.COVERAGE_VALID: {
        IngestionState.READY_FOR_PRODUCTION,
        IngestionState.REJECTED,
    },
    IngestionState.REJECTED: {
        IngestionState.QUARANTINED,
    },
    IngestionState.QUARANTINED: set(),
    IngestionState.READY_FOR_PRODUCTION: set(),
}


def validate_state_transition(
    current_state: IngestionState,
    target_state: IngestionState,
) -> None:
    """Validate that a state transition is legal."""
    allowed = VALID_STATE_TRANSITIONS.get(current_state, set())
    if target_state not in allowed:
        raise InvalidStateTransitionError(
            f"Cannot transition from {current_state.value} to {target_state.value}. "
            f"Allowed target states: {[s.value for s in allowed]}"
        )


def compute_checksum(data: bytes | str | Path) -> str:
    """Compute a deterministic SHA-256 checksum for bytes, string, or file path."""
    hasher = hashlib.sha256()

    if isinstance(data, Path):
        with open(data, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
    elif isinstance(data, str):
        hasher.update(data.encode("utf-8"))
    elif isinstance(data, bytes):
        hasher.update(data)
    else:
        raise TypeError(f"Unsupported data type for checksum: {type(data)}")

    return hasher.hexdigest()


@dataclass(frozen=True)
class SymbolMapping:
    """Explicit mapping record between current and historical ticker symbols."""

    current_symbol: str
    historical_symbol: str
    effective_start: str
    effective_end: str
    mapping_reason: str
    source: str
    confidence: float = 1.0


@dataclass(frozen=True)
class ListingConstraint:
    """Listing-era constraint for post-2015 IPO stocks."""

    symbol: str
    listing_date: str
    first_legitimate_candle: str
    notes: str


class SymbolMappingRegistry:
    """Centralized, controlled registry for legacy symbol mappings and listing constraints."""

    _MAPPINGS: dict[str, SymbolMapping] = {
        "TMPV": SymbolMapping(
            current_symbol="TMPV",
            historical_symbol="TATAMOTORS",
            effective_start="2015-01-01",
            effective_end="2024-03-26",
            mapping_reason="Tata Motors passenger vehicle demerger successor",
            source="Corporate Action Circular 2024",
            confidence=1.0,
        ),
        "SHRIRAMFIN": SymbolMapping(
            current_symbol="SHRIRAMFIN",
            historical_symbol="SRTRANSFIN",
            effective_start="2015-01-01",
            effective_end="2022-12-05",
            mapping_reason="Shriram Transport Finance merged into Shriram Finance",
            source="NCLT Merger Order Dec 2022",
            confidence=1.0,
        ),
        "TATACONSUM": SymbolMapping(
            current_symbol="TATACONSUM",
            historical_symbol="TATAGLOBAL",
            effective_start="2015-01-01",
            effective_end="2020-02-10",
            mapping_reason="Tata Global Beverages rebranded to Tata Consumer Products",
            source="ROC Rebranding Feb 2020",
            confidence=1.0,
        ),
        "ETERNAL": SymbolMapping(
            current_symbol="ETERNAL",
            historical_symbol="ZOMATO",
            effective_start="2021-07-23",
            effective_end="2024-03-26",
            mapping_reason="Zomato corporate restructuring and listing continuity",
            source="NSE Listing Circular Jul 2021",
            confidence=1.0,
        ),
    }

    _LISTING_CONSTRAINTS: dict[str, ListingConstraint] = {
        "HDFCLIFE": ListingConstraint(
            symbol="HDFCLIFE",
            listing_date="2017-11-17",
            first_legitimate_candle="2017-11-17 09:44:00",
            notes="IPO listing on 2017-11-17; zero synthetic pre-listing data permitted",
        ),
        "SBILIFE": ListingConstraint(
            symbol="SBILIFE",
            listing_date="2017-10-03",
            first_legitimate_candle="2017-10-03 13:40:00",
            notes="IPO listing on 2017-10-03; zero synthetic pre-listing data permitted",
        ),
        "INDIGO": ListingConstraint(
            symbol="INDIGO",
            listing_date="2015-11-10",
            first_legitimate_candle="2015-11-10 09:44:00",
            notes="IPO listing on 2015-11-10; zero synthetic pre-listing data permitted",
        ),
        "MAXHEALTH": ListingConstraint(
            symbol="MAXHEALTH",
            listing_date="2020-08-21",
            first_legitimate_candle="2020-08-21 09:15:00",
            notes="Relisting on 2020-08-21; zero synthetic pre-listing data permitted",
        ),
        "JIOFIN": ListingConstraint(
            symbol="JIOFIN",
            listing_date="2023-08-21",
            first_legitimate_candle="2023-08-21 09:15:00",
            notes="Spinoff listing on 2023-08-21; zero synthetic pre-listing data permitted",
        ),
    }

    @classmethod
    def get_mapping(cls, symbol: str) -> SymbolMapping | None:
        """Return the symbol mapping if one exists."""
        return cls._MAPPINGS.get(symbol.upper().strip())

    @classmethod
    def get_historical_symbol(cls, symbol: str) -> str:
        """Return historical symbol if mapped, or the symbol itself."""
        mapping = cls.get_mapping(symbol)
        return mapping.historical_symbol if mapping else symbol.upper().strip()

    @classmethod
    def get_listing_constraint(cls, symbol: str) -> ListingConstraint | None:
        """Return listing constraint if stock listed post-2015."""
        return cls._LISTING_CONSTRAINTS.get(symbol.upper().strip())

    @classmethod
    def is_listing_constrained(cls, symbol: str) -> bool:
        """Return True if stock has listing date restrictions."""
        return symbol.upper().strip() in cls._LISTING_CONSTRAINTS

    @classmethod
    def validate_listing_boundary(
        cls,
        symbol: str,
        earliest_timestamp: pd.Timestamp | str,
    ) -> bool:
        """Assert that a listing-constrained stock does not contain pre-listing candles."""
        constraint = cls.get_listing_constraint(symbol)
        if constraint is None:
            return True

        ts = pd.Timestamp(earliest_timestamp)
        listing_ts = pd.Timestamp(constraint.listing_date)
        return ts >= listing_ts


@dataclass
class DatasetManifest:
    """Immutable audit manifest for a market dataset."""

    dataset_id: str
    source: str
    source_file: str
    symbol: str
    historical_symbol: str
    requested_start: str
    requested_end: str
    actual_start: str
    actual_end: str
    interval: str
    timezone: str
    row_count: int
    checksum: str
    ingested_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    validation_status: IngestionState = IngestionState.RECEIVED
    validation_errors: list[str] = field(default_factory=list)
    mapping_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        """Serialize manifest to dictionary."""
        data = asdict(self)
        data["validation_status"] = self.validation_status.value
        return data

    def to_json(self, indent: int = 2) -> str:
        """Serialize manifest to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatasetManifest:
        """Instantiate manifest from dictionary."""
        d = dict(data)
        if isinstance(d.get("validation_status"), str):
            d["validation_status"] = IngestionState(d["validation_status"])
        return cls(**d)

    @classmethod
    def from_json(cls, json_str: str) -> DatasetManifest:
        """Instantiate manifest from JSON string."""
        return cls.from_dict(json.loads(json_str))


class DataDirectoryContract:
    """Strict directory layout contract and path resolver."""

    def __init__(self, base_dir: Path | str = "data/historical") -> None:
        self.base_dir = Path(base_dir)
        self.raw_dir = self.base_dir / "raw"
        self.normalized_dir = self.base_dir / "normalized"
        self.validated_dir = self.base_dir / "validated"
        self.quarantine_dir = self.base_dir / "quarantine"
        self.stocks_dir = self.base_dir / "stocks"

    def ensure_directories(self) -> None:
        """Safely create directory structure if not already existing."""
        for directory in (
            self.raw_dir,
            self.normalized_dir,
            self.validated_dir,
            self.quarantine_dir,
            self.stocks_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def raw_path(self, symbol: str, filename: str) -> Path:
        """Resolve path in raw landing staging."""
        return self.raw_dir / symbol.upper() / filename

    def normalized_path(self, symbol: str) -> Path:
        """Resolve path in normalized staging."""
        return self.normalized_dir / f"{symbol.upper()}_1m.parquet"

    def validated_path(self, symbol: str) -> Path:
        """Resolve path in validated candidate staging."""
        return self.validated_dir / f"{symbol.upper()}_1m.parquet"

    def production_path(self, symbol: str) -> Path:
        """Resolve path in canonical production storage."""
        return self.stocks_dir / f"{symbol.upper()}_1m.csv"

    def quarantine_path(self, symbol: str, filename: str, reason: str) -> Path:
        """Generate quarantine destination path with diagnostic directory."""
        safe_reason = reason.lower().replace(" ", "_").replace("-", "_")[:40]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        folder = self.quarantine_dir / f"{symbol.upper()}_{timestamp}_{safe_reason}"
        return folder / filename


class DataIntegrityValidator:
    """Validate canonical OHLCV schema, mathematical invariants, and temporal integrity."""

    @staticmethod
    def validate_ohlcv_dataframe(df: pd.DataFrame) -> None:
        """Validate DataFrame against canonical SignalForge rules.

        Reuses core validation from validate_market_data.
        Raises ValueError or TypeError on violation.
        """
        if not isinstance(df, pd.DataFrame):
            raise TypeError("data must be a pandas DataFrame.")

        if not isinstance(df.index, pd.DatetimeIndex):
            raise TypeError("Market data index must be a pandas DatetimeIndex.")

        # 1. Explicit check for malformed timestamps (NaT)
        if df.index.isna().any():
            raise ValueError("Market data index contains NaT (malformed timestamp).")

        # 2. Base validation via established SignalForge validator
        validate_market_data(df)

        # 3. Explicit check for negative volumes
        if (df["volume"] < 0).any():
            raise ValueError("Market data contains negative volume.")


@dataclass
class IngestionResult:
    """Result of an ingestion pipeline run."""

    symbol: str
    state: IngestionState
    manifest: DatasetManifest | None
    quarantine_path: Path | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        """Return True if dataset reached READY_FOR_PRODUCTION."""
        return self.state == IngestionState.READY_FOR_PRODUCTION
