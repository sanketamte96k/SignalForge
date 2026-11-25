"""
SignalForge — Phase 36B: Long-Only Relative Strength Strategy Configuration
===========================================================================
File: src/strategy/strategy_36b/config.py

Defines configuration parameters, execution rules, cost profiles, and constraints
for the Phase 36B Cross-Sectional Relative Strength strategy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class RebalanceFrequency(str, Enum):
    """Rebalance schedule frequency."""
    BI_WEEKLY = "BI_WEEKLY"  # Every 10 trading sessions (~2 calendar weeks)
    MONTHLY = "MONTHLY"      # Every 20 trading sessions (~1 calendar month)


class CostScenario(str, Enum):
    """Transaction cost scenario."""
    OFFICIAL = "OFFICIAL"  # Statutory NSE rates (₹325/cr 2017-Mar 2019, STT 0.1%, DP ₹15.93, 5 bps slippage)
    STRESS = "STRESS"      # Stress rates (statutory rates + 25% surcharge, 15 bps slippage)


@dataclass(frozen=True)
class Strategy36BConfig:
    """Configuration for Phase 36B Long-Only Relative Strength strategy."""
    config_id: str
    rebalance_frequency: RebalanceFrequency = RebalanceFrequency.BI_WEEKLY
    rebalance_period_sessions: int = 10  # 10 for BI_WEEKLY, 20 for MONTHLY
    initial_capital: float = 100000.0   # ₹1,00,000 initial research capital
    max_holdings: int = 10              # Maximum 10 concurrent stock positions
    target_position_pct: float = 0.10   # Target 10% allocation per position

    # Lookback windows (sessions)
    lookback_fast: int = 20   # 20-session (~1 month) return
    lookback_mid: int = 40    # 40-session (~2 month) return
    lookback_slow: int = 60   # 60-session (~3 month) return

    # Composite Relative Strength Score (CRSS) weights
    weight_fast: float = 0.20
    weight_mid: float = 0.40
    weight_slow: float = 0.40

    # Entry and Exit rules
    entry_rank_max: int = 10               # Select stocks ranked in the top 10 by CRSS
    exit_percentile_threshold: float = 0.70  # Exit holding if its CRSS drops below 70th percentile

    # Portfolio constraints
    max_sector_exposure_pct: float = 0.30  # Maximum 30% of total portfolio value in any single sector

    # Execution & Cost assumptions
    cost_scenario: CostScenario = CostScenario.OFFICIAL
    execution_slippage_bps: float = 5.0    # 5 bps for Official, 15 bps for Stress
    use_stress_costs: bool = False

    # Risk-free rate for Sharpe ratio calculation (CCIL 91-day T-Bill historical avg)
    annual_risk_free_rate: float = 0.062   # 6.2% annual risk-free rate


# Pre-registered configurations
CFG1_BIWEEKLY_OFFICIAL = Strategy36BConfig(
    config_id="CFG-1_BIWEEKLY_OFFICIAL",
    rebalance_frequency=RebalanceFrequency.BI_WEEKLY,
    rebalance_period_sessions=10,
    cost_scenario=CostScenario.OFFICIAL,
    execution_slippage_bps=5.0,
    use_stress_costs=False,
)

CFG1_BIWEEKLY_STRESS = Strategy36BConfig(
    config_id="CFG-1_BIWEEKLY_STRESS",
    rebalance_frequency=RebalanceFrequency.BI_WEEKLY,
    rebalance_period_sessions=10,
    cost_scenario=CostScenario.STRESS,
    execution_slippage_bps=15.0,
    use_stress_costs=True,
)

CFG2_MONTHLY_OFFICIAL = Strategy36BConfig(
    config_id="CFG-2_MONTHLY_OFFICIAL",
    rebalance_frequency=RebalanceFrequency.MONTHLY,
    rebalance_period_sessions=20,
    cost_scenario=CostScenario.OFFICIAL,
    execution_slippage_bps=5.0,
    use_stress_costs=False,
)

CFG2_MONTHLY_STRESS = Strategy36BConfig(
    config_id="CFG-2_MONTHLY_STRESS",
    rebalance_frequency=RebalanceFrequency.MONTHLY,
    rebalance_period_sessions=20,
    cost_scenario=CostScenario.STRESS,
    execution_slippage_bps=15.0,
    use_stress_costs=True,
)
