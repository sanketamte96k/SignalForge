"""
SignalForge — Phase 36C: Portfolio Constructor & Rebalance Engine
=================================================================
File: src/strategy/strategy_36c/portfolio_constructor.py

Implements hysteresis exit rules (<70th percentile or >25 rank), regime-gated
entry permissions, and 30% sector concentration limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Set, Tuple

from src.strategy.strategy_36c.config import Strategy36CConfig
from src.strategy.strategy_36c.cross_sectional_ranker import StockRankEntry


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
    highest_close_since_entry: float
    current_atr_stop: float  # Current 3 x ATR(14) trailing stop level

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

    def __init__(self, config: Strategy36CConfig, isin_map: Dict[str, str]) -> None:
        self.config = config
        self.isin_map = isin_map

    def generate_rebalance_plan(
        self,
        signal_date: date,
        execution_date: date,
        current_holdings: Dict[str, HoldingPosition],
        rankings: List[StockRankEntry],
        is_bull_regime: bool,
    ) -> RebalancePlan:
        """
        Determines exits and entries for the upcoming rebalance session.
        """
        notes: List[str] = []
        rank_lookup = {r.symbol: r for r in rankings}

        symbols_to_exit: List[str] = []
        retained_symbols: List[str] = []

        # If Regime filter is enabled and regime is BEAR: Mandatory liquidation to cash!
        if self.config.use_regime_filter and not is_bull_regime:
            for sym in current_holdings.keys():
                symbols_to_exit.append(sym)
                notes.append(f"Exit {sym}: Bear Regime active on {signal_date}; moving to cash.")
            return RebalancePlan(
                signal_date=signal_date,
                execution_date=execution_date,
                symbols_to_exit=symbols_to_exit,
                symbols_to_enter=[],
                retained_symbols=[],
                notes=notes,
            )

        # 1. Evaluate Exits for existing holdings
        for sym, pos in current_holdings.items():
            if sym not in rank_lookup:
                symbols_to_exit.append(sym)
                notes.append(f"Exit {sym}: Missing from active rankings on {signal_date}")
                continue

            rank_entry = rank_lookup[sym]

            # Exit rule check
            if self.config.exit_rank_threshold is not None:
                # CFG-4: Exit when rank falls outside the top 25 (rank > 25)
                if rank_entry.universe_rank > self.config.exit_rank_threshold:
                    symbols_to_exit.append(sym)
                    notes.append(
                        f"Exit {sym}: Universe rank #{rank_entry.universe_rank} fell outside top {self.config.exit_rank_threshold}"
                    )
                else:
                    retained_symbols.append(sym)
            else:
                # CFG-0..3: Exit when CRSS falls below 70th percentile of universe
                if rank_entry.crss_percentile < self.config.exit_percentile_threshold:
                    symbols_to_exit.append(sym)
                    notes.append(
                        f"Exit {sym}: CRSS percentile {rank_entry.crss_percentile:.3f} "
                        f"dropped below {self.config.exit_percentile_threshold:.2f} (Rank #{rank_entry.universe_rank})"
                    )
                else:
                    retained_symbols.append(sym)

        # 2. Sector allocations of retained holdings
        sector_counts: Dict[str, int] = {}
        for sym in retained_symbols:
            sec = current_holdings[sym].sector
            sector_counts[sec] = sector_counts.get(sec, 0) + 1

        max_stocks_per_sector = int(self.config.max_holdings * self.config.max_sector_exposure_pct)

        # 3. Available slots for new entries
        available_slots = self.config.max_holdings - len(retained_symbols)
        symbols_to_enter: List[StockRankEntry] = []

        if available_slots > 0:
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

                if current_sector_count + 1 > max_stocks_per_sector:
                    notes.append(
                        f"Skip {cand.symbol} (#{cand.universe_rank}): Sector '{cand_sector}' "
                        f"at limit ({current_sector_count}/{max_stocks_per_sector})"
                    )
                    continue

                symbols_to_enter.append(cand)
                sector_counts[cand_sector] = current_sector_count + 1

        return RebalancePlan(
            signal_date=signal_date,
            execution_date=execution_date,
            symbols_to_exit=symbols_to_exit,
            symbols_to_enter=symbols_to_enter,
            retained_symbols=retained_symbols,
            notes=notes,
        )
