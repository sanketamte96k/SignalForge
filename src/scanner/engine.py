"""Validated stock scanner engine for SignalForge."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.backtest.simulator import Position
from src.signals.signal_engine import SignalResult
from src.strategy.context import CausalStrategyContext
from src.universe.manager import UniverseManager
from src.universe.models import Instrument


@dataclass(frozen=True)
class StockScanResult:
    """Latest scanner state for one stock."""

    symbol: str
    name: str
    exchange: str
    signal: str
    position: str | None
    signal_eligible: bool
    timestamp: pd.Timestamp | None
    price: float | None
    signal_result: SignalResult | None
    reason: str


class StockScannerEngine:
    """
    Generate causal signals for validated instruments only.

    The engine never validates instruments itself. Validation is a
    separate gate owned by the validation/universe layers.
    """

    def __init__(
        self,
        universe: UniverseManager,
    ) -> None:
        if not isinstance(
            universe,
            UniverseManager,
        ):
            raise TypeError(
                "universe must be a UniverseManager."
            )

        self._universe = universe

    def scan(
        self,
        data_by_symbol: dict[str, pd.DataFrame],
    ) -> tuple[StockScanResult, ...]:
        """Scan every instrument in universe order."""

        if not isinstance(
            data_by_symbol,
            dict,
        ):
            raise TypeError(
                "data_by_symbol must be a dictionary."
            )

        results: list[StockScanResult] = []

        for instrument in self._universe.all_instruments():
            data = data_by_symbol.get(
                instrument.symbol
            )

            results.append(
                self._scan_instrument(
                    instrument,
                    data,
                )
            )

        return tuple(results)

    def scan_symbol(
        self,
        symbol: str,
        data: pd.DataFrame | None,
    ) -> StockScanResult:
        """Scan one instrument."""

        instrument = self._universe.get_instrument(
            symbol
        )

        return self._scan_instrument(
            instrument,
            data,
        )

    def _scan_instrument(
        self,
        instrument: Instrument,
        data: pd.DataFrame | None,
    ) -> StockScanResult:
        """Process one instrument according to its eligibility."""

        if not self._universe.is_signal_eligible(
            instrument.symbol
        ):
            return StockScanResult(
                symbol=instrument.symbol,
                name=instrument.name,
                exchange=instrument.exchange,
                signal="NO_TRADE",
                position=None,
                signal_eligible=False,
                timestamp=None,
                price=None,
                signal_result=None,
                reason=(
                    "Stock is not VALIDATED and is blocked "
                    "from signal generation."
                ),
            )

        if data is None:
            return StockScanResult(
                symbol=instrument.symbol,
                name=instrument.name,
                exchange=instrument.exchange,
                signal="NO_TRADE",
                position=None,
                signal_eligible=True,
                timestamp=None,
                price=None,
                signal_result=None,
                reason=(
                    "Stock is VALIDATED, but market data "
                    "is unavailable."
                ),
            )

        if not isinstance(
            data,
            pd.DataFrame,
        ):
            raise TypeError(
                "stock market data must be a pandas DataFrame."
            )

        if data.empty:
            return StockScanResult(
                symbol=instrument.symbol,
                name=instrument.name,
                exchange=instrument.exchange,
                signal="NO_TRADE",
                position=None,
                signal_eligible=True,
                timestamp=None,
                price=None,
                signal_result=None,
                reason=(
                    "Stock is VALIDATED, but market data "
                    "is empty."
                ),
            )

        context = CausalStrategyContext()

        latest_timestamp: pd.Timestamp | None = None
        latest_price: float | None = None
        latest_position: Position | None = None

        for timestamp, candle in data.iterrows():
            candle = candle.copy()
            candle.name = timestamp

            result = context.process_candle(
                candle
            )

            latest_timestamp = pd.Timestamp(
                timestamp
            )
            latest_price = float(
                candle["close"]
            )
            latest_position = result.position

        signal_result = context.last_signal_result

        if latest_position == Position.LONG:
            signal = "BUY"
        elif latest_position == Position.SHORT:
            signal = "SELL"
        else:
            signal = "NO_TRADE"

        reason = (
            signal_result.reason
            if signal_result is not None
            else (
                "Strategy warm-up incomplete or "
                "no actionable signal."
            )
        )

        return StockScanResult(
            symbol=instrument.symbol,
            name=instrument.name,
            exchange=instrument.exchange,
            signal=signal,
            position=(
                latest_position.value
                if latest_position is not None
                else None
            ),
            signal_eligible=True,
            timestamp=latest_timestamp,
            price=latest_price,
            signal_result=signal_result,
            reason=reason,
        )
