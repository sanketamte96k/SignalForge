"""SignalForge validation components."""

from src.validation.approval import (
    ApprovalResult,
    ApprovalValidator,
)
from src.validation.causality import (
    CausalityResult,
    CausalityValidator,
)
from src.validation.cost_slippage import (
    CostSlippageResult,
    CostSlippageScenario,
    CostSlippageValidator,
)
from src.validation.data_availability import (
    DataAvailabilityChecker,
    DataAvailabilityResult,
)
from src.validation.data_quality import (
    DataQualityChecker,
    DataQualityResult,
)
from src.validation.historical_backtest import (
    HistoricalBacktestResult,
    HistoricalBacktestValidator,
)
from src.validation.indicator_compatibility import (
    IndicatorCompatibilityChecker,
    IndicatorCompatibilityResult,
)
from src.validation.regime_oos import (
    DIRECTION_REGIMES,
    VOLATILITY_REGIMES,
    OOSMetrics,
    RegimeMetrics,
    RegimeOOSResult,
    RegimeOOSValidator,
)

__all__ = [
    "ApprovalResult",
    "ApprovalValidator",
    "CausalityResult",
    "CausalityValidator",
    "CostSlippageResult",
    "CostSlippageScenario",
    "CostSlippageValidator",
    "DataAvailabilityChecker",
    "DataAvailabilityResult",
    "DataQualityChecker",
    "DataQualityResult",
    "HistoricalBacktestResult",
    "HistoricalBacktestValidator",
    "IndicatorCompatibilityChecker",
    "IndicatorCompatibilityResult",
    "DIRECTION_REGIMES",
    "VOLATILITY_REGIMES",
    "OOSMetrics",
    "RegimeMetrics",
    "RegimeOOSResult",
    "RegimeOOSValidator",
]
