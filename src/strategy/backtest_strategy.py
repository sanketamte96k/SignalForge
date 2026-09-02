"""Historical-data strategy adapter for SignalForge."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.backtest.simulator import Position
from src.data.resampler import resample_ohlcv
from src.indicators.indicators import (
    calculate_atr,
    calculate_ema,
    calculate_rsi,
    calculate_rvol,
)
from src.signals.signal_engine import (
    Signal,
    SignalResult,
    TimeframeState,
    generate_signal,
)


@dataclass(frozen=True)
class StrategyConfig:
    """Configuration for the frozen SignalForge strategy."""

    ema_fast_period: int = 20
    ema_slow_period: int = 50
    rsi_period: int = 14
    atr_period: int = 14
    rvol_period: int = 20

    minimum_rvol: float = 1.5
    minimum_atr: float = 0.0

    # Locked research-validated LONG filter.
    minimum_long_rsi: float = 60.0

    use_rvol: bool = True


TIMEFRAMES = (
    "5m",
    "10m",
    "15m",
    "30m",
)


def _validate_config(config: StrategyConfig) -> None:
    """Validate strategy configuration."""

    if not isinstance(config, StrategyConfig):
        raise TypeError("config must be a StrategyConfig.")

    periods = {
        "ema_fast_period": config.ema_fast_period,
        "ema_slow_period": config.ema_slow_period,
        "rsi_period": config.rsi_period,
        "atr_period": config.atr_period,
        "rvol_period": config.rvol_period,
    }

    for name, value in periods.items():
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{name} must be an integer.")
        if value <= 0:
            raise ValueError(f"{name} must be greater than zero.")

    if config.ema_fast_period >= config.ema_slow_period:
        raise ValueError(
            "ema_fast_period must be less than ema_slow_period."
        )

    if not isinstance(config.minimum_rvol, (int, float)) or isinstance(
        config.minimum_rvol, bool
    ):
        raise TypeError("minimum_rvol must be numeric.")

    if config.minimum_rvol < 0:
        raise ValueError("minimum_rvol cannot be negative.")

    if not isinstance(config.minimum_atr, (int, float)) or isinstance(
        config.minimum_atr, bool
    ):
        raise TypeError("minimum_atr must be numeric.")

    if config.minimum_atr < 0:
        raise ValueError("minimum_atr cannot be negative.")

    if not isinstance(config.minimum_long_rsi, (int, float)) or isinstance(
        config.minimum_long_rsi, bool
    ):
        raise TypeError("minimum_long_rsi must be numeric.")

    if not 0 <= config.minimum_long_rsi <= 100:
        raise ValueError(
            "minimum_long_rsi must be between 0 and 100."
        )

    if not isinstance(config.use_rvol, bool):
        raise TypeError("use_rvol must be a boolean.")


def _validate_market_data(data: pd.DataFrame) -> None:
    """Validate input OHLCV data."""

    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame.")

    if data.empty:
        raise ValueError("data cannot be empty.")

    required_columns = {
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing = sorted(required_columns.difference(data.columns))

    if missing:
        raise ValueError(
            "data is missing required columns: "
            f"{missing}"
        )

    if not isinstance(data.index, pd.DatetimeIndex):
        raise TypeError("data index must be a DatetimeIndex.")

    if data.index.has_duplicates:
        raise ValueError("data index cannot contain duplicates.")

    if not data.index.is_monotonic_increasing:
        raise ValueError("data index must be sorted.")


def _has_usable_volume(data: pd.DataFrame) -> bool:
    """Return whether the dataset contains usable volume."""

    return bool((data["volume"] > 0).any())


def _disable_rvol_if_unavailable(
    data: pd.DataFrame,
    config: StrategyConfig,
) -> StrategyConfig:
    """Disable RVOL automatically when source volume is unavailable."""

    if config.use_rvol and not _has_usable_volume(data):
        return StrategyConfig(
            ema_fast_period=config.ema_fast_period,
            ema_slow_period=config.ema_slow_period,
            rsi_period=config.rsi_period,
            atr_period=config.atr_period,
            rvol_period=config.rvol_period,
            minimum_rvol=config.minimum_rvol,
            minimum_atr=config.minimum_atr,
            minimum_long_rsi=config.minimum_long_rsi,
            use_rvol=False,
        )

    return config


def calculate_timeframe_indicators(
    data: pd.DataFrame,
    config: StrategyConfig | None = None,
) -> dict[str, pd.DataFrame]:
    """Build all SignalForge timeframes with indicators."""

    if config is None:
        config = StrategyConfig()

    _validate_config(config)
    _validate_market_data(data)

    result: dict[str, pd.DataFrame] = {}

    for timeframe in TIMEFRAMES:
        frame = resample_ohlcv(data, timeframe).copy()

        frame["ema20"] = calculate_ema(
            frame["close"],
            config.ema_fast_period,
        )

        frame["ema50"] = calculate_ema(
            frame["close"],
            config.ema_slow_period,
        )

        frame["rsi"] = calculate_rsi(
            frame["close"],
            config.rsi_period,
        )

        frame["atr"] = calculate_atr(
            frame["high"],
            frame["low"],
            frame["close"],
            config.atr_period,
        )

        frame["rvol"] = calculate_rvol(
            frame["volume"],
            config.rvol_period,
        )

        result[timeframe] = frame

    return result


def _row_to_state(
    frame: pd.DataFrame,
    position: int,
    use_rvol: bool,
) -> TimeframeState | None:
    """Convert a preselected completed candle into TimeframeState."""

    if position < 0 or position >= len(frame):
        return None

    row = frame.iloc[position]

    close = row["close"]
    ema20 = row["ema20"]
    ema50 = row["ema50"]
    rsi = row["rsi"]
    atr = row["atr"]

    if (
        pd.isna(close)
        or pd.isna(ema20)
        or pd.isna(ema50)
        or pd.isna(rsi)
        or pd.isna(atr)
    ):
        return None

    if use_rvol and pd.isna(row["rvol"]):
        return None

    return TimeframeState(
        close=float(close),
        ema20=float(ema20),
        ema50=float(ema50),
        rsi=float(rsi),
        rvol=float(row["rvol"]) if use_rvol else 0.0,
        atr=float(atr),
    )


def _completed_state(
    frame: pd.DataFrame,
    timestamp: pd.Timestamp,
    use_rvol: bool,
) -> TimeframeState | None:
    """
    Return the latest completed candle before timestamp.

    Uses DatetimeIndex.searchsorted instead of constructing a full
    boolean mask for every timestamp.
    """

    position = frame.index.searchsorted(timestamp, side="left") - 1

    return _row_to_state(
        frame,
        int(position),
        use_rvol,
    )


def _apply_locked_long_filter(
    result: SignalResult,
    states: tuple[TimeframeState, ...],
    minimum_long_rsi: float,
) -> SignalResult:
    """
    Apply the frozen RSI >= 60 LONG filter.

    The filter is deliberately applied only to BUY signals.

    SELL signals are left unchanged because the robustness research
    showed that the RSI threshold was specifically beneficial for
    LONG trades while preserving SHORT performance.
    """

    if result.signal != Signal.BUY:
        return result

    if all(
        state.rsi >= minimum_long_rsi
        for state in states
    ):
        return result

    return SignalResult(
        signal=Signal.NO_TRADE,
        score=0,
        confidence=0.0,
        timeframe_alignment=result.timeframe_alignment,
        reason=(
            "LONG rejected: RSI below locked threshold "
            f"{minimum_long_rsi:.1f} on at least one timeframe."
        ),
    )


def _generate_filtered_signal(
    states: tuple[TimeframeState, ...],
    config: StrategyConfig,
) -> SignalResult:
    """Generate the authoritative frozen SignalForge signal."""

    result = generate_signal(
        timeframe_30m=states[0],
        timeframe_15m=states[1],
        timeframe_10m=states[2],
        timeframe_5m=states[3],
        minimum_rvol=config.minimum_rvol,
        minimum_atr=config.minimum_atr,
        use_rvol=config.use_rvol,
    )

    return _apply_locked_long_filter(
        result=result,
        states=states,
        minimum_long_rsi=config.minimum_long_rsi,
    )


def evaluate_timestamp(
    timestamp: pd.Timestamp,
    timeframe_data: dict[str, pd.DataFrame],
    config: StrategyConfig | None = None,
) -> SignalResult | None:
    """Generate the frozen SignalForge signal available at one timestamp."""

    if config is None:
        config = StrategyConfig()

    _validate_config(config)

    states: dict[str, TimeframeState] = {}

    for timeframe in ("30m", "15m", "10m", "5m"):
        if timeframe not in timeframe_data:
            raise ValueError(f"Missing timeframe data: {timeframe}")

        state = _completed_state(
            timeframe_data[timeframe],
            timestamp,
            config.use_rvol,
        )

        if state is None:
            return None

        states[timeframe] = state

    ordered_states = (
        states["30m"],
        states["15m"],
        states["10m"],
        states["5m"],
    )

    return _generate_filtered_signal(
        states=ordered_states,
        config=config,
    )


def signal_result_to_position(
    result: SignalResult | None,
) -> Position | None:
    """Convert Signal Engine output into backtest position."""

    if result is None:
        return None

    if result.signal == Signal.BUY:
        return Position.LONG

    if result.signal == Signal.SELL:
        return Position.SHORT

    return None


class _TimeframeCursor:
    """
    Fast chronological cursor for completed timeframe candles.

    The backtest processes timestamps in increasing order, so each
    timeframe index only moves forward. This avoids repeated Pandas
    filtering and repeated binary searches.
    """

    __slots__ = (
        "frame",
        "use_rvol",
        "position",
        "state",
    )

    def __init__(
        self,
        frame: pd.DataFrame,
        use_rvol: bool,
    ) -> None:
        self.frame = frame
        self.use_rvol = use_rvol
        self.position = -1
        self.state: TimeframeState | None = None

    def update(
        self,
        timestamp: pd.Timestamp,
    ) -> TimeframeState | None:
        """Advance to the latest candle strictly before timestamp."""

        target = (
            self.frame.index.searchsorted(
                timestamp,
                side="left",
            )
            - 1
        )

        target = int(target)

        if target == self.position:
            return self.state

        self.position = target

        self.state = _row_to_state(
            self.frame,
            target,
            self.use_rvol,
        )

        return self.state


def _make_cursors(
    timeframe_data: dict[str, pd.DataFrame],
    use_rvol: bool,
) -> dict[str, _TimeframeCursor]:
    """Create one chronological cursor per required timeframe."""

    return {
        timeframe: _TimeframeCursor(
            timeframe_data[timeframe],
            use_rvol,
        )
        for timeframe in ("30m", "15m", "10m", "5m")
    }


def create_signal_function(
    data: pd.DataFrame,
    config: StrategyConfig | None = None,
):
    """Create a fast chronological frozen strategy signal function."""

    if config is None:
        config = StrategyConfig()

    _validate_config(config)
    _validate_market_data(data)

    config = _disable_rvol_if_unavailable(
        data,
        config,
    )

    timeframe_data = calculate_timeframe_indicators(
        data,
        config,
    )

    cursors = _make_cursors(
        timeframe_data,
        config.use_rvol,
    )

    def signal_function(
        row: pd.Series,
        previous_row: pd.Series,
    ) -> Position | None:
        timestamp = row.name

        if not isinstance(timestamp, pd.Timestamp):
            timestamp = pd.Timestamp(timestamp)

        state_30m = cursors["30m"].update(timestamp)
        state_15m = cursors["15m"].update(timestamp)
        state_10m = cursors["10m"].update(timestamp)
        state_5m = cursors["5m"].update(timestamp)

        if (
            state_30m is None
            or state_15m is None
            or state_10m is None
            or state_5m is None
        ):
            return None

        result = _generate_filtered_signal(
            states=(
                state_30m,
                state_15m,
                state_10m,
                state_5m,
            ),
            config=config,
        )

        return signal_result_to_position(result)

    return signal_function


def generate_signals(
    data: pd.DataFrame,
    config: StrategyConfig | None = None,
) -> pd.DataFrame:
    """Generate the frozen multi-timeframe signal for every 1-minute candle."""

    if config is None:
        config = StrategyConfig()

    _validate_config(config)
    _validate_market_data(data)

    config = _disable_rvol_if_unavailable(
        data,
        config,
    )

    timeframe_data = calculate_timeframe_indicators(
        data,
        config,
    )

    cursors = _make_cursors(
        timeframe_data,
        config.use_rvol,
    )

    result = data.copy()

    signals: list[Signal] = []
    scores: list[int] = []
    confidences: list[float] = []
    alignments: list[int] = []
    reasons: list[str] = []

    insufficient_reason = (
        "Insufficient completed timeframe history."
    )

    for timestamp in result.index:
        state_30m = cursors["30m"].update(timestamp)
        state_15m = cursors["15m"].update(timestamp)
        state_10m = cursors["10m"].update(timestamp)
        state_5m = cursors["5m"].update(timestamp)

        if (
            state_30m is None
            or state_15m is None
            or state_10m is None
            or state_5m is None
        ):
            signals.append(Signal.NO_TRADE)
            scores.append(0)
            confidences.append(0.0)
            alignments.append(0)
            reasons.append(insufficient_reason)
            continue

        signal_result = _generate_filtered_signal(
            states=(
                state_30m,
                state_15m,
                state_10m,
                state_5m,
            ),
            config=config,
        )

        signals.append(signal_result.signal)
        scores.append(signal_result.score)
        confidences.append(signal_result.confidence)
        alignments.append(signal_result.timeframe_alignment)
        reasons.append(signal_result.reason)

    result["signal"] = signals
    result["score"] = scores
    result["confidence"] = confidences
    result["timeframe_alignment"] = alignments
    result["reason"] = reasons

    return result