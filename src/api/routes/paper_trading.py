from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from src.api.models import (
    PaperTradeResponse,
    PaperTradingReportResponse,
    PaperTradingStatusResponse,
)
from src.data.downloader import load_market_data
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


def _empty_report() -> PaperTradingReportResponse:
    return PaperTradingReportResponse(
        starting_capital=100000.0,
        ending_equity=100000.0,
        realized_pnl=0.0,
        total_transaction_cost=0.0,
        trade_count=0,
        winning_trades=0,
        losing_trades=0,
        gross_profit=0.0,
        gross_loss=0.0,
        long_trades=0,
        short_trades=0,
        net_return_pct=0.0,
        win_rate_pct=0.0,
        profit_factor=0.0,
    )


@router.get(
    "/status",
    response_model=PaperTradingStatusResponse,
)
def get_paper_trading_status() -> PaperTradingStatusResponse:
    """
    Return the current authoritative paper-trading state.

    Before a replay, the session is READY with zero trades.

    After a replay, the completed replay runner becomes the
    authoritative state exposed by this endpoint.
    """
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
    response_model=list[PaperTradeResponse],
)
def get_paper_trading_trades() -> list[PaperTradeResponse]:
    """Return completed paper trades from the authoritative runner."""
    runner = _get_current_runner()

    if runner is None:
        return []

    return [
        PaperTradeResponse(
            position=trade.position.name,
            entry_price=float(trade.entry_price),
            exit_price=float(trade.exit_price),
            quantity=int(trade.quantity),
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            gross_pnl=float(trade.gross_pnl),
            transaction_cost=float(
                trade.transaction_cost
            ),
            net_pnl=float(trade.net_pnl),
            reason=trade.reason,
            return_pct=float(trade.return_pct),
        )
        for trade in runner.engine.state.completed_trades
    ]


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
    """Reset the current paper-trading session."""
    global _runner
    global _replay_runner

    _runner = PaperTradingRunner()
    _replay_runner = None

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