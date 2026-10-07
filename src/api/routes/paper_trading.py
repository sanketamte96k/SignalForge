from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status

from src.api.models import (
    InteractivePaperTradeResponse,
    PaperTradeCloseRequest,
    PaperTradeCreateRequest,
    PaperTradeUpdateRequest,
    PaperTradingAccountResponse,
    PaperTradingConfigRequest,
    PaperTradingCostBreakdownResponse,
    PaperTradingEquityPointResponse,
    PaperTradingReportResponse,
    PaperTradingRiskMetricsResponse,
    PaperTradingStatusResponse,
    PaperTradingSummaryResponse,
)
from src.data.downloader import load_market_data
from src.paper_trading.cost_model import CostModel
from src.paper_trading.interactive_engine import (
    InteractivePaperTrade,
    InteractivePaperTradingService,
)
from src.paper_trading.replay_runner import PaperTradingReplayRunner
from src.paper_trading.runner import PaperTradingRunner


router = APIRouter(
    prefix="/api/paper-trading",
    tags=["paper-trading"],
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "historical"
    / "nifty50_1m.csv"
)


_runner: PaperTradingRunner | None = None
_replay_runner: PaperTradingReplayRunner | None = None
_interactive_service: InteractivePaperTradingService | None = None


def _get_interactive_service() -> InteractivePaperTradingService:
    global _interactive_service
    if _interactive_service is None:
        _interactive_service = InteractivePaperTradingService()
    return _interactive_service


def _get_or_create_runner() -> PaperTradingRunner:
    global _runner

    if _runner is None:
        _runner = PaperTradingRunner()

    return _runner


def _get_current_runner() -> PaperTradingRunner | None:
    """
    Return the runner whose state should currently be exposed.

    A completed replay owns the authoritative paper-trading state
    after /start. Before a replay exists, use the normal runner.
    """
    if _replay_runner is not None:
        return _replay_runner

    return _runner


def _interactive_trade_to_response(
    trade: InteractivePaperTrade,
) -> InteractivePaperTradeResponse:
    """Convert an InteractivePaperTrade to the full response schema."""
    return InteractivePaperTradeResponse(
        trade_id=trade.trade_id,
        symbol=trade.symbol,
        side=trade.side,
        direction=trade.direction,
        timeframe=trade.timeframe,
        strategy=trade.strategy,
        signal_timestamp=trade.signal_timestamp,
        entry_timestamp=trade.entry_timestamp,
        exit_timestamp=trade.exit_timestamp,
        signal_price=trade.signal_price,
        entry_signal_price=trade.entry_signal_price,
        entry_price=trade.entry_price,
        actual_entry_price=trade.actual_entry_price,
        exit_signal_price=trade.exit_signal_price,
        exit_price=trade.exit_price,
        actual_exit_price=trade.actual_exit_price,
        stop_loss=trade.stop_loss,
        target_1=trade.target_1,
        target_2=trade.target_2,
        quantity=trade.quantity,
        status=trade.status,
        gross_pnl=trade.gross_pnl,
        realized_pnl=trade.realized_pnl,
        unrealized_pnl=trade.unrealized_pnl,
        brokerage=trade.brokerage,
        stt=trade.stt,
        exchange_fee=trade.exchange_fee,
        sebi_fee=trade.sebi_fee,
        gst=trade.gst,
        stamp_duty=trade.stamp_duty,
        taxes_and_fees=trade.taxes_and_fees,
        slippage_cost=trade.slippage_cost,
        spread_penalty=trade.spread_penalty,
        total_cost=trade.total_cost,
        net_pnl=trade.net_pnl,
        exit_reason=trade.exit_reason,
        config_id=trade.config_id,
        client_request_id=trade.client_request_id,
        created_at=trade.created_at,
        updated_at=trade.updated_at,
        position=trade.side,
        entry_time=trade.entry_timestamp,
        exit_time=trade.exit_timestamp,
        reason=trade.exit_reason or "",
        return_pct=trade.return_pct,
    )


def _report_to_response() -> PaperTradingReportResponse:
    """
    Convert the authoritative paper-trading report into
    the public API response model.
    """
    if _replay_runner is not None:
        report = _replay_runner.report
    else:
        runner = _get_or_create_runner()
        report = runner.report

    return PaperTradingReportResponse(
        starting_capital=float(report.starting_capital),
        ending_equity=float(report.ending_equity),
        realized_pnl=float(report.realized_pnl),
        total_transaction_cost=float(
            report.total_transaction_cost
        ),
        trade_count=int(report.trade_count),
        winning_trades=int(report.winning_trades),
        losing_trades=int(report.losing_trades),
        gross_profit=float(report.gross_profit),
        gross_loss=float(report.gross_loss),
        long_trades=int(report.long_trades),
        short_trades=int(report.short_trades),
        net_return_pct=float(report.net_return_pct),
        win_rate_pct=float(report.win_rate_pct),
        profit_factor=float(report.profit_factor),
    )


# ----------------------------------------------------------------------------
# Phase 17 & 18: Interactive Paper Trading Endpoints
# ----------------------------------------------------------------------------


@router.post(
    "/trades",
    response_model=InteractivePaperTradeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_paper_trade(
    req: PaperTradeCreateRequest,
) -> InteractivePaperTradeResponse:
    """
    Open a new interactive paper trade based on an active strategy signal.
    Rejects duplicate active positions (409) and invalid signals/brackets/capital (400).
    """
    service = _get_interactive_service()

    try:
        trade = service.create_trade(
            symbol=req.symbol,
            side=req.side,
            timeframe=req.timeframe,
            entry_price=req.entry_price,
            stop_loss=req.stop_loss,
            target_1=req.target_1,
            target_2=req.target_2,
            quantity=req.quantity,
            signal_price=req.signal_price,
            signal_timestamp=req.signal_timestamp,
            entry_timestamp=req.entry_timestamp,
            strategy_signal=req.strategy_signal,
            client_request_id=req.client_request_id,
            max_signal_age_seconds=req.max_signal_age_seconds,
        )
        return _interactive_trade_to_response(trade)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc).strip("'"),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/open",
    response_model=list[InteractivePaperTradeResponse],
)
def get_open_paper_trades() -> list[InteractivePaperTradeResponse]:
    """Return all currently active open paper trades."""
    service = _get_interactive_service()
    open_trades = service.get_open_trades()
    return [_interactive_trade_to_response(t) for t in open_trades]


@router.get(
    "/trades/{trade_id}",
    response_model=InteractivePaperTradeResponse,
)
def get_paper_trade(trade_id: str) -> InteractivePaperTradeResponse:
    """Return a single paper trade by trade_id."""
    service = _get_interactive_service()
    trade = service.get_trade(trade_id)
    if trade is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper trade '{trade_id}' not found",
        )
    return _interactive_trade_to_response(trade)


@router.post(
    "/trades/{trade_id}/update",
    response_model=InteractivePaperTradeResponse,
)
def update_paper_trade(
    trade_id: str,
    req: PaperTradeUpdateRequest,
) -> InteractivePaperTradeResponse:
    """
    Update an open paper trade against current market price or candle.
    Evaluates stop-loss and targets with conservative ambiguity resolution.
    """
    service = _get_interactive_service()

    try:
        updated = service.update_trade(
            trade_id=trade_id,
            current_price=req.current_price,
            candle_open=req.open,
            candle_high=req.high,
            candle_low=req.low,
            candle_close=req.close,
            timestamp=req.timestamp,
        )
        return _interactive_trade_to_response(updated)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc).strip("'"),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/trades/{trade_id}/close",
    response_model=InteractivePaperTradeResponse,
)
def close_paper_trade(
    trade_id: str,
    req: PaperTradeCloseRequest,
) -> InteractivePaperTradeResponse:
    """Manually close an open paper trade."""
    service = _get_interactive_service()

    try:
        closed = service.close_trade(
            trade_id=trade_id,
            exit_price=req.exit_price,
            exit_time=req.exit_time,
            reason=req.reason,
        )
        return _interactive_trade_to_response(closed)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc).strip("'"),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/summary",
    response_model=PaperTradingSummaryResponse,
)
def get_paper_trading_summary() -> PaperTradingSummaryResponse:
    """Return performance summary for interactive paper trading."""
    service = _get_interactive_service()
    summary = service.get_summary()
    return PaperTradingSummaryResponse(**summary)


# ----------------------------------------------------------------------------
# Phase 18: Account State, Risk Metrics, Equity Curve & Cost Breakdown
# ----------------------------------------------------------------------------


@router.get(
    "/account",
    response_model=PaperTradingAccountResponse,
)
def get_paper_trading_account() -> PaperTradingAccountResponse:
    """Return current paper account capital, equity, and drawdown state."""
    service = _get_interactive_service()
    return PaperTradingAccountResponse(**service.get_account_state())


@router.get(
    "/metrics",
    response_model=PaperTradingRiskMetricsResponse,
)
def get_paper_trading_metrics() -> PaperTradingRiskMetricsResponse:
    """Return comprehensive risk and performance metrics."""
    service = _get_interactive_service()
    return PaperTradingRiskMetricsResponse(**service.get_risk_metrics())


@router.get(
    "/costs",
    response_model=PaperTradingCostBreakdownResponse,
)
def get_paper_trading_costs() -> PaperTradingCostBreakdownResponse:
    """Return aggregate transaction cost and slippage breakdown."""
    service = _get_interactive_service()
    return PaperTradingCostBreakdownResponse(**service.get_cost_breakdown())


@router.get(
    "/equity-curve",
    response_model=list[PaperTradingEquityPointResponse],
)
def get_paper_trading_equity_curve() -> list[PaperTradingEquityPointResponse]:
    """Return chronological equity curve points."""
    service = _get_interactive_service()
    return [PaperTradingEquityPointResponse(**pt) for pt in service.get_equity_curve()]


@router.post(
    "/config",
    response_model=PaperTradingAccountResponse,
)
def configure_paper_trading(
    req: PaperTradingConfigRequest,
) -> PaperTradingAccountResponse:
    """Update paper account capital or transaction cost model parameters."""
    service = _get_interactive_service()
    current_model_dict = asdict(service.cost_model)

    for key in [
        "config_id",
        "brokerage_per_order",
        "brokerage_rate",
        "use_min_brokerage",
        "stt_rate",
        "exchange_fee_rate",
        "sebi_fee_rate",
        "gst_rate",
        "stamp_duty_rate",
        "slippage_bps",
        "entry_slippage_bps",
        "exit_slippage_bps",
        "spread_penalty_bps",
    ]:
        val = getattr(req, key)
        if val is not None:
            current_model_dict[key] = val

    try:
        new_model = CostModel(**current_model_dict)
        service.configure(
            starting_capital=req.starting_capital,
            cost_model=new_model,
            max_signal_age_seconds=req.max_signal_age_seconds,
        )
        return PaperTradingAccountResponse(**service.get_account_state())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


# ----------------------------------------------------------------------------
# Legacy & Shared Endpoints
# ----------------------------------------------------------------------------


@router.get(
    "/status",
    response_model=PaperTradingStatusResponse,
)
def get_paper_trading_status() -> PaperTradingStatusResponse:
    """Return the current authoritative paper-trading state."""
    global _replay_runner

    if _replay_runner is not None:
        state = _replay_runner.engine.state

        return PaperTradingStatusResponse(
            active=True,
            has_position=state.has_position,
            trade_count=state.trade_count,
            starting_capital=float(
                state.starting_capital
            ),
            realized_pnl=float(
                state.realized_pnl
            ),
            current_equity=float(
                state.current_equity
            ),
            total_transaction_cost=float(
                state.total_transaction_cost
            ),
        )

    runner = _get_or_create_runner()
    state = runner.engine.state

    return PaperTradingStatusResponse(
        active=False,
        has_position=state.has_position,
        trade_count=state.trade_count,
        starting_capital=float(
            state.starting_capital
        ),
        realized_pnl=float(
            state.realized_pnl
        ),
        current_equity=float(
            state.current_equity
        ),
        total_transaction_cost=float(
            state.total_transaction_cost
        ),
    )


@router.get(
    "/report",
    response_model=PaperTradingReportResponse,
)
def get_paper_trading_report() -> PaperTradingReportResponse:
    """Return the current paper-trading performance report."""
    return _report_to_response()


@router.get(
    "/trades",
    response_model=list[InteractivePaperTradeResponse],
)
def get_paper_trading_trades(
    symbol: str | None = Query(None),
    side: str | None = Query(None),
    timeframe: str | None = Query(None),
    status: str | None = Query(None),
) -> list[InteractivePaperTradeResponse]:
    """
    Return paper trades history.
    Includes interactive trades if present, or completed replay trades if run.
    """
    service = _get_interactive_service()
    interactive_trades = service.list_trades(
        symbol=symbol,
        side=side,
        timeframe=timeframe,
        status=status,
    )
    if interactive_trades:
        return [_interactive_trade_to_response(t) for t in interactive_trades]

    # Replay fallback for legacy test compatibility
    runner = _get_current_runner()
    if runner is not None and runner.engine.state.completed_trades:
        return [
            InteractivePaperTradeResponse(
                trade_id=f"legacy_{idx+1}",
                symbol="NIFTY 50",
                side=trade.position.name,
                direction=trade.position.name,
                timeframe="15m",
                signal_timestamp=trade.entry_time,
                entry_timestamp=trade.entry_time,
                exit_timestamp=trade.exit_time,
                signal_price=float(trade.entry_price),
                entry_signal_price=float(trade.entry_price),
                entry_price=float(trade.entry_price),
                actual_entry_price=float(trade.entry_price),
                exit_signal_price=float(trade.exit_price),
                exit_price=float(trade.exit_price),
                actual_exit_price=float(trade.exit_price),
                stop_loss=0.0,
                target_1=0.0,
                target_2=0.0,
                quantity=int(trade.quantity),
                status="CLOSED",
                gross_pnl=float(trade.gross_pnl),
                realized_pnl=float(trade.gross_pnl),
                unrealized_pnl=0.0,
                total_cost=float(trade.transaction_cost),
                net_pnl=float(trade.net_pnl),
                exit_reason=trade.reason,
                created_at=trade.entry_time,
                updated_at=trade.exit_time,
                position=trade.position.name,
                entry_time=trade.entry_time,
                exit_time=trade.exit_time,
                reason=trade.reason,
                return_pct=float(trade.return_pct),
            )
            for idx, trade in enumerate(runner.engine.state.completed_trades)
        ]

    return []


@router.post(
    "/start",
    response_model=PaperTradingReportResponse,
)
def start_paper_trading() -> PaperTradingReportResponse:
    """
    Run a deterministic paper-trading replay over
    the available historical NIFTY dataset.

    This endpoint does not place real broker orders.
    """
    global _replay_runner

    if not DATA_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "NIFTY historical dataset is unavailable."
            ),
        )

    try:
        data = load_market_data(DATA_PATH)

        _replay_runner = PaperTradingReplayRunner(
            adapter_data=data,
        )

        _replay_runner.run()

        return _report_to_response()

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Paper-trading replay failed: "
                f"{exc}"
            ),
        ) from exc


@router.post(
    "/reset",
    response_model=PaperTradingStatusResponse,
)
def reset_paper_trading() -> PaperTradingStatusResponse:
    """Reset the current paper-trading session and interactive state."""
    global _runner
    global _replay_runner

    _runner = PaperTradingRunner()
    _replay_runner = None

    _get_interactive_service().reset()

    state = _runner.engine.state

    return PaperTradingStatusResponse(
        active=False,
        has_position=False,
        trade_count=0,
        starting_capital=float(
            state.starting_capital
        ),
        realized_pnl=float(
            state.realized_pnl
        ),
        current_equity=float(
            state.current_equity
        ),
        total_transaction_cost=float(
            state.total_transaction_cost
        ),
    )