"""Tests for historical stock CSV importing."""

from pathlib import Path

import pandas as pd
import pytest

from src.data.stock_importer import StockDataImporter
from src.data.stock_provider import StockDataProvider


def make_data() -> pd.DataFrame:
    index = pd.date_range(
        "2024-01-01 09:15",
        periods=3,
        freq="min",
    )

    return pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000, 1100, 1200],
        },
        index=index,
    )


def test_import_csv_saves_normalized_stock_data(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.csv"
    output_directory = tmp_path / "stocks"

    data = make_data()

    source_data = data.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    ).reset_index(names="timestamp")

    source_data.to_csv(source, index=False)

    provider = StockDataProvider(
        data_directory=output_directory,
    )
    importer = StockDataImporter(provider)

    imported = importer.import_csv(
        "TESTSTOCK",
        source,
    )

    assert list(imported.columns) == [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    saved_path = output_directory / "TESTSTOCK_1m.csv"

    assert saved_path.exists()

    loaded = provider.load("TESTSTOCK")

    imported.index.name = None

    pd.testing.assert_frame_equal(
        imported,
        loaded,
    )


def test_import_csv_accepts_datetime_column(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.csv"

    data = make_data().reset_index(
        names="Datetime"
    )

    data.to_csv(source, index=False)

    provider = StockDataProvider(
        data_directory=tmp_path / "stocks",
    )
    importer = StockDataImporter(provider)

    imported = importer.import_csv(
        "TESTSTOCK",
        source,
    )

    assert isinstance(
        imported.index,
        pd.DatetimeIndex,
    )
    assert len(imported) == 3


def test_import_csv_rejects_missing_source(
    tmp_path: Path,
) -> None:
    importer = StockDataImporter(
        StockDataProvider(
            data_directory=tmp_path / "stocks",
        )
    )

    with pytest.raises(FileNotFoundError):
        importer.import_csv(
            "TESTSTOCK",
            tmp_path / "missing.csv",
        )


def test_import_csv_rejects_empty_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "empty.csv"

    source.write_text(
        "timestamp,open,high,low,close,volume\n",
        encoding="utf-8",
    )

    importer = StockDataImporter(
        StockDataProvider(
            data_directory=tmp_path / "stocks",
        )
    )

    with pytest.raises(ValueError, match="empty"):
        importer.import_csv(
            "TESTSTOCK",
            source,
        )


def test_import_csv_rejects_missing_ohlcv_columns(
    tmp_path: Path,
) -> None:
    source = tmp_path / "invalid.csv"

    pd.DataFrame(
        {
            "timestamp": [
                "2024-01-01 09:15",
            ],
            "open": [100.0],
            "close": [101.0],
        }
    ).to_csv(
        source,
        index=False,
    )

    importer = StockDataImporter(
        StockDataProvider(
            data_directory=tmp_path / "stocks",
        )
    )

    with pytest.raises(ValueError, match="missing required OHLCV"):
        importer.import_csv(
            "TESTSTOCK",
            source,
        )


def test_import_csv_rejects_invalid_ohlc(
    tmp_path: Path,
) -> None:
    source = tmp_path / "invalid_ohlc.csv"

    pd.DataFrame(
        {
            "timestamp": [
                "2024-01-01 09:15",
            ],
            "open": [100.0],
            "high": [99.0],
            "low": [98.0],
            "close": [99.0],
            "volume": [1000],
        }
    ).to_csv(
        source,
        index=False,
    )

    importer = StockDataImporter(
        StockDataProvider(
            data_directory=tmp_path / "stocks",
        )
    )

    with pytest.raises(ValueError):
        importer.import_csv(
            "TESTSTOCK",
            source,
        )


def test_import_csv_normalizes_symbol(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.csv"

    make_data().reset_index(
        names="timestamp"
    ).to_csv(
        source,
        index=False,
    )

    provider = StockDataProvider(
        data_directory=tmp_path / "stocks",
    )
    importer = StockDataImporter(provider)

    importer.import_csv(
        "  teststock  ",
        source,
    )

    assert (
        tmp_path / "stocks" / "TESTSTOCK_1m.csv"
    ).exists()