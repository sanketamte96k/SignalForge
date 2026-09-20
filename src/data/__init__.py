"""SignalForge market-data package."""

from src.data.market_data import (
    CANONICAL_OHLCV_COLUMNS,
    MarketDataProvider,
    MarketDataRequest,
    MarketDataResult,
    normalize_ohlcv_columns,
    validate_normalized_ohlcv,
)
from src.data.market_data_service import (
    MarketDataService,
    ProviderUnavailableError,
    UnknownProviderError,
)
from src.data.providers.groww import GrowwProvider
from src.data.providers.groww_auth import GrowwAuthManager
from src.data.providers.groww_config import GrowwConfig
from src.data.providers.groww_errors import (
    GrowwAPIError,
    GrowwAuthenticationError,
    GrowwDataFormatError,
    GrowwError,
    GrowwRateLimitError,
    GrowwSymbolMappingError,
)
from src.data.providers.local import LocalProvider
from src.data.stock_provider import StockDataProvider

__all__ = [
    "CANONICAL_OHLCV_COLUMNS",
    "GrowwAPIError",
    "GrowwAuthManager",
    "GrowwAuthenticationError",
    "GrowwConfig",
    "GrowwDataFormatError",
    "GrowwError",
    "GrowwProvider",
    "GrowwRateLimitError",
    "GrowwSymbolMappingError",
    "LocalProvider",
    "MarketDataProvider",
    "MarketDataRequest",
    "MarketDataResult",
    "MarketDataService",
    "ProviderUnavailableError",
    "StockDataProvider",
    "UnknownProviderError",
    "normalize_ohlcv_columns",
    "validate_normalized_ohlcv",
]
