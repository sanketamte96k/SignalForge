"""Pydantic response models for the SignalForge API."""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class HealthResponse(BaseModel):
    """API health response."""

    model_config = ConfigDict(extra="forbid")

    status: str
    service: str


class NiftyLatestResponse(BaseModel):
    """Latest NIFTY 50 market candle."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class StrategyIndicators(BaseModel):
    """Indicators for the strategy response."""

    model_config = ConfigDict(extra="forbid")

    ema_fast: float | None = None
    ema_slow: float | None = None
    rsi: float | None = None
    atr: float | None = None
    volume: float | None = None
    vwap: float | None = None


class StrategyConfirmation(BaseModel):
    """Confirmation factors for the strategy response."""

    model_config = ConfigDict(extra="forbid")

    ema: bool | None = None
    rsi_momentum: bool | None = None
    volume: bool | None = None
    multi_timeframe: bool | None = None


class StrategySignalResponse(BaseModel):
    """Strategy signal response exposing genuine engine state."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    timeframe: str
    timestamp: datetime
    signal: str
    signal_reason: str
    entry_price: float | None = None
    stop_loss: float | None = None
    target_1: float | None = None
    target_2: float | None = None
    confidence: float | None = None
    indicators: StrategyIndicators
    confirmation: StrategyConfirmation
    status: str
    position: str | None = None
    price: float | None = None
    strategy: str = "SignalForge"


class NiftySignalResponse(StrategySignalResponse):
    """Latest NIFTY 50 SignalForge strategy state."""

    pass


class SignalAnalysisDetail(BaseModel):
    """Signal engine decision details."""

    model_config = ConfigDict(extra="forbid")

    score: int | None = None
    confidence: float | None = None
    reason: str | None = None
    timeframe_alignment: int | None = None


class BaseIndicatorsResponse(BaseModel):
    """1-minute base candle indicators, if calculated."""

    model_config = ConfigDict(extra="forbid")

    ema20: float | None = None
    ema50: float | None = None
    rsi14: float | None = None
    atr14: float | None = None
    rvol20: float | None = None


class TimeframeDetail(BaseModel):
    """Analysis state for a specific timeframe."""

    model_config = ConfigDict(extra="forbid")

    timeframe: str
    timestamp: datetime | None = None
    close: float | None = None
    ema20: float | None = None
    ema50: float | None = None
    rsi14: float | None = None
    atr14: float | None = None
    rvol20: float | None = None
    trend: str | None = None
    ready: bool = False


class NiftyAnalysisResponse(BaseModel):
    """Complete NIFTY 50 analysis response."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    timestamp: datetime
    price: float
    signal: str
    position: str | None
    strategy: str
    analysis: SignalAnalysisDetail
    indicators: BaseIndicatorsResponse
    timeframes: dict[str, TimeframeDetail]


class NiftyChartCandle(BaseModel):
    """One real NIFTY 50 chart candle with backend RSI(14)."""

    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    rsi14: float | None = None


class NiftyChartResponse(BaseModel):
    """Historical NIFTY 50 chart data for a selected timeframe."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    timeframe: str
    candles: list[NiftyChartCandle]


class StockChartCandle(BaseModel):
    """One real stock chart candle with backend RSI(14)."""

    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    rsi14: float | None = None


class StockChartResponse(BaseModel):
    """Historical stock chart data for a selected timeframe."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    timeframe: str
    candles: list[StockChartCandle]


class StockResponse(BaseModel):
    """Stock universe response."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    exchange: str
    instrument_type: str
    validation_status: str
    signal_eligible: bool


class StockSearchResponse(BaseModel):
    """Stock search response."""

    model_config = ConfigDict(extra="forbid")

    results: list[StockResponse]


class StockAddRequest(BaseModel):
    """Request for adding a stock to the SignalForge universe."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    exchange: str = "NSE"
    instrument_type: str = "EQUITY"


class StockScannerItem(BaseModel):
    """Latest scanner state for one stock."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    name: str
    exchange: str
    validation_status: str
    signal_eligible: bool
    signal: str
    position: str | None
    timestamp: datetime | None = None
    price: float | None = None
    score: int | None = None
    confidence: float | None = None
    timeframe_alignment: int | None = None
    reason: str


class StockScannerResponse(BaseModel):
    """Complete NIFTY 50 stock scanner response."""

    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    universe: str
    total_stocks: int
    signal_eligible_stocks: int
    buy_count: int
    sell_count: int
    no_trade_count: int
    items: list[StockScannerItem]


class StockDataReadinessResponse(BaseModel):
    """Historical stock-data readiness response."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    available: bool
    ready: bool
    missing: bool
    path: str
    total_rows: int
    first_timestamp: datetime | None
    last_timestamp: datetime | None
    required_start: datetime
    required_end: datetime
    covers_required_period: bool
    issues: list[str]


class StockValidationResponse(BaseModel):
    """Stock validation and approval response."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    status: str
    signal_eligible: bool
    approved: bool
    passed_gates: list[str]
    failed_gates: list[str]
    issues: list[str]


class StockImportResponse(BaseModel):
    """Historical stock-data import response."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    filename: str
    imported: bool
    total_rows: int
    path: str
    readiness: StockDataReadinessResponse


class SectorCreateRequest(BaseModel):
    """Request for creating a custom sector."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""


class SectorResponse(BaseModel):
    """Custom sector response."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    symbols: list[str]


class SectorListResponse(BaseModel):
    """List of configured sectors."""

    model_config = ConfigDict(extra="forbid")

    sectors: list[SectorResponse]


class WatchlistCreateRequest(BaseModel):
    """Request for creating a custom watchlist."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""


class WatchlistResponse(BaseModel):
    """Custom watchlist response."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    symbols: list[str]


class WatchlistListResponse(BaseModel):
    """List of configured watchlists."""

    model_config = ConfigDict(extra="forbid")

    watchlists: list[WatchlistResponse]


class PaperTradingStatusResponse(BaseModel):
    """Current paper-trading session status."""

    model_config = ConfigDict(extra="forbid")

    active: bool
    has_position: bool
    trade_count: int
    starting_capital: float
    realized_pnl: float
    current_equity: float
    total_transaction_cost: float


class PaperTradingReportResponse(BaseModel):
    """Paper-trading performance report."""

    model_config = ConfigDict(extra="forbid")

    starting_capital: float
    ending_equity: float
    realized_pnl: float
    total_transaction_cost: float
    trade_count: int
    winning_trades: int
    losing_trades: int
    gross_profit: float
    gross_loss: float
    long_trades: int
    short_trades: int
    net_return_pct: float
    win_rate_pct: float
    profit_factor: float


class PaperTradeResponse(BaseModel):
    """Completed or historical paper trade (legacy compatibility)."""

    model_config = ConfigDict(extra="allow")

    position: str
    entry_price: float
    exit_price: float
    quantity: int
    entry_time: datetime
    exit_time: datetime
    gross_pnl: float
    transaction_cost: float
    net_pnl: float
    reason: str
    return_pct: float


class PaperTradeCreateRequest(BaseModel):
    """Request to open a new interactive paper trade."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    side: str
    timeframe: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    quantity: int = 1
    signal_price: float | None = None
    signal_timestamp: datetime | None = None
    entry_timestamp: datetime | None = None
    strategy_signal: str | None = None
    client_request_id: str | None = None
    max_signal_age_seconds: float | None = None


class PaperTradeUpdateRequest(BaseModel):
    """Request to evaluate an open paper trade against market data."""

    model_config = ConfigDict(extra="forbid")

    current_price: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    timestamp: datetime | None = None


class PaperTradeCloseRequest(BaseModel):
    """Request to manually close an open paper trade."""

    model_config = ConfigDict(extra="forbid")

    exit_price: float | None = None
    exit_time: datetime | None = None
    reason: str = "MANUAL_CLOSE"


class InteractivePaperTradeResponse(BaseModel):
    """Full lifecycle interactive paper trade response model."""

    model_config = ConfigDict(extra="allow")

    trade_id: str
    symbol: str
    side: str
    direction: str = "LONG"
    timeframe: str
    strategy: str = "SignalForge"

    signal_timestamp: datetime
    entry_timestamp: datetime
    exit_timestamp: datetime | None = None

    signal_price: float
    entry_signal_price: float = 0.0
    entry_price: float
    actual_entry_price: float = 0.0
    exit_signal_price: float | None = None
    exit_price: float | None = None
    actual_exit_price: float | None = None

    stop_loss: float
    target_1: float
    target_2: float

    quantity: int

    status: str

    gross_pnl: float = 0.0
    realized_pnl: float
    unrealized_pnl: float

    brokerage: float = 0.0
    stt: float = 0.0
    exchange_fee: float = 0.0
    sebi_fee: float = 0.0
    gst: float = 0.0
    stamp_duty: float = 0.0
    taxes_and_fees: float = 0.0
    slippage_cost: float = 0.0
    spread_penalty: float = 0.0
    total_cost: float = 0.0
    net_pnl: float = 0.0

    exit_reason: str | None = None
    config_id: str = "REALISTIC_INDIA_INTRADAY_V1"
    client_request_id: str | None = None

    created_at: datetime
    updated_at: datetime

    # Backward-compatible fields
    position: str | None = None
    entry_time: datetime | None = None
    exit_time: datetime | None = None
    reason: str | None = None
    return_pct: float | None = None


class PaperTradingSummaryResponse(BaseModel):
    """Aggregate performance summary for interactive paper trading."""

    model_config = ConfigDict(extra="allow")

    total_trades: int
    open_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    gross_pnl: float
    total_costs: float = 0.0
    net_pnl: float = 0.0
    average_trade: float
    average_net_trade: float = 0.0
    largest_win: float
    largest_loss: float
    profit_factor: float | None = None
    max_drawdown: float = 0.0


class PaperTradingAccountResponse(BaseModel):
    """Paper trading account capital, equity, and drawdown state."""

    model_config = ConfigDict(extra="forbid")

    simulation_only: bool = True
    starting_capital: float
    available_capital: float
    used_capital: float
    gross_realized_pnl: float
    total_costs: float
    realized_pnl: float
    unrealized_pnl: float
    total_equity: float
    peak_equity: float
    drawdown: float
    drawdown_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    open_positions_count: int
    completed_trades_count: int
    cost_model_id: str


class PaperTradingRiskMetricsResponse(BaseModel):
    """Comprehensive deterministic risk and performance metrics."""

    model_config = ConfigDict(extra="forbid")

    simulation_only: bool = True
    total_trades: int
    open_trades: int
    closed_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float | None = None
    gross_pnl: float
    total_costs: float
    net_pnl: float
    average_gross_trade: float | None = None
    average_net_trade: float | None = None
    profit_factor: float | None = None
    max_drawdown: float
    max_drawdown_pct: float
    average_win: float | None = None
    average_loss: float | None = None
    expectancy: float | None = None
    largest_win: float | None = None
    largest_loss: float | None = None


class PaperTradingCostBreakdownResponse(BaseModel):
    """Aggregate transaction cost & slippage breakdown."""

    model_config = ConfigDict(extra="forbid")

    simulation_only: bool = True
    config_id: str
    cost_model: dict
    completed_trades: int
    gross_pnl: float
    brokerage: float
    stt: float
    exchange_fee: float
    sebi_fee: float
    gst: float
    stamp_duty: float
    taxes_and_fees: float
    slippage_cost: float
    spread_penalty: float
    total_cost: float
    net_pnl: float


class PaperTradingEquityPointResponse(BaseModel):
    """Chronological equity curve snapshot."""

    model_config = ConfigDict(extra="forbid")

    step: int
    timestamp: str
    event: str
    trade_id: str | None = None
    starting_capital: float
    available_capital: float
    used_capital: float
    gross_realized_pnl: float
    total_costs: float
    realized_pnl: float
    unrealized_pnl: float
    total_equity: float
    peak_equity: float
    drawdown: float
    drawdown_pct: float
    max_drawdown: float
    max_drawdown_pct: float


class PaperTradingConfigRequest(BaseModel):
    """Request to configure paper account capital or cost model."""

    model_config = ConfigDict(extra="forbid")

    starting_capital: float | None = None
    config_id: str | None = None
    brokerage_per_order: float | None = None
    brokerage_rate: float | None = None
    use_min_brokerage: bool | None = None
    stt_rate: float | None = None
    exchange_fee_rate: float | None = None
    sebi_fee_rate: float | None = None
    gst_rate: float | None = None
    stamp_duty_rate: float | None = None
    slippage_bps: float | None = None
    entry_slippage_bps: float | None = None
    exit_slippage_bps: float | None = None
    spread_penalty_bps: float | None = None
    max_signal_age_seconds: float | None = None
class UniverseStockResponse(BaseModel):
    symbol: str
    exchange: str
    name: str | None = None
    category: str
    membership_verified_at: datetime | None = None
    data_quality_status: str
    created_at: datetime

class UniverseStockAddRequest(BaseModel):
    symbol: str
    exchange: str
    name: str | None = None
    category: str


class QualificationUpdateRequest(BaseModel):
    strategy_version: str
    historical_data_status: str
    backtest_status: str
    backtest_net_profit: float | None = None
    oos_validation_status: str
    forward_paper_test_status: str
    completed_trade_count: int = 0
    qualification_status: str
    status_reason: str | None = None
    evidence_reference: str | None = None

    @field_validator("completed_trade_count", mode="before")
    @classmethod
    def validate_trade_count(cls, v: object) -> object:
        if isinstance(v, bool):
            raise ValueError("completed_trade_count cannot be boolean")
        if isinstance(v, int) and v < 0:
            raise ValueError("completed_trade_count cannot be negative")
        return v

    @field_validator("backtest_net_profit", mode="before")
    @classmethod
    def validate_finite_profit(cls, v: object) -> object:
        if isinstance(v, bool):
            raise ValueError("backtest_net_profit cannot be boolean")
        if isinstance(v, (int, float)):
            if not math.isfinite(v):
                raise ValueError("backtest_net_profit must be a finite number")
        return v

class QualificationResponse(QualificationUpdateRequest):
    symbol: str
    exchange: str
    strategy_id: str
    updated_at: datetime


class DataQualityResponse(BaseModel):
    symbol: str
    has_local_data: bool
    data_source: str | None = None
    file_path: str | None = None
    total_candles: int
    start_time: datetime | None = None
    end_time: datetime | None = None
    freshness_hours: float | None = None
    missing_candle_count: int = 0
    invalid_candle_count: int = 0
    data_quality_status: str
    readiness_classification: str = "NO_DATA"
    gap_count: int = 0
    notes: list[str] = []


class StageAssessmentResponse(BaseModel):
    stage_name: str
    status: str
    is_passing: bool
    details: str


class StockReadinessResponse(BaseModel):
    symbol: str
    exchange: str
    category: str
    strategy_id: str
    strategy_version: str
    readiness_state: str
    exchange_valid: bool
    data_quality: DataQualityResponse
    has_sufficient_backtest_data: bool
    backtest_stage: StageAssessmentResponse
    oos_stage: StageAssessmentResponse
    forward_paper_stage: StageAssessmentResponse
    forward_trade_count: int
    meets_initial_sample_threshold: bool
    meets_preferred_sample_threshold: bool
    qualification_status: str
    missing_evidence: list[str]
    next_required_step: str
    assessed_at: datetime


class UniverseReadinessSummaryResponse(BaseModel):
    strategy_id: str
    total_registered_stocks: int
    assessed_at: datetime
    summary: dict[str, Any]
    assessments: list[StockReadinessResponse]


class IngestionRequest(BaseModel):
    category: str
    confirm_removals: bool = False


class PipelineIngestSymbolRequest(BaseModel):
    symbol: str
    exchange: str = "NSE"
    interval: str = "1m"
    provider: str = "local_archive"
    dry_run: bool = True
    confirm_replace: bool = False


class PipelineBatchIngestRequest(BaseModel):
    symbols: list[str]
    exchange: str = "NSE"
    interval: str = "1m"
    provider: str = "local_archive"
    dry_run: bool = True
    confirm_replace: bool = False
    confirm_large_batch: bool = False


class BacktestRunRequest(BaseModel):
    """
    Request payload to initiate an asynchronous backtest simulation.

    Cost Model Configuration:
    - cost_profile: Selects the transaction cost schedule. Allowed values:
      'DISCOUNT_BROKER_REALISTIC' (default, canonical Indian market schedule),
      'STATUTORY_ONLY', 'CONSERVATIVE_STRESS', 'ZERO_COST', 'LEGACY_LINEAR'.
    - transaction_cost_rate: Single linear turnover multiplier, active ONLY when
      cost_profile is explicitly set to 'LEGACY_LINEAR' (default: 0.0001).
    """

    model_config = ConfigDict(extra="forbid")

    symbol: str = "NIFTY 50"
    start_date: str | None = None
    end_date: str | None = None
    initial_capital: float = 10_000.0
    quantity: int = 1
    transaction_cost_rate: float = 0.0001
    cost_profile: str = "DISCOUNT_BROKER_REALISTIC"
    execution_model: str = "next_open"

    # Optional strategy parameter overrides (frozen defaults)
    ema_fast_period: int = 20
    ema_slow_period: int = 50
    rsi_period: int = 14
    atr_period: int = 14
    rvol_period: int = 20
    minimum_rvol: float = 1.5
    minimum_atr: float = 0.0
    minimum_long_rsi: float = 60.0
    use_rvol: bool = False

    # Production Intraday Risk Controls (Phase 27C.2)
    stop_loss_atr: float = 1.5
    take_profit_atr: float = 3.0
    session_end_time: str = "15:15"
    risk_per_trade_pct: float = 0.01
    max_leverage: float = 5.0
    max_exposure: float | None = None
    capital_protection_floor: float | None = None
    overall_loss_limit: float | None = None

    # Production Opening Market Cooldown (Phase 27C.3.4)
    opening_cooldown_minutes: int = 10
    market_open_time: str = "09:15"

    @field_validator("symbol")
    @classmethod
    def validate_symbol_field(cls, v: str) -> str:
        s = v.strip().upper()
        if not s:
            raise ValueError("symbol cannot be empty.")
        return s

    @field_validator("initial_capital")
    @classmethod
    def validate_capital_field(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("initial_capital must be greater than zero.")
        return v

    @field_validator("quantity")
    @classmethod
    def validate_quantity_field(cls, v: int) -> int:
        if v < 1:
            raise ValueError("quantity must be at least 1.")
        return v

    @field_validator("transaction_cost_rate")
    @classmethod
    def validate_cost_field(cls, v: float) -> float:
        if v < 0:
            raise ValueError("transaction_cost_rate cannot be negative.")
        return v

    @field_validator("cost_profile")
    @classmethod
    def validate_cost_profile_field(cls, v: str) -> str:
        s = v.strip().upper()
        allowed = {"DISCOUNT_BROKER_REALISTIC", "STATUTORY_ONLY", "CONSERVATIVE_STRESS", "ZERO_COST", "LEGACY_LINEAR"}
        if s not in allowed:
            raise ValueError(f"Unsupported cost_profile: '{v}'. Supported profiles: {sorted(allowed)}")
        return s

    @field_validator("execution_model")
    @classmethod
    def validate_execution_model_field(cls, v: str) -> str:
        if v not in {"next_open", "same_close"}:
            raise ValueError("execution_model must be 'next_open' or 'same_close'.")
        return v

    @field_validator("stop_loss_atr")
    @classmethod
    def validate_stop_loss_atr_field(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("stop_loss_atr must be greater than zero.")
        return v

    @field_validator("take_profit_atr")
    @classmethod
    def validate_take_profit_atr_field(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("take_profit_atr must be greater than zero.")
        return v

    @field_validator("session_end_time")
    @classmethod
    def validate_session_end_time_field(cls, v: str) -> str:
        s = v.strip()
        if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", s):
            raise ValueError(f"session_end_time must be in 'HH:MM' 24-hour format, got '{v}'.")
        return s

    @field_validator("risk_per_trade_pct")
    @classmethod
    def validate_risk_per_trade_pct_field(cls, v: float) -> float:
        if v <= 0 or v > 1.0:
            raise ValueError("risk_per_trade_pct must be in range (0.0, 1.0].")
        return v

    @field_validator("max_leverage")
    @classmethod
    def validate_max_leverage_field(cls, v: float) -> float:
        if v < 1.0:
            raise ValueError("max_leverage must be at least 1.0.")
        return v

    @field_validator("capital_protection_floor")
    @classmethod
    def validate_capital_protection_floor_field(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("capital_protection_floor cannot be negative.")
        return v

    @field_validator("overall_loss_limit")
    @classmethod
    def validate_overall_loss_limit_field(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("overall_loss_limit must be greater than zero.")
        return v

    @field_validator("max_exposure")
    @classmethod
    def validate_max_exposure_field(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("max_exposure must be greater than zero.")
        return v

    @field_validator("opening_cooldown_minutes")
    @classmethod
    def validate_opening_cooldown_minutes_field(cls, v: int) -> int:
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError("opening_cooldown_minutes must be an integer.")
        if v < 0:
            raise ValueError("opening_cooldown_minutes cannot be negative.")
        return v


class BacktestJobCreatedResponse(BaseModel):
    """Response returned upon successfully creating a backtest job."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: str
    symbol: str
    created_at: str
    message: str


class BacktestJobStatusResponse(BaseModel):
    """Response returned when querying backtest job status."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: str
    symbol: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    progress: float = 0.0
    error: str | None = None


class BacktestTradeItem(BaseModel):
    """A simulated trade item within a completed backtest."""

    model_config = ConfigDict(extra="ignore")

    trade_id: int
    entry_time: str
    exit_time: str
    side: str
    entry_price: float
    exit_price: float
    quantity: int
    gross_pnl: float
    costs: float
    net_pnl: float
    return_pct: float
    exit_reason: str


class BacktestMetricsItem(BaseModel):
    """Performance summary metrics for a backtest."""

    model_config = ConfigDict(extra="ignore")

    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    total_pnl: float
    total_return_pct: float
    win_rate_pct: float
    average_win: float
    average_loss: float
    profit_factor: float | str
    expectancy: float
    max_drawdown_pct: float


class BacktestJobResultResponse(BaseModel):
    """Detailed response returned for a completed backtest job."""

    model_config = ConfigDict(extra="ignore")

    job_id: str
    status: str
    symbol: str
    date_range: dict[str, Any]
    execution_model: str
    metrics: BacktestMetricsItem
    portfolio: dict[str, Any]
    trades: list[BacktestTradeItem]
    bankruptcy_reason: str | None = None
    risk_config: dict[str, Any] | None = None
    cost_model: dict[str, Any] | None = None



