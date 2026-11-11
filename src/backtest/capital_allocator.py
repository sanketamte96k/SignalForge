"""
Intelligent Capital Sizing and Multi-Stock Allocation Strategy for SignalForge.

Decides:
1. How much capital / margin collateral can be allocated to each stock.
2. How many shares can be purchased based on risk budget, stop-loss distance, and transaction costs.
3. How much total portfolio risk is permitted and remaining.
4. How much capital must remain reserved for liquidity buffer.
5. Deterministic ranking of competing intraday opportunities.
6. Whether candidate opportunities should be accepted, reduced, or rejected.

Integrates with Phase 27C.3.1 PortfolioManager and Phase 27B TransactionCostEngine
without mutating portfolio state during evaluation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any

from src.backtest.simulator import Position
from src.backtest.portfolio import PortfolioManager, OpenPosition
from src.backtest.indian_market_costs import (
    IntradayCostConfig,
    DISCOUNT_BROKER_REALISTIC_CONFIG,
    calculate_trade_transaction_costs,
)


def calculate_cost_aware_position_size(
    entry_price: float,
    stop_loss: float,
    capital: float,
    risk_per_trade_pct: float,
    max_leverage: float,
    side: Position | str = Position.LONG,
    cost_config: Optional[IntradayCostConfig] = None,
    max_exposure: Optional[float] = None,
    max_stock_allocation_pct: float = 1.0,
    available_margin: Optional[float] = None,
    min_trade_quantity: int = 1,
    include_costs_in_sizing: bool = True,
    conservative_cost_buffer_rate: float = 0.0,
) -> tuple[int, int, int]:
    """
    Compute integer position size aligning single-stock and multi-asset risk rules.

    Parameters
    ----------
    entry_price: Proposed entry execution price.
    stop_loss: Planned stop-loss price.
    capital: Total equity or account cash before entry.
    risk_per_trade_pct: Fraction of capital to risk (e.g. 0.01 for 1%).
    max_leverage: Leverage multiplier ceiling (e.g. 5.0).
    side: Trade direction (Position.LONG or Position.SHORT).
    cost_config: Canonical Phase 27B IntradayCostConfig schedule.
    max_exposure: Optional rupee cap on gross notional exposure.
    max_stock_allocation_pct: Maximum stock allocation limit (1.0 for single-stock, 0.35 for multi-asset).
    available_margin: Optional unencumbered margin collateral. If provided, constrains position size.
    min_trade_quantity: Minimum allowable trade quantity (default 1).
    include_costs_in_sizing: If True and cost_config is present, solve via binary search so
                             Gross Risk + Estimated Round-Trip Cost <= Risk Budget.
    conservative_cost_buffer_rate: Optional additional safety buffer per rupee.

    Returns
    -------
    (final_quantity, risk_based_quantity, max_allowed_quantity)
    """
    if (
        entry_price <= 0
        or stop_loss <= 0
        or capital <= 0
        or risk_per_trade_pct <= 0
        or max_leverage <= 0
    ):
        return 0, 0, 0

    base_dist = abs(entry_price - stop_loss)
    stop_dist = base_dist + (entry_price * conservative_cost_buffer_rate)
    if stop_dist <= 0:
        return 0, 0, 0

    risk_amount = capital * risk_per_trade_pct
    risk_qty = int(risk_amount / stop_dist)

    max_notional = capital * max_leverage * max_stock_allocation_pct
    if max_exposure is not None:
        max_notional = min(max_notional, max_exposure)

    max_allowed_qty = int(max_notional / entry_price)
    if available_margin is not None:
        margin_per_share = entry_price / max_leverage
        if margin_per_share > 0:
            q_margin = int(available_margin / margin_per_share)
            max_allowed_qty = min(max_allowed_qty, q_margin)

    upper_bound = min(risk_qty, max_allowed_qty)
    if upper_bound < min_trade_quantity:
        return 0, risk_qty, max_allowed_qty

    if not include_costs_in_sizing or cost_config is None:
        return upper_bound, risk_qty, max_allowed_qty

    # Binary search for highest integer quantity within cost-inclusive risk budget
    low = 0
    high = upper_bound
    best_q = 0
    side_str = side.value if isinstance(side, Position) else str(side).upper()

    while low <= high:
        mid = (low + high) // 2
        if mid == 0:
            low = mid + 1
            continue

        gross_risk = mid * stop_dist
        cost_breakdown = calculate_trade_transaction_costs(
            side=side_str,
            entry_price=entry_price,
            exit_price=stop_loss,
            quantity=mid,
            config=cost_config,
        )
        total_risk = gross_risk + float(cost_breakdown.total_costs)

        if total_risk <= risk_amount:
            best_q = mid
            low = mid + 1
        else:
            high = mid - 1

    if best_q < min_trade_quantity:
        return 0, risk_qty, max_allowed_qty

    return best_q, risk_qty, max_allowed_qty


@dataclass(frozen=True)
class CapitalAllocationConfig:
    """
    Configuration parameters for intelligent capital allocation and position sizing.

    Capital Allocation & Margin Terminology:
    ----------------------------------------
    1. Account Equity:
       The real-time liquidation value of the portfolio:
       Equity = Realized Cash + Mark-to-Market Unrealized P&L across open positions.
    2. Margin Collateral:
       The fraction of account equity encumbered/pledged with the broker to initiate and
       maintain an open position. Under leverage L, Margin Required = Gross Notional Exposure / L.
       Margin is an encumbrance on available collateral, NOT an expense or cash deduction.
    3. Gross Notional Exposure:
       The full market value of the underlying securities traded (Quantity * Price).
    4. Available Margin:
       Unencumbered equity available to pledge for new positions:
       Available Margin = max(0.0, (Equity - Reserved Capital) - Allocated Margin).
    5. Leverage Ceiling:
       A configurable software parameter defining the maximum ratio of purchasing power
       to margin collateral (Notional / Margin). Actual permitted leverage depends on the
       broker, instrument, applicable regulatory/exchange margin requirements, and market
       conditions; it is not a guaranteed entitlement.

    Parameters
    ----------
    risk_per_trade_pct:
        Maximum percentage of current portfolio equity to risk on a single trade (default 1.0%).
    max_stock_allocation_pct:
        Maximum fraction of current portfolio equity that may be encumbered as margin collateral
        for an individual stock (default 35.0%).
        The corresponding maximum notional exposure is:
        Max Stock Notional = Current Equity * max_stock_allocation_pct * max_leverage.
        The actual allocation remains constrained by available margin, liquidity reserves, and risk limits.
    max_portfolio_risk_pct:
        Maximum aggregate open portfolio risk across all concurrent positions (default 3.0%).
    reserve_capital_pct:
        Percentage of portfolio equity reserved as liquidity buffer (default 15.0%).
    max_leverage:
        Configurable SignalForge software ceiling for intraday equity simulation (default 5.0x).
        Actual permitted leverage depends on the broker, instrument, applicable margin requirements,
        and market conditions; it is not a universal broker entitlement.
    min_trade_quantity:
        Minimum allowable trade quantity (default 1 share).
    min_free_capital:
        Minimum unencumbered cash required in portfolio (default 0.0).
    include_estimated_round_trip_costs_in_sizing:
        Whether to incorporate estimated round-trip transaction costs (brokerage, STT, exchange charges,
        GST, SEBI charges, stamp duty, slippage) into planned position risk (default True).
        When True, Estimated Total Risk = Gross Stop Risk + Estimated Round-Trip Cost <= Risk Budget.
    cost_config:
        Canonical IntradayCostConfig schedule from Phase 27B used for cost estimation.
        Defaults to DISCOUNT_BROKER_REALISTIC_CONFIG if None.
    conservative_cost_buffer_rate:
        Optional additional proportional safety rate added to risk per share (default 0.0).
    """

    risk_per_trade_pct: float = 0.01
    max_stock_allocation_pct: float = 0.35
    max_portfolio_risk_pct: float = 0.03
    reserve_capital_pct: float = 0.15
    max_leverage: float = 5.0
    min_trade_quantity: int = 1
    min_free_capital: float = 0.0
    include_estimated_round_trip_costs_in_sizing: bool = True
    cost_config: Optional[IntradayCostConfig] = None
    conservative_cost_buffer_rate: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.risk_per_trade_pct, (int, float)) or isinstance(self.risk_per_trade_pct, bool):
            raise TypeError("risk_per_trade_pct must be numeric.")
        if not (0.0 < self.risk_per_trade_pct <= 1.0):
            raise ValueError("risk_per_trade_pct must be between 0.0 and 1.0.")

        if not isinstance(self.max_stock_allocation_pct, (int, float)) or isinstance(self.max_stock_allocation_pct, bool):
            raise TypeError("max_stock_allocation_pct must be numeric.")
        if not (0.0 < self.max_stock_allocation_pct <= 1.0):
            raise ValueError("max_stock_allocation_pct must be between 0.0 and 1.0.")

        if not isinstance(self.max_portfolio_risk_pct, (int, float)) or isinstance(self.max_portfolio_risk_pct, bool):
            raise TypeError("max_portfolio_risk_pct must be numeric.")
        if not (0.0 < self.max_portfolio_risk_pct <= 1.0):
            raise ValueError("max_portfolio_risk_pct must be between 0.0 and 1.0.")

        if self.max_portfolio_risk_pct < self.risk_per_trade_pct:
            raise ValueError("max_portfolio_risk_pct cannot be less than risk_per_trade_pct.")

        if not isinstance(self.reserve_capital_pct, (int, float)) or isinstance(self.reserve_capital_pct, bool):
            raise TypeError("reserve_capital_pct must be numeric.")
        if not (0.0 <= self.reserve_capital_pct < 1.0):
            raise ValueError("reserve_capital_pct must be between 0.0 and 1.0 (exclusive of 1.0).")

        if not isinstance(self.max_leverage, (int, float)) or isinstance(self.max_leverage, bool):
            raise TypeError("max_leverage must be numeric.")
        if self.max_leverage <= 0:
            raise ValueError("max_leverage must be greater than zero.")

        if not isinstance(self.min_trade_quantity, int) or isinstance(self.min_trade_quantity, bool):
            raise TypeError("min_trade_quantity must be an integer.")
        if self.min_trade_quantity < 1:
            raise ValueError("min_trade_quantity must be at least 1.")

        if not isinstance(self.min_free_capital, (int, float)) or isinstance(self.min_free_capital, bool):
            raise TypeError("min_free_capital must be numeric.")
        if self.min_free_capital < 0:
            raise ValueError("min_free_capital cannot be negative.")

        if not isinstance(self.include_estimated_round_trip_costs_in_sizing, bool):
            raise TypeError("include_estimated_round_trip_costs_in_sizing must be a boolean.")

        if not isinstance(self.conservative_cost_buffer_rate, (int, float)) or isinstance(self.conservative_cost_buffer_rate, bool):
            raise TypeError("conservative_cost_buffer_rate must be numeric.")
        if self.conservative_cost_buffer_rate < 0:
            raise ValueError("conservative_cost_buffer_rate cannot be negative.")


@dataclass
class TradeOpportunity:
    """
    Candidate trading opportunity evaluated by the capital allocator.

    Parameters
    ----------
    symbol:
        Market symbol (e.g. 'RELIANCE', 'ICICIBANK').
    side:
        Direction of the trade (Position.LONG or Position.SHORT).
    entry_price:
        Proposed entry execution price.
    stop_loss:
        Protective stop-loss exit price.
    target_price:
        Planned profit target price (optional, used for reward/risk calculation).
    requested_quantity:
        Explicitly requested quantity (0 means dynamically size by risk).
    signal_quality:
        Primary ranking metric: model confidence or signal strength (higher = better).
    reward_risk_ratio:
        Secondary ranking metric: ratio of potential gain to risk (higher = better).
    relative_volume:
        Tertiary ranking metric: liquidity / volume confirmation (higher = better).
    is_tradeable:
        Hard gate: False if halted, in circuit filter, or corporate action blocked.
    timestamp:
        Candidate signal timestamp.
    atr:
        Average True Range at signal generation.
    """

    symbol: str
    side: Position
    entry_price: float
    stop_loss: float
    target_price: float = 0.0
    requested_quantity: int = 0
    signal_quality: float = 1.0
    reward_risk_ratio: float = 0.0
    relative_volume: float = 1.0
    is_tradeable: bool = True
    timestamp: Optional[object] = None
    atr: float = 0.0

    def __post_init__(self) -> None:
        self.symbol = str(self.symbol).strip().upper()
        if isinstance(self.side, str):
            self.side = Position(self.side)
        self.entry_price = float(self.entry_price)
        self.stop_loss = float(self.stop_loss)
        self.target_price = float(self.target_price)
        self.requested_quantity = int(self.requested_quantity)
        self.signal_quality = float(self.signal_quality)
        self.relative_volume = float(self.relative_volume)

        # Auto-compute reward-to-risk ratio if not provided and target_price > 0
        if self.reward_risk_ratio == 0.0 and self.target_price > 0.0:
            stop_dist = abs(self.entry_price - self.stop_loss)
            if stop_dist > 0:
                reward = abs(self.target_price - self.entry_price)
                self.reward_risk_ratio = reward / stop_dist


@dataclass(frozen=True)
class AllocationDecision:
    """
    Structured, auditable decision produced by the capital allocator.
    """

    symbol: str
    accepted: bool
    requested_quantity: int
    allocated_quantity: int
    entry_price: float
    stop_loss: float
    risk_budget: float
    estimated_risk: float
    estimated_margin_required: float
    remaining_available_margin: float
    remaining_portfolio_risk: float
    rejection_reason: Optional[str] = None
    limiting_constraint: Optional[str] = None
    estimated_round_trip_cost: float = 0.0
    gross_risk: float = 0.0


class CapitalAllocator:
    """
    Intelligent Capital Sizing and Multi-Stock Allocation Engine.

    Determines position sizing, margin encumbrances, per-stock allocation ceilings,
    and portfolio aggregate risk budgets for candidate intraday trading opportunities.
    """

    def __init__(self, config: Optional[CapitalAllocationConfig] = None) -> None:
        self.config = config if config is not None else CapitalAllocationConfig()

    def calculate_risk_budget(self, equity: float) -> float:
        """Calculate single-trade risk budget in rupees from current portfolio equity."""
        return max(0.0, float(equity) * self.config.risk_per_trade_pct)

    def calculate_risk_per_share(self, entry_price: float, stop_loss: float) -> float:
        """
        Calculate planned rupee risk per share (pure price distance plus optional safety buffer).
        """
        base_distance = abs(float(entry_price) - float(stop_loss))
        cost_buffer = float(entry_price) * self.config.conservative_cost_buffer_rate
        return base_distance + cost_buffer

    def estimate_round_trip_cost(
        self,
        side: Position | str,
        entry_price: float,
        stop_loss: float,
        quantity: int,
        cost_config: Optional[IntradayCostConfig] = None,
    ) -> float:
        """
        Estimate canonical round-trip transaction costs for a hypothetical trade exiting at stop-loss.
        Uses the canonical Phase 27B transaction cost engine (calculate_trade_transaction_costs).
        Includes brokerage, STT, ETC, SEBI, GST, stamp duty, slippage, and spread.
        """
        if quantity <= 0:
            return 0.0

        cfg = cost_config or self.config.cost_config or DISCOUNT_BROKER_REALISTIC_CONFIG
        side_str = side.value if isinstance(side, Position) else str(side)

        try:
            breakdown = calculate_trade_transaction_costs(
                side=side_str,
                entry_price=float(entry_price),
                exit_price=float(stop_loss),
                quantity=int(quantity),
                config=cfg,
            )
            return float(breakdown.total_costs)
        except Exception:
            return 0.0

    def calculate_candidate_total_risk(
        self,
        side: Position | str,
        entry_price: float,
        stop_loss: float,
        quantity: int,
        cost_config: Optional[IntradayCostConfig] = None,
    ) -> Tuple[float, float, float]:
        """
        Calculate gross risk, estimated round-trip costs, and total planned risk for quantity q.
        Returns (gross_risk, estimated_cost, total_risk).
        """
        if quantity <= 0:
            return 0.0, 0.0, 0.0

        stop_dist = self.calculate_risk_per_share(entry_price, stop_loss)
        gross_risk = float(quantity) * stop_dist

        if self.config.include_estimated_round_trip_costs_in_sizing:
            est_cost = self.estimate_round_trip_cost(
                side=side,
                entry_price=entry_price,
                stop_loss=stop_loss,
                quantity=quantity,
                cost_config=cost_config,
            )
        else:
            est_cost = 0.0

        total_risk = gross_risk + est_cost
        return gross_risk, est_cost, total_risk

    def calculate_existing_open_risk(self, portfolio: PortfolioManager) -> float:
        """
        Calculate total open rupee risk across all active positions in the portfolio.
        Accounts for planned stop distance and estimated transaction costs when enabled.
        """
        total_risk = 0.0
        for pos in portfolio.open_positions.values():
            if pos.risk_amount > 0:
                total_risk += float(pos.risk_amount)
            elif pos.stop_price > 0:
                dist = abs(pos.entry_price - pos.stop_price)
                g_risk = pos.quantity * dist
                if self.config.include_estimated_round_trip_costs_in_sizing:
                    cost = self.estimate_round_trip_cost(
                        side=pos.side,
                        entry_price=pos.entry_price,
                        stop_loss=pos.stop_price,
                        quantity=pos.quantity,
                    )
                else:
                    cost = 0.0
                total_risk += (g_risk + cost)
            elif pos.stop_distance > 0:
                total_risk += pos.quantity * pos.stop_distance
        return total_risk

    def calculate_remaining_portfolio_risk(
        self,
        portfolio: PortfolioManager,
        current_open_risk: Optional[float] = None,
    ) -> float:
        """
        Calculate remaining aggregate portfolio risk capacity in rupees.
        """
        open_risk = (
            current_open_risk
            if current_open_risk is not None
            else self.calculate_existing_open_risk(portfolio)
        )
        total_risk_budget = float(portfolio.equity) * self.config.max_portfolio_risk_pct
        return max(0.0, total_risk_budget - open_risk)

    def calculate_max_stock_notional(self, portfolio: PortfolioManager) -> float:
        """
        Calculate maximum notional exposure capacity permitted for a single stock.

        Max Notional = Current Equity * max_stock_allocation_pct * max_leverage.
        Represents single-stock margin collateral allocation capped at (Equity * max_stock_allocation_pct).
        """
        return (
            float(portfolio.equity)
            * self.config.max_leverage
            * self.config.max_stock_allocation_pct
        )

    def validate_opportunity_inputs(
        self,
        opportunity: TradeOpportunity,
        portfolio: PortfolioManager,
    ) -> Tuple[bool, Optional[str]]:
        """
        Perform hard eligibility checks on candidate opportunity before sizing.
        """
        # 1. Portfolio health check
        if portfolio.is_bankrupt:
            reason = f"Portfolio is bankrupt or protection floor reached ({portfolio.bankruptcy_reason})"
            return False, reason

        if getattr(portfolio, "has_unresolved_liquidations", False):
            return False, "Portfolio has unresolved emergency liquidations pending valid market data"

        if getattr(portfolio, "has_indeterminate_valuation", False):
            reason = f"Portfolio has indeterminate valuation: {getattr(portfolio, 'indeterminate_valuation_reason', 'Uncertain valuation')}"
            return False, reason

        # 2. Hard tradeability check
        if not opportunity.is_tradeable:
            return False, "Opportunity flagged as not tradeable (circuit filter / trading halted)"

        # 3. Duplicate position check
        if opportunity.symbol in portfolio.open_positions:
            return False, f"Position already active for symbol '{opportunity.symbol}'"

        # 4. Price positivity check
        if opportunity.entry_price <= 0:
            return False, "Invalid entry price: must be greater than zero"

        if opportunity.stop_loss <= 0:
            return False, "Invalid stop loss: must be greater than zero"

        # 5. Stop direction sanity
        if opportunity.side == Position.LONG:
            if opportunity.stop_loss >= opportunity.entry_price:
                return (
                    False,
                    f"Invalid stop loss for LONG ({opportunity.stop_loss:.2f} >= entry {opportunity.entry_price:.2f})",
                )
        elif opportunity.side == Position.SHORT:
            if opportunity.stop_loss <= opportunity.entry_price:
                return (
                    False,
                    f"Invalid stop loss for SHORT ({opportunity.stop_loss:.2f} <= entry {opportunity.entry_price:.2f})",
                )

        # 6. Stop distance positivity
        stop_dist = abs(opportunity.entry_price - opportunity.stop_loss)
        if stop_dist <= 0:
            return False, "Stop loss distance cannot be zero"

        return True, None

    def evaluate_opportunity(
        self,
        opportunity: TradeOpportunity,
        portfolio: PortfolioManager,
        simulated_available_margin: Optional[float] = None,
        simulated_open_risk: Optional[float] = None,
    ) -> AllocationDecision:
        """
        Evaluate a single candidate opportunity against capital, margin, cost, and risk constraints.

        Purity guarantee: Does NOT mutate the underlying PortfolioManager.
        """
        entry_price = float(opportunity.entry_price)
        stop_loss = float(opportunity.stop_loss)
        equity = float(portfolio.equity)

        # Pre-validation
        valid, failure_reason = self.validate_opportunity_inputs(opportunity, portfolio)
        if not valid:
            return AllocationDecision(
                symbol=opportunity.symbol,
                accepted=False,
                requested_quantity=opportunity.requested_quantity,
                allocated_quantity=0,
                entry_price=entry_price,
                stop_loss=stop_loss,
                risk_budget=0.0,
                estimated_risk=0.0,
                estimated_margin_required=0.0,
                remaining_available_margin=(
                    simulated_available_margin
                    if simulated_available_margin is not None
                    else portfolio.available_margin
                ),
                remaining_portfolio_risk=self.calculate_remaining_portfolio_risk(
                    portfolio, simulated_open_risk
                ),
                rejection_reason=failure_reason,
                limiting_constraint="ELIGIBILITY",
                estimated_round_trip_cost=0.0,
                gross_risk=0.0,
            )

        # Determine effective available margin and open risk
        avail_margin = (
            simulated_available_margin
            if simulated_available_margin is not None
            else portfolio.available_margin
        )
        rem_port_risk = self.calculate_remaining_portfolio_risk(
            portfolio, simulated_open_risk
        )

        risk_budget = self.calculate_risk_budget(equity)
        effective_risk_budget = min(risk_budget, rem_port_risk)

        stop_dist = self.calculate_risk_per_share(entry_price, stop_loss)
        margin_per_share = entry_price / self.config.max_leverage

        # --------------------------------------------------------------------
        # Non-cost upper bounds
        # --------------------------------------------------------------------
        q_stock = math.floor(self.calculate_max_stock_notional(portfolio) / entry_price)
        q_margin = math.floor(avail_margin / margin_per_share) if margin_per_share > 0 else 0
        q_gross_risk = math.floor(effective_risk_budget / stop_dist) if stop_dist > 0 else 0
        req_q = opportunity.requested_quantity if opportunity.requested_quantity > 0 else q_gross_risk

        upper_bound = min(q_stock, q_margin, req_q, q_gross_risk)

        if upper_bound < self.config.min_trade_quantity:
            # Determine specific limiting factor for rejection
            if q_margin < self.config.min_trade_quantity:
                min_constraint = "AVAILABLE_MARGIN"
                reason = (
                    f"Insufficient available margin ({avail_margin:.2f}) for "
                    f"minimum trade quantity ({self.config.min_trade_quantity} shares require {margin_per_share * self.config.min_trade_quantity:.2f})"
                )
            elif q_stock < self.config.min_trade_quantity:
                min_constraint = "STOCK_ALLOCATION_LIMIT"
                reason = (
                    f"Per-stock allocation limit ({self.calculate_max_stock_notional(portfolio):.2f}) prevents "
                    f"minimum trade quantity ({self.config.min_trade_quantity})"
                )
            elif rem_port_risk < stop_dist * self.config.min_trade_quantity:
                min_constraint = "PORTFOLIO_RISK_LIMIT"
                reason = (
                    f"Aggregate portfolio risk budget exhausted (remaining {rem_port_risk:.2f}, "
                    f"minimum quantity requires {stop_dist * self.config.min_trade_quantity:.2f})"
                )
            elif req_q < self.config.min_trade_quantity:
                min_constraint = "REQUESTED"
                reason = "Requested quantity is below minimum trade quantity"
            else:
                min_constraint = "RISK_BUDGET"
                reason = (
                    f"Risk per share ({stop_dist:.2f}) exceeds risk budget "
                    f"({risk_budget:.2f}) for minimum quantity ({self.config.min_trade_quantity})"
                )

            return AllocationDecision(
                symbol=opportunity.symbol,
                accepted=False,
                requested_quantity=req_q,
                allocated_quantity=0,
                entry_price=entry_price,
                stop_loss=stop_loss,
                risk_budget=risk_budget,
                estimated_risk=0.0,
                estimated_margin_required=0.0,
                remaining_available_margin=avail_margin,
                remaining_portfolio_risk=rem_port_risk,
                rejection_reason=reason,
                limiting_constraint=min_constraint,
                estimated_round_trip_cost=0.0,
                gross_risk=0.0,
            )

        # --------------------------------------------------------------------
        # Cost-Aware Quantity Solving (Monotonic Binary Search)
        # --------------------------------------------------------------------
        if not self.config.include_estimated_round_trip_costs_in_sizing:
            final_quantity = upper_bound
            g_risk, est_cost, tot_risk = self.calculate_candidate_total_risk(
                side=opportunity.side,
                entry_price=entry_price,
                stop_loss=stop_loss,
                quantity=final_quantity,
            )
        else:
            low = 0
            high = upper_bound
            best_q = 0
            best_cost = 0.0
            best_g_risk = 0.0
            best_tot_risk = 0.0

            while low <= high:
                mid = (low + high) // 2
                if mid == 0:
                    low = mid + 1
                    continue

                g_r, c_est, t_r = self.calculate_candidate_total_risk(
                    side=opportunity.side,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    quantity=mid,
                )

                if t_r <= effective_risk_budget:
                    best_q = mid
                    best_cost = c_est
                    best_g_risk = g_r
                    best_tot_risk = t_r
                    low = mid + 1  # Seek larger valid quantity
                else:
                    high = mid - 1 # Exceeds budget, search lower

            if best_q < self.config.min_trade_quantity:
                # Check min trade cost
                min_q = self.config.min_trade_quantity
                min_g, min_c, min_tot = self.calculate_candidate_total_risk(
                    side=opportunity.side,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    quantity=min_q,
                )
                return AllocationDecision(
                    symbol=opportunity.symbol,
                    accepted=False,
                    requested_quantity=req_q,
                    allocated_quantity=0,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    risk_budget=risk_budget,
                    estimated_risk=0.0,
                    estimated_margin_required=0.0,
                    remaining_available_margin=avail_margin,
                    remaining_portfolio_risk=rem_port_risk,
                    rejection_reason=(
                        f"Estimated total risk ({min_tot:.2f} = gross {min_g:.2f} + cost {min_c:.2f}) "
                        f"exceeds risk budget ({effective_risk_budget:.2f}) for minimum quantity ({min_q})"
                    ),
                    limiting_constraint="RISK_BUDGET",
                    estimated_round_trip_cost=0.0,
                    gross_risk=0.0,
                )

            final_quantity = best_q
            est_cost = best_cost
            g_risk = best_g_risk
            tot_risk = best_tot_risk

        # Determine limiting constraint
        if final_quantity == q_margin and q_margin < q_gross_risk and q_margin < q_stock:
            limiting_constraint = "AVAILABLE_MARGIN"
        elif final_quantity == q_stock and q_stock < q_gross_risk and q_stock < q_margin:
            limiting_constraint = "STOCK_ALLOCATION_LIMIT"
        elif req_q != q_gross_risk and final_quantity == req_q:
            limiting_constraint = "REQUESTED"
        elif rem_port_risk < risk_budget and tot_risk > rem_port_risk - (stop_dist + 1.0):
            limiting_constraint = "PORTFOLIO_RISK_LIMIT"
        else:
            limiting_constraint = "RISK_BUDGET"

        estimated_margin = final_quantity * margin_per_share
        rem_margin_after = max(0.0, avail_margin - estimated_margin)
        rem_risk_after = max(0.0, rem_port_risk - tot_risk)

        return AllocationDecision(
            symbol=opportunity.symbol,
            accepted=True,
            requested_quantity=req_q,
            allocated_quantity=final_quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_budget=risk_budget,
            estimated_risk=tot_risk,
            estimated_margin_required=estimated_margin,
            remaining_available_margin=rem_margin_after,
            remaining_portfolio_risk=rem_risk_after,
            rejection_reason=None,
            limiting_constraint=limiting_constraint,
            estimated_round_trip_cost=est_cost,
            gross_risk=g_risk,
        )

    def rank_opportunities(
        self,
        opportunities: List[TradeOpportunity],
    ) -> List[TradeOpportunity]:
        """
        Deterministically sort opportunities by quality metrics with alphabetical tie-breaking:
        1. signal_quality descending (higher quality first)
        2. reward_risk_ratio descending (higher R:R first)
        3. relative_volume descending (higher liquidity first)
        4. symbol ascending (lexicographical tie-breaker)
        """
        return sorted(
            opportunities,
            key=lambda opp: (
                -float(opp.signal_quality),
                -float(opp.reward_risk_ratio),
                -float(opp.relative_volume),
                str(opp.symbol).strip().upper(),
            ),
        )

    def allocate_batch(
        self,
        opportunities: List[TradeOpportunity],
        portfolio: PortfolioManager,
    ) -> List[AllocationDecision]:
        """
        Evaluate a batch of candidate opportunities in deterministic ranked order.

        Simulates sequential margin encumbrance and portfolio risk addition across the batch,
        ensuring later candidates properly account for allocations granted to higher-priority candidates.

        Purity guarantee: Does NOT mutate the underlying PortfolioManager.
        """
        if not opportunities:
            return []

        # 1. Partition into eligible and ineligible
        eligible: List[TradeOpportunity] = []
        immediate_rejections: List[AllocationDecision] = []

        for opp in opportunities:
            valid, reason = self.validate_opportunity_inputs(opp, portfolio)
            if not valid:
                dec = AllocationDecision(
                    symbol=opp.symbol,
                    accepted=False,
                    requested_quantity=opp.requested_quantity,
                    allocated_quantity=0,
                    entry_price=float(opp.entry_price),
                    stop_loss=float(opp.stop_loss),
                    risk_budget=0.0,
                    estimated_risk=0.0,
                    estimated_margin_required=0.0,
                    remaining_available_margin=portfolio.available_margin,
                    remaining_portfolio_risk=self.calculate_remaining_portfolio_risk(portfolio),
                    rejection_reason=reason,
                    limiting_constraint="ELIGIBILITY",
                    estimated_round_trip_cost=0.0,
                    gross_risk=0.0,
                )
                immediate_rejections.append(dec)
            else:
                eligible.append(opp)

        # 2. Deterministically rank eligible candidates
        ranked_eligible = self.rank_opportunities(eligible)

        # 3. Sequentially evaluate ranked candidates with virtual capacity tracking
        sim_avail_margin = portfolio.available_margin
        sim_open_risk = self.calculate_existing_open_risk(portfolio)
        batch_decisions: List[AllocationDecision] = []

        # Map to track already-allocated symbols within this single batch
        allocated_in_batch: set[str] = set()

        for opp in ranked_eligible:
            if opp.symbol in allocated_in_batch:
                dec = AllocationDecision(
                    symbol=opp.symbol,
                    accepted=False,
                    requested_quantity=opp.requested_quantity,
                    allocated_quantity=0,
                    entry_price=float(opp.entry_price),
                    stop_loss=float(opp.stop_loss),
                    risk_budget=self.calculate_risk_budget(portfolio.equity),
                    estimated_risk=0.0,
                    estimated_margin_required=0.0,
                    remaining_available_margin=sim_avail_margin,
                    remaining_portfolio_risk=self.calculate_remaining_portfolio_risk(
                        portfolio, sim_open_risk
                    ),
                    rejection_reason=f"Duplicate candidate for symbol '{opp.symbol}' already allocated in current batch",
                    limiting_constraint="DUPLICATE_BATCH",
                    estimated_round_trip_cost=0.0,
                    gross_risk=0.0,
                )
                batch_decisions.append(dec)
                continue

            dec = self.evaluate_opportunity(
                opportunity=opp,
                portfolio=portfolio,
                simulated_available_margin=sim_avail_margin,
                simulated_open_risk=sim_open_risk,
            )

            batch_decisions.append(dec)

            if dec.accepted and dec.allocated_quantity > 0:
                allocated_in_batch.add(opp.symbol)
                sim_avail_margin = dec.remaining_available_margin
                sim_open_risk += dec.estimated_risk

        return batch_decisions + immediate_rejections
