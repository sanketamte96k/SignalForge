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

from src.backtest.engine import IntradayEngineConfig, run_backtest, run_intraday_backtest
from src.backtest.multi_asset_engine import (
    MultiAssetBacktestResult,
    MultiAssetEngineConfig,
    run_multi_asset_backtest,
)
from src.backtest.indian_market_costs import (
    COST_PROFILES,
    DISCOUNT_BROKER_REALISTIC_CONFIG,
    get_cost_config,
)
from src.core.security import validate_safe_path, validate_symbol
from src.data.downloader import load_market_data
from src.data.stock_provider import StockDataProvider
from src.strategy.backtest_strategy import (
    StrategyConfig,
    create_signal_function,
    generate_signals,
)


class JobStatus(str, Enum):
    """Lifecycle states for backtest jobs."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class BacktestJob:
    """State and payload for a single or multi-asset backtest job."""

    job_id: str
    symbol: str
    status: JobStatus
    created_at: datetime
    request_params: dict[str, Any]
    symbols: list[str] = field(default_factory=list)
    is_multi_asset: bool = False
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    _future: Optional[Future] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.symbols and self.symbol:
            self.symbols = [self.symbol]
        elif self.symbols and not self.symbol:
            self.symbol = "MULTI" if len(self.symbols) > 1 else self.symbols[0]

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
            "symbols": list(self.symbols),
            "is_multi_asset": self.is_multi_asset,
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
        Instantiate and store a single or multi-asset backtest job in QUEUED state without scheduling execution.
        """
        combined = dict(params or {})
        combined.update(kwargs)

        is_multi_asset = False
        raw_symbols_list: list[str] = []

        if "symbols" in combined and combined["symbols"] is not None:
            symbols_input = combined["symbols"]
            if not isinstance(symbols_input, list) or not symbols_input:
                raise ValueError("symbols must be a non-empty list of stock symbols.")

            seen_symbols: set[str] = set()
            for s in symbols_input:
                if not isinstance(s, str):
                    raise ValueError("Every symbol in symbols must be a string.")
                s_strip = s.strip()
                if not s_strip:
                    raise ValueError("Symbol cannot be empty.")
                if s_strip.upper() in {"NIFTY 50", "NIFTY", "^NSEI"}:
                    norm = "NIFTY 50"
                else:
                    norm = validate_symbol(s_strip)
                if norm.upper() in seen_symbols:
                    raise ValueError(f"Duplicate symbol detected in request: '{norm}'.")
                seen_symbols.add(norm.upper())
                raw_symbols_list.append(norm)

            is_multi_asset = True
            normalized_symbol = "MULTI" if len(raw_symbols_list) > 1 else raw_symbols_list[0]
        else:
            raw_symbol = str(combined.get("symbol", "NIFTY 50")).strip()
            if raw_symbol.upper() in {"NIFTY 50", "NIFTY", "^NSEI"}:
                normalized_symbol = "NIFTY 50"
            else:
                normalized_symbol = validate_symbol(raw_symbol)
            raw_symbols_list = [normalized_symbol]

        start_date = combined.get("start_date")
        end_date = combined.get("end_date")
        if "NIFTY 50" in raw_symbols_list:
            if (start_date and str(start_date)[:10] > "2024-03-26") or (end_date and str(end_date)[:10] > "2024-03-26"):
                raise ValueError("NIFTY 50 historical backtest date exceeds verified dataset boundary. Maximum permitted date is 2024-03-26.")

        job_id = f"job-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        job = BacktestJob(
            job_id=job_id,
            symbol=normalized_symbol,
            symbols=raw_symbols_list,
            is_multi_asset=is_multi_asset,
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
        Automatically routes to single or multi-asset worker based on job configuration.
        """
        job = self.create_job(params, **kwargs)
        if job.is_multi_asset:
            future = self._executor.submit(self._execute_multi_asset_job, job.job_id)
        else:
            future = self._executor.submit(self._execute_job, job.job_id)
        job._future = future
        return job

    def create_multi_asset_job(self, params: Optional[dict[str, Any]] = None, **kwargs) -> BacktestJob:
        """Explicit convenience method to create a multi-asset backtest job."""
        combined = dict(params or {})
        combined.update(kwargs)
        return self.create_job(combined)

    def submit_multi_asset_job(self, params: Optional[dict[str, Any]] = None, **kwargs) -> BacktestJob:
        """Explicit convenience method to submit a multi-asset backtest job."""
        combined = dict(params or {})
        combined.update(kwargs)
        return self.submit_job(combined)

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

            # Ensure lowercase column aliases exist for strategy calculation
            for col in ("open", "high", "low", "close", "volume"):
                if col not in data.columns:
                    for existing in list(data.columns):
                        if str(existing).lower() == col:
                            data[col] = data[existing]
                            break

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

            if "cost_profile" in params and params["cost_profile"] is not None:
                cost_profile_raw = str(params["cost_profile"]).strip().upper()
            else:
                # Default across all entry points: canonical realistic model.
                # Legacy linear mode is never silently activated; it requires explicit cost_profile="LEGACY_LINEAR".
                cost_profile_raw = "DISCOUNT_BROKER_REALISTIC"

            if exec_model not in {"next_open", "same_close"}:
                raise ValueError(f"Invalid execution_model: '{exec_model}'. Supported: 'next_open', 'same_close'.")

            if cost_profile_raw == "LEGACY_LINEAR":
                cost_config = None
                cost_model_meta = {
                    "mode": "LEGACY_LINEAR",
                    "transaction_cost_rate": cost_rate,
                    "description": "Legacy linear turnover multiplier",
                }
            else:
                cost_config = get_cost_config(cost_profile_raw)
                cost_model_meta = {
                    "mode": "CANONICAL",
                    "profile_name": cost_config.name,
                    "description": cost_config.description,
                    "brokerage_rate_pct": cost_config.brokerage_rate_pct,
                    "brokerage_max_per_leg_inr": cost_config.brokerage_max_per_leg_inr,
                    "stt_rate_sell_pct": cost_config.stt_rate_sell_pct,
                    "exchange_charge_rate_pct": cost_config.exchange_charge_rate_pct,
                    "sebi_charge_rate_pct": cost_config.sebi_charge_rate_pct,
                    "stamp_duty_rate_buy_pct": cost_config.stamp_duty_rate_buy_pct,
                    "gst_rate_pct": cost_config.gst_rate_pct,
                    "slippage_rate_pct": cost_config.slippage_rate_pct,
                    "spread_rate_pct": cost_config.spread_rate_pct,
                }
                cost_rate = 0.0

            # Phase 27C.2 Production Intraday Risk Configuration
            stop_loss_atr = float(params.get("stop_loss_atr", 1.5))
            take_profit_atr = float(params.get("take_profit_atr", 3.0))
            session_end_time = str(params.get("session_end_time", "15:15"))
            risk_per_trade_pct = float(params.get("risk_per_trade_pct", 0.01))
            max_leverage = float(params.get("max_leverage", 5.0))

            max_exposure = params.get("max_exposure")
            if max_exposure is not None:
                max_exposure = float(max_exposure)
            elif initial_capital == 10_000.0:
                max_exposure = 50_000.0
            else:
                max_exposure = initial_capital * max_leverage

            overall_loss_limit = params.get("overall_loss_limit")
            if overall_loss_limit is not None:
                overall_loss_limit = float(overall_loss_limit)

            capital_protection_floor = params.get("capital_protection_floor")
            if capital_protection_floor is not None:
                capital_protection_floor = float(capital_protection_floor)
            elif overall_loss_limit is not None:
                capital_protection_floor = max(0.0, initial_capital - overall_loss_limit)
            elif initial_capital == 10_000.0:
                capital_protection_floor = 8_000.0
                overall_loss_limit = 2_000.0

            opening_cooldown_minutes = params.get("opening_cooldown_minutes", 10)
            if opening_cooldown_minutes is not None:
                opening_cooldown_minutes = int(opening_cooldown_minutes)
            market_open_time = str(params.get("market_open_time", "09:15"))

            risk_config_meta = {
                "initial_capital": initial_capital,
                "risk_per_trade_pct": risk_per_trade_pct,
                "max_leverage": max_leverage,
                "max_exposure": max_exposure,
                "stop_loss_atr": stop_loss_atr,
                "take_profit_atr": take_profit_atr,
                "session_end_time": session_end_time,
                "capital_protection_floor": capital_protection_floor,
                "overall_loss_limit": overall_loss_limit,
                "enforce_eod_square_off": True,
                "gap_execution": True,
                "conservative_same_candle": True,
                "opening_cooldown_minutes": opening_cooldown_minutes,
                "market_open_time": market_open_time,
            }

            with self._lock:
                if job.status == JobStatus.CANCELLED:
                    return
                job.progress = 75.0

            intraday_cfg = IntradayEngineConfig(
                initial_capital=initial_capital,
                risk_per_trade=risk_per_trade_pct,
                max_leverage=max_leverage,
                max_exposure=max_exposure,
                capital_protection_floor=capital_protection_floor,
                overall_loss_limit=overall_loss_limit,
                stop_atr_multiplier=stop_loss_atr,
                target_atr_multiplier=take_profit_atr,
                transaction_cost_rate=cost_rate,
                session_end_time=session_end_time,
                enforce_eod_square_off=True,
                gap_execution=True,
                conservative_same_candle=True,
                execution_model=exec_model,
                cost_config=cost_config,
                opening_cooldown_minutes=opening_cooldown_minutes,
                market_open_time=market_open_time,
            )

            backtest_result = run_intraday_backtest(
                data=data,
                signal_generator=sig_fn,
                config=intraday_cfg,
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
                        "return_pct": round(float(t.return_pct), 3),
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
                "cost_model": cost_model_meta,
                "risk_config": risk_config_meta,
                "bankruptcy_reason": backtest_result.bankruptcy_reason,
                "metrics": {
                    "total_trades": metrics.total_trades,
                    "winning_trades": metrics.winning_trades,
                    "losing_trades": metrics.losing_trades,
                    "breakeven_trades": metrics.breakeven_trades,
                    "total_pnl": round(float(metrics.total_pnl), 2),
                    "total_return_pct": round(float(metrics.total_return_pct), 2),
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
                    "is_bankrupt": portfolio.is_bankrupt or (backtest_result.bankruptcy_reason is not None),
                    "bankruptcy_reason": backtest_result.bankruptcy_reason,
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

    def _execute_multi_asset_job(self, job_id: str) -> None:
        """Worker thread entry point for multi-asset backtest execution."""
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
            symbols = list(job.symbols)
            start_date = params.get("start_date")
            end_date = params.get("end_date")

            # Checkpoint 1: Cancellation check before loading data
            with self._lock:
                if job.status == JobStatus.CANCELLED:
                    return

            # 1. Load Data for each symbol
            data_by_symbol: dict[str, pd.DataFrame] = {}
            for sym in symbols:
                sym_data = self._load_data_for_job(sym)
                if start_date or end_date:
                    sym_data = sym_data.loc[start_date:end_date].copy()
                else:
                    sym_data = sym_data.copy()

                if sym_data.empty:
                    raise ValueError(
                        f"No market data available for '{sym}' within date range [{start_date} to {end_date}]."
                    )

                min_req = int(params.get("min_required_candles", 100))
                if len(sym_data) < min_req:
                    raise ValueError(
                        f"Insufficient market data ({len(sym_data)} candles) for '{sym}'. Minimum {min_req} required."
                    )
                data_by_symbol[sym] = sym_data

            # Checkpoint 2: Cancellation check after loading data
            with self._lock:
                if job.status == JobStatus.CANCELLED:
                    return
                job.progress = 30.0

            # 2. Strategy Configuration & Signal Generation per symbol
            strat_config = StrategyConfig(
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

            # Check if custom signals_by_symbol was passed in params (e.g. synthetic test fixtures)
            if "signals_by_symbol" in params and params["signals_by_symbol"] is not None:
                signals_by_symbol = params["signals_by_symbol"]
            else:
                signals_by_symbol = {}
                for sym, s_df in data_by_symbol.items():
                    sig_input_df = s_df.copy()
                    sig_input_df.columns = [str(c).lower() for c in sig_input_df.columns]
                    sig_df = generate_signals(sig_input_df, strat_config)
                    signals_by_symbol[sym] = sig_df["signal"]

            # Checkpoint 3: Cancellation check before backtest configuration
            with self._lock:
                if job.status == JobStatus.CANCELLED:
                    return
                job.progress = 55.0

            # 3. Transaction Cost Model Configuration
            if "cost_profile" in params and params["cost_profile"] is not None:
                cost_profile_raw = str(params["cost_profile"]).strip().upper()
            else:
                cost_profile_raw = "DISCOUNT_BROKER_REALISTIC"

            cost_rate = float(params.get("transaction_cost_rate", 0.0001))
            exec_model = str(params.get("execution_model", "next_open"))
            if exec_model not in {"next_open", "same_close"}:
                raise ValueError(f"Invalid execution_model: '{exec_model}'. Supported: 'next_open', 'same_close'.")

            if cost_profile_raw == "LEGACY_LINEAR":
                cost_config = None
                cost_model_meta = {
                    "mode": "LEGACY_LINEAR",
                    "transaction_cost_rate": cost_rate,
                    "description": "Legacy linear turnover multiplier",
                }
            else:
                cost_config = get_cost_config(cost_profile_raw)
                cost_model_meta = {
                    "mode": "CANONICAL",
                    "profile_name": cost_config.name,
                    "description": cost_config.description,
                    "brokerage_rate_pct": cost_config.brokerage_rate_pct,
                    "brokerage_max_per_leg_inr": cost_config.brokerage_max_per_leg_inr,
                    "stt_rate_sell_pct": cost_config.stt_rate_sell_pct,
                    "exchange_charge_rate_pct": cost_config.exchange_charge_rate_pct,
                    "sebi_charge_rate_pct": cost_config.sebi_charge_rate_pct,
                    "stamp_duty_rate_buy_pct": cost_config.stamp_duty_rate_buy_pct,
                    "gst_rate_pct": cost_config.gst_rate_pct,
                    "slippage_rate_pct": cost_config.slippage_rate_pct,
                    "spread_rate_pct": cost_config.spread_rate_pct,
                }
                cost_rate = 0.0

            # 4. Multi-Asset Engine Risk Configuration
            initial_capital = float(params.get("initial_capital", 100_000.0))
            risk_per_trade_pct = float(params.get("risk_per_trade_pct", 0.01))
            max_stock_allocation_pct = float(params.get("max_stock_allocation_pct", 0.35))
            max_portfolio_risk_pct = float(params.get("max_portfolio_risk_pct", 0.03))
            reserve_capital_pct = float(params.get("reserve_capital_pct", 0.15))
            max_leverage = float(params.get("max_leverage", 5.0))
            stop_loss_atr = float(params.get("stop_loss_atr", 1.5))
            take_profit_atr = float(params.get("take_profit_atr", 3.0))
            session_end_time = str(params.get("session_end_time", "15:15"))
            enforce_eod_square_off = bool(params.get("enforce_eod_square_off", True))
            opening_cooldown_minutes = int(params.get("opening_cooldown_minutes", 10))
            market_open_time = str(params.get("market_open_time", "09:15"))
            max_consecutive_missing_bars = int(params.get("max_consecutive_missing_bars", 3))

            capital_protection_floor = params.get("capital_protection_floor")
            if capital_protection_floor is not None:
                capital_protection_floor = float(capital_protection_floor)

            overall_loss_limit = params.get("overall_loss_limit")
            if overall_loss_limit is not None:
                overall_loss_limit = float(overall_loss_limit)

            min_trade_quantity = int(params.get("min_trade_quantity", 1))
            min_free_capital = float(params.get("min_free_capital", 0.0))
            include_estimated_round_trip_costs_in_sizing = bool(
                params.get("include_estimated_round_trip_costs_in_sizing", True)
            )

            expected_timeline = params.get("expected_timeline")
            expected_end_time = params.get("expected_end_time")

            risk_config_meta = {
                "initial_capital": initial_capital,
                "risk_per_trade_pct": risk_per_trade_pct,
                "max_stock_allocation_pct": max_stock_allocation_pct,
                "max_portfolio_risk_pct": max_portfolio_risk_pct,
                "reserve_capital_pct": reserve_capital_pct,
                "max_leverage": max_leverage,
                "stop_loss_atr": stop_loss_atr,
                "take_profit_atr": take_profit_atr,
                "session_end_time": session_end_time,
                "enforce_eod_square_off": enforce_eod_square_off,
                "capital_protection_floor": capital_protection_floor,
                "overall_loss_limit": overall_loss_limit,
                "opening_cooldown_minutes": opening_cooldown_minutes,
                "market_open_time": market_open_time,
                "max_consecutive_missing_bars": max_consecutive_missing_bars,
                "min_trade_quantity": min_trade_quantity,
                "min_free_capital": min_free_capital,
                "include_estimated_round_trip_costs_in_sizing": include_estimated_round_trip_costs_in_sizing,
                "expected_end_time": str(expected_end_time) if expected_end_time else None,
            }

            engine_cfg = MultiAssetEngineConfig(
                initial_capital=initial_capital,
                risk_per_trade_pct=risk_per_trade_pct,
                max_stock_allocation_pct=max_stock_allocation_pct,
                max_portfolio_risk_pct=max_portfolio_risk_pct,
                reserve_capital_pct=reserve_capital_pct,
                max_leverage=max_leverage,
                stop_loss_atr=stop_loss_atr,
                take_profit_atr=take_profit_atr,
                session_end_time=session_end_time,
                enforce_eod_square_off=enforce_eod_square_off,
                execution_model=exec_model,
                capital_protection_floor=capital_protection_floor,
                overall_loss_limit=overall_loss_limit,
                cost_config=cost_config,
                include_estimated_round_trip_costs_in_sizing=include_estimated_round_trip_costs_in_sizing,
                min_trade_quantity=min_trade_quantity,
                min_free_capital=min_free_capital,
                transaction_cost_rate=cost_rate,
                opening_cooldown_minutes=opening_cooldown_minutes,
                market_open_time=market_open_time,
                max_consecutive_missing_bars=max_consecutive_missing_bars,
                expected_timeline=expected_timeline,
                expected_end_time=expected_end_time,
            )

            # Checkpoint 4: Cancellation check before running backtest
            with self._lock:
                if job.status == JobStatus.CANCELLED:
                    return
                job.progress = 75.0

            # 5. Run Synchronized Multi-Asset Backtest
            backtest_result = run_multi_asset_backtest(
                data_by_symbol=data_by_symbol,
                signals_by_symbol=signals_by_symbol,
                config=engine_cfg,
            )

            # Checkpoint 5: Check cancellation before formatting & persisting results
            with self._lock:
                if job.status == JobStatus.CANCELLED:
                    return
                job.progress = 90.0

            # 6. Format and Serialize Results
            metrics = backtest_result.metrics
            portfolio = backtest_result.portfolio

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
                        "symbol": getattr(t, "symbol", "UNKNOWN"),
                        "entry_time": str(t.entry_time),
                        "exit_time": str(t.exit_time),
                        "side": t.position.value if hasattr(t.position, "value") else str(t.position),
                        "entry_price": round(float(t.entry_price), 2),
                        "exit_price": round(float(t.exit_price), 2),
                        "quantity": int(t.quantity),
                        "gross_pnl": round(float(t.gross_pnl), 2),
                        "costs": round(float(t.transaction_cost), 2),
                        "net_pnl": round(float(t.net_pnl), 2),
                        "return_pct": round(float(t.return_pct), 3),
                        "exit_reason": str(t.exit_reason),
                    }
                )

            unresolved_serialized = []
            for pos in backtest_result.unresolved_positions:
                unresolved_serialized.append(
                    {
                        "symbol": pos.symbol,
                        "side": pos.side.value if hasattr(pos.side, "value") else str(pos.side),
                        "entry_time": str(pos.entry_time),
                        "entry_price": round(float(pos.entry_price), 2),
                        "quantity": int(pos.quantity),
                        "current_price": round(float(pos.current_price), 2),
                        "allocated_margin": round(float(pos.allocated_margin), 2),
                        "notional_value": round(float(pos.notional_value), 2),
                        "unrealized_pnl": round(float(pos.unrealized_pnl()), 2),
                        "is_stale": pos.is_stale,
                        "pending_liquidation": pos.pending_liquidation,
                        "pending_liquidation_reason": pos.pending_liquidation_reason,
                    }
                )

            # Per-symbol attribution
            symbol_metrics_serialized: dict[str, Any] = {}
            for s, s_metrics in backtest_result.symbol_metrics.items():
                pos_status = "CLOSED"
                if s in portfolio.open_positions:
                    p = portfolio.open_positions[s]
                    pos_status = "PENDING_LIQUIDATION" if p.pending_liquidation else ("STALE" if p.is_stale else "ACTIVE")
                sm_copy = dict(s_metrics)
                sm_copy["position_status"] = pos_status
                pf_s = sm_copy.get("profit_factor", 0.0)
                if isinstance(pf_s, float) and (math.isinf(pf_s) or math.isnan(pf_s)):
                    sm_copy["profit_factor"] = "inf"
                symbol_metrics_serialized[s] = sm_copy

            stale_symbols_list = [s for s, p in portfolio.open_positions.items() if p.is_stale]
            risk_quality_meta = {
                "active_risk_blockers": dict(backtest_result.active_risk_reasons),
                "stale_symbols": stale_symbols_list,
                "missing_candle_stats": dict(backtest_result.missing_candle_stats),
                "global_feed_outage_events": backtest_result.global_feed_outage_events,
                "indeterminate_valuation_events": backtest_result.indeterminate_valuation_events,
                "stale_price_events": backtest_result.stale_price_events,
                "stale_notional_exposure": round(float(backtest_result.stale_notional_exposure), 2),
                "unresolved_liquidation_exposure": round(float(backtest_result.unresolved_liquidation_exposure), 2),
                "global_outage_detection_status": backtest_result.global_outage_detection_status,
                "expected_timeline_provided": backtest_result.expected_timeline_provided,
            }

            all_indices = [df.index for df in data_by_symbol.values() if not df.empty]
            min_ts = str(min(idx[0] for idx in all_indices)) if all_indices else ""
            max_ts = str(max(idx[-1] for idx in all_indices)) if all_indices else ""
            total_candles_all = sum(len(df) for df in data_by_symbol.values())

            portfolio_summary = {
                "initial_capital": round(float(portfolio.initial_capital), 2),
                "final_equity": round(float(portfolio.equity), 2),
                "realized_net_pnl": round(float(portfolio.total_pnl), 2),
                "unrealized_pnl": round(float(portfolio.unrealized_pnl), 2),
                "total_transaction_costs": round(float(sum(t.transaction_cost for t in backtest_result.trades)), 2),
                "peak_equity": round(float(portfolio.peak_equity), 2),
                "max_drawdown_pct": round(float(portfolio.max_drawdown), 2),
                "total_trades": len(backtest_result.trades),
                "win_rate_pct": round(float(metrics.win_rate_pct), 2),
                "gross_exposure": round(float(portfolio.gross_exposure), 2),
                "available_margin": round(float(portfolio.available_margin), 2),
                "allocated_margin": round(float(portfolio.allocated_margin), 2),
                "is_bankrupt": portfolio.is_bankrupt or (backtest_result.bankruptcy_reason is not None),
                "bankruptcy_reason": backtest_result.bankruptcy_reason,
            }

            formatted_result = {
                "job_id": job.job_id,
                "status": JobStatus.COMPLETED.value,
                "symbols": symbols,
                "date_range": {
                    "start": min_ts,
                    "end": max_ts,
                    "requested_start": start_date,
                    "requested_end": end_date,
                    "total_candles": total_candles_all,
                },
                "execution_model": exec_model,
                "risk_config": risk_config_meta,
                "cost_model": cost_model_meta,
                "portfolio": portfolio_summary,
                "metrics": {
                    "total_trades": metrics.total_trades,
                    "winning_trades": metrics.winning_trades,
                    "losing_trades": metrics.losing_trades,
                    "breakeven_trades": metrics.breakeven_trades,
                    "total_pnl": round(float(metrics.total_pnl), 2),
                    "total_return_pct": round(float(metrics.total_return_pct), 2),
                    "win_rate_pct": round(float(metrics.win_rate_pct), 2),
                    "average_win": round(float(metrics.average_win), 2) if not math.isnan(metrics.average_win) else 0.0,
                    "average_loss": round(float(metrics.average_loss), 2) if not math.isnan(metrics.average_loss) else 0.0,
                    "profit_factor": pf_display,
                    "expectancy": round(float(metrics.expectancy), 2) if not math.isnan(metrics.expectancy) else 0.0,
                    "max_drawdown_pct": round(float(metrics.max_drawdown_pct), 2),
                },
                "symbol_metrics": symbol_metrics_serialized,
                "risk_and_quality": risk_quality_meta,
                "trades": trades_serialized,
                "unresolved_positions": unresolved_serialized,
                "bankruptcy_reason": backtest_result.bankruptcy_reason,
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
