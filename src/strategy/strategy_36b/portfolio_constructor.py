"""
SignalForge — Phase 36B: Portfolio Constructor & Rebalance Rule Engine
======================================================================
File: src/strategy/strategy_36b/portfolio_constructor.py

Implements equal-weight portfolio construction, hysteresis-buffer exit rules,
top-10 CRSS entry selection, and sector concentration limits (max 30% per sector).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Set, Tuple

from src.strategy.strategy_36b.config import Strategy36BConfig
from src.strategy.strategy_36b.cross_sectional_ranker import StockRankEntry


@dataclass
class HoldingPosition:
    """Represents an active holding position in the portfolio."""
    symbol: str
    sector: str
    isin: str
    quantity: int
    entry_date: date
    effective_entry_price: float
    last_close_price: float

    @property
    def market_value(self) -> float:
        return self.quantity * self.last_close_price


@dataclass(frozen=True)
class RebalancePlan:
    """Plan specifying positions to exit and new positions to enter."""
    signal_date: date
    execution_date: date
    symbols_to_exit: List[str]
    symbols_to_enter: List[StockRankEntry]
    retained_symbols: List[str]
    notes: List[str]


class PortfolioConstructor:
    """
    Constructs target portfolios based on cross-sectional rankings and project constraints.
    """

    def __init__(self, config: Strategy36BConfig, isin_map: Dict[str, str]) -> None:
        self.config = config
        self.isin_map = isin_map

    def generate_rebalance_plan(
        self,
        signal_date: date,
        execution_date: date,
        current_holdings: Dict[str, HoldingPosition],
        rankings: List[StockRankEntry],
        current_equity: float,
    ) -> RebalancePlan:
        """
        Determines exits and entries for the upcoming rebalance session.
        """
        notes: List[str] = []
        rank_lookup = {r.symbol: r for r in rankings}

        # 1. Evaluate Exits for existing holdings
        symbols_to_exit: List[str] = []
        retained_symbols: List[str] = []

        for sym, pos in current_holdings.items():
            if sym not in rank_lookup:
                # Delisted, suspended, or missing data -> mandatory exit
                symbols_to_exit.append(sym)
                notes.append(f"Exit {sym}: Missing from active rankings on {signal_date}")
                continue

            rank_entry = rank_lookup[sym]
            # Exit rule: CRSS falls below 70th percentile of universe
            if rank_entry.crss_percentile < self.config.exit_percentile_threshold:
                symbols_to_exit.append(sym)
                notes.append(
                    f"Exit {sym}: CRSS percentile {rank_entry.crss_percentile:.3f} "
                    f"dropped below threshold {self.config.exit_percentile_threshold:.2f} "
                    f"(Rank #{rank_entry.universe_rank})"
                )
            else:
                retained_symbols.append(sym)

        # 2. Calculate sector exposure of retained holdings
        sector_counts: Dict[str, int] = {}
        for sym in retained_symbols:
            sec = current_holdings[sym].sector
            sector_counts[sec] = sector_counts.get(sec, 0) + 1

        # Maximum allowable stocks in any single sector
        # For equal weight 10-stock portfolio, 30% max sector = at most 3 stocks per sector
        max_stocks_per_sector = int(self.config.max_holdings * self.config.max_sector_exposure_pct)

        # 3. Determine available slots for new entries
        available_slots = self.config.max_holdings - len(retained_symbols)
        symbols_to_enter: List[StockRankEntry] = []

        if available_slots > 0:
            # Candidates must be in top 10 CRSS rankings
            top_candidates = [
                r for r in rankings
                if r.universe_rank <= self.config.entry_rank_max
                and r.symbol not in retained_symbols
                and r.symbol not in symbols_to_exit
            ]

            for cand in top_candidates:
                if len(symbols_to_enter) >= available_slots:
                    break

                cand_sector = cand.sector
                current_sector_count = sector_counts.get(cand_sector, 0)

                # Check sector concentration constraint
                if current_sector_count + 1 > max_stocks_per_sector:
                    notes.append(
                        f"Skip {cand.symbol} (#{cand.universe_rank}): Sector '{cand_sector}' "
                        f"at limit ({current_sector_count}/{max_stocks_per_sector})"
                    )
                    continue

                symbols_to_enter.append(cand)
                sector_counts[cand_sector] = current_sector_count + 1

        if len(retained_symbols) + len(symbols_to_enter) < self.config.max_holdings:
            held_total = len(retained_symbols) + len(symbols_to_enter)
            notes.append(
                f"Holding {held_total} stocks (below max {self.config.max_holdings}) "
                f"due to top-10 candidate exhaustion or sector limits; cash preserved."
            )

        return RebalancePlan(
            signal_date=signal_date,
            execution_date=execution_date,
            symbols_to_exit=symbols_to_exit,
            symbols_to_enter=symbols_to_enter,
            retained_symbols=retained_symbols,
            notes=notes,
        )
