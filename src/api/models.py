"""Pydantic response models for the SignalForge API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


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


class NiftySignalResponse(BaseModel):
    """Latest NIFTY 50 SignalForge strategy state."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    signal: str
    position: str | None
    timestamp: datetime
    price: float
    strategy: str


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
    """Completed paper trade."""

    model_config = ConfigDict(extra="forbid")

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