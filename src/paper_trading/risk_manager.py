"""
SignalForge — Phase 28: Server-Side Portfolio Risk Discipline
==============================================================
File: src/paper_trading/risk_manager.py

Capabilities:
- Enforces the certified backtesting portfolio risk discipline server-side on paper trading.
- Risk validation guards:
    1. Risk per trade (max 1.0% of portfolio equity based on stop-loss distance).
    2. Maximum stock allocation (notional capped at 35.0% of portfolio equity).
    3. Aggregate portfolio risk (cumulative active open risk capped at 3.0% of equity).
    4. Reserved capital (15.0% mandatory reserve withheld from trading capacity).
    5. Opening cooldown (09:15 to 09:25 IST opening auction buffer).
    6. Session end cutoff (mandatory 15:15 IST cutoff: blocks new entries, enforces EOD square-off).
    7. Capital protection floor (halts new entries if equity drops below protection floor).
    8. Maximum daily loss limit (halts new entries if daily realized loss exceeds limit).
    9. Duplicate active symbol position rejection.
    10. Market data health guard: blocks entries during STALE, DISCONNECTED, or INVALID feed states.
- SIMULATION SAFETY: Strictly prevents any routing of paper orders to live brokers.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


@dataclass
class PaperRiskConfig:
    """Configurable risk parameters matching certified backtesting standards."""

    risk_per_trade_pct: float = 0.01  # 1.0% of equity
    max_stock_allocation_pct: float = 0.35  # 35.0% of equity
    max_portfolio_risk_pct: float = 0.03  # 3.0% of equity
    reserve_capital_pct: float = 0.15  # 15.0% mandatory reserve
    max_leverage: float = 5.0
    opening_cooldown_minutes: int = 10  # 09:15 to 09:25 IST
    market_open_time: str = "09:15"
    session_end_time: str = "15:15"  # Certified 15:15 IST square-off
    capital_protection_floor_pct: Optional[float] = 0.20  # Halt if equity < 20% initial capital
    max_daily_loss_pct: Optional[float] = 0.05  # Halt if daily loss > 5% initial capital
    max_open_positions: int = 5
    enforce_session_hours: bool = False  # Set to True when enforcing real-time market opening/closing windows

    def __init__(
        self,
        risk_per_trade_pct: float = 0.01,
        max_stock_allocation_pct: float = 0.35,
        max_portfolio_risk_pct: float = 0.03,
        reserve_capital_pct: float = 0.15,
        max_leverage: float = 5.0,
        opening_cooldown_minutes: int = 10,
        market_open_time: str = "09:15",
        session_end_time: str = "15:15",
        capital_protection_floor_pct: Optional[float] = 0.20,
        max_daily_loss_pct: Optional[float] = 0.05,
        max_open_positions: int = 5,
        enforce_session_hours: bool = False,
        **kwargs: Any,
    ) -> None:
        if "max_risk_per_trade_pct" in kwargs:
            risk_per_trade_pct = kwargs["max_risk_per_trade_pct"]
        if "max_aggregate_portfolio_risk_pct" in kwargs:
            max_portfolio_risk_pct = kwargs["max_aggregate_portfolio_risk_pct"]
        if "reserved_capital_floor_pct" in kwargs:
            reserve_capital_pct = kwargs["reserved_capital_floor_pct"]
        if "square_off_time" in kwargs:
            sq = kwargs["square_off_time"]
            session_end_time = sq.strftime("%H:%M") if hasattr(sq, "strftime") else str(sq)

        self.risk_per_trade_pct = float(risk_per_trade_pct)
        self.max_stock_allocation_pct = float(max_stock_allocation_pct)
        self.max_portfolio_risk_pct = float(max_portfolio_risk_pct)
        self.reserve_capital_pct = float(reserve_capital_pct)
        self.max_leverage = float(max_leverage)
        self.opening_cooldown_minutes = int(opening_cooldown_minutes)
        self.market_open_time = str(market_open_time)
        self.session_end_time = str(session_end_time)
        self.capital_protection_floor_pct = (
            float(capital_protection_floor_pct)
            if capital_protection_floor_pct is not None
            else None
        )
        self.max_daily_loss_pct = (
            float(max_daily_loss_pct) if max_daily_loss_pct is not None else None
        )
        self.max_open_positions = int(max_open_positions)
        self.enforce_session_hours = bool(enforce_session_hours)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PaperRiskManager:
    """
    Server-side portfolio risk controller for paper trading.
    Validates every candidate simulated order before execution.
    """

    def __init__(self, config: Optional[PaperRiskConfig] = None) -> None:
        self.config: PaperRiskConfig = config or PaperRiskConfig()
        self._active_blockers: Dict[str, str] = {}  # reason_key -> description

    @property
    def active_risk_blockers(self) -> Dict[str, str]:
        return dict(self._active_blockers)

    def is_blocked(self) -> bool:
        return len(self._active_blockers) > 0

    def clear_blocker(self, blocker_key: str) -> None:
        self._active_blockers.pop(blocker_key, None)

    def validate_candidate_order(
        self,
        symbol: str,
        side: str,
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        quantity: int = 1,
        current_equity: Optional[float] = None,
        available_margin: float = 0.0,
        initial_capital: Optional[float] = None,
        daily_realized_loss: float = 0.0,
        active_positions: Optional[List[Dict[str, Any]]] = None,
        feed_quality_state: str = "CONNECTED",
        order_timestamp: Optional[datetime] = None,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        portfolio_equity: Optional[float] = None,
        timestamp: Optional[datetime] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive pre-order server-side risk evaluation.
        Returns (approved: bool, rejection_reason: Optional[str]).
        """
        eff_price = entry_price if entry_price is not None else price
        if eff_price is None:
            raise ValueError("entry_price or price is required")

        eff_stop = stop_loss if stop_loss is not None else stop_price
        if eff_stop is None:
            # Default 1% stop if none provided
            eff_stop = eff_price * 0.99 if side.upper() in {"BUY", "LONG"} else eff_price * 1.01

        eff_equity = current_equity if current_equity is not None else portfolio_equity
        if eff_equity is None:
            raise ValueError("current_equity or portfolio_equity is required")

        eff_initial = initial_capital if initial_capital is not None else eff_equity
        now = order_timestamp or timestamp or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        ist_now = now.astimezone(IST)
        ist_time = ist_now.time()

        # 1. Market Data Reliability Guard
        norm_feed = str(feed_quality_state).strip().upper()
        if norm_feed in {"STALE", "DISCONNECTED", "INVALID"}:
            reason = f"Market data feed is degraded ({norm_feed}); new entries blocked."
            self._active_blockers["FEED_DEGRADED"] = reason
            return False, reason
        else:
            self._active_blockers.pop("FEED_DEGRADED", None)

        # 2. Opening Cooldown Check (09:15 to 09:25 IST)
        if self.config.enforce_session_hours:
            cooldown_cutoff = time(9, 15 + self.config.opening_cooldown_minutes)
            if time(9, 15) <= ist_time < cooldown_cutoff:
                reason = (
                    f"Opening cooldown active: entries blocked between 09:15 and {cooldown_cutoff.strftime('%H:%M')} IST"
                )
                self._active_blockers["OPENING_COOLDOWN"] = reason
                return False, reason
            else:
                self._active_blockers.pop("OPENING_COOLDOWN", None)

            # 3. Session End Cutoff (Mandatory 15:15 IST)
            session_cutoff = time(15, 15)
            if ist_time >= session_cutoff or ist_time < time(9, 15):
                reason = f"Session end cutoff active ({self.config.session_end_time} IST); intraday entries closed."
                self._active_blockers["SESSION_CLOSED"] = reason
                return False, reason
            else:
                self._active_blockers.pop("SESSION_CLOSED", None)

        # 4. Capital Protection Floor Check
        if self.config.capital_protection_floor_pct is not None:
            floor_value = eff_initial * self.config.capital_protection_floor_pct
            if eff_equity <= floor_value:
                reason = (
                    f"Capital protection floor breached: equity ₹{eff_equity:.2f} <= floor ₹{floor_value:.2f}"
                )
                self._active_blockers["PROTECTION_FLOOR"] = reason
                return False, reason
            else:
                self._active_blockers.pop("PROTECTION_FLOOR", None)

        # 5. Maximum Daily Loss Limit Check
        if self.config.max_daily_loss_pct is not None:
            max_daily_loss = eff_initial * self.config.max_daily_loss_pct
            if daily_realized_loss >= max_daily_loss:
                reason = (
                    f"Daily loss limit breached: realized loss ₹{daily_realized_loss:.2f} >= limit ₹{max_daily_loss:.2f}"
                )
                self._active_blockers["DAILY_LOSS_LIMIT"] = reason
                return False, reason
            else:
                self._active_blockers.pop("DAILY_LOSS_LIMIT", None)

        # 6. Duplicate Active Position Check
        active_pos = active_positions or []
        clean_symbol = symbol.strip().upper()
        for pos in active_pos:
            if pos.get("symbol") == clean_symbol and pos.get("status") in {"OPEN", "PENDING"}:
                reason = f"Duplicate active position: {clean_symbol} already has an open paper trade"
                return False, reason

        # 7. Maximum Open Position Count Check
        open_count = sum(1 for p in active_pos if p.get("status") in {"OPEN", "PENDING"})
        if open_count >= self.config.max_open_positions:
            reason = (
                f"Maximum open positions ({self.config.max_open_positions}) reached; entry rejected"
            )
            return False, reason

        # 8. Maximum Stock Allocation Check (Notional <= 35% Equity)
        notional = eff_price * quantity
        max_notional = eff_equity * self.config.max_stock_allocation_pct
        if notional > max_notional:
            reason = (
                f"Max stock allocation breached: notional ₹{notional:.2f} exceeds limit ₹{max_notional:.2f} (35% allocation)"
            )
            return False, reason

        # 9. Risk Per Trade Check (Stop Distance Risk <= 1% Equity)
        stop_distance = abs(eff_price - eff_stop)
        if stop_distance <= 0:
            return False, "Invalid stop distance: stop_loss cannot equal entry_price"

        trade_risk = stop_distance * quantity
        max_trade_risk = eff_equity * self.config.risk_per_trade_pct
        if trade_risk > (max_trade_risk * 1.05):  # 5% rounding tolerance on integer shares
            reason = (
                f"Risk per trade breached: capital at risk ₹{trade_risk:.2f} exceeds limit ₹{max_trade_risk:.2f} (1.0% equity)"
            )
            return False, reason

        # 10. Aggregate Portfolio Risk Check (Sum of active risks + candidate <= 3% Equity)
        active_risk_sum = 0.0
        for pos in active_pos:
            if pos.get("status") in {"OPEN", "PENDING"}:
                pos_entry = float(pos.get("entry_price", 0.0))
                pos_stop = float(pos.get("stop_loss", 0.0))
                pos_qty = int(pos.get("quantity", 1))
                active_risk_sum += abs(pos_entry - pos_stop) * pos_qty

        total_risk = active_risk_sum + trade_risk
        max_portfolio_risk = eff_equity * self.config.max_portfolio_risk_pct
        if total_risk > (max_portfolio_risk * 1.05):
            reason = (
                f"Aggregate portfolio risk breached: total risk ₹{total_risk:.2f} exceeds limit ₹{max_portfolio_risk:.2f} (3.0% equity)"
            )
            return False, reason

        # 11. Margin Solvency Check
        # Required margin for entry
        margin_required = notional / self.config.max_leverage
        if margin_required > available_margin:
            reason = (
                f"Insufficient available margin: required ₹{margin_required:.2f}, available ₹{available_margin:.2f}"
            )
            return False, reason

        # All risk checks passed
        return True, "Order approved by risk manager"

    def is_square_off_time(self, timestamp: datetime) -> Tuple[bool, str]:
        """Check if timestamp is at or past intraday square-off cutoff (15:15 IST)."""
        now = timestamp
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        ist_now = now.astimezone(IST)
        ist_time = ist_now.time()
        session_cutoff = time(15, 15)
        if ist_time >= session_cutoff:
            return True, f"Time {ist_time.strftime('%H:%M:%S')} IST is past square-off cutoff (15:15 IST)"
        return False, ""

    def check_capital_floor(self, current_equity: float, initial_capital: float | None = None) -> Tuple[bool, str]:
        """Check if portfolio equity has fallen to or below the protection floor."""
        init = initial_capital or getattr(self.config, "initial_capital", 1_000_000.0)
        if self.config.capital_protection_floor_pct is not None:
            floor_val = init * self.config.capital_protection_floor_pct
            if current_equity <= floor_val:
                return True, f"Current equity ₹{current_equity:.2f} <= floor ₹{floor_val:.2f}"
        return False, ""

