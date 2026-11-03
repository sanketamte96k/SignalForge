"""Strategy state and asynchronous backtesting API routes."""

from __future__ import annotations

from typing import List
from fastapi import APIRouter, HTTPException, Query, status

from src.api.models import (
    BacktestJobCreatedResponse,
    BacktestJobResultResponse,
    BacktestJobStatusResponse,
    BacktestRunRequest,
    StrategySignalResponse,
)
from src.api.routes.nifty import (
    SUPPORTED_STRATEGY_TIMEFRAMES,
    _build_strategy_signal,
    _load_nifty_data,
)
from src.data.downloader import load_market_data
from src.data.stock_provider import StockDataProvider
from src.strategy.job_manager import JobStatus, get_job_manager


router = APIRouter(
    prefix="/api/strategy",
    tags=["strategy"],
)

_stock_provider = StockDataProvider()


@router.get(
    "/signal",
    response_model=StrategySignalResponse,
)
def get_strategy_signal(
    symbol: str = Query("NIFTY 50"),
    timeframe: str = Query("15m"),
) -> StrategySignalResponse:
    """Return the current strategy state for a symbol and timeframe."""
    normalized_symbol = symbol.strip().upper()

    if not normalized_symbol:
        raise HTTPException(
            status_code=400,
            detail="Symbol cannot be empty.",
        )

    if timeframe not in SUPPORTED_STRATEGY_TIMEFRAMES:
        supported = ", ".join(SUPPORTED_STRATEGY_TIMEFRAMES)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported strategy timeframe: '{timeframe}'. "
                f"Supported: {supported}."
            ),
        )

    if normalized_symbol in {"NIFTY 50", "NIFTY", "^NSEI"}:
        data = _load_nifty_data()
        return _build_strategy_signal(data, "NIFTY 50", timeframe)

    path = _stock_provider.local_path(normalized_symbol)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Historical data not available for symbol '{normalized_symbol}'.",
        )

    try:
        data = load_market_data(path)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Unable to load data for {normalized_symbol}: {exc}",
        ) from exc

    if data.empty:
        raise HTTPException(
            status_code=503,
            detail=f"Market data for {normalized_symbol} is empty.",
        )

    return _build_strategy_signal(data, normalized_symbol, timeframe)


# ----------------------------------------------------------------------------
# Backtest Job Interface Endpoints
# ----------------------------------------------------------------------------

@router.post(
    "/backtest/run",
    response_model=BacktestJobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_backtest_job(
    request: BacktestRunRequest,
) -> BacktestJobCreatedResponse:
    """
    Validate and queue an asynchronous backtest simulation.
    """
    manager = get_job_manager()
    job = manager.submit_job(request.model_dump())

    return BacktestJobCreatedResponse(
        job_id=job.job_id,
        status=job.status.value,
        symbol=job.symbol,
        created_at=job.created_at.isoformat(),
        message="Backtest job successfully queued for execution.",
    )


@router.get(
    "/backtest/jobs/{job_id}",
    response_model=BacktestJobStatusResponse,
)
def get_backtest_job_status(
    job_id: str,
) -> BacktestJobStatusResponse:
    """
    Query the status and execution progress of a backtest job.
    """
    manager = get_job_manager()
    job = manager.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Backtest job '{job_id}' not found.",
        )

    return BacktestJobStatusResponse(**job.to_status_dict())


@router.get(
    "/backtest/jobs/{job_id}/result",
    response_model=BacktestJobResultResponse,
)
def get_backtest_job_result(
    job_id: str,
) -> BacktestJobResultResponse:
    """
    Retrieve the completed quantitative results of a backtest job.
    """
    manager = get_job_manager()
    job = manager.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Backtest job '{job_id}' not found.",
        )

    if job.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Backtest job '{job_id}' is still in progress (status: {job.status.value}). Results are not yet ready.",
        )

    if job.status == JobStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Backtest job '{job_id}' failed: {job.error}",
        )

    if job.status == JobStatus.CANCELLED:
        raise HTTPException(
            status_code=400,
            detail=f"Backtest job '{job_id}' was cancelled.",
        )

    if not job.result:
        raise HTTPException(
            status_code=500,
            detail=f"Backtest job '{job_id}' completed without result payload.",
        )

    return BacktestJobResultResponse(**job.result)


@router.get(
    "/backtest/jobs",
    response_model=List[BacktestJobStatusResponse],
)
def list_backtest_jobs() -> List[BacktestJobStatusResponse]:
    """
    List recently submitted backtest jobs.
    """
    manager = get_job_manager()
    jobs = manager.list_jobs()
    return [BacktestJobStatusResponse(**j) for j in jobs]


@router.post(
    "/backtest/jobs/{job_id}/cancel",
)
def cancel_backtest_job(
    job_id: str,
) -> dict[str, Any]:
    """
    Cancel a queued or running backtest job.
    """
    manager = get_job_manager()
    cancelled = manager.cancel_job(job_id)
    if not cancelled:
        job = manager.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Backtest job '{job_id}' not found.",
            )
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job '{job_id}' with status '{job.status.value}'.",
        )
    return {"job_id": job_id, "status": "CANCELLED", "message": "Job cancellation initiated."}
