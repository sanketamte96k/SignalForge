from __future__ import annotations

from dataclasses import dataclass

from src.paper_trading.models import PaperTradingState


@dataclass(frozen=True)
class PaperTradingReport:
    """Immutable performance summary for a paper-trading session."""

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

    @property
    def net_return_pct(self) -> float:
        """Return percentage based on starting capital."""

        if self.starting_capital <= 0:
            return 0.0

        return (
            self.realized_pnl
            / self.starting_capital
        ) * 100.0

    @property
    def win_rate_pct(self) -> float:
        """Percentage of completed trades that were profitable."""

        if self.trade_count == 0:
            return 0.0

        return (
            self.winning_trades
            / self.trade_count
        ) * 100.0

    @property
    def profit_factor(self) -> float:
        """
        Gross profit divided by absolute gross loss.

        Returns 0 when there is no gross loss.
        """

        if self.gross_loss >= 0:
            if self.gross_profit > 0:
                return float("inf")

            return 0.0

        return (
            self.gross_profit
            / abs(self.gross_loss)
        )


def create_paper_trading_report(
    state: PaperTradingState,
) -> PaperTradingReport:
    """Create a performance report from paper-trading state."""

    if state.starting_capital <= 0:
        raise ValueError(
            "starting_capital must be positive."
        )

    trades = state.completed_trades

    winning_trades = sum(
        1
        for trade in trades
        if trade.net_pnl > 0
    )

    losing_trades = sum(
        1
        for trade in trades
        if trade.net_pnl < 0
    )

    gross_profit = sum(
        trade.net_pnl
        for trade in trades
        if trade.net_pnl > 0
    )

    gross_loss = sum(
        trade.net_pnl
        for trade in trades
        if trade.net_pnl < 0
    )

    long_trades = sum(
        1
        for trade in trades
        if trade.position.name == "LONG"
    )

    short_trades = sum(
        1
        for trade in trades
        if trade.position.name == "SHORT"
    )

    return PaperTradingReport(
        starting_capital=state.starting_capital,
        ending_equity=state.current_equity,
        realized_pnl=state.realized_pnl,
        total_transaction_cost=state.total_transaction_cost,
        trade_count=len(trades),
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        long_trades=long_trades,
        short_trades=short_trades,
    )