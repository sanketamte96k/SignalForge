"""Portfolio management for SignalForge backtesting."""

from dataclasses import dataclass, field

from src.backtest.simulator import Trade


@dataclass
class Portfolio:
    """
    Manage account capital and completed trades.

    Parameters
    ----------
    initial_capital:
        Starting account capital.

    Attributes
    ----------
    cash:
        Current account equity after completed trades.

    peak_equity:
        Highest equity reached so far.

    max_drawdown:
        Largest percentage drawdown observed.

    trades:
        Completed trades applied to the portfolio.
    """

    initial_capital: float

    cash: float = field(init=False)

    peak_equity: float = field(init=False)

    max_drawdown: float = field(init=False)

    trades: list[Trade] = field(
        default_factory=list,
        init=False,
    )

    def __post_init__(self) -> None:
        """Validate and initialize portfolio state."""

        if not isinstance(
            self.initial_capital,
            (int, float),
        ):
            raise TypeError(
                "initial_capital must be numeric."
            )

        if self.initial_capital <= 0:
            raise ValueError(
                "initial_capital must be greater than zero."
            )

        self.cash = float(
            self.initial_capital
        )

        self.peak_equity = float(
            self.initial_capital
        )

        self.max_drawdown = 0.0

    @property
    def equity(self) -> float:
        """Return current portfolio equity."""

        return self.cash

    @property
    def total_pnl(self) -> float:
        """Return total net P&L from all completed trades."""

        return sum(
            trade.net_pnl
            for trade in self.trades
        )

    @property
    def total_return_pct(self) -> float:
        """Return total portfolio return percentage."""

        return (
            (self.equity - self.initial_capital)
            / self.initial_capital
        ) * 100

    @property
    def trade_count(self) -> int:
        """Return number of completed trades."""

        return len(self.trades)

    def apply_trade(
        self,
        trade: Trade,
    ) -> None:
        """
        Apply a completed trade to the portfolio.

        Only the trade's net P&L changes account equity.

        The trade itself is stored in the portfolio history.
        """

        if not isinstance(trade, Trade):
            raise TypeError(
                "trade must be a Trade."
            )

        new_equity = (
            self.cash + trade.net_pnl
        )

        if new_equity < 0:
            raise ValueError(
                "Trade would reduce portfolio "
                "equity below zero."
            )

        self.cash = new_equity

        self.trades.append(trade)

        if self.equity > self.peak_equity:
            self.peak_equity = self.equity

        if self.peak_equity > 0:
            drawdown = (
                (
                    self.peak_equity
                    - self.equity
                )
                / self.peak_equity
            ) * 100
        else:
            drawdown = 0.0

        self.max_drawdown = max(
            self.max_drawdown,
            drawdown,
        )

    def reset(self) -> None:
        """Reset the portfolio to its initial state."""

        self.cash = float(
            self.initial_capital
        )

        self.peak_equity = float(
            self.initial_capital
        )

        self.max_drawdown = 0.0

        self.trades.clear()