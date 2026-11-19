"""
SignalForge — Phase 30: Scanner & Strategy Integration Bridge
=============================================================
File: src/market_data/scanner_integration.py

Capabilities:
- Bridges the ProviderNeutralMarketDataAdapter with StockScannerEngine and CausalStrategyContext.
- Ensures scanner receives only normalized, validated, completed candles.
- Enforces strict feed-health gating:
    - If a symbol's feed is STALE, DISCONNECTED, or INVALID:
      Immediately emits signal='NO_TRADE' with signal_eligible=False.
    - If feed is RECOVERING:
      Suspends actionable signals until synchronization is certified.
- Guarantees zero look-ahead bias:
    - Only finalized (is_closed=True) bars are converted to DataFrames.
    - In-progress bars cannot trigger indicator or ATR updates.
- Strictly preserves rejection of the three Phase 27C.9 strategies.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import pandas as pd

from src.market_data.live_adapter import (
    DataQualityState,
    FeedType,
    ProviderNeutralMarketDataAdapter,
)
from src.scanner.engine import StockScannerEngine, StockScanResult
from src.universe.manager import UniverseManager
from src.universe.models import Instrument

logger = logging.getLogger(__name__)


class LiveScannerBridge:
    """
    Coordinates feed-health validation and safe ingestion into the SignalForge stock scanner.
    """

    def __init__(
        self,
        adapter: ProviderNeutralMarketDataAdapter,
        scanner_engine: StockScannerEngine,
        min_candles_required: int = 30,  # ATR / EMA warm-up requirement
    ) -> None:
        self.adapter = adapter
        self.scanner_engine = scanner_engine
        self.min_candles_required = min_candles_required

    def scan_live_symbol(self, symbol: str) -> StockScanResult:
        """
        Scan a single symbol with fail-closed feed-health gating.
        """
        clean_sym = symbol.strip().upper()
        stream_state = self.adapter.get_or_create_symbol(clean_sym)
        quality_state = stream_state.quality_state

        # 1. Fail-closed feed-state checks
        if quality_state == DataQualityState.DISCONNECTED:
            return StockScanResult(
                symbol=clean_sym,
                name=clean_sym,
                exchange="NSE",
                signal="NO_TRADE",
                position=None,
                signal_eligible=False,
                timestamp=stream_state.last_event_timestamp,
                price=stream_state.last_quote.ltp if stream_state.last_quote else None,
                signal_result=None,
                reason="Market data feed DISCONNECTED. Entry blocked by fail-closed gate.",
            )

        if quality_state == DataQualityState.STALE:
            return StockScanResult(
                symbol=clean_sym,
                name=clean_sym,
                exchange="NSE",
                signal="NO_TRADE",
                position=None,
                signal_eligible=False,
                timestamp=stream_state.last_event_timestamp,
                price=stream_state.last_quote.ltp if stream_state.last_quote else None,
                signal_result=None,
                reason="Market data feed STALE. Entry blocked by staleness guard.",
            )

        if quality_state == DataQualityState.INVALID:
            return StockScanResult(
                symbol=clean_sym,
                name=clean_sym,
                exchange="NSE",
                signal="NO_TRADE",
                position=None,
                signal_eligible=False,
                timestamp=stream_state.last_event_timestamp,
                price=stream_state.last_quote.ltp if stream_state.last_quote else None,
                signal_result=None,
                reason="Market data feed INVALID. Corrupt or unphysical observations detected.",
            )

        if quality_state == DataQualityState.RECOVERING:
            return StockScanResult(
                symbol=clean_sym,
                name=clean_sym,
                exchange="NSE",
                signal="NO_TRADE",
                position=None,
                signal_eligible=False,
                timestamp=stream_state.last_event_timestamp,
                price=stream_state.last_quote.ltp if stream_state.last_quote else None,
                signal_result=None,
                reason=f"Market data feed RECOVERING ({stream_state.recovery_observations_count}/{self.adapter.recovery_required_bars} bars).",
            )

        # 2. Export canonical completed DataFrame (no in-progress bars)
        df = self.adapter.export_canonical_dataframe(clean_sym)

        if len(df) < self.min_candles_required:
            return StockScanResult(
                symbol=clean_sym,
                name=clean_sym,
                exchange="NSE",
                signal="NO_TRADE",
                position=None,
                signal_eligible=True,
                timestamp=df.index[-1] if not df.empty else None,
                price=float(df["Close"].iloc[-1]) if not df.empty else None,
                signal_result=None,
                reason=f"Insufficient history for causal indicator warm-up ({len(df)}/{self.min_candles_required} bars).",
            )

        # 3. Scan symbol through canonical scanner engine
        return self.scanner_engine.scan_symbol(clean_sym, df)

    def scan_all_universe(self) -> Tuple[StockScanResult, ...]:
        """
        Scan all instruments registered in the universe manager.
        """
        results: List[StockScanResult] = []
        for instrument in self.scanner_engine._universe.all_instruments():
            results.append(self.scan_live_symbol(instrument.symbol))
        return tuple(results)
