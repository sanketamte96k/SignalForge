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
    """Configuration for the SignalForge strategy."""

    ema_fast_period: int = 20
    ema_slow_period: int = 50
    rsi_period: int = 14
    atr_period: int = 14
    rvol_period: int = 20

    minimum_rvol: float = 1.5
    minimum_atr: float = 0.0

    # RVOL is enabled by default so existing behavior remains unchanged.
    use_rvol: bool = True


TIMEFRAMES = (
    "5m",
    "10m",
    "15m",
    "30m",
)


def _validate_config(
    config: StrategyConfig,
) -> None:
    """Validate strategy configuration."""

    if not isinstance(
        config,
        StrategyConfig,
    ):
        raise TypeError(
            "config must be a StrategyConfig."
        )

    periods = {
        "ema_fast_period": config.ema_fast_period,
        "ema_slow_period": config.ema_slow_period,
        "rsi_period": config.rsi_period,
        "atr_period": config.atr_period,
        "rvol_period": config.rvol_period,
    }

    for name, value in periods.items():

        if not isinstance(value, int) or isinstance(
            value,
            bool,
        ):
            raise TypeError(
                f"{name} must be an integer."
            )

        if value <= 0:
            raise ValueError(
                f"{name} must be greater than zero."
            )

    if (
        config.ema_fast_period
        >= config.ema_slow_period
    ):
        raise ValueError(
            "ema_fast_period must be less than "
            "ema_slow_period."
        )

    if not isinstance(
        config.minimum_rvol,
        (int, float),
    ) or isinstance(
        config.minimum_rvol,
        bool,
    ):
        raise TypeError(
            "minimum_rvol must be numeric."
        )

    if config.minimum_rvol < 0:
        raise ValueError(
            "minimum_rvol cannot be negative."
        )

    if not isinstance(
        config.minimum_atr,
        (int, float),
    ) or isinstance(
        config.minimum_atr,
        bool,
    ):
        raise TypeError(
            "minimum_atr must be numeric."
        )

    if config.minimum_atr < 0:
        raise ValueError(
            "minimum_atr cannot be negative."
        )

    if not isinstance(
        config.use_rvol,
        bool,
    ):
        raise TypeError(
            "use_rvol must be a boolean."
        )


def _validate_market_data(
    data: pd.DataFrame,
) -> None:
    """Validate input OHLCV data."""

    if not isinstance(
        data,
        pd.DataFrame,
    ):
        raise TypeError(
            "data must be a pandas DataFrame."
        )

    if data.empty:
        raise ValueError(
            "data cannot be empty."
        )

    required_columns = {
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing = sorted(
        required_columns.difference(
            data.columns
        )
    )

    if missing:
        raise ValueError(
            "data is missing required columns: "
            f"{missing}"
        )

    if not isinstance(
        data.index,
        pd.DatetimeIndex,
    ):
        raise TypeError(
            "data index must be a DatetimeIndex."
        )

    if data.index.has_duplicates:
        raise ValueError(
            "data index cannot contain duplicates."
        )

    if not data.index.is_monotonic_increasing:
        raise ValueError(
            "data index must be sorted."
        )


def _has_usable_volume(
    data: pd.DataFrame,
) -> bool:
    """
    Return whether the dataset contains usable volume.

    Volume is considered unavailable when all values
    are zero. We never replace unavailable volume with
    fabricated values.
    """

    volume = data["volume"]

    return bool(
        (volume > 0).any()
    )


def calculate_timeframe_indicators(
    data: pd.DataFrame,
    config: StrategyConfig | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Build all SignalForge timeframes with indicators.

    Timeframes:
        5m
        10m
        15m
        30m

    RVOL is calculated whenever requested. If the source
    dataset has no usable volume, the resulting RVOL values
    remain unavailable and are handled explicitly during
    signal evaluation.
    """

    if config is None:
        config = StrategyConfig()

    _validate_config(config)
    _validate_market_data(data)

    result: dict[str, pd.DataFrame] = {}

    for timeframe in TIMEFRAMES:

        frame = resample_ohlcv(
            data,
            timeframe,
        ).copy()

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


def _completed_state(
    frame: pd.DataFrame,
    timestamp: pd.Timestamp,
    use_rvol: bool,
) -> TimeframeState | None:
    """
    Return the latest completed candle before timestamp.

    A candle beginning exactly at timestamp is excluded.

    When RVOL is disabled, an unavailable RVOL value is
    represented internally by 0.0 because the signal engine
    does not use it in that mode.
    """

    completed = frame[
        frame.index < timestamp
    ]

    if completed.empty:
        return None

    row = completed.iloc[-1]

    required_columns = (
        "close",
        "ema20",
        "ema50",
        "rsi",
        "atr",
    )

    if row[
        list(required_columns)
    ].isna().any():
        return None

    if use_rvol and pd.isna(
        row["rvol"]
    ):
        return None

    rvol = (
        float(row["rvol"])
        if use_rvol
        else 0.0
    )

    return TimeframeState(
        close=float(row["close"]),
        ema20=float(row["ema20"]),
        ema50=float(row["ema50"]),
        rsi=float(row["rsi"]),
        rvol=rvol,
        atr=float(row["atr"]),
    )


def evaluate_timestamp(
    timestamp: pd.Timestamp,
    timeframe_data: dict[str, pd.DataFrame],
    config: StrategyConfig | None = None,
) -> SignalResult | None:
    """
    Generate the SignalForge signal available at one timestamp.

    Only completed higher-timeframe candles are used.
    """

    if config is None:
        config = StrategyConfig()

    _validate_config(config)

    states: dict[str, TimeframeState] = {}

    for timeframe in (
        "30m",
        "15m",
        "10m",
        "5m",
    ):

        if timeframe not in timeframe_data:
            raise ValueError(
                f"Missing timeframe data: {timeframe}"
            )

        state = _completed_state(
            timeframe_data[timeframe],
            timestamp,
            config.use_rvol,
        )

        if state is None:
            return None

        states[timeframe] = state

    return generate_signal(
        timeframe_30m=states["30m"],
        timeframe_15m=states["15m"],
        timeframe_10m=states["10m"],
        timeframe_5m=states["5m"],
        minimum_rvol=config.minimum_rvol,
        minimum_atr=config.minimum_atr,
        use_rvol=config.use_rvol,
    )


def signal_result_to_position(
    result: SignalResult | None,
) -> Position | None:
    """
    Convert Signal Engine output into backtest position.

    BUY       -> LONG
    SELL      -> SHORT
    NO_TRADE  -> None
    """

    if result is None:
        return None

    if result.signal == Signal.BUY:
        return Position.LONG

    if result.signal == Signal.SELL:
        return Position.SHORT

    return None


def create_signal_function(
    data: pd.DataFrame,
    config: StrategyConfig | None = None,
):
    """
    Create a signal function compatible with run_backtest().
    """

    if config is None:
        config = StrategyConfig()

    _validate_config(config)
    _validate_market_data(data)

    # Automatically disable RVOL for datasets such as
    # the NIFTY 50 index where volume is unavailable.
    if config.use_rvol and not _has_usable_volume(data):

        config = StrategyConfig(
            ema_fast_period=config.ema_fast_period,
            ema_slow_period=config.ema_slow_period,
            rsi_period=config.rsi_period,
            atr_period=config.atr_period,
            rvol_period=config.rvol_period,
            minimum_rvol=config.minimum_rvol,
            minimum_atr=config.minimum_atr,
            use_rvol=False,
        )

    timeframe_data = (
        calculate_timeframe_indicators(
            data,
            config,
        )
    )

    def signal_function(
        row: pd.Series,
        previous_row: pd.Series,
    ) -> Position | None:

        timestamp = row.name

        if not isinstance(
            timestamp,
            pd.Timestamp,
        ):
            timestamp = pd.Timestamp(
                timestamp
            )

        result = evaluate_timestamp(
            timestamp,
            timeframe_data,
            config,
        )

        return signal_result_to_position(
            result
        )

    return signal_function


def generate_signals(
    data: pd.DataFrame,
    config: StrategyConfig | None = None,
) -> pd.DataFrame:
    """
    Generate a multi-timeframe signal for every 1-minute candle.

    Adds:

        signal
        score
        confidence
        timeframe_alignment
        reason
    """

    if config is None:
        config = StrategyConfig()

    _validate_config(config)
    _validate_market_data(data)

    if config.use_rvol and not _has_usable_volume(data):

        config = StrategyConfig(
            ema_fast_period=config.ema_fast_period,
            ema_slow_period=config.ema_slow_period,
            rsi_period=config.rsi_period,
            atr_period=config.atr_period,
            rvol_period=config.rvol_period,
            minimum_rvol=config.minimum_rvol,
            minimum_atr=config.minimum_atr,
            use_rvol=False,
        )

    timeframe_data = (
        calculate_timeframe_indicators(
            data,
            config,
        )
    )

    result = data.copy()

    signals: list[Signal] = []
    scores: list[int] = []
    confidences: list[float] = []
    alignments: list[int] = []
    reasons: list[str] = []

    for timestamp in result.index:

        signal_result = evaluate_timestamp(
            timestamp,
            timeframe_data,
            config,
        )

        if signal_result is None:

            signals.append(
                Signal.NO_TRADE
            )

            scores.append(0)

            confidences.append(
                0.0
            )

            alignments.append(0)

            reasons.append(
                "Insufficient completed "
                "timeframe history."
            )

            continue

        signals.append(
            signal_result.signal
        )

        scores.append(
            signal_result.score
        )

        confidences.append(
            signal_result.confidence
        )

        alignments.append(
            signal_result.timeframe_alignment
        )

        reasons.append(
            signal_result.reason
        )

    result["signal"] = signals
    result["score"] = scores
    result["confidence"] = confidences
    result["timeframe_alignment"] = alignments
    result["reason"] = reasons

    return result