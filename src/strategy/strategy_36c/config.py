"""
SignalForge — Phase 36C: Controlled Dynamic Cash Relative Strength Configuration
================================================================================
File: src/strategy/strategy_36c/config.py

Defines configuration parameters, pre-registered configurations (CFG-0 to CFG-4),
execution rules, cost scenarios, and risk controls for Phase 36C.
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
class Strategy36CConfig:
    """Configuration for Phase 36C strategy experiments."""
    config_id: str
    rebalance_period_sessions: int = 10  # Baseline 10 sessions (bi-weekly)
    initial_capital: float = 100000.0   # ₹1,00,000 initial capital
    max_holdings: int = 10              # Maximum 10 concurrent stock positions
    target_position_pct: float = 0.10   # Target 10% allocation per position

    # Lookback windows (sessions)
    lookback_fast: int = 20   # 20-session return
    lookback_mid: int = 40    # 40-session return
    lookback_slow: int = 60   # 60-session return

    # CRSS weights
    weight_fast: float = 0.20
    weight_mid: float = 0.40
    weight_slow: float = 0.40

    # Entry rules
    entry_rank_max: int = 10  # Select stocks ranked in the top 10 by CRSS

    # Exit rules
    exit_percentile_threshold: float = 0.70  # CFG-0..3 baseline: exit if percentile < 0.70
    exit_rank_threshold: Optional[int] = None # CFG-4: exit if rank > 25

    # Sector constraint
    max_sector_exposure_pct: float = 0.30  # Max 30% per sector

    # Regime Filter Settings (CFG-1, CFG-3)
    use_regime_filter: bool = False
    regime_nifty_sma_fast: int = 50   # Nifty SMA50
    regime_nifty_sma_slow: int = 200  # Nifty SMA200

    # ATR Trailing Stop Settings (CFG-2, CFG-3)
    use_atr_stop: bool = False
    atr_stop_multiplier: float = 3.0  # 3 x ATR(14)
    atr_period: int = 14

    # Execution & Cost assumptions
    cost_scenario: CostScenario = CostScenario.OFFICIAL
    execution_slippage_bps: float = 5.0    # 5 bps for Official, 15 bps for Stress
    use_stress_costs: bool = False

    # Risk-free rate for Sharpe calculation
    annual_risk_free_rate: float = 0.062   # 6.2% annual


# Pre-registered configurations (Official & Stress)

# CFG-0: Baseline (Phase 36B CFG-1)
CFG0_BASELINE_OFFICIAL = Strategy36CConfig(
    config_id="CFG-0_BASELINE_OFFICIAL",
    use_regime_filter=False,
    use_atr_stop=False,
    exit_rank_threshold=None,
    exit_percentile_threshold=0.70,
    cost_scenario=CostScenario.OFFICIAL,
    execution_slippage_bps=5.0,
    use_stress_costs=False,
)

CFG0_BASELINE_STRESS = Strategy36CConfig(
    config_id="CFG-0_BASELINE_STRESS",
    use_regime_filter=False,
    use_atr_stop=False,
    exit_rank_threshold=None,
    exit_percentile_threshold=0.70,
    cost_scenario=CostScenario.STRESS,
    execution_slippage_bps=15.0,
    use_stress_costs=True,
)

# CFG-1: Nifty regime filter only
CFG1_REGIME_OFFICIAL = Strategy36CConfig(
    config_id="CFG-1_REGIME_OFFICIAL",
    use_regime_filter=True,
    use_atr_stop=False,
    exit_rank_threshold=None,
    exit_percentile_threshold=0.70,
    cost_scenario=CostScenario.OFFICIAL,
    execution_slippage_bps=5.0,
    use_stress_costs=False,
)

CFG1_REGIME_STRESS = Strategy36CConfig(
    config_id="CFG-1_REGIME_STRESS",
    use_regime_filter=True,
    use_atr_stop=False,
    exit_rank_threshold=None,
    exit_percentile_threshold=0.70,
    cost_scenario=CostScenario.STRESS,
    execution_slippage_bps=15.0,
    use_stress_costs=True,
)

# CFG-2: ATR trailing stop only (3 x ATR14)
CFG2_ATR_STOP_OFFICIAL = Strategy36CConfig(
    config_id="CFG-2_ATR_STOP_OFFICIAL",
    use_regime_filter=False,
    use_atr_stop=True,
    atr_stop_multiplier=3.0,
    atr_period=14,
    exit_rank_threshold=None,
    exit_percentile_threshold=0.70,
    cost_scenario=CostScenario.OFFICIAL,
    execution_slippage_bps=5.0,
    use_stress_costs=False,
)

CFG2_ATR_STOP_STRESS = Strategy36CConfig(
    config_id="CFG-2_ATR_STOP_STRESS",
    use_regime_filter=False,
    use_atr_stop=True,
    atr_stop_multiplier=3.0,
    atr_period=14,
    exit_rank_threshold=None,
    exit_percentile_threshold=0.70,
    cost_scenario=CostScenario.STRESS,
    execution_slippage_bps=15.0,
    use_stress_costs=True,
)

# CFG-3: Regime filter + ATR trailing stop
CFG3_REGIME_ATR_OFFICIAL = Strategy36CConfig(
    config_id="CFG-3_REGIME_ATR_OFFICIAL",
    use_regime_filter=True,
    use_atr_stop=True,
    atr_stop_multiplier=3.0,
    atr_period=14,
    exit_rank_threshold=None,
    exit_percentile_threshold=0.70,
    cost_scenario=CostScenario.OFFICIAL,
    execution_slippage_bps=5.0,
    use_stress_costs=False,
)

CFG3_REGIME_ATR_STRESS = Strategy36CConfig(
    config_id="CFG-3_REGIME_ATR_STRESS",
    use_regime_filter=True,
    use_atr_stop=True,
    atr_stop_multiplier=3.0,
    atr_period=14,
    exit_rank_threshold=None,
    exit_percentile_threshold=0.70,
    cost_scenario=CostScenario.STRESS,
    execution_slippage_bps=15.0,
    use_stress_costs=True,
)

# CFG-4: Dynamic cash and ranking-based exits (exit rank > 25)
CFG4_DYNAMIC_CASH_OFFICIAL = Strategy36CConfig(
    config_id="CFG-4_DYNAMIC_CASH_OFFICIAL",
    use_regime_filter=False,
    use_atr_stop=False,
    exit_rank_threshold=25,
    exit_percentile_threshold=0.70,
    cost_scenario=CostScenario.OFFICIAL,
    execution_slippage_bps=5.0,
    use_stress_costs=False,
)

CFG4_DYNAMIC_CASH_STRESS = Strategy36CConfig(
    config_id="CFG-4_DYNAMIC_CASH_STRESS",
    use_regime_filter=False,
    use_atr_stop=False,
    exit_rank_threshold=25,
    exit_percentile_threshold=0.70,
    cost_scenario=CostScenario.STRESS,
    execution_slippage_bps=15.0,
    use_stress_costs=True,
)
