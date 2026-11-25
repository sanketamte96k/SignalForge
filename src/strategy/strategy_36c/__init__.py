"""
SignalForge — Phase 36C Strategy Package
"""

from src.strategy.strategy_36c.config import (
    CFG0_BASELINE_OFFICIAL,
    CFG0_BASELINE_STRESS,
    CFG1_REGIME_OFFICIAL,
    CFG1_REGIME_STRESS,
    CFG2_ATR_STOP_OFFICIAL,
    CFG2_ATR_STOP_STRESS,
    CFG3_REGIME_ATR_OFFICIAL,
    CFG3_REGIME_ATR_STRESS,
    CFG4_DYNAMIC_CASH_OFFICIAL,
    CFG4_DYNAMIC_CASH_STRESS,
    CostScenario,
    RebalanceFrequency,
    Strategy36CConfig,
)
from src.strategy.strategy_36c.cross_sectional_ranker import (
    CrossSectionalRanker,
    StockRankEntry,
)
from src.strategy.strategy_36c.indicators import (
    compute_stock_atr_dict,
    load_nifty_regime_series,
)
from src.strategy.strategy_36c.performance_metrics import (
    BootstrapAlphaResult,
    DrawdownEpisode,
    MonthlyPerformanceEntry,
    PerformanceMetricsEngine,
    SectorPerformanceEntry,
    StockContributionEntry,
    YearlyPerformanceEntry,
)
from src.strategy.strategy_36c.portfolio_constructor import (
    HoldingPosition,
    PortfolioConstructor,
    RebalancePlan,
)
from src.strategy.strategy_36c.rebalance_simulator import (
    CompletedTrade36C,
    DailyPortfolioSnapshot,
    RebalanceSimulator,
    SimulationResult36C,
)
from src.strategy.strategy_36c.risk_engine import (
    RiskEngine36C,
    RiskMetrics36C,
)

__all__ = [
    "CFG0_BASELINE_OFFICIAL",
    "CFG0_BASELINE_STRESS",
    "CFG1_REGIME_OFFICIAL",
    "CFG1_REGIME_STRESS",
    "CFG2_ATR_STOP_OFFICIAL",
    "CFG2_ATR_STOP_STRESS",
    "CFG3_REGIME_ATR_OFFICIAL",
    "CFG3_REGIME_ATR_STRESS",
    "CFG4_DYNAMIC_CASH_OFFICIAL",
    "CFG4_DYNAMIC_CASH_STRESS",
    "CostScenario",
    "RebalanceFrequency",
    "Strategy36CConfig",
    "CrossSectionalRanker",
    "StockRankEntry",
    "load_nifty_regime_series",
    "compute_stock_atr_dict",
    "HoldingPosition",
    "PortfolioConstructor",
    "RebalancePlan",
    "CompletedTrade36C",
    "DailyPortfolioSnapshot",
    "RebalanceSimulator",
    "SimulationResult36C",
    "RiskEngine36C",
    "RiskMetrics36C",
    "PerformanceMetricsEngine",
    "MonthlyPerformanceEntry",
    "YearlyPerformanceEntry",
    "StockContributionEntry",
    "SectorPerformanceEntry",
    "DrawdownEpisode",
    "BootstrapAlphaResult",
]
