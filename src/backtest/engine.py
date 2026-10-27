from dataclasses import dataclass
from datetime import time
from typing import Callable

import numpy as np
import pandas as pd

from src.backtest.metrics import (
    PerformanceMetrics,
    calculate_metrics,
)
from src.backtest.portfolio import Portfolio
from src.backtest.simulator import (
    Position,
    Trade,
    simulate_trade,
)


@dataclass(frozen=True)
class BacktestResult:
    """Complete result returned by the backtest engine."""

    trades: list[Trade]
    portfolio: Portfolio
    metrics: PerformanceMetrics
    bankruptcy_reason: str | None = None


SignalFunction = Callable[
    [pd.Series, pd.Series],
    Position | None,
]


def _validate_data(
    data: pd.DataFrame,
) -> None:
    """Validate basic backtest input."""

    if not isinstance(data, pd.DataFrame):
        raise TypeError(
            "data must be a pandas DataFrame."
        )

    if data.empty:
        raise ValueError(
            "data cannot be empty."
        )

    required_columns = {
        "close",
    }

    missing_columns = (
        required_columns
        - set(data.columns)
    )

    if missing_columns:
        raise ValueError(
            f"Missing required columns: "
            f"{sorted(missing_columns)}"
        )

    if not isinstance(
        data.index,
        pd.DatetimeIndex,
    ):
        raise TypeError(
            "data index must be a "
            "pandas DatetimeIndex."
        )

    if data.index.has_duplicates:
        raise ValueError(
            "data index cannot contain duplicates."
        )

    if not data.index.is_monotonic_increasing:
        raise ValueError(
            "data index must be sorted."
        )

    if data["close"].isna().any():
        raise ValueError(
            "close cannot contain missing values."
        )


def _validate_capital(
    initial_capital: float,
) -> None:
    """Validate initial capital."""

    if not isinstance(
        initial_capital,
        (int, float),
    ):
        raise TypeError(
            "initial_capital must be numeric."
        )

    if isinstance(
        initial_capital,
        bool,
    ):
        raise TypeError(
            "initial_capital must be numeric."
        )

    if initial_capital <= 0:
        raise ValueError(
            "initial_capital must be greater than zero."
        )


def _validate_quantity(
    quantity: int,
) -> None:
    """Validate trade quantity."""

    if not isinstance(
        quantity,
        int,
    ) or isinstance(quantity, bool):
        raise TypeError(
            "quantity must be an integer."
        )

    if quantity <= 0:
        raise ValueError(
            "quantity must be greater than zero."
        )


def _close_position(
    portfolio: Portfolio,
    trades: list[Trade],
    position: Position,
    entry_time: pd.Timestamp,
    entry_price: float,
    exit_time: pd.Timestamp,
    exit_price: float,
    quantity: int,
    transaction_cost_rate: float,
) -> None:
    """Close an open position and record the completed trade."""

    trade = simulate_trade(
        position=position,
        entry_time=entry_time,
        exit_time=exit_time,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        transaction_cost_rate=transaction_cost_rate,
    )

    portfolio.apply_trade(trade)

    trades.append(trade)


def run_backtest(
    data: pd.DataFrame,
    signal_function: SignalFunction,
    initial_capital: float,
    quantity: int = 1,
    transaction_cost_rate: float = 0.0,
    execution_model: str = "same_close",
) -> BacktestResult:
    """
    Run a sequential intraday backtest.

    The signal function is called once per row.

    Execution models:
    - "same_close": Legacy backtest contract. A signal opens/closes a position
      using the current candle close.
    - "next_open": Causal next-available execution contract. A signal produced at
      candle t close executes at candle t+1 open (or next available bar), guarding
      against session rollover and data gaps.

    Positions are never carried overnight across session boundaries.
    Any position still open at the final candle is closed using the final close.
    """

    if execution_model not in ("same_close", "next_open"):
        raise ValueError(
            f"Unsupported execution_model: {execution_model}. "
            "Supported models: 'same_close', 'next_open'"
        )

    _validate_data(data)

    _validate_capital(
        initial_capital
    )

    _validate_quantity(
        quantity
    )

    if not callable(signal_function):
        raise TypeError(
            "signal_function must be callable."
        )

    portfolio = Portfolio(
        initial_capital=initial_capital
    )

    trades: list[Trade] = []

    current_position: Position | None = None
    entry_time: pd.Timestamp | None = None
    entry_price: float | None = None
    pending_signal: Position | None = None

    for index in range(len(data)):

        row = data.iloc[index]

        if index == 0:
            previous_row = row
        else:
            previous_row = data.iloc[index - 1]

        current_time = data.index[index]
        current_price = float(
            row["close"]
        )

        # ----------------------------------------------------
        # Session boundary handling
        # ----------------------------------------------------
        #
        # If the current timestamp belongs to a new
        # calendar session, close the previous position
        # at the previous candle's close before processing
        # the current candle.
        #
        # This prevents overnight positions.
        # ----------------------------------------------------

        if (
            index > 0
            and current_time.date()
            != data.index[index - 1].date()
        ):
            if current_position is not None:
                previous_time = data.index[index - 1]
                previous_price = float(
                    data.iloc[index - 1]["close"]
                )

                _close_position(
                    portfolio=portfolio,
                    trades=trades,
                    position=current_position,
                    entry_time=entry_time,
                    entry_price=entry_price,
                    exit_time=previous_time,
                    exit_price=previous_price,
                    quantity=quantity,
                    transaction_cost_rate=(
                        transaction_cost_rate
                    ),
                )

                current_position = None
                entry_time = None
                entry_price = None

            pending_signal = None

        if execution_model == "next_open":
            # Execute pending signal from candle t-1 at candle t open
            if pending_signal is not None:
                fill_price = (
                    float(row["open"])
                    if "open" in data.columns
                    else current_price
                )
                if current_position is None:
                    current_position = pending_signal
                    entry_time = current_time
                    entry_price = fill_price
                elif pending_signal != current_position:
                    _close_position(
                        portfolio=portfolio,
                        trades=trades,
                        position=current_position,
                        entry_time=entry_time,
                        entry_price=entry_price,
                        exit_time=current_time,
                        exit_price=fill_price,
                        quantity=quantity,
                        transaction_cost_rate=transaction_cost_rate,
                    )
                    current_position = pending_signal
                    entry_time = current_time
                    entry_price = fill_price
                pending_signal = None

            # Generate signal at candle close
            signal = signal_function(
                row,
                previous_row,
            )

            if signal is not None and not isinstance(
                signal,
                Position,
            ):
                raise TypeError(
                    "signal_function must return "
                    "Position or None."
                )

            if signal is not None and signal != current_position:
                pending_signal = signal

            continue

        # ----------------------------------------------------
        # Generate signal (same_close legacy contract)
        # ----------------------------------------------------

        signal = signal_function(
            row,
            previous_row,
        )

        if signal is not None and not isinstance(
            signal,
            Position,
        ):
            raise TypeError(
                "signal_function must return "
                "Position or None."
            )

        # ----------------------------------------------------
        # No current position
        # ----------------------------------------------------

        if current_position is None:

            if signal is None:
                continue

            current_position = signal
            entry_time = current_time
            entry_price = current_price

            continue

        # ----------------------------------------------------
        # Existing position
        # ----------------------------------------------------

        if signal is None:
            continue

        if signal == current_position:
            continue

        # ----------------------------------------------------
        # Opposite signal:
        # close current position first.
        # ----------------------------------------------------

        _close_position(
            portfolio=portfolio,
            trades=trades,
            position=current_position,
            entry_time=entry_time,
            entry_price=entry_price,
            exit_time=current_time,
            exit_price=current_price,
            quantity=quantity,
            transaction_cost_rate=(
                transaction_cost_rate
            ),
        )

        # ----------------------------------------------------
        # Immediately reverse into new position.
        # ----------------------------------------------------

        current_position = signal
        entry_time = current_time
        entry_price = current_price

    # --------------------------------------------------------
    # Close any remaining open position.
    # --------------------------------------------------------

    if current_position is not None:

        final_time = data.index[-1]
        final_price = float(
            data.iloc[-1]["close"]
        )

        _close_position(
            portfolio=portfolio,
            trades=trades,
            position=current_position,
            entry_time=entry_time,
            entry_price=entry_price,
            exit_time=final_time,
            exit_price=final_price,
            quantity=quantity,
            transaction_cost_rate=(
                transaction_cost_rate
            ),
        )

    metrics = calculate_metrics(
        trades=trades,
        initial_capital=initial_capital,
        max_drawdown_pct=(
            portfolio.max_drawdown
        ),
    )

    return BacktestResult(
        trades=trades,
        portfolio=portfolio,
        metrics=metrics,
    )


# ============================================================
# PRODUCTION INTRADAY EXECUTION ENGINE
# ============================================================

@dataclass(frozen=True)
class IntradayEngineConfig:
    """Configuration for production intraday backtesting."""

    initial_capital: float = 100000.0
    risk_per_trade: float = 0.01
    max_leverage: float = 5.0
    stop_atr_multiplier: float = 1.5
    target_atr_multiplier: float = 3.0
    brokerage_per_trade: float = 20.0
    slippage_rate: float = 0.0005
    statutory_fee_rate: float = 0.0
    session_end_time: str = "15:29"
    enforce_eod_square_off: bool = True
    gap_execution: bool = True
    conservative_same_candle: bool = True
    execution_model: str = "next_open"


def run_intraday_backtest(
    data: pd.DataFrame,
    signal_generator: Callable,
    config: IntradayEngineConfig | None = None,
) -> BacktestResult:
    """
    Run a risk-bounded, session-aware production intraday backtest.

    Key guarantees:
    - Zero overnight positions: enforced EOD square-off at session_end_time.
    - Risk-bounded position sizing: quantity = min(risk_quantity, leverage_quantity).
    - Maximum leverage cap: notional exposure capped at capital * max_leverage.
    - Realistic gap execution: fills at open if market gaps through stop/target.
    - Deterministic same-candle resolution: STOP is evaluated before TARGET.
    - Transparent turnover-based transaction costs: slippage + brokerage + statutory fees.
    - Bankruptcy protection: stops trading if capital <= 0 with explicit reason.
    """

    if config is None:
        config = IntradayEngineConfig()

    _validate_capital(config.initial_capital)

    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame.")

    if data.empty:
        raise ValueError("data cannot be empty.")

    df = data.copy()

    # Normalize datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date", drop=False)
        else:
            raise TypeError("data must have DatetimeIndex or Date column.")
    else:
        df["Date"] = df.index

    # Case-insensitive column resolution
    col_map = {str(c).lower(): c for c in df.columns}
    for standard in ("open", "high", "low", "close", "volume"):
        if standard not in col_map:
            raise ValueError(f"Missing required column: {standard}")

    df["Open"] = df[col_map["open"]].astype(float)
    df["High"] = df[col_map["high"]].astype(float)
    df["Low"] = df[col_map["low"]].astype(float)
    df["Close"] = df[col_map["close"]].astype(float)
    df["Volume"] = df[col_map["volume"]].astype(float)

    # Ensure ATR column exists
    if "atr" in col_map:
        df["ATR"] = df[col_map["atr"]].astype(float)
    elif "ATR" not in df.columns:
        prev_close = df["Close"].shift(1)
        tr1 = df["High"] - df["Low"]
        tr2 = (df["High"] - prev_close).abs()
        tr3 = (df["Low"] - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(14).mean()

    capital = float(config.initial_capital)
    portfolio = Portfolio(initial_capital=config.initial_capital)
    trades: list[Trade] = []
    position: dict | None = None
    bankruptcy_reason: str | None = None

    session_end_t = pd.Timestamp(config.session_end_time).time()

    # Pre-extract arrays for blazing-fast execution
    dates_raw = pd.to_datetime(df["Date"]).dt.to_pydatetime()
    opens = df["Open"].to_numpy(dtype=float)
    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    closes = df["Close"].to_numpy(dtype=float)
    atrs = df["ATR"].to_numpy(dtype=float)

    # If signals are precomputed (array/Series/list), index directly
    precomputed_signals = None
    if isinstance(signal_generator, (pd.Series, np.ndarray, list)):
        precomputed_signals = signal_generator

    call_by_rows = False
    if precomputed_signals is None and callable(signal_generator):
        try:
            signal_generator(df, 1)
        except (TypeError, AttributeError):
            call_by_rows = True

    n_bars = len(df)

    for i in range(1, n_bars):
        current_time = dates_raw[i]
        prev_time = dates_raw[i - 1]

        current_date = current_time.date()
        prev_date = prev_time.date()

        bar_open = opens[i]
        bar_high = highs[i]
        bar_low = lows[i]
        bar_close = closes[i]

        prev_bar_close = closes[i - 1]

        # ----------------------------------------------------
        # 1. SESSION BOUNDARY ENFORCEMENT
        # ----------------------------------------------------
        # If date rolled over, force close open position at prev Close
        if current_date != prev_date and position is not None:
            exit_price = prev_bar_close
            trade = simulate_trade(
                position=Position(position["side"]),
                entry_time=position["entry_time"],
                exit_time=prev_time,
                entry_price=position["entry_price"],
                exit_price=exit_price,
                quantity=position["quantity"],
                brokerage=config.brokerage_per_trade,
                slippage_rate=config.slippage_rate,
                statutory_fee_rate=config.statutory_fee_rate,
                exit_reason="EOD",
                capital_before=position["capital_before"],
                capital_after=capital,
                risk_amount=position["risk_amount"],
                atr=position["atr"],
                stop_distance=position["stop_distance"],
                risk_based_quantity=position["risk_based_quantity"],
                max_allowed_quantity=position["max_allowed_quantity"],
            )
            capital += trade.net_pnl
            portfolio.apply_trade(trade)
            trades.append(trade)
            position = None

        # ----------------------------------------------------
        # 2. MANAGE EXISTING POSITION
        # ----------------------------------------------------
        if position is not None:
            side = position["side"]
            entry_p = position["entry_price"]
            stop_p = position["stop_price"]
            target_p = position["target_price"]

            exit_price = None
            exit_reason = None

            if side == "LONG":
                # A. Gap down through stop at Open
                if config.gap_execution and bar_open <= stop_p:
                    exit_price = bar_open
                    exit_reason = "STOP"
                # B. Same-candle hit: both stop and target touched
                elif bar_low <= stop_p and bar_high >= target_p:
                    if config.conservative_same_candle:
                        exit_price = stop_p
                        exit_reason = "STOP"
                    else:
                        exit_price = target_p
                        exit_reason = "TARGET"
                # C. Intrabar stop hit
                elif bar_low <= stop_p:
                    exit_price = stop_p
                    exit_reason = "STOP"
                # D. Gap up through target at Open
                elif config.gap_execution and bar_open >= target_p:
                    exit_price = bar_open
                    exit_reason = "TARGET"
                # E. Intrabar target hit
                elif bar_high >= target_p:
                    exit_price = target_p
                    exit_reason = "TARGET"

            elif side == "SHORT":
                # A. Gap up through stop at Open
                if config.gap_execution and bar_open >= stop_p:
                    exit_price = bar_open
                    exit_reason = "STOP"
                # B. Same-candle hit
                elif bar_high >= stop_p and bar_low <= target_p:
                    if config.conservative_same_candle:
                        exit_price = stop_p
                        exit_reason = "STOP"
                    else:
                        exit_price = target_p
                        exit_reason = "TARGET"
                # C. Intrabar stop hit
                elif bar_high >= stop_p:
                    exit_price = stop_p
                    exit_reason = "STOP"
                # D. Gap down through target at Open
                elif config.gap_execution and bar_open <= target_p:
                    exit_price = bar_open
                    exit_reason = "TARGET"
                # E. Intrabar target hit
                elif bar_low <= target_p:
                    exit_price = target_p
                    exit_reason = "TARGET"

            # F. End of Day Square-Off if neither stop nor target hit
            if (
                exit_price is None
                and config.enforce_eod_square_off
                and current_time.time() >= session_end_t
            ):
                exit_price = bar_close
                exit_reason = "EOD"

            # Execute exit
            if exit_price is not None:
                trade = simulate_trade(
                    position=Position(side),
                    entry_time=position["entry_time"],
                    exit_time=current_time,
                    entry_price=entry_p,
                    exit_price=exit_price,
                    quantity=position["quantity"],
                    brokerage=config.brokerage_per_trade,
                    slippage_rate=config.slippage_rate,
                    statutory_fee_rate=config.statutory_fee_rate,
                    exit_reason=exit_reason,
                    capital_before=position["capital_before"],
                    capital_after=capital,
                    risk_amount=position["risk_amount"],
                    atr=position["atr"],
                    stop_distance=position["stop_distance"],
                    risk_based_quantity=position["risk_based_quantity"],
                    max_allowed_quantity=position["max_allowed_quantity"],
                )
                capital += trade.net_pnl
                portfolio.apply_trade(trade)
                trades.append(trade)
                position = None

                # Check bankruptcy
                if capital <= 0:
                    bankruptcy_reason = (
                        f"BANKRUPTCY: Capital dropped to {capital:.2f} at {current_time}"
                    )
                    break
                continue

        # ----------------------------------------------------
        # 3. OPEN NEW POSITION
        # ----------------------------------------------------
        if position is None and capital > 0:
            # Do not enter at or after session end time
            if config.enforce_eod_square_off and current_time.time() >= session_end_t:
                continue

            if precomputed_signals is not None:
                sig = precomputed_signals[i]
            elif call_by_rows:
                sig = signal_generator(df.iloc[i], df.iloc[i - 1])
            else:
                try:
                    sig = signal_generator(df, i)
                except (TypeError, AttributeError):
                    sig = signal_generator(df.iloc[i], df.iloc[i - 1])

            if sig is None:
                continue

            if isinstance(sig, Position):
                side = sig.value
            elif isinstance(sig, str):
                side = sig.upper()
            else:
                continue

            if side not in ("LONG", "SHORT"):
                continue

            atr = atrs[i]
            if pd.isna(atr) or atr <= 0:
                continue

            entry_p = bar_close
            if entry_p <= 0:
                continue

            # Position Sizing
            risk_amount = capital * config.risk_per_trade
            stop_dist = atr * config.stop_atr_multiplier
            if stop_dist <= 0:
                continue

            risk_qty = int(risk_amount / stop_dist)
            max_notional = capital * config.max_leverage
            max_allowed_qty = int(max_notional / entry_p)

            final_qty = min(risk_qty, max_allowed_qty)
            if final_qty <= 0:
                continue

            if side == "LONG":
                stop_p = entry_p - stop_dist
                target_p = entry_p + (atr * config.target_atr_multiplier)
            else:
                stop_p = entry_p + stop_dist
                target_p = entry_p - (atr * config.target_atr_multiplier)

            position = {
                "side": side,
                "entry_time": current_time,
                "entry_price": entry_p,
                "stop_price": stop_p,
                "target_price": target_p,
                "quantity": final_qty,
                "capital_before": capital,
                "risk_amount": risk_amount,
                "atr": atr,
                "stop_distance": stop_dist,
                "risk_based_quantity": risk_qty,
                "max_allowed_quantity": max_allowed_qty,
            }

    # --------------------------------------------------------
    # 4. FINAL DATASET CLOSE
    # --------------------------------------------------------
    if position is not None:
        last_row = df.iloc[-1]
        exit_price = float(last_row["Close"])
        exit_time = last_row["Date"]
        trade = simulate_trade(
            position=Position(position["side"]),
            entry_time=position["entry_time"],
            exit_time=exit_time,
            entry_price=position["entry_price"],
            exit_price=exit_price,
            quantity=position["quantity"],
            brokerage=config.brokerage_per_trade,
            slippage_rate=config.slippage_rate,
            statutory_fee_rate=config.statutory_fee_rate,
            exit_reason="EOD",
            capital_before=position["capital_before"],
            capital_after=capital,
            risk_amount=position["risk_amount"],
            atr=position["atr"],
            stop_distance=position["stop_distance"],
            risk_based_quantity=position["risk_based_quantity"],
            max_allowed_quantity=position["max_allowed_quantity"],
        )
        capital += trade.net_pnl
        portfolio.apply_trade(trade)
        trades.append(trade)

    metrics = calculate_metrics(
        trades=trades,
        initial_capital=config.initial_capital,
        max_drawdown_pct=portfolio.max_drawdown,
    )

    return BacktestResult(
        trades=trades,
        portfolio=portfolio,
        metrics=metrics,
        bankruptcy_reason=bankruptcy_reason,
    )