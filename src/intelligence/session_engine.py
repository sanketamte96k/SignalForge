"""
SignalForge Intelligence Engine — Session Engine
================================================
NSE trading session tracking (09:15-15:30 IST), calculating session state,
elapsed/remaining minutes, and intraday execution suitability.
"""

from __future__ import annotations

import datetime
from typing import List
import pandas as pd

from src.intelligence.models import SessionContext, SessionState
from src.intelligence.config import IntelligenceThresholds


def calculate_session_context(
    dt_val: pd.Timestamp | datetime.datetime | str,
    thresholds: IntelligenceThresholds | None = None
) -> SessionContext:
    """
    Evaluates session timing relative to Indian market hours (09:15 - 15:30).
    """
    if thresholds is None:
        thresholds = IntelligenceThresholds()

    if isinstance(dt_val, str):
        ts = pd.to_datetime(dt_val)
    elif isinstance(dt_val, (pd.Timestamp, datetime.datetime)):
        ts = dt_val
    else:
        ts = pd.Timestamp.now()

    time_obj = ts.time()
    hour = time_obj.hour
    minute = time_obj.minute
    total_minutes = hour * 60 + minute

    # NSE session boundaries in minutes from midnight
    market_open = 9 * 60 + 15   # 555 mins (09:15)
    market_close = 15 * 60 + 30 # 930 mins (15:30)

    minutes_from_open = max(0, total_minutes - market_open)
    minutes_to_close = max(0, market_close - total_minutes)

    reasons: List[str] = []

    # Session classification
    if total_minutes < 10 * 60:  # 09:15 to 10:00
        state = SessionState.OPENING
        if minutes_from_open < thresholds.opening_settle_minutes:
            session_quality = 40.0
            reasons.append(f"Opening rush period ({minutes_from_open}m from open) — wide spreads and gap volatility")
        else:
            session_quality = 70.0
            reasons.append(f"Opening session price discovery ({minutes_from_open}m from open)")
    elif total_minutes < 11 * 60 + 30:  # 10:00 to 11:30
        state = SessionState.EARLY_SESSION
        session_quality = 90.0
        reasons.append(f"Prime early session liquidity window ({minutes_from_open}m elapsed)")
    elif total_minutes < 13 * 60 + 30:  # 11:30 to 13:30
        state = SessionState.MIDDAY
        session_quality = 75.0
        reasons.append("Midday session — volume and momentum typically subside")
    elif total_minutes < 15 * 60:  # 13:30 to 15:00
        state = SessionState.AFTERNOON
        session_quality = 85.0
        reasons.append("Afternoon institutional trend continuation / expansion window")
    else:  # 15:00 to 15:30
        state = SessionState.CLOSING
        if minutes_to_close <= thresholds.no_trade_session_minutes_remaining:
            session_quality = 15.0
            reasons.append(f"Imminent market close ({minutes_to_close}m remaining) — broker auto-square-off danger")
        else:
            session_quality = 35.0
            reasons.append(f"Closing auction preparation ({minutes_to_close}m remaining) — intraday unwinding")

    return SessionContext(
        state=state,
        timestamp=str(ts),
        minutes_from_open=int(minutes_from_open),
        minutes_to_close=int(minutes_to_close),
        session_quality_score=round(float(session_quality), 1),
        reasons=reasons
    )
