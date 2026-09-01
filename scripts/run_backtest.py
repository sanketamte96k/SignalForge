"""Run the SignalForge strategy on historical NIFTY 50 data."""

from pathlib import Path

import pandas as pd

from src.backtest.engine import run_backtest
from src.backtest.report import build_report
from src.strategy.backtest_strategy import (
    StrategyConfig,
    create_signal_function,
)


DATA_PATH = Path(
    "data/historical/nifty50_1m.csv"
)

INITIAL_CAPITAL = 100_000.0
QUANTITY = 1
TRANSACTION_COST_RATE = 0.0001


def main() -> None:
    """Run and display the historical backtest."""

    print("=" * 60)
    print("SignalForge — Real NIFTY 50 Backtest")
    print("=" * 60)

    # --------------------------------------------------------
    # Load historical data
    # --------------------------------------------------------

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Historical dataset not found: {DATA_PATH}"
        )

    data = pd.read_csv(
        DATA_PATH,
        index_col=0,
        parse_dates=True,
    ).sort_index()

    if data.empty:
        raise ValueError(
            "Historical dataset is empty."
        )

    print()
    print("Dataset:")
    print(
        f"Rows:   {len(data):,}"
    )
    print(
        f"Start:  {data.index.min()}"
    )
    print(
        f"End:    {data.index.max()}"
    )

    # --------------------------------------------------------
    # Strategy configuration
    # --------------------------------------------------------

    strategy_config = StrategyConfig(
        ema_fast_period=20,
        ema_slow_period=50,
        rsi_period=14,
        atr_period=14,
        rvol_period=20,
        minimum_rvol=1.5,
        minimum_atr=0.0,
        use_rvol=False,
    )

    print()
    print("Strategy:")
    print(
        f"EMA:      "
        f"{strategy_config.ema_fast_period} / "
        f"{strategy_config.ema_slow_period}"
    )
    print(
        f"RSI:      "
        f"{strategy_config.rsi_period}"
    )
    print(
        f"ATR:      "
        f"{strategy_config.atr_period}"
    )
    print(
        f"RVOL:     "
        f"{strategy_config.rvol_period}"
    )
    print(
        f"Min RVOL: "
        f"{strategy_config.minimum_rvol}"
    )
    print(
        f"Min ATR:  "
        f"{strategy_config.minimum_atr}"
    )
    print(
        f"Use RVOL: "
        f"{strategy_config.use_rvol}"
    )

    # --------------------------------------------------------
    # Build strategy
    # --------------------------------------------------------

    print()
    print(
        "Preparing multi-timeframe strategy..."
    )

    signal_function = create_signal_function(
        data,
        strategy_config,
    )

    # --------------------------------------------------------
    # Run backtest
    # --------------------------------------------------------

    print(
        "Running backtest..."
    )

    result = run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=INITIAL_CAPITAL,
        quantity=QUANTITY,
        transaction_cost_rate=(
            TRANSACTION_COST_RATE
        ),
    )

    report = build_report(
        result
    )

    print()
    print(
        "Backtest complete."
    )

    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------

    print()
    print("-" * 60)
    print("RESULTS")
    print("-" * 60)

    print(
        f"Initial capital: "
        f"{report.initial_capital:,.2f}"
    )

    print(
        f"Final equity:    "
        f"{report.final_equity:,.2f}"
    )

    print(
        f"Total P&L:       "
        f"{report.total_pnl:,.2f}"
    )

    print(
        f"Return:          "
        f"{report.total_return_pct:.2f}%"
    )

    print(
        f"Trades:          "
        f"{report.total_trades}"
    )

    # --------------------------------------------------------
    # Trade summary
    # --------------------------------------------------------

    if result.trades:

        print()
        print("Trade summary:")

        for number, trade in enumerate(
            result.trades,
            start=1,
        ):

            print(
                f"  Trade {number}: "
                f"{trade.position.value} | "
                f"Entry={trade.entry_price:.2f} "
                f"@ {trade.entry_time} | "
                f"Exit={trade.exit_price:.2f} "
                f"@ {trade.exit_time} | "
                f"Qty={trade.quantity:.2f} | "
                f"Gross P&L={trade.gross_pnl:.2f} | "
                f"Cost={trade.transaction_cost:.2f} | "
                f"Net P&L={trade.net_pnl:.2f} | "
                f"Return={trade.return_pct:.4f}%"
            )

    else:

        print()
        print(
            "No trades were generated."
        )

    # --------------------------------------------------------
    # Performance
    # --------------------------------------------------------

    print()
    print("-" * 60)
    print("PERFORMANCE")
    print("-" * 60)

    print(
        f"Winning trades:   "
        f"{report.winning_trades}"
    )

    print(
        f"Losing trades:    "
        f"{report.losing_trades}"
    )

    print(
        f"Breakeven trades: "
        f"{report.breakeven_trades}"
    )

    print(
        f"Win rate:         "
        f"{report.win_rate_pct:.2f}%"
    )

    print(
        f"Average win:      "
        f"{report.average_win:.2f}"
    )

    print(
        f"Average loss:     "
        f"{report.average_loss:.2f}"
    )

    print(
        f"Profit factor:    "
        f"{report.profit_factor:.2f}"
    )

    print(
        f"Expectancy:       "
        f"{report.expectancy:.2f}"
    )

    print(
        f"Max drawdown:     "
        f"{report.max_drawdown_pct:.2f}%"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()