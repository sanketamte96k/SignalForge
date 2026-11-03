from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from src.core.io_utils import atomic_write_json
from src.paper_trading.reporting import PaperTradingReport


def save_paper_trading_report(
    report: PaperTradingReport,
    path: str | Path,
) -> Path:
    """
    Save a paper-trading report as JSON atomically.

    The parent directory is created automatically.
    """

    if not isinstance(report, PaperTradingReport):
        raise TypeError(
            "report must be a PaperTradingReport."
        )

    output_path = Path(path)

    payload = asdict(report)

    # JSON does not support infinity.
    # Represent an infinite profit factor explicitly.
    if report.profit_factor == float("inf"):
        payload["profit_factor"] = "inf"
    else:
        payload["profit_factor"] = report.profit_factor

    payload["net_return_pct"] = report.net_return_pct
    payload["win_rate_pct"] = report.win_rate_pct

    atomic_write_json(
        output_path,
        payload,
        indent=2,
    )

    return output_path


def load_paper_trading_report(
    path: str | Path,
) -> dict:
    """
    Load a previously saved paper-trading report.

    Returns the persisted JSON representation.
    """

    input_path = Path(path)

    if not input_path.exists():
        raise FileNotFoundError(
            f"Report file not found: {input_path}"
        )

    with input_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)
