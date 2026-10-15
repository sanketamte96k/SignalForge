"""SignalForge Per-Stock, Per-Strategy Readiness Assessment Engine.

Provides a read-only, non-fabricating audit of:
- Stock registration & exchange validity.
- Historical data availability, coverage period, and freshness.
- Missing candles, invalid OHLCV records, and known data-quality limitations.
- Historical backtest sufficiency (>= 500 validated candles).
- Out-of-sample validation evidence.
- Forward paper trade counts against the 30-trade minimum and 50-trade preferred thresholds.
- Missing evidence and the next required evaluation step.

SAFETY BOUNDARY:
- Read-only with respect to trading execution.
- Never fabricates evidence or backtest profits.
- Never interacts with the active V1 ledger or running collectors.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from src.universe.registry import (
    DEFAULT_MIN_FORWARD_TRADES,
    DEFAULT_PREFERRED_FORWARD_TRADES,
    QualificationStatus,
    StockRecord,
    StockUniverseRegistry,
)


class ReadinessState(str, Enum):
    NOT_TESTED = "NOT_TESTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    IN_PROGRESS = "IN_PROGRESS"
    READY = "READY"
    FAILED = "FAILED"
    APPROVED = "APPROVED"


class HistoricalReadinessClassification(str, Enum):
    """Granular readiness classification for historical market data."""

    NO_DATA = "NO_DATA"
    INVALID_DATA = "INVALID_DATA"
    INCOMPLETE_COVERAGE = "INCOMPLETE_COVERAGE"
    PRELIMINARY_BACKTEST_READY = "PRELIMINARY_BACKTEST_READY"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"


MIN_BACKTEST_CANDLES: int = 500
VALID_EXCHANGES: set[str] = {"NSE", "BSE"}


@dataclass
class DataQualityReport:
    """Audit of locally available historical market data for a stock."""

    symbol: str
    has_local_data: bool
    data_source: Optional[str] = None
    file_path: Optional[str] = None
    total_candles: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    freshness_hours: Optional[float] = None
    missing_candle_count: int = 0
    invalid_candle_count: int = 0
    data_quality_status: str = "UNKNOWN"
    readiness_classification: str = HistoricalReadinessClassification.NO_DATA.value
    gap_count: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "has_local_data": self.has_local_data,
            "data_source": self.data_source,
            "file_path": self.file_path,
            "total_candles": self.total_candles,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "freshness_hours": round(self.freshness_hours, 1) if self.freshness_hours is not None else None,
            "missing_candle_count": self.missing_candle_count,
            "invalid_candle_count": self.invalid_candle_count,
            "data_quality_status": self.data_quality_status,
            "readiness_classification": self.readiness_classification,
            "gap_count": self.gap_count,
            "notes": self.notes,
        }


@dataclass
class StageAssessment:
    """Assessment of an individual qualification pipeline stage."""

    stage_name: str
    status: str
    is_passing: bool
    details: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_name": self.stage_name,
            "status": self.status,
            "is_passing": self.is_passing,
            "details": self.details,
        }


@dataclass
class StockStrategyReadiness:
    """Comprehensive readiness assessment for a stock / strategy pair."""

    symbol: str
    exchange: str
    category: str
    strategy_id: str
    strategy_version: str
    readiness_state: ReadinessState
    exchange_valid: bool
    data_quality: DataQualityReport
    has_sufficient_backtest_data: bool
    backtest_stage: StageAssessment
    oos_stage: StageAssessment
    forward_paper_stage: StageAssessment
    forward_trade_count: int
    meets_initial_sample_threshold: bool
    meets_preferred_sample_threshold: bool
    qualification_status: QualificationStatus
    missing_evidence: list[str]
    next_required_step: str
    assessed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "category": self.category,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "readiness_state": self.readiness_state.value,
            "exchange_valid": self.exchange_valid,
            "data_quality": self.data_quality.to_dict(),
            "has_sufficient_backtest_data": self.has_sufficient_backtest_data,
            "backtest_stage": self.backtest_stage.to_dict(),
            "oos_stage": self.oos_stage.to_dict(),
            "forward_paper_stage": self.forward_paper_stage.to_dict(),
            "forward_trade_count": self.forward_trade_count,
            "meets_initial_sample_threshold": self.meets_initial_sample_threshold,
            "meets_preferred_sample_threshold": self.meets_preferred_sample_threshold,
            "qualification_status": self.qualification_status.value,
            "missing_evidence": self.missing_evidence,
            "next_required_step": self.next_required_step,
            "assessed_at": self.assessed_at.isoformat(),
        }


def inspect_stock_historical_data(
    symbol: str,
    data_dir: Optional[Path] = None,
    as_of: Optional[datetime] = None,
) -> DataQualityReport:
    """
    Inspect local market data files for a stock and evaluate data quality.
    """
    base_dir = data_dir or (Path(__file__).resolve().parents[2] / "data" / "historical" / "stocks")
    norm_symbol = symbol.strip().upper()
    file_path = base_dir / f"{norm_symbol}_1m.csv"
    now_utc = as_of or datetime.now(timezone.utc)

    if not file_path.exists():
        return DataQualityReport(
            symbol=norm_symbol,
            has_local_data=False,
            data_source=None,
            file_path=str(file_path),
            total_candles=0,
            data_quality_status="UNKNOWN",
            readiness_classification=HistoricalReadinessClassification.NO_DATA.value,
            gap_count=0,
            notes=["No local historical data file found."],
        )

    try:
        df = pd.read_csv(file_path)
    except Exception as exc:
        return DataQualityReport(
            symbol=norm_symbol,
            has_local_data=True,
            data_source="local_csv",
            file_path=str(file_path),
            total_candles=0,
            data_quality_status="INCOMPLETE",
            readiness_classification=HistoricalReadinessClassification.INVALID_DATA.value,
            gap_count=0,
            notes=[f"Failed to read CSV: {exc}"],
        )

    if df.empty:
        return DataQualityReport(
            symbol=norm_symbol,
            has_local_data=True,
            data_source="local_csv",
            file_path=str(file_path),
            total_candles=0,
            data_quality_status="UNKNOWN",
            readiness_classification=HistoricalReadinessClassification.NO_DATA.value,
            gap_count=0,
            notes=["Market data file is empty."],
        )

    # Check for timestamp column
    time_col = None
    for cand in ("timestamp", "Datetime", "datetime", "date", "Date"):
        if cand in df.columns:
            time_col = cand
            break

    if time_col is None and isinstance(df.index, pd.DatetimeIndex):
        ts_series = df.index.to_series()
    elif time_col is not None:
        try:
            ts_series = pd.to_datetime(df[time_col], utc=True)
        except Exception:
            ts_series = None
    else:
        # Check first column
        try:
            ts_series = pd.to_datetime(df.iloc[:, 0], utc=True)
        except Exception:
            ts_series = None

    start_dt = None
    end_dt = None
    freshness_hours = None
    notes = []

    if ts_series is not None and len(ts_series) > 0:
        try:
            start_dt = ts_series.min().to_pydatetime()
            end_dt = ts_series.max().to_pydatetime()
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            freshness_hours = max(0.0, (now_utc - end_dt).total_seconds() / 3600.0)
        except Exception as e:
            notes.append(f"Timestamp parsing limitation: {e}")

    # Column inspection
    cols = [c.lower() for c in df.columns]
    req_cols = {"open", "high", "low", "close", "volume"}
    missing_cols = req_cols - set(cols)
    if missing_cols:
        return DataQualityReport(
            symbol=norm_symbol,
            has_local_data=True,
            data_source="local_csv",
            file_path=str(file_path),
            total_candles=len(df),
            start_time=start_dt,
            end_time=end_dt,
            freshness_hours=freshness_hours,
            data_quality_status="INCOMPLETE",
            readiness_classification=HistoricalReadinessClassification.INVALID_DATA.value,
            gap_count=0,
            notes=[f"Missing required OHLCV columns: {sorted(missing_cols)}"],
        )

    # Find lowercase column names
    col_map = {c.lower(): c for c in df.columns}
    o_col = col_map["open"]
    h_col = col_map["high"]
    l_col = col_map["low"]
    c_col = col_map["close"]
    v_col = col_map["volume"]

    # Invalid candle checks
    invalid_mask = (
        (df[h_col] < df[o_col])
        | (df[h_col] < df[c_col])
        | (df[l_col] > df[o_col])
        | (df[l_col] > df[c_col])
        | (df[v_col] < 0)
        | df[[o_col, h_col, l_col, c_col, v_col]].isna().any(axis=1)
    )
    invalid_count = int(invalid_mask.sum())

    if invalid_count > 0:
        notes.append(f"Detected {invalid_count} invalid OHLCV rows (high < low, negative volume, or nulls).")

    # Missing candles estimate (if timestamps exist and > 1 row)
    missing_gap_count = 0
    if ts_series is not None and len(ts_series) > 1:
        # Check monotonic ordering
        if not ts_series.is_monotonic_increasing:
            notes.append("Timestamps are not monotonically increasing.")

        # Intra-day gap detection within NSE trading session (09:15 to 15:30)
        try:
            ts_sorted = ts_series.sort_values().reset_index(drop=True)
            for i in range(len(ts_sorted) - 1):
                t1 = ts_sorted.iloc[i]
                t2 = ts_sorted.iloc[i + 1]
                if pd.notna(t1) and pd.notna(t2) and t1.date() == t2.date():
                    diff_min = int((t2 - t1).total_seconds() // 60)
                    if diff_min > 1:
                        # Only count during market hours
                        t_open = datetime.strptime("09:15:00", "%H:%M:%S").time()
                        t_close = datetime.strptime("15:30:00", "%H:%M:%S").time()
                        if t1.time() >= t_open and t2.time() <= t_close:
                            missing_gap_count += (diff_min - 1)
        except Exception as e:
            notes.append(f"Gap detection calculation limitation: {e}")

    candle_count = len(df)
    if candle_count < MIN_BACKTEST_CANDLES:
        notes.append(f"Candle count ({candle_count}) is below minimum backtest threshold ({MIN_BACKTEST_CANDLES}).")

    if missing_gap_count > 0:
        notes.append(f"Detected {missing_gap_count} missing candle minutes within standard trading sessions.")

    # Corporate action / overnight price jump inspection (demergers, stock splits)
    corp_action_jumps = []
    if ts_series is not None and len(ts_series) > 1 and o_col in df.columns and c_col in df.columns:
        try:
            temp_df = pd.DataFrame({"ts": ts_series, "open": df[o_col], "close": df[c_col]})
            temp_df["date"] = temp_df["ts"].dt.date
            daily_agg = temp_df.groupby("date").agg({"open": "first", "close": "last"}).reset_index()
            if len(daily_agg) > 1:
                daily_agg["prev_close"] = daily_agg["close"].shift(1)
                valid_prev = daily_agg["prev_close"] > 0
                gaps = (
                    (daily_agg.loc[valid_prev, "open"] - daily_agg.loc[valid_prev, "prev_close"]).abs()
                    / daily_agg.loc[valid_prev, "prev_close"]
                    * 100.0
                )
                extreme_indices = gaps[gaps >= 20.0].index
                for idx in extreme_indices:
                    row = daily_agg.loc[idx]
                    gap_pct = (row["open"] - row["prev_close"]) / row["prev_close"] * 100.0
                    corp_action_jumps.append(
                        f"Overnight gap of {gap_pct:+.1f}% on {row['date']} (prev close {row['prev_close']:.2f} -> open {row['open']:.2f})"
                    )
        except Exception as e:
            notes.append(f"Corporate action inspection limitation: {e}")

    if corp_action_jumps:
        notes.append(
            f"Corporate action risk: Detected {len(corp_action_jumps)} unadjusted price jump(s) >= 20% ({'; '.join(corp_action_jumps[:3])}). Demerger or split verification required before backtesting."
        )

    # Historical staleness check (older than 1 year)
    if freshness_hours is not None and freshness_hours > 24 * 365:
        stale_days = int(freshness_hours / 24)
        notes.append(
            f"Historical dataset ends on {end_dt.date()} (stale by {stale_days} days); contemporary data required before forward trading alignment."
        )

    # Assign backward-compatible status and 5-tier classification
    if invalid_count > 0:
        status = "INCOMPLETE"
        classification = HistoricalReadinessClassification.INVALID_DATA.value
    elif candle_count < MIN_BACKTEST_CANDLES:
        status = "INCOMPLETE"
        classification = HistoricalReadinessClassification.INCOMPLETE_COVERAGE.value
    elif missing_gap_count > (candle_count * 0.15):
        status = "INCOMPLETE"
        classification = HistoricalReadinessClassification.VERIFICATION_REQUIRED.value
        notes.append(f"High intraday gap density ({missing_gap_count} gaps vs {candle_count} candles) requires verification.")
    elif len(corp_action_jumps) > 0:
        status = "INCOMPLETE"
        classification = HistoricalReadinessClassification.VERIFICATION_REQUIRED.value
    else:
        status = "READY"
        classification = HistoricalReadinessClassification.PRELIMINARY_BACKTEST_READY.value

    return DataQualityReport(
        symbol=norm_symbol,
        has_local_data=True,
        data_source="local_csv",
        file_path=str(file_path),
        total_candles=candle_count,
        start_time=start_dt,
        end_time=end_dt,
        freshness_hours=freshness_hours,
        missing_candle_count=missing_gap_count,
        invalid_candle_count=invalid_count,
        data_quality_status=status,
        readiness_classification=classification,
        gap_count=missing_gap_count,
        notes=notes,
    )


def assess_stock_readiness(
    stock: StockRecord,
    strategy_id: str = "SignalForge_V1",
    registry: Optional[StockUniverseRegistry] = None,
    data_dir: Optional[Path] = None,
    as_of: Optional[datetime] = None,
) -> StockStrategyReadiness:
    """
    Perform a read-only readiness assessment for a registered stock and strategy.
    """
    now_utc = as_of or datetime.now(timezone.utc)
    symbol = stock.symbol
    exchange = stock.exchange
    exchange_valid = exchange.upper() in VALID_EXCHANGES

    # 1. Historical data inspection
    data_report = inspect_stock_historical_data(symbol, data_dir=data_dir, as_of=now_utc)
    has_sufficient_data = (
        data_report.total_candles >= MIN_BACKTEST_CANDLES
        and data_report.invalid_candle_count == 0
        and data_report.readiness_classification == HistoricalReadinessClassification.PRELIMINARY_BACKTEST_READY.value
    )

    # 2. Retrieve qualification record
    if registry:
        qual_record = registry.get_qualification(symbol, strategy_id)
    else:
        qual_record = None

    if qual_record:
        strat_version = qual_record.strategy_version
        bt_status = qual_record.backtest_status
        bt_net_profit = qual_record.backtest_net_profit
        oos_status = qual_record.oos_validation_status
        fwd_status = qual_record.forward_paper_test_status
        fwd_trades = qual_record.completed_trade_count
        qual_status = qual_record.qualification_status
    else:
        strat_version = "1.0"
        bt_status = "NOT_TESTED"
        bt_net_profit = None
        oos_status = "NOT_TESTED"
        fwd_status = "NOT_TESTED"
        fwd_trades = 0
        qual_status = QualificationStatus.NOT_TESTED

    # 3. Stage assessments
    bt_stage = StageAssessment(
        stage_name="historical_backtest",
        status=bt_status,
        is_passing=bt_status == "PASSED",
        details=(
            f"Backtest passed with profit {bt_net_profit:.2f}"
            if bt_status == "PASSED" and bt_net_profit is not None
            else f"Backtest status: {bt_status}"
        ),
    )

    oos_stage = StageAssessment(
        stage_name="out_of_sample_validation",
        status=oos_status,
        is_passing=oos_status == "PASSED",
        details=f"OOS validation status: {oos_status}",
    )

    meets_initial = fwd_trades >= DEFAULT_MIN_FORWARD_TRADES
    meets_preferred = fwd_trades >= DEFAULT_PREFERRED_FORWARD_TRADES
    fwd_stage = StageAssessment(
        stage_name="forward_paper_test",
        status=fwd_status,
        is_passing=fwd_status == "PASSED" and meets_initial,
        details=(
            f"{fwd_trades} completed trades (initial threshold: 30, preferred: 50)"
        ),
    )

    # 4. Missing evidence & Next Step evaluation
    missing_evidence: list[str] = []

    if not exchange_valid:
        missing_evidence.append(f"Invalid exchange: {exchange} (supported: {sorted(VALID_EXCHANGES)})")

    if not data_report.has_local_data:
        missing_evidence.append("Historical 1-minute OHLCV data missing")
    elif data_report.invalid_candle_count > 0:
        missing_evidence.append(
            f"Historical data contains {data_report.invalid_candle_count} invalid candles"
        )
    elif data_report.readiness_classification == HistoricalReadinessClassification.VERIFICATION_REQUIRED.value:
        corp_notes = [n for n in data_report.notes if "Corporate action" in n]
        if corp_notes:
            missing_evidence.append(
                "Historical data requires corporate-action verification (unadjusted split/demerger risk)"
            )
        else:
            missing_evidence.append(
                f"Historical data requires verification ({data_report.missing_candle_count} missing candles)"
            )
    elif not has_sufficient_data:
        missing_evidence.append(
            f"Insufficient historical data: {data_report.total_candles}/{MIN_BACKTEST_CANDLES} candles"
        )

    if bt_status != "PASSED":
        missing_evidence.append(f"Historical backtest not passed (current: {bt_status})")

    if oos_status != "PASSED":
        missing_evidence.append(f"Out-of-sample validation not passed (current: {oos_status})")

    if not meets_initial:
        missing_evidence.append(
            f"Forward paper trade sample size insufficient ({fwd_trades}/30 completed trades)"
        )
    elif not meets_preferred:
        missing_evidence.append(
            f"Preferred sample threshold not yet reached ({fwd_trades}/50 completed trades)"
        )

    if fwd_status != "PASSED":
        missing_evidence.append(f"Forward paper test run not passed (current: {fwd_status})")

    # Determine next required step
    if not exchange_valid:
        next_step = f"Correct stock exchange mapping from '{exchange}' to valid NSE/BSE exchange"
    elif not data_report.has_local_data:
        next_step = "Ingest historical 1-minute OHLCV market data"
    elif data_report.invalid_candle_count > 0:
        next_step = f"Quarantine {data_report.invalid_candle_count} invalid candles and re-ingest clean historical data"
    elif data_report.readiness_classification == HistoricalReadinessClassification.VERIFICATION_REQUIRED.value:
        corp_notes = [n for n in data_report.notes if "Corporate action" in n]
        if corp_notes:
            next_step = "Verify corporate-action adjustments (splits/demergers) before backtest execution"
        else:
            next_step = f"Verify historical data continuity and resolve missing intraday candles ({data_report.missing_candle_count} missing candles)"
    elif not has_sufficient_data:
        next_step = f"Acquire additional validated candles (current: {data_report.total_candles}, required: {MIN_BACKTEST_CANDLES})"
    elif bt_status != "PASSED":
        next_step = "Execute historical backtest on validated data"
    elif oos_status != "PASSED":
        next_step = "Execute out-of-sample validation on holdout period"
    elif not meets_initial:
        next_step = f"Accumulate forward paper trades: {fwd_trades}/30 completed"
    elif fwd_status != "PASSED":
        next_step = "Complete forward paper test evaluation run"
    elif qual_status != QualificationStatus.APPROVED:
        next_step = "Ready for qualification governance review"
    else:
        next_step = "Qualification criteria met and approved"

    # Determine overall readiness state
    if qual_status == QualificationStatus.APPROVED:
        overall_state = ReadinessState.APPROVED
    elif qual_status == QualificationStatus.REJECTED or "FAILED" in (bt_status, oos_status, fwd_status):
        overall_state = ReadinessState.FAILED
    elif not data_report.has_local_data or not has_sufficient_data:
        overall_state = ReadinessState.INSUFFICIENT_DATA
    elif any(s in ("PASSED", "IN_PROGRESS") for s in (bt_status, oos_status, fwd_status)) or fwd_trades > 0:
        overall_state = ReadinessState.IN_PROGRESS
    else:
        overall_state = ReadinessState.NOT_TESTED

    return StockStrategyReadiness(
        symbol=symbol,
        exchange=exchange,
        category=stock.category.value,
        strategy_id=strategy_id,
        strategy_version=strat_version,
        readiness_state=overall_state,
        exchange_valid=exchange_valid,
        data_quality=data_report,
        has_sufficient_backtest_data=has_sufficient_data,
        backtest_stage=bt_stage,
        oos_stage=oos_stage,
        forward_paper_stage=fwd_stage,
        forward_trade_count=fwd_trades,
        meets_initial_sample_threshold=meets_initial,
        meets_preferred_sample_threshold=meets_preferred,
        qualification_status=qual_status,
        missing_evidence=missing_evidence,
        next_required_step=next_step,
        assessed_at=now_utc,
    )


def assess_universe_readiness(
    registry: StockUniverseRegistry,
    strategy_id: str = "SignalForge_V1",
    data_dir: Optional[Path] = None,
    as_of: Optional[datetime] = None,
) -> dict[str, Any]:
    """
    Evaluate readiness summary across the entire registered stock universe.
    """
    stocks = registry.list_all()
    now_utc = as_of or datetime.now(timezone.utc)

    assessments = [
        assess_stock_readiness(
            stock=s,
            strategy_id=strategy_id,
            registry=registry,
            data_dir=data_dir,
            as_of=now_utc,
        )
        for s in stocks
    ]

    state_counts: dict[str, int] = {state.value: 0 for state in ReadinessState}
    category_counts: dict[str, int] = {}
    data_ready_count = 0

    for a in assessments:
        state_counts[a.readiness_state.value] = state_counts.get(a.readiness_state.value, 0) + 1
        category_counts[a.category] = category_counts.get(a.category, 0) + 1
        if a.has_sufficient_backtest_data:
            data_ready_count += 1

    return {
        "strategy_id": strategy_id,
        "total_registered_stocks": len(stocks),
        "assessed_at": now_utc.isoformat(),
        "summary": {
            "by_state": state_counts,
            "by_category": category_counts,
            "data_ready_count": data_ready_count,
            "meets_initial_sample_count": sum(1 for a in assessments if a.meets_initial_sample_threshold),
            "approved_count": sum(1 for a in assessments if a.qualification_status == QualificationStatus.APPROVED),
        },
        "assessments": [a.to_dict() for a in assessments],
    }
