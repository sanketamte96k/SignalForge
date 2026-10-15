"""SignalForge Phase 24G — Validated Historical Market Data Pipeline.

Provides a robust, reproducible historical market-data ingestion engine for NSE equities:
- Normalization: symbol, exchange, timestamps (converted to IST), interval, canonical OHLCV types.
- Strict Invariants: finite numeric values, positive prices, OHLC relationships, non-negative volume.
- Temporal Integrity: monotonic ascending order, duplicate timestamp quarantine, intraday gap detection.
- Diagnostic Distinction: distinguishes missing data/volume from valid zero-volume trades.
- Quarantine: segregates invalid rows into machine-readable quarantine files.
- Atomic Persistence: temporary file writes with fsync and atomic os.replace preventing corrupt writes.
- Provenance & Audit: SHA-256 content hashes, structured manifests, and data-quality reports.
- Idempotence: safe repeated runs without side-effects or state degradation.
- Resource Controls: bounded retries, exponential backoff, rate limiting, and large-batch safeguards.
- Credential Safety: zero leakage of API keys or auth tokens in logs, manifests, or error messages.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable, Optional, Sequence

import numpy as np
import pandas as pd

from src.data.acquisition import DataDirectoryContract
from src.universe.registry import (
    DataQualityStatus,
    StockUniverseRegistry,
    UniverseCategory,
)

logger = logging.getLogger(__name__)

# Canonical NSE market hours in IST (Asia/Kolkata)
NSE_MARKET_OPEN_HOUR = 9
NSE_MARKET_OPEN_MINUTE = 15
NSE_MARKET_CLOSE_HOUR = 15
NSE_MARKET_CLOSE_MINUTE = 30

# Known symbol alias mappings between registered tickers and local archive archives
DEFAULT_ARCHIVE_ALIASES: dict[str, str] = {
    "BAJAJ-AUTO": "BAJAJ_AUTO",
    "M&M": "M_M",
    "M&MFIN": "M_MFIN",
    "L&TFH": "L_TFH",
    "NAM-INDIA": "NAM_INDIA",
    "SHRIRAMFIN": "SRTRANSFIN",
}

# Maximum default batch size allowed without explicit confirmation
MAX_UNATTENDED_BATCH_SIZE: int = 10


class HistoricalReadinessClassification(str, Enum):
    """Granular readiness classifications for historical equity data."""

    NO_DATA = "NO_DATA"
    INVALID_DATA = "INVALID_DATA"
    INCOMPLETE_COVERAGE = "INCOMPLETE_COVERAGE"
    PRELIMINARY_BACKTEST_READY = "PRELIMINARY_BACKTEST_READY"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"


class PipelineAction(str, Enum):
    """Action outcome from a pipeline ingestion run."""

    INGESTED = "INGESTED"
    DRY_RUN_VALIDATED = "DRY_RUN_VALIDATED"
    SKIPPED_EXISTING = "SKIPPED_EXISTING"
    QUARANTINED = "QUARANTINED"
    FAILED = "FAILED"


@dataclass
class IntradayGapEvent:
    """Record of missing candles within standard market hours."""

    date: str
    gap_start: str
    gap_end: str
    missing_minutes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "gap_start": self.gap_start,
            "gap_end": self.gap_end,
            "missing_minutes": self.missing_minutes,
        }


@dataclass
class HistoricalDataQualityReport:
    """Comprehensive data-quality assessment produced by ingestion pipeline."""

    symbol: str
    exchange: str
    provider: str
    row_count: int
    valid_rows: int
    rejected_rows: int
    zero_volume_rows: int
    gap_count: int
    gap_events: list[IntradayGapEvent] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    content_hash: Optional[str] = None
    quarantine_file: Optional[str] = None
    readiness_classification: HistoricalReadinessClassification = (
        HistoricalReadinessClassification.NO_DATA
    )
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "provider": self.provider,
            "row_count": self.row_count,
            "valid_rows": self.valid_rows,
            "rejected_rows": self.rejected_rows,
            "zero_volume_rows": self.zero_volume_rows,
            "gap_count": self.gap_count,
            "gap_events": [g.to_dict() for g in self.gap_events[:20]],  # Cap detailed events for reporting
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "content_hash": self.content_hash,
            "quarantine_file": self.quarantine_file,
            "readiness_classification": self.readiness_classification.value,
            "issues": self.issues,
        }


@dataclass
class PipelineIngestionRequest:
    """Standardized request for historical pipeline ingestion."""

    symbol: str
    exchange: str = "NSE"
    interval: str = "1m"
    provider: str = "local_archive"
    source_path: Optional[str | Path] = None
    data_override: Optional[pd.DataFrame] = None
    dry_run: bool = True
    confirm_replace: bool = False
    max_retries: int = 3
    timeout_seconds: float = 10.0
    start: Optional[str | datetime] = None
    end: Optional[str | datetime] = None

    def __post_init__(self) -> None:
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol must not be empty.")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "exchange", self.exchange.strip().upper())
        object.__setattr__(self, "interval", self.interval.strip().lower())


@dataclass
class PipelineIngestionResult:
    """Outcome for a single symbol ingestion."""

    symbol: str
    success: bool
    dry_run: bool
    action: PipelineAction
    output_path: Optional[str]
    quality_report: HistoricalDataQualityReport
    retries_attempted: int = 0
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "success": self.success,
            "dry_run": self.dry_run,
            "action": self.action.value,
            "output_path": self.output_path,
            "quality_report": self.quality_report.to_dict(),
            "retries_attempted": self.retries_attempted,
            "error_message": self.error_message,
        }


@dataclass
class BatchIngestionResult:
    """Aggregate report across a batch of symbols."""

    total_requested: int
    succeeded_count: int
    failed_count: int
    skipped_count: int
    dry_run: bool
    results: list[PipelineIngestionResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_requested": self.total_requested,
            "succeeded_count": self.succeeded_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "dry_run": self.dry_run,
            "results": [r.to_dict() for r in self.results],
        }


def compute_sha256(file_path: Path | str) -> str:
    """Compute deterministic SHA-256 hash for a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def normalize_to_ist_series(raw_timestamps: pd.Series) -> pd.Series:
    """Normalize input timestamp series to IST (Asia/Kolkata).

    Handles UTC, explicit timezone offsets, and tz-naive strings (assumed IST).
    Returns tz-naive pd.Series representing wall-clock IST time.
    """
    try:
        # Step 1: Parse to DatetimeIndex or Series
        parsed = pd.to_datetime(raw_timestamps, errors="coerce")
        if parsed.isna().all():
            return parsed

        # Step 2: Handle timezones
        if hasattr(parsed.dt, "tz") and parsed.dt.tz is not None:
            # Has timezone: convert to Asia/Kolkata, then remove tz for canonical storage
            ist_converted = parsed.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
            return ist_converted
        else:
            # Tz-naive: treat directly as IST
            return parsed
    except Exception as e:
        logger.warning(f"Error normalizing timestamps to IST: {e}")
        return pd.to_datetime(raw_timestamps, errors="coerce")


def detect_intraday_gaps(
    timestamps: pd.Series,
    min_gap_minutes: int = 1,
) -> tuple[int, list[IntradayGapEvent]]:
    """Detect missing candle gaps strictly within standard NSE trading hours.

    Session rules:
    - Monday to Friday only (weekends ignored).
    - Hours: 09:15:00 to 15:30:00 IST.
    - Overnight transitions (e.g. 15:29 -> next day 09:15) are session boundaries, not gaps.
    - Weekend transitions (Friday 15:29 -> Monday 09:15) are market closures, not gaps.
    """
    if len(timestamps) <= 1:
        return 0, []

    gap_events: list[IntradayGapEvent] = []
    total_missing_minutes = 0

    ts_list = timestamps.tolist()
    for i in range(len(ts_list) - 1):
        t1 = ts_list[i]
        t2 = ts_list[i + 1]

        if pd.isna(t1) or pd.isna(t2):
            continue

        # Same calendar day check
        if t1.date() == t2.date():
            # Check if within market hours (09:15 to 15:30)
            t1_time = t1.time()
            t2_time = t2.time()

            t_open = datetime.strptime("09:15:00", "%H:%M:%S").time()
            t_close = datetime.strptime("15:30:00", "%H:%M:%S").time()

            if t1_time >= t_open and t2_time <= t_close:
                diff_sec = (t2 - t1).total_seconds()
                diff_min = int(diff_sec // 60)
                if diff_min > min_gap_minutes:
                    missing = diff_min - min_gap_minutes
                    total_missing_minutes += missing
                    gap_events.append(
                        IntradayGapEvent(
                            date=t1.strftime("%Y-%m-%d"),
                            gap_start=t1.strftime("%H:%M:%S"),
                            gap_end=t2.strftime("%H:%M:%S"),
                            missing_minutes=missing,
                        )
                    )

    return total_missing_minutes, gap_events


class HistoricalDataPipeline:
    """SignalForge Historical Market Data Ingestion and Validation Engine."""

    def __init__(
        self,
        contract: Optional[DataDirectoryContract] = None,
        registry: Optional[StockUniverseRegistry] = None,
        archive_dir: Optional[Path | str] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.contract = contract or DataDirectoryContract()
        self.contract.ensure_directories()
        self.manifests_dir = self.contract.base_dir / "manifests"
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.registry = registry
        self.archive_dir = Path(archive_dir) if archive_dir else Path("temp_nse_data/NSE Minute Data/NSE_Stocks_Data")
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _resolve_archive_path(self, symbol: str) -> Optional[Path]:
        """Resolve historical archive CSV path for a symbol using alias mappings."""
        norm_sym = symbol.strip().upper()
        candidates = [norm_sym]
        if norm_sym in DEFAULT_ARCHIVE_ALIASES:
            candidates.append(DEFAULT_ARCHIVE_ALIASES[norm_sym])

        for cand in candidates:
            cand_path = self.archive_dir / f"{cand}__EQ__NSE__NSE__MINUTE.csv"
            if cand_path.exists():
                return cand_path

        return None

    def validate_and_normalize_ohlcv(
        self,
        raw_df: pd.DataFrame,
        symbol: str,
        exchange: str = "NSE",
        provider_name: str = "unknown",
    ) -> tuple[pd.DataFrame, pd.DataFrame, HistoricalDataQualityReport]:
        """Validate and normalize raw market data DataFrame according to canonical contracts.

        Returns:
            (valid_df, invalid_df, quality_report)
        """
        issues: list[str] = []

        if raw_df is None or raw_df.empty:
            report = HistoricalDataQualityReport(
                symbol=symbol,
                exchange=exchange,
                provider=provider_name,
                row_count=0,
                valid_rows=0,
                rejected_rows=0,
                zero_volume_rows=0,
                gap_count=0,
                readiness_classification=HistoricalReadinessClassification.NO_DATA,
                issues=["Source dataset is empty or None."],
            )
            return pd.DataFrame(), pd.DataFrame(), report

        # Step 1: Normalize column headers
        col_map: dict[str, str] = {}
        for c in raw_df.columns:
            c_str = str(c).strip().lower()
            if c_str in ("timestamp", "datetime", "date", "time"):
                col_map[c] = "timestamp"
            elif c_str in ("open", "high", "low", "close", "volume"):
                col_map[c] = c_str

        df = raw_df.rename(columns=col_map).copy()

        req_cols = {"timestamp", "open", "high", "low", "close", "volume"}
        missing_cols = req_cols - set(df.columns)
        if missing_cols:
            report = HistoricalDataQualityReport(
                symbol=symbol,
                exchange=exchange,
                provider=provider_name,
                row_count=len(df),
                valid_rows=0,
                rejected_rows=len(df),
                zero_volume_rows=0,
                gap_count=0,
                readiness_classification=HistoricalReadinessClassification.INVALID_DATA,
                issues=[f"Missing required canonical OHLCV columns: {sorted(missing_cols)}"],
            )
            return pd.DataFrame(), df, report

        # Step 2: Timestamp Normalization to IST
        df["timestamp"] = normalize_to_ist_series(df["timestamp"])
        initial_count = len(df)

        # Separate out rows with malformed timestamps (NaT)
        nat_mask = df["timestamp"].isna()
        nat_count = int(nat_mask.sum())
        if nat_count > 0:
            issues.append(f"Detected {nat_count} rows with malformed timestamps (NaT).")

        # Step 3: Numeric Conversion & Finite Checks
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Check for NaN / non-finite in OHLC
        ohlc_non_finite_mask = (
            df[["open", "high", "low", "close"]].isna().any(axis=1)
            | ~np.isfinite(df["open"])
            | ~np.isfinite(df["high"])
            | ~np.isfinite(df["low"])
            | ~np.isfinite(df["close"])
        )

        # Distinguish missing volume from zero volume
        missing_volume_mask = df["volume"].isna() | ~np.isfinite(df["volume"])
        negative_volume_mask = df["volume"] < 0
        zero_volume_mask = df["volume"] == 0

        # Positive price checks
        non_positive_price_mask = (
            (df["open"] <= 0)
            | (df["high"] <= 0)
            | (df["low"] <= 0)
            | (df["close"] <= 0)
        )

        # Mathematical Invariants:
        # High must be >= Open, Close, Low
        # Low must be <= Open, Close, High
        high_low_violation_mask = (
            (df["high"] < df["low"])
            | (df["high"] < df["open"])
            | (df["high"] < df["close"])
            | (df["low"] > df["open"])
            | (df["low"] > df["close"])
        )

        # Step 4: Aggregate Invalid Rows
        invalid_mask = (
            nat_mask
            | ohlc_non_finite_mask
            | missing_volume_mask
            | negative_volume_mask
            | non_positive_price_mask
            | high_low_violation_mask
        )

        invalid_df = df[invalid_mask].copy()
        valid_df = df[~invalid_mask].copy()

        # Step 5: Duplicate and Monotonic Ordering on Valid Data
        if not valid_df.empty:
            # Sort chronologically
            valid_df = valid_df.sort_values(by="timestamp").reset_index(drop=True)

            # Check for duplicate timestamps
            dup_mask = valid_df.duplicated(subset=["timestamp"], keep="first")
            dup_count = int(dup_mask.sum())
            if dup_count > 0:
                issues.append(f"Detected {dup_count} duplicate candle timestamps. Deduplicated keeping first instance.")
                # Add duplicates to invalid for quarantine audit
                dup_rows = valid_df[dup_mask].copy()
                invalid_df = pd.concat([invalid_df, dup_rows], axis=0)
                valid_df = valid_df[~dup_mask].reset_index(drop=True)

        valid_count = len(valid_df)
        rejected_count = len(invalid_df)
        zero_vol_count = int(zero_volume_mask[~invalid_mask].sum()) if valid_count > 0 else 0

        # Step 6: Temporal Intraday Gap Detection
        gap_count = 0
        gap_events: list[IntradayGapEvent] = []
        start_time = None
        end_time = None

        if valid_count > 0:
            start_time = valid_df["timestamp"].iloc[0].to_pydatetime()
            end_time = valid_df["timestamp"].iloc[-1].to_pydatetime()
            gap_count, gap_events = detect_intraday_gaps(valid_df["timestamp"])

        if gap_count > 0:
            issues.append(f"Detected {gap_count} missing intraday candle minutes across {len(gap_events)} gap events.")

        # Step 7: Granular Readiness Classification
        if valid_count == 0:
            classification = (
                HistoricalReadinessClassification.INVALID_DATA
                if rejected_count > 0
                else HistoricalReadinessClassification.NO_DATA
            )
        elif valid_count < 500:
            classification = HistoricalReadinessClassification.INCOMPLETE_COVERAGE
            issues.append(f"Valid candle count ({valid_count}) is below minimum technical threshold (500).")
        elif gap_count > (valid_count * 0.15):  # High gap density (>15% of records missing)
            classification = HistoricalReadinessClassification.VERIFICATION_REQUIRED
            issues.append(f"High intraday gap density ({gap_count} gaps vs {valid_count} candles) requires manual verification.")
        else:
            classification = HistoricalReadinessClassification.PRELIMINARY_BACKTEST_READY

        report = HistoricalDataQualityReport(
            symbol=symbol,
            exchange=exchange,
            provider=provider_name,
            row_count=initial_count,
            valid_rows=valid_count,
            rejected_rows=rejected_count,
            zero_volume_rows=zero_vol_count,
            gap_count=gap_count,
            gap_events=gap_events,
            start_time=start_time,
            end_time=end_time,
            readiness_classification=classification,
            issues=issues,
        )

        return valid_df, invalid_df, report

    def _fetch_source_data(
        self,
        request: PipelineIngestionRequest,
    ) -> tuple[pd.DataFrame, str]:
        """Fetch raw market data from requested provider with bounded retries and backoff."""
        if request.data_override is not None:
            return request.data_override.copy(), "memory_override"

        provider_name = request.provider.lower()

        # Provider 1: Local Archive
        if provider_name in ("local_archive", "archive", "local"):
            source_file = (
                Path(request.source_path)
                if request.source_path
                else self._resolve_archive_path(request.symbol)
            )
            if not source_file or not source_file.exists():
                raise FileNotFoundError(
                    f"No local historical archive file found for symbol '{request.symbol}' "
                    f"in {self.archive_dir}"
                )
            df = pd.read_csv(source_file)
            return df, f"local_archive:{source_file.name}"

        # Provider 2: Groww Trading API
        if provider_name == "groww":
            from src.data.market_data import MarketDataRequest
            from src.data.providers.groww import GrowwProvider

            provider_inst = GrowwProvider()
            if not provider_inst.is_available():
                raise ConnectionError(
                    "Groww credentials are not configured or available in environment."
                )

            req = MarketDataRequest(
                symbol=request.symbol,
                exchange=request.exchange,
                interval=request.interval,
                start=request.start,
                end=request.end,
            )

            # Bounded retry loop with exponential backoff
            last_exc = None
            for attempt in range(request.max_retries):
                try:
                    result = provider_inst.get_historical(req)
                    # Convert to DataFrame with timestamp column
                    res_df = result.data.reset_index()
                    return res_df, "groww"
                except Exception as exc:
                    last_exc = exc
                    wait_time = 0.5 * (2**attempt)
                    logger.warning(
                        f"Groww fetch attempt {attempt+1}/{request.max_retries} failed for {request.symbol}: {type(exc).__name__}. Retrying in {wait_time:.1f}s"
                    )
                    time.sleep(wait_time)

            raise ConnectionError(
                f"Failed to fetch data from Groww after {request.max_retries} retries: {type(last_exc).__name__}"
            ) from last_exc

        # Provider 3: Yahoo Finance
        if provider_name in ("yfinance", "yahoo"):
            from src.data.market_data import MarketDataRequest
            from src.data.providers.yfinance_provider import YFinanceProvider

            yf_provider = YFinanceProvider()
            req = MarketDataRequest(
                symbol=request.symbol,
                exchange=request.exchange,
                interval=request.interval,
                start=request.start,
                end=request.end,
            )

            last_exc = None
            for attempt in range(request.max_retries):
                try:
                    result = yf_provider.get_historical(req)
                    res_df = result.data.reset_index()
                    return res_df, "yfinance"
                except Exception as exc:
                    last_exc = exc
                    wait_time = 0.5 * (2**attempt)
                    time.sleep(wait_time)

            raise ConnectionError(
                f"Failed to fetch data from yfinance after {request.max_retries} retries: {type(last_exc).__name__}"
            ) from last_exc

        raise ValueError(f"Unsupported provider: '{request.provider}'. Supported: ['local_archive', 'groww', 'yfinance']")

    def _persist_atomic_csv(
        self,
        df: pd.DataFrame,
        dest_path: Path,
    ) -> str:
        """Atomically persist DataFrame to target destination using temporary file and fsync."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = dest_path.with_suffix(f".tmp_{os.getpid()}_{int(time.time()*1000)}")

        try:
            # Format timestamp strings cleanly as YYYY-MM-DD HH:MM:SS
            out_df = df.copy()
            if "timestamp" in out_df.columns:
                out_df["timestamp"] = pd.to_datetime(out_df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")

            # Canonical column order
            canonical_cols = ["timestamp", "open", "high", "low", "close", "volume"]
            present_cols = [c for c in canonical_cols if c in out_df.columns]
            out_df = out_df[present_cols]

            with open(temp_file, "w", encoding="utf-8", newline="") as f:
                out_df.to_csv(f, index=False)
                f.flush()
                os.fsync(f.fileno())

            # Atomic swap
            os.replace(temp_file, dest_path)
            return compute_sha256(dest_path)
        except Exception:
            if temp_file.exists():
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass
            raise

    def ingest_symbol(
        self,
        request: PipelineIngestionRequest,
    ) -> PipelineIngestionResult:
        """Execute safe historical market data ingestion for an individual symbol."""
        dest_path = self.contract.production_path(request.symbol)

        # 1. Protection against inadvertent overwrite of existing production files
        if dest_path.exists() and not request.dry_run and not request.confirm_replace:
            existing_report = HistoricalDataQualityReport(
                symbol=request.symbol,
                exchange=request.exchange,
                provider="existing_file",
                row_count=0,
                valid_rows=0,
                rejected_rows=0,
                zero_volume_rows=0,
                gap_count=0,
                readiness_classification=HistoricalReadinessClassification.PRELIMINARY_BACKTEST_READY,
                issues=["Destination dataset already exists. Explicit confirmation (confirm_replace=True) required to overwrite."],
            )
            return PipelineIngestionResult(
                symbol=request.symbol,
                success=False,
                dry_run=request.dry_run,
                action=PipelineAction.SKIPPED_EXISTING,
                output_path=str(dest_path),
                quality_report=existing_report,
                error_message="Destination dataset already exists; confirmation required to overwrite.",
            )

        # 2. Fetch raw source data
        try:
            raw_df, provider_source = self._fetch_source_data(request)
        except Exception as exc:
            report = HistoricalDataQualityReport(
                symbol=request.symbol,
                exchange=request.exchange,
                provider=request.provider,
                row_count=0,
                valid_rows=0,
                rejected_rows=0,
                zero_volume_rows=0,
                gap_count=0,
                readiness_classification=HistoricalReadinessClassification.NO_DATA,
                issues=[f"Data acquisition failed: {type(exc).__name__}: {str(exc)}"],
            )
            return PipelineIngestionResult(
                symbol=request.symbol,
                success=False,
                dry_run=request.dry_run,
                action=PipelineAction.FAILED,
                output_path=None,
                quality_report=report,
                error_message=str(exc),
            )

        # 3. Validate, Normalize, and Detect Invariants
        valid_df, invalid_df, report = self.validate_and_normalize_ohlcv(
            raw_df=raw_df,
            symbol=request.symbol,
            exchange=request.exchange,
            provider_name=provider_source,
        )

        # 4. Handle Quarantine if invalid records exist
        quarantine_file_str: Optional[str] = None
        if not invalid_df.empty and not request.dry_run:
            ts_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            quarantine_path = (
                self.contract.quarantine_dir
                / f"{request.symbol}_{ts_stamp}_quarantined.csv"
            )
            quarantine_path.parent.mkdir(parents=True, exist_ok=True)
            invalid_df.to_csv(quarantine_path, index=False)
            quarantine_file_str = str(quarantine_path)
            report.quarantine_file = quarantine_file_str

        # 5. Dry-run Mode
        if request.dry_run:
            return PipelineIngestionResult(
                symbol=request.symbol,
                success=report.valid_rows > 0,
                dry_run=True,
                action=PipelineAction.DRY_RUN_VALIDATED,
                output_path=str(dest_path) if report.valid_rows > 0 else None,
                quality_report=report,
            )

        # 6. Check for valid data presence
        if valid_df.empty:
            return PipelineIngestionResult(
                symbol=request.symbol,
                success=False,
                dry_run=False,
                action=PipelineAction.QUARANTINED if not invalid_df.empty else PipelineAction.FAILED,
                output_path=None,
                quality_report=report,
                error_message="Zero valid OHLCV candles remained after validation filtering.",
            )

        # 7. Atomic Write to Production
        try:
            content_hash = self._persist_atomic_csv(valid_df, dest_path)
            report.content_hash = content_hash

            # 8. Write Machine-Readable Manifest
            manifest_data = {
                "dataset_id": f"{request.symbol}_1m",
                "symbol": request.symbol,
                "exchange": request.exchange,
                "provider": provider_source,
                "retrieval_timestamp": self.clock().isoformat(),
                "actual_start": report.start_time.isoformat() if report.start_time else None,
                "actual_end": report.end_time.isoformat() if report.end_time else None,
                "interval": request.interval,
                "timezone": "Asia/Kolkata",
                "row_count": report.valid_rows,
                "rejected_rows_count": report.rejected_rows,
                "zero_volume_count": report.zero_volume_rows,
                "gap_count": report.gap_count,
                "content_hash": content_hash,
                "quarantine_file": quarantine_file_str,
                "readiness_classification": report.readiness_classification.value,
                "issues": report.issues,
            }
            manifest_file = self.manifests_dir / f"{request.symbol}_1m_manifest.json"
            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2)

            # 9. Update Registry Quality Status if registry provided
            if self.registry and self.registry.get(request.symbol):
                new_status = (
                    DataQualityStatus.READY
                    if report.readiness_classification == HistoricalReadinessClassification.PRELIMINARY_BACKTEST_READY
                    else DataQualityStatus.INCOMPLETE
                )
                self.registry.update_stock(
                    symbol=request.symbol,
                    data_quality_status=new_status,
                )

            return PipelineIngestionResult(
                symbol=request.symbol,
                success=True,
                dry_run=False,
                action=PipelineAction.INGESTED,
                output_path=str(dest_path),
                quality_report=report,
            )
        except Exception as exc:
            report.issues.append(f"Persistence error: {exc}")
            return PipelineIngestionResult(
                symbol=request.symbol,
                success=False,
                dry_run=False,
                action=PipelineAction.FAILED,
                output_path=None,
                quality_report=report,
                error_message=f"Atomic write failed: {exc}",
            )

    def ingest_batch(
        self,
        symbols: Sequence[str],
        exchange: str = "NSE",
        interval: str = "1m",
        provider: str = "local_archive",
        dry_run: bool = True,
        confirm_replace: bool = False,
        confirm_large_batch: bool = False,
        rate_limit_delay_seconds: float = 0.0,
    ) -> BatchIngestionResult:
        """Execute bounded, safe batch ingestion across a list of symbols.

        Safety boundaries:
        - Prevents unattended execution for batches > 10 without confirm_large_batch=True.
        - Provides isolated execution per symbol (partial failures do not crash batch).
        """
        symbol_list = [s.strip().upper() for s in symbols if s.strip()]

        if len(symbol_list) > MAX_UNATTENDED_BATCH_SIZE and not confirm_large_batch:
            raise ValueError(
                f"Requested batch size ({len(symbol_list)}) exceeds safety limit ({MAX_UNATTENDED_BATCH_SIZE}). "
                "Provide confirm_large_batch=True to execute large batch after reviewing small-batch validation."
            )

        results: list[PipelineIngestionResult] = []
        succeeded = 0
        failed = 0
        skipped = 0

        for idx, sym in enumerate(symbol_list):
            req = PipelineIngestionRequest(
                symbol=sym,
                exchange=exchange,
                interval=interval,
                provider=provider,
                dry_run=dry_run,
                confirm_replace=confirm_replace,
            )

            try:
                res = self.ingest_symbol(req)
                results.append(res)
                if res.success:
                    succeeded += 1
                elif res.action == PipelineAction.SKIPPED_EXISTING:
                    skipped += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                fail_report = HistoricalDataQualityReport(
                    symbol=sym,
                    exchange=exchange,
                    provider=provider,
                    row_count=0,
                    valid_rows=0,
                    rejected_rows=0,
                    zero_volume_rows=0,
                    gap_count=0,
                    readiness_classification=HistoricalReadinessClassification.NO_DATA,
                    issues=[f"Unhandled symbol error: {e}"],
                )
                results.append(
                    PipelineIngestionResult(
                        symbol=sym,
                        success=False,
                        dry_run=dry_run,
                        action=PipelineAction.FAILED,
                        output_path=None,
                        quality_report=fail_report,
                        error_message=str(e),
                    )
                )

            # Apply rate limiting delay if multiple symbols
            if rate_limit_delay_seconds > 0 and idx < len(symbol_list) - 1:
                time.sleep(rate_limit_delay_seconds)

        return BatchIngestionResult(
            total_requested=len(symbol_list),
            succeeded_count=succeeded,
            failed_count=failed,
            skipped_count=skipped,
            dry_run=dry_run,
            results=results,
        )
