"""Historical market data downloader for SignalForge."""

from pathlib import Path

import pandas as pd
import yfinance as yf

from src.data.validator import validate_market_data


SUPPORTED_INTERVALS = {
    "1m",
    "2m",
    "5m",
    "15m",
    "30m",
    "60m",
    "90m",
    "1h",
    "1d",
    "5d",
    "1wk",
    "1mo",
    "3mo",
}


def _validate_parameters(
    ticker: str,
    start: str | None = None,
    end: str | None = None,
    interval: str = "1m",
) -> None:
    """Validate downloader parameters."""

    if not isinstance(ticker, str):
        raise TypeError(
            "ticker must be a string."
        )

    if not ticker.strip():
        raise ValueError(
            "ticker cannot be empty."
        )

    if interval not in SUPPORTED_INTERVALS:
        raise ValueError(
            f"Unsupported interval: {interval}. "
            f"Supported: {sorted(SUPPORTED_INTERVALS)}"
        )

    if start is not None and not isinstance(
        start,
        str,
    ):
        raise TypeError(
            "start must be a string or None."
        )

    if end is not None and not isinstance(
        end,
        str,
    ):
        raise TypeError(
            "end must be a string or None."
        )


def _normalize_downloaded_data(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Normalize Yahoo Finance OHLCV output."""

    if not isinstance(
        data,
        pd.DataFrame,
    ):
        raise TypeError(
            "Downloaded data must be a pandas DataFrame."
        )

    if data.empty:
        raise ValueError(
            "Downloaded market data is empty."
        )

    data = data.copy()

    required_columns = {
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    }

    # yfinance can return MultiIndex columns even
    # when only one ticker is downloaded.
    #
    # Example:
    #
    # Price       Open  High  Low  Close  Volume
    # Ticker     ^NSEI ^NSEI ^NSEI ^NSEI  ^NSEI
    #
    # Identify which level contains the OHLCV
    # column names and discard the ticker level.
    if isinstance(
        data.columns,
        pd.MultiIndex,
    ):
        if data.columns.nlevels != 2:
            raise ValueError(
                "Unsupported MultiIndex structure."
            )

        level_0 = list(
            data.columns.get_level_values(0)
        )

        level_1 = list(
            data.columns.get_level_values(1)
        )

        if required_columns.issubset(
            set(level_0)
        ):
            data.columns = level_0

        elif required_columns.issubset(
            set(level_1)
        ):
            data.columns = level_1

        else:
            raise ValueError(
                "Downloaded data does not contain "
                "standard OHLCV columns."
            )

    missing_columns = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:
        raise ValueError(
            "Downloaded data is missing columns: "
            f"{missing_columns}"
        )

    data = data[
        [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]
    ].rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )

    if not isinstance(
        data.index,
        pd.DatetimeIndex,
    ):
        data.index = pd.to_datetime(
            data.index
        )

    data = data.sort_index()

    # Convert Yahoo Finance timestamps to
    # Indian Standard Time before removing
    # timezone information.
    #
    # This is important because simply calling
    # tz_localize(None) would remove the timezone
    # without converting the actual clock time.
    if data.index.tz is not None:
        data.index = data.index.tz_convert(
            "Asia/Kolkata"
        ).tz_localize(
            None
        )

    return data


def download_market_data(
    ticker: str,
    start: str | None = None,
    end: str | None = None,
    interval: str = "1m",
) -> pd.DataFrame:
    """
    Download historical OHLCV market data.

    Parameters
    ----------
    ticker:
        Yahoo Finance ticker symbol.

    start:
        Optional start date in YYYY-MM-DD format.

    end:
        Optional end date in YYYY-MM-DD format.

    interval:
        Yahoo Finance interval.

    Returns
    -------
    pd.DataFrame
        Validated OHLCV DataFrame.
    """

    _validate_parameters(
        ticker=ticker,
        start=start,
        end=end,
        interval=interval,
    )

    try:
        data = yf.download(
            tickers=ticker.strip(),
            start=start,
            end=end,
            interval=interval,
            auto_adjust=False,
            progress=False,
            group_by="column",
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to download market data "
            f"for {ticker}: {exc}"
        ) from exc

    data = _normalize_downloaded_data(
        data
    )

    validate_market_data(data)

    return data


def save_market_data(
    data: pd.DataFrame,
    path: str | Path,
) -> Path:
    """
    Save validated market data as CSV.

    Parameters
    ----------
    data:
        Validated OHLCV DataFrame.

    path:
        Destination CSV path.

    Returns
    -------
    Path
        Path of the saved file.
    """

    if not isinstance(
        data,
        pd.DataFrame,
    ):
        raise TypeError(
            "data must be a pandas DataFrame."
        )

    validate_market_data(data)

    output_path = Path(path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    data.to_csv(
        output_path
    )

    return output_path


def load_market_data(
    path: str | Path,
) -> pd.DataFrame:
    """
    Load OHLCV data previously saved by SignalForge.

    Parameters
    ----------
    path:
        CSV file path.

    Returns
    -------
    pd.DataFrame
        Validated OHLCV DataFrame.
    """

    input_path = Path(path)

    if not input_path.exists():
        raise FileNotFoundError(
            f"Market data file not found: "
            f"{input_path}"
        )

    data = pd.read_csv(
        input_path,
        index_col=0,
        parse_dates=True,
    )

    data.index.name = None

    validate_market_data(data)

    return data