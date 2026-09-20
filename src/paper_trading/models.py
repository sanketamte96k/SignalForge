from dataclasses import dataclass
from datetime import datetime

from src.backtest.simulator import Position


@dataclass(frozen=True)
class PaperOrder:
    timestamp: datetime
    position: Position
    price: float
    quantity: int
    reason: str = ""


@dataclass
class PaperPosition:
    position: Position
    entry_price: float
    entry_time: datetime
    quantity: int

    @property
    def is_long(self) -> bool:
        return self.position == Position.LONG

    @property
    def is_short(self) -> bool:
        return self.position == Position.SHORT


@dataclass(frozen=True)
class PaperTrade:
    position: Position
    entry_price: float
    exit_price: float
    quantity: int
    entry_time: datetime
    exit_time: datetime
    gross_pnl: float
    transaction_cost: float
    net_pnl: float
    reason: str = ""

    @property
    def return_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0

        if self.position == Position.LONG:
            return (
                (self.exit_price - self.entry_price)
                / self.entry_price
            ) * 100

        return (
            (self.entry_price - self.exit_price)
            / self.entry_price
        ) * 100


@dataclass
class PaperTradingState:
    starting_capital: float
    realized_pnl: float = 0.0
    total_transaction_cost: float = 0.0
    open_position: PaperPosition | None = None
    completed_trades: list[PaperTrade] | None = None

    def __post_init__(self) -> None:
        if self.completed_trades is None:
            self.completed_trades = []

    @property
    def current_equity(self) -> float:
        return self.starting_capital + self.realized_pnl

    @property
    def trade_count(self) -> int:
        return len(self.completed_trades)

    @property
    def has_position(self) -> bool:
        return self.open_position is not None
