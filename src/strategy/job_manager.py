"""
SignalForge — Backtest Job Management & Execution Engine
=========================================================
Provides asynchronous, non-blocking backtest job queuing, lifecycle tracking,
and execution safety for local workstations.
Features:
1. Thread-safe in-memory job store guarded by threading.Lock.
2. Bounded memory footprint (max 50 jobs with deterministic FIFO eviction).
3. ThreadPoolExecutor background execution preventing ASGI event loop blocking.
4. Independent dataset slicing and cursor instantiation (zero shared mutable state).
5. Comprehensive error capture, state progression, and clean serialization.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional
import uuid

import numpy as np
import pandas as pd

from src.backtest.engine import run_backtest
from src.core.security import validate_safe_path, validate_symbol
from src.data.downloader import load_market_data
from src.data.stock_provider import StockDataProvider
from src.strategy.backtest_strategy import StrategyConfig, create_signal_function


class JobStatus(str, Enum):
    """Lifecycle states for backtest jobs."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class BacktestJob:
    """State and payload for a single backtest job."""

    job_id: str
    symbol: str
    status: JobStatus
    created_at: datetime
    request_params: dict[str, Any]
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    _future: Optional[Future] = field(default=None, repr=False)

    @property
    def error_message(self) -> Optional[str]:
        """Convenience alias for error string."""
        return self.error

    @error_message.setter
    def error_message(self, val: Optional[str]) -> None:
        self.error = val

    @property
    def metrics(self) -> Optional[dict[str, Any]]:
        """Convenience accessor for metrics dictionary from result."""
        return self.result.get("metrics") if self.result else None

    @property
    def trades(self) -> Optional[list[dict[str, Any]]]:
        """Convenience accessor for trades list from result."""
        return self.result.get("trades") if self.result else None

    def to_status_dict(self) -> dict[str, Any]:
        """Convert job status to serializable response dictionary."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "symbol": self.symbol,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": round(self.progress, 1),
            "error": self.error,
        }


class BacktestJobManager:
    """
    Thread-safe, bounded in-memory manager for asynchronous backtest execution.
    """

    def __init__(
        self,
        max_workers: int = 2,
        max_retained_jobs: int = 50,
        max_jobs: Optional[int] = None,
    ) -> None:
        self._max_workers = max_workers
        self._max_retained_jobs = max_jobs if max_jobs is not None else max_retained_jobs
        self._lock = threading.Lock()
        self._jobs: dict[str, BacktestJob] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="BacktestWorker",
        )
        self._stock_provider = StockDataProvider()

    def create_job(self, params: Optional[dict[str, Any]] = None, **kwargs) -> BacktestJob:
        """
        Instantiate and store a backtest job in QUEUED state without scheduling execution.
        """
        combined = dict(params or {})
        combined.update(kwargs)

        raw_symbol = str(combined.get("symbol", "NIFTY 50")).strip()
        if raw_symbol.upper() in {"NIFTY 50", "NIFTY", "^NSEI"}:
            normalized_symbol = "NIFTY 50"
        else:
            normalized_symbol = validate_symbol(raw_symbol)

        start_date = combined.get("start_date")
        end_date = combined.get("end_date")
        if normalized_symbol == "NIFTY 50":
            if (start_date and str(start_date)[:10] > "2024-03-26") or (end_date and str(end_date)[:10] > "2024-03-26"):
                raise ValueError("NIFTY 50 historical backtest date exceeds verified dataset boundary. Maximum permitted date is 2024-03-26.")

        job_id = f"job-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        job = BacktestJob(
            job_id=job_id,
            symbol=normalized_symbol,
            status=JobStatus.QUEUED,
            created_at=now,
            request_params=combined,
            progress=0.0,
        )

        with self._lock:
            # Deterministic bounded capacity: prune oldest finished jobs if limit reached
            if len(self._jobs) >= self._max_retained_jobs:
                self._prune_oldest_jobs()

            self._jobs[job_id] = job

        return job

    def submit_job(self, params: Optional[dict[str, Any]] = None, **kwargs) -> BacktestJob:
        """
        Validate parameters, instantiate job, and submit to background thread pool.
        """
        job = self.create_job(params, **kwargs)
        future = self._executor.submit(self._execute_job, job.job_id)
        job._future = future
        return job

    def get_job(self, job_id: str) -> Optional[BacktestJob]:
        """Thread-safe retrieval of a backtest job by identifier."""
        with self._lock:
            return self._jobs.get(job_id)

    def get_job_status(self, job_id: str) -> Optional[BacktestJob]:
        """Convenience alias for get_job returning status object."""
        return self.get_job(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Attempt to cancel a queued or running job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False

            if job.status == JobStatus.QUEUED:
                if job._future:
                    job._future.cancel()
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now(timezone.utc)
                job.error = "Job cancelled by user before execution."
                return True

            if job.status == JobStatus.RUNNING:
                # Flag cancellation (will terminate upon check)
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now(timezone.utc)
                job.error = "Job cancelled by user during execution."
                return True

            return False

    def list_jobs(self) -> List[dict[str, Any]]:
        """Return list of all retained jobs sorted by creation timestamp descending."""
        with self._lock:
            return [
                job.to_status_dict()
                for job in sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
            ]

    def _prune_oldest_jobs(self) -> None:
        """Prune completed or failed jobs when storage limit is reached (caller holds lock)."""
        terminal_statuses = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
        prunable = [
            (jid, job)
            for jid, job in self._jobs.items()
            if job.status in terminal_statuses
        ]
        # Sort by creation time ascending (oldest first)
        prunable.sort(key=lambda item: item[1].created_at)

        to_remove = len(self._jobs) - self._max_retained_jobs + 1
        for i in range(min(to_remove, len(prunable))):
            del self._jobs[prunable[i][0]]

    def _load_data_for_job(self, symbol: str) -> pd.DataFrame:
        """Load and validate market data for the requested symbol."""
        if symbol in {"NIFTY 50", "NIFTY", "^NSEI"}:
            path = Path("data/historical/nifty50_1m_signalforge.csv")
            if not path.exists():
                raise FileNotFoundError("NIFTY 50 historical data file not found on disk.")
            data = pd.read_csv(path, index_col=0, parse_dates=True)
            data.index.name = None
            return data

        # Equity symbol
        path = self._stock_provider.local_path(symbol)
        if not path.exists():
            raise FileNotFoundError(
                f"Historical 1m market data file not found for symbol '{symbol}'."
            )
        return load_market_data(path)

    def _execute_job(self, job_id: str) -> None:
        """Worker thread entry point for sequential execution."""
        job = self.get_job(job_id)
        if not job:
            return

        with self._lock:
            if job.status == JobStatus.CANCELLED:
                return
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            job.progress = 10.0

        try:
            params = job.request_params
            symbol = job.symbol

            # Checkpoint 1: Cancellation check before loading data
            with self._lock:
                if job.status == JobStatus.CANCELLED:
                    return

            # 1. Load Data
            data = self._load_data_for_job(symbol)

            # Checkpoint 2: Cancellation check after loading data
            with self._lock:
                if job.status == JobStatus.CANCELLED:
                    return
                job.progress = 20.0

            # 2. Slice Date Range (explicit copy for full thread isolation)
            start_date = params.get("start_date")
            end_date = params.get("end_date")

            if start_date or end_date:
                data = data.loc[start_date:end_date].copy()
            else:
                data = data.copy()

            if data.empty:
                raise ValueError(
                    f"No market data available for '{symbol}' within date range [{start_date} to {end_date}]."
                )

            total_candles = len(data)
            if total_candles < 100:
                raise ValueError(
                    f"Insufficient market data ({total_candles} candles) to compute multi-timeframe indicators. Minimum 100 required."
                )

            # Checkpoint 3: Cancellation check before indicator & signal build
            with self._lock:
                if job.status == JobStatus.CANCELLED:
                    return
                job.progress = 40.0

            # 3. Strategy Configuration (per-job independent instance)
            config = StrategyConfig(
                ema_fast_period=int(params.get("ema_fast_period", 20)),
                ema_slow_period=int(params.get("ema_slow_period", 50)),
                rsi_period=int(params.get("rsi_period", 14)),
                atr_period=int(params.get("atr_period", 14)),
                rvol_period=int(params.get("rvol_period", 20)),
                minimum_rvol=float(params.get("minimum_rvol", 1.5)),
                minimum_atr=float(params.get("minimum_atr", 0.0)),
                minimum_long_rsi=float(params.get("minimum_long_rsi", 60.0)),
                use_rvol=bool(params.get("use_rvol", False)),
            )

            # 4. Create Signal Function
            sig_fn = create_signal_function(data, config)

            # Checkpoint 4: Cancellation check before backtest simulation
            with self._lock:
                if job.status == JobStatus.CANCELLED:
                    return
                job.progress = 60.0

            # 5. Run Backtest
            initial_capital = float(params.get("initial_capital", 100_000.0))
            quantity = int(params.get("quantity", 1))
            cost_rate = float(params.get("transaction_cost_rate", 0.0001))
            exec_model = str(params.get("execution_model", "next_open"))

            if exec_model not in {"next_open", "same_close"}:
                raise ValueError(f"Invalid execution_model: '{exec_model}'. Supported: 'next_open', 'same_close'.")

            with self._lock:
                if job.status == JobStatus.CANCELLED:
                    return
                job.progress = 75.0

            backtest_result = run_backtest(
                data=data,
                signal_function=sig_fn,
                initial_capital=initial_capital,
                quantity=quantity,
                transaction_cost_rate=cost_rate,
                execution_model=exec_model,
            )

            # Checkpoint 5: Check cancellation before formatting & persisting results
            with self._lock:
                if job.status == JobStatus.CANCELLED:
                    return
                job.progress = 90.0

            metrics = backtest_result.metrics
            portfolio = backtest_result.portfolio

            # Safe profit factor serialization
            pf_val = metrics.profit_factor
            if math.isinf(pf_val) or math.isnan(pf_val):
                pf_display = "inf"
            else:
                pf_display = round(float(pf_val), 2)

            trades_serialized = []
            for idx, t in enumerate(backtest_result.trades, 1):
                trades_serialized.append(
                    {
                        "trade_id": idx,
                        "entry_time": str(t.entry_time),
                        "exit_time": str(t.exit_time),
                        "side": t.position.value if hasattr(t.position, "value") else str(t.position),
                        "entry_price": round(float(t.entry_price), 2),
                        "exit_price": round(float(t.exit_price), 2),
                        "quantity": int(t.quantity),
                        "gross_pnl": round(float(t.gross_pnl), 2),
                        "costs": round(float(t.transaction_cost), 2),
                        "net_pnl": round(float(t.net_pnl), 2),
                        "return_pct": round(float(t.return_pct) * 100.0, 3),
                        "exit_reason": str(t.exit_reason),
                    }
                )

            first_dt = str(data.index[0])
            last_dt = str(data.index[-1])

            formatted_result = {
                "job_id": job.job_id,
                "status": JobStatus.COMPLETED.value,
                "symbol": symbol,
                "date_range": {
                    "start": first_dt,
                    "end": last_dt,
                    "requested_start": start_date,
                    "requested_end": end_date,
                    "total_candles": total_candles,
                },
                "execution_model": exec_model,
                "metrics": {
                    "total_trades": metrics.total_trades,
                    "winning_trades": metrics.winning_trades,
                    "losing_trades": metrics.losing_trades,
                    "breakeven_trades": metrics.breakeven_trades,
                    "total_pnl": round(float(metrics.total_pnl), 2),
                    "total_return_pct": round(float(metrics.total_return_pct) * 100.0, 2),
                    "win_rate_pct": round(float(metrics.win_rate_pct), 2),
                    "average_win": round(float(metrics.average_win), 2) if not math.isnan(metrics.average_win) else 0.0,
                    "average_loss": round(float(metrics.average_loss), 2) if not math.isnan(metrics.average_loss) else 0.0,
                    "profit_factor": pf_display,
                    "expectancy": round(float(metrics.expectancy), 2) if not math.isnan(metrics.expectancy) else 0.0,
                    "max_drawdown_pct": round(float(metrics.max_drawdown_pct), 2),
                },
                "portfolio": {
                    "initial_capital": round(float(portfolio.initial_capital), 2),
                    "final_equity": round(float(portfolio.cash), 2),
                    "peak_equity": round(float(portfolio.peak_equity), 2),
                    "max_drawdown_pct": round(float(portfolio.max_drawdown), 2),
                    "is_bankrupt": portfolio.is_bankrupt,
                },
                "trades": trades_serialized,
            }

            with self._lock:
                if job.status == JobStatus.CANCELLED:
                    return
                job.result = formatted_result
                job.status = JobStatus.COMPLETED
                job.progress = 100.0
                job.completed_at = datetime.now(timezone.utc)

        except Exception as exc:
            with self._lock:
                if job.status == JobStatus.CANCELLED:
                    return
                job.status = JobStatus.FAILED
                job.error = str(exc)
                job.completed_at = datetime.now(timezone.utc)
                job.progress = 0.0


# Global singleton instance for the FastAPI application
_job_manager: Optional[BacktestJobManager] = None
_manager_lock = threading.Lock()


def get_job_manager() -> BacktestJobManager:
    """Return the global BacktestJobManager singleton instance."""
    global _job_manager
    with _manager_lock:
        if _job_manager is None:
            _job_manager = BacktestJobManager(max_workers=2, max_retained_jobs=50)
        return _job_manager
