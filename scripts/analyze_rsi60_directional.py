from __future__ import annotations

import sys
from pathlib import Path

# ================================================================
# PROJECT ROOT
# ================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import pandas as pd

from src.backtest.engine import run_backtest

from src.strategy.backtest_strategy import (
    StrategyConfig,
    _make_cursors,
    calculate_timeframe_indicators,
    signal_result_to_position,
)

from src.signals.signal_engine import (
    Signal,
    generate_signal,
)


# ================================================================
# CONFIGURATION
# ================================================================

DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "historical"
    / "nifty50_1m_signalforge.csv"
)

INITIAL_CAPITAL = 100_000.0
QUANTITY = 1
TRANSACTION_COST_RATE = 0.0001

LONG_RSI_THRESHOLD = 60.0


# ================================================================
# RESEARCH PERIODS
# ================================================================

PERIODS = [
    (
        "DEVELOPMENT (2015-2020)",
        "2015-01-01",
        "2020-12-31 23:59:59",
    ),
    (
        "VALIDATION (2021-2022)",
        "2021-01-01",
        "2022-12-31 23:59:59",
    ),
    (
        "OOS (2023-2024)",
        "2023-01-01",
        "2024-03-31 23:59:59",
    ),
]


# ================================================================
# DATA LOADING
# ================================================================

def load_data() -> pd.DataFrame:
    """Load SignalForge historical research data."""

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Data file not found:\n{DATA_PATH}"
        )

    data = pd.read_csv(
        DATA_PATH,
        index_col=0,
        parse_dates=True,
    ).sort_index()

    if data.empty:
        raise ValueError(
            "Loaded dataset is empty."
        )

    return data


# ================================================================
# STRATEGY CONFIG
# ================================================================

def make_config() -> StrategyConfig:
    """Create the current SignalForge baseline configuration."""

    return StrategyConfig(
        ema_fast_period=20,
        ema_slow_period=50,
        rsi_period=14,
        atr_period=14,
        rvol_period=20,
        minimum_rvol=1.5,
        minimum_atr=0.0,
        use_rvol=False,
    )


# ================================================================
# BUILD TIMEFRAME CURSORS
# ================================================================

def build_cursors(
    data: pd.DataFrame,
    config: StrategyConfig,
):
    """Create the same timeframe cursors used by production."""

    timeframe_data = calculate_timeframe_indicators(
        data,
        config,
    )

    return _make_cursors(
        timeframe_data,
        config.use_rvol,
    )


# ================================================================
# BASELINE SIGNAL FUNCTION
# ================================================================

def build_baseline_signal_function(
    data: pd.DataFrame,
):
    """
    Reproduce the actual SignalForge production signal path.
    """

    config = make_config()

    cursors = build_cursors(
        data,
        config,
    )

    def signal_function(
        row: pd.Series,
        previous_row: pd.Series,
    ):
        timestamp = row.name

        if not isinstance(
            timestamp,
            pd.Timestamp,
        ):
            timestamp = pd.Timestamp(timestamp)

        state_30m = cursors["30m"].update(
            timestamp
        )

        state_15m = cursors["15m"].update(
            timestamp
        )

        state_10m = cursors["10m"].update(
            timestamp
        )

        state_5m = cursors["5m"].update(
            timestamp
        )

        if (
            state_30m is None
            or state_15m is None
            or state_10m is None
            or state_5m is None
        ):
            return None

        result = generate_signal(
            state_30m,
            state_15m,
            state_10m,
            state_5m,
            use_rvol=config.use_rvol,
            minimum_rvol=config.minimum_rvol,
            minimum_atr=config.minimum_atr,
        )

        return signal_result_to_position(
            result
        )

    return signal_function


# ================================================================
# RSI >= 60 CANDIDATE SIGNAL FUNCTION
# ================================================================

def build_rsi60_signal_function(
    data: pd.DataFrame,
):
    """
    Build the production SignalForge signal path and add:

        LONG requires RSI >= 60

    The filter is applied to the same four timeframe RSI values
    used by the strategy.

    SHORT signals are NOT modified.
    """

    config = make_config()

    cursors = build_cursors(
        data,
        config,
    )

    def signal_function(
        row: pd.Series,
        previous_row: pd.Series,
    ):
        timestamp = row.name

        if not isinstance(
            timestamp,
            pd.Timestamp,
        ):
            timestamp = pd.Timestamp(timestamp)

        # --------------------------------------------------------
        # Update timeframe states.
        # --------------------------------------------------------

        state_30m = cursors["30m"].update(
            timestamp
        )

        state_15m = cursors["15m"].update(
            timestamp
        )

        state_10m = cursors["10m"].update(
            timestamp
        )

        state_5m = cursors["5m"].update(
            timestamp
        )

        # --------------------------------------------------------
        # Require all timeframe states.
        # --------------------------------------------------------

        if (
            state_30m is None
            or state_15m is None
            or state_10m is None
            or state_5m is None
        ):
            return None

        # --------------------------------------------------------
        # Run the ORIGINAL SignalForge signal engine.
        # --------------------------------------------------------

        result = generate_signal(
            state_30m,
            state_15m,
            state_10m,
            state_5m,
            use_rvol=config.use_rvol,
            minimum_rvol=config.minimum_rvol,
            minimum_atr=config.minimum_atr,
        )

        # --------------------------------------------------------
        # SHORT:
        #
        # Completely unchanged.
        # --------------------------------------------------------

        if result.signal == Signal.SELL:

            return signal_result_to_position(
                result
            )

        # --------------------------------------------------------
        # NO TRADE:
        # --------------------------------------------------------

        if result.signal != Signal.BUY:
            return None

        # --------------------------------------------------------
        # LONG:
        #
        # RSI >= 60 on ALL FOUR TIMEFRAMES.
        # --------------------------------------------------------

        rsi_values = [
            state_30m.rsi,
            state_15m.rsi,
            state_10m.rsi,
            state_5m.rsi,
        ]

        # --------------------------------------------------------
        # Safety check.
        # --------------------------------------------------------

        if any(
            pd.isna(rsi)
            for rsi in rsi_values
        ):
            return None

        # --------------------------------------------------------
        # Apply LONG RSI filter.
        # --------------------------------------------------------

        if any(
            rsi < LONG_RSI_THRESHOLD
            for rsi in rsi_values
        ):
            return None

        # --------------------------------------------------------
        # LONG passes RSI >= 60.
        # --------------------------------------------------------

        return signal_result_to_position(
            result
        )

    return signal_function


# ================================================================
# RUN ONE PERIOD
# ================================================================

def run_period(
    data: pd.DataFrame,
    period_name: str,
    start: str,
    end: str,
    candidate: bool,
):
    """Run one chronological research period."""

    period_data = data.loc[start:end].copy()

    if period_data.empty:
        raise ValueError(
            f"No data found for {period_name}: "
            f"{start} -> {end}"
        )

    if candidate:

        signal_function = (
            build_rsi60_signal_function(
                period_data
            )
        )

    else:

        signal_function = (
            build_baseline_signal_function(
                period_data
            )
        )

    result = run_backtest(
        period_data,
        signal_function=signal_function,
        initial_capital=INITIAL_CAPITAL,
        quantity=QUANTITY,
        transaction_cost_rate=TRANSACTION_COST_RATE,
    )

    return result


# ================================================================
# SIDE STATISTICS
# ================================================================

def calculate_side_stats(
    trades,
):
    """Calculate LONG/SHORT performance statistics."""

    if not trades:

        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "pnl": 0.0,
            "avg_trade": 0.0,
            "profit_factor": 0.0,
        }

    pnls = [
        trade.net_pnl
        for trade in trades
    ]

    wins = [
        pnl
        for pnl in pnls
        if pnl > 0
    ]

    losses = [
        pnl
        for pnl in pnls
        if pnl < 0
    ]

    gross_profit = sum(wins)

    gross_loss = abs(
        sum(losses)
    )

    if gross_loss == 0:

        if gross_profit > 0:
            profit_factor = float("inf")
        else:
            profit_factor = 0.0

    else:

        profit_factor = (
            gross_profit
            / gross_loss
        )

    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (
            len(wins)
            / len(trades)
            * 100
        ),
        "pnl": sum(pnls),
        "avg_trade": (
            sum(pnls)
            / len(pnls)
        ),
        "profit_factor": profit_factor,
    }


# ================================================================
# SPLIT TRADES BY DIRECTION
# ================================================================

def trade_stats(
    result,
):
    """Split backtest trades into LONG and SHORT."""

    long_trades = [
        trade
        for trade in result.trades
        if trade.position.value == "LONG"
    ]

    short_trades = [
        trade
        for trade in result.trades
        if trade.position.value == "SHORT"
    ]

    return {
        "long": calculate_side_stats(
            long_trades
        ),
        "short": calculate_side_stats(
            short_trades
        ),
    }


# ================================================================
# FORMAT PROFIT FACTOR
# ================================================================

def format_profit_factor(
    value: float,
) -> str:

    if value == float("inf"):
        return "inf"

    return f"{value:.3f}"


# ================================================================
# PRINT SIDE RESULTS
# ================================================================

def print_side_stats(
    period_name: str,
    strategy_name: str,
    result,
):
    """Print directional statistics."""

    stats = trade_stats(
        result
    )

    print()
    print("=" * 80)

    print(
        f"{period_name} | "
        f"{strategy_name}"
    )

    print("=" * 80)

    for side in (
        "long",
        "short",
    ):

        s = stats[side]

        print()
        print(
            side.upper()
        )

        print(
            f"Trades        : "
            f"{s['trades']}"
        )

        print(
            f"Wins          : "
            f"{s['wins']}"
        )

        print(
            f"Losses        : "
            f"{s['losses']}"
        )

        print(
            f"Win rate      : "
            f"{s['win_rate']:.2f}%"
        )

        print(
            f"P&L           : "
            f"{s['pnl']:.2f}"
        )

        print(
            f"Avg trade     : "
            f"{s['avg_trade']:.2f}"
        )

        print(
            f"Profit factor : "
            f"{format_profit_factor(s['profit_factor'])}"
        )


# ================================================================
# COMPARISON
# ================================================================

def print_comparison(
    period_name: str,
    baseline_result,
    candidate_result,
):
    """Compare baseline and RSI >= 60 candidate."""

    baseline = trade_stats(
        baseline_result
    )

    candidate = trade_stats(
        candidate_result
    )

    print()
    print("-" * 80)

    print(
        f"{period_name} | "
        f"RSI >= 60 IMPACT"
    )

    print("-" * 80)

    for side in (
        "long",
        "short",
    ):

        b = baseline[side]
        c = candidate[side]

        print()
        print(
            side.upper()
        )

        # --------------------------------------------------------
        # Trades
        # --------------------------------------------------------

        trade_difference = (
            c["trades"]
            - b["trades"]
        )

        print(
            f"Trades        : "
            f"{b['trades']} -> "
            f"{c['trades']} "
            f"({trade_difference:+d})"
        )

        # --------------------------------------------------------
        # Win rate
        # --------------------------------------------------------

        win_rate_difference = (
            c["win_rate"]
            - b["win_rate"]
        )

        print(
            f"Win rate      : "
            f"{b['win_rate']:.2f}% -> "
            f"{c['win_rate']:.2f}% "
            f"({win_rate_difference:+.2f} pp)"
        )

        # --------------------------------------------------------
        # P&L
        # --------------------------------------------------------

        pnl_difference = (
            c["pnl"]
            - b["pnl"]
        )

        print(
            f"P&L           : "
            f"{b['pnl']:.2f} -> "
            f"{c['pnl']:.2f} "
            f"({pnl_difference:+.2f})"
        )

        # --------------------------------------------------------
        # Average trade
        # --------------------------------------------------------

        avg_difference = (
            c["avg_trade"]
            - b["avg_trade"]
        )

        print(
            f"Avg trade     : "
            f"{b['avg_trade']:.2f} -> "
            f"{c['avg_trade']:.2f} "
            f"({avg_difference:+.2f})"
        )

        # --------------------------------------------------------
        # Profit factor
        # --------------------------------------------------------

        print(
            f"Profit factor : "
            f"{format_profit_factor(b['profit_factor'])} -> "
            f"{format_profit_factor(c['profit_factor'])}"
        )


# ================================================================
# MAIN
# ================================================================

def main():

    print("=" * 80)

    print(
        "SIGNALFORGE — "
        "RSI >= 60 DIRECTIONAL ROBUSTNESS"
    )

    print("=" * 80)

    # ------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------

    print()
    print(
        "Loading data..."
    )

    data = load_data()

    print(
        f"Rows  : "
        f"{len(data):,}"
    )

    print(
        f"Start : "
        f"{data.index.min()}"
    )

    print(
        f"End   : "
        f"{data.index.max()}"
    )

    # ------------------------------------------------------------
    # Run research periods
    # ------------------------------------------------------------

    for (
        period_name,
        start,
        end,
    ) in PERIODS:

        print()
        print("#" * 80)

        print(
            f"# {period_name}"
        )

        print("#" * 80)

        # --------------------------------------------------------
        # BASELINE
        # --------------------------------------------------------

        print()
        print(
            "Running BASELINE..."
        )

        baseline_result = run_period(
            data=data,
            period_name=period_name,
            start=start,
            end=end,
            candidate=False,
        )

        # --------------------------------------------------------
        # RSI >= 60
        # --------------------------------------------------------

        print(
            "Running RSI >= 60 candidate..."
        )

        candidate_result = run_period(
            data=data,
            period_name=period_name,
            start=start,
            end=end,
            candidate=True,
        )

        # --------------------------------------------------------
        # Print detailed results
        # --------------------------------------------------------

        print_side_stats(
            period_name,
            "BASELINE",
            baseline_result,
        )

        print_side_stats(
            period_name,
            "RSI >= 60 CANDIDATE",
            candidate_result,
        )

        # --------------------------------------------------------
        # Print comparison
        # --------------------------------------------------------

        print_comparison(
            period_name,
            baseline_result,
            candidate_result,
        )

    # ------------------------------------------------------------
    # COMPLETE
    # ------------------------------------------------------------

    print()
    print("=" * 80)

    print(
        "ROBUSTNESS TEST COMPLETE"
    )

    print("=" * 80)

    print()
    print(
        "Research questions:"
    )

    print(
        "1. Did RSI >= 60 improve LONG performance?"
    )

    print(
        "2. Did LONG win rate improve?"
    )

    print(
        "3. Did LONG P&L improve?"
    )

    print(
        "4. Did LONG profit factor improve?"
    )

    print(
        "5. Did SHORT performance remain intact?"
    )

    print(
        "6. Did the improvement persist across "
        "Development, Validation and OOS?"
    )

    print()
    print(
        "IMPORTANT: This is robustness evidence, "
        "not proof of future profitability."
    )


# ================================================================
# ENTRY POINT
# ================================================================

if __name__ == "__main__":
    main()