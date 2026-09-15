"""Base provider interface and contracts for SignalForge market data providers.

Re-exports core abstractions from `src.data.market_data` to ensure a clean,
non-duplicated architectural hierarchy.
"""

from src.data.market_data import (
    CANONICAL_OHLCV_COLUMNS,
    MarketDataProvider,
    MarketDataRequest,
    MarketDataResult,
    normalize_ohlcv_columns,
    validate_normalized_ohlcv,
)

__all__ = [
    "CANONICAL_OHLCV_COLUMNS",
    "MarketDataProvider",
    "MarketDataRequest",
    "MarketDataResult",
    "normalize_ohlcv_columns",
    "validate_normalized_ohlcv",
]
