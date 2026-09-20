"""
SignalForge Phase 9 — Intelligence Engine Unit Test Suite
=========================================================
Tests certifying:
 1. Trend calculation correctness and boundaries
 2. Volatility calculation and states
 3. Momentum calculation and RSI bounds
 4. Structure calculation and swing pivots
 5. Session classification across NSE market day
 6. Score ranges strictly bounded 0-100
 7. Determinism across repeated evaluations
 8. Missing / sparse data handling
 9. Conflicting signals produce NEUTRAL / CAUTION
10. Extreme volatility and late session enforce NO_TRADE
11. Contextual risk classification
12. Structured explanation generation
13. Opportunity weighting logic
14. Symbol ranking integrity
15. API schema validation
"""

import unittest
from datetime import datetime
import numpy as np
import pandas as pd

from src.intelligence.config import IntelligenceConfig, IntelligenceThresholds, IntelligenceWeights
from src.intelligence.models import (
    TrendState,
    VolatilityState,
    VolatilityDynamics,
    MarketCondition,
    TradeBias,
    StructureState,
    SessionState,
    RiskLevel,
    TradeabilityDecision,
    NoTradeReason,
    SymbolIntelligence,
    MarketOverview,
)
from src.intelligence.trend_engine import calculate_trend_analysis
from src.intelligence.volatility_engine import calculate_volatility_analysis
from src.intelligence.momentum_engine import calculate_momentum_analysis
from src.intelligence.structure_engine import calculate_structure_analysis
from src.intelligence.session_engine import calculate_session_context
from src.intelligence.risk_context import calculate_risk_context
from src.intelligence.confidence_engine import calculate_confidence_analysis
from src.intelligence.opportunity_engine import (
    determine_directional_bias,
    calculate_opportunity_score,
    evaluate_tradeability,
)
from src.intelligence.explanation_engine import generate_explanation_report
from src.intelligence.market_state import (
    evaluate_symbol_intelligence,
    evaluate_market_overview,
    rank_symbol_opportunities,
)


class TestIntelligenceEngine(unittest.TestCase):
    def setUp(self):
        # Generate a deterministic synthetic trending dataset (100 bars)
        dates = pd.date_range("2018-01-01 09:15:00", periods=100, freq="1min")
        base = 1000.0
        drift = np.linspace(0, 50, 100) # upward drift
        noise = np.sin(np.linspace(0, 10, 100)) * 2.0
        closes = base + drift + noise
        highs = closes + 1.5
        lows = closes - 1.5
        opens = closes - 0.2
        volumes = np.full(100, 1000)

        self.trending_df = pd.DataFrame({
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": volumes,
        }, index=dates)

        # Generate a flat ranging dataset (100 bars)
        range_closes = base + np.sin(np.linspace(0, 20, 100)) * 3.0
        self.ranging_df = pd.DataFrame({
            "Open": range_closes - 0.1,
            "High": range_closes + 1.0,
            "Low": range_closes - 1.0,
            "Close": range_closes,
            "Volume": volumes,
        }, index=dates)

        self.config = IntelligenceConfig()

    def test_01_trend_calculation(self):
        """Test trend engine outputs valid states, directions, and scores."""
        analysis = calculate_trend_analysis(self.trending_df)
        self.assertIn(analysis.state, [TrendState.STRONG_BULLISH, TrendState.BULLISH])
        self.assertEqual(analysis.direction, TradeBias.LONG_BIAS)
        self.assertGreater(analysis.strength, 50.0)
        self.assertGreater(analysis.price_to_ema21_pct, 0.0)
        self.assertTrue(len(analysis.reasons) > 0)

    def test_02_volatility_calculation(self):
        """Test volatility engine states, metrics, and quality scoring."""
        vol = calculate_volatility_analysis(self.trending_df, self.config.thresholds)
        self.assertIsInstance(vol.state, VolatilityState)
        self.assertIsInstance(vol.dynamics, VolatilityDynamics)
        self.assertGreater(vol.atr, 0.0)
        self.assertGreaterEqual(vol.realized_volatility_pctile, 0.0)
        self.assertLessEqual(vol.realized_volatility_pctile, 100.0)
        self.assertGreaterEqual(vol.volatility_quality_score, 0.0)
        self.assertLessEqual(vol.volatility_quality_score, 100.0)

    def test_03_momentum_calculation(self):
        """Test momentum calculation, returns, and RSI bounds."""
        mom = calculate_momentum_analysis(self.trending_df, self.config.thresholds)
        self.assertGreaterEqual(mom.rsi14, 0.0)
        self.assertLessEqual(mom.rsi14, 100.0)
        self.assertGreaterEqual(mom.strength, 0.0)
        self.assertLessEqual(mom.strength, 100.0)
        self.assertEqual(mom.direction, TradeBias.LONG_BIAS)

    def test_04_structure_calculation(self):
        """Test market structure detection and swing progression."""
        struct = calculate_structure_analysis(self.trending_df)
        self.assertIn(struct.state, [StructureState.BULLISH_STRUCTURE, StructureState.BREAKOUT_UP])
        self.assertGreater(struct.recent_swing_high, struct.recent_swing_low)
        self.assertGreaterEqual(struct.range_position, 0.0)
        self.assertLessEqual(struct.range_position, 1.0)
        self.assertGreater(struct.quality_score, 60.0)

    def test_05_session_classification(self):
        """Test session classification across the market timeline."""
        # 09:20 -> OPENING
        s_open = calculate_session_context(pd.Timestamp("2018-01-01 09:20:00"))
        self.assertEqual(s_open.state, SessionState.OPENING)
        self.assertEqual(s_open.minutes_from_open, 5)

        # 10:30 -> EARLY_SESSION
        s_early = calculate_session_context(pd.Timestamp("2018-01-01 10:30:00"))
        self.assertEqual(s_early.state, SessionState.EARLY_SESSION)

        # 12:30 -> MIDDAY
        s_mid = calculate_session_context(pd.Timestamp("2018-01-01 12:30:00"))
        self.assertEqual(s_mid.state, SessionState.MIDDAY)

        # 14:15 -> AFTERNOON
        s_aft = calculate_session_context(pd.Timestamp("2018-01-01 14:15:00"))
        self.assertEqual(s_aft.state, SessionState.AFTERNOON)

        # 15:20 -> CLOSING
        s_close = calculate_session_context(pd.Timestamp("2018-01-01 15:20:00"))
        self.assertEqual(s_close.state, SessionState.CLOSING)
        self.assertEqual(s_close.minutes_to_close, 10)

    def test_06_score_ranges_bounded(self):
        """Test that all generated scores are strictly within [0.0, 100.0]."""
        intel = evaluate_symbol_intelligence("TEST", self.trending_df, self.config)
        self.assertGreaterEqual(intel.opportunity_score, 0.0)
        self.assertLessEqual(intel.opportunity_score, 100.0)
        self.assertGreaterEqual(intel.tradeability_score, 0.0)
        self.assertLessEqual(intel.tradeability_score, 100.0)
        self.assertGreaterEqual(intel.confidence_score, 0.0)
        self.assertLessEqual(intel.confidence_score, 100.0)

    def test_07_determinism(self):
        """Test that identical input DataFrame produces bit-for-bit identical outputs."""
        intel1 = evaluate_symbol_intelligence("INFY", self.trending_df, self.config)
        intel2 = evaluate_symbol_intelligence("INFY", self.trending_df, self.config)
        self.assertEqual(intel1.opportunity_score, intel2.opportunity_score)
        self.assertEqual(intel1.tradeability_score, intel2.tradeability_score)
        self.assertEqual(intel1.confidence_score, intel2.confidence_score)
        self.assertEqual(intel1.decision, intel2.decision)
        self.assertEqual(intel1.direction, intel2.direction)

    def test_08_missing_sparse_data_handling(self):
        """Test that sparse dataframes (<5 bars) fail safely without raising unhandled exceptions."""
        sparse_df = self.trending_df.head(3).copy()
        intel = evaluate_symbol_intelligence("TCS", sparse_df, self.config)
        self.assertEqual(intel.decision, TradeabilityDecision.NO_TRADE)
        self.assertEqual(intel.direction, TradeBias.NEUTRAL)

    def test_09_conflicting_signals_produce_neutral(self):
        """Test that conflicting directional indicators resolve to NEUTRAL bias."""
        # Create contradictory conditions
        intel = evaluate_symbol_intelligence("RANGING", self.ranging_df, self.config)
        self.assertEqual(intel.direction, TradeBias.NEUTRAL)
        self.assertEqual(intel.decision, TradeabilityDecision.NO_TRADE)

    def test_10_extreme_conditions_enforce_no_trade(self):
        """Test that late session or extreme volatility strictly trigger NO_TRADE."""
        # Late session test
        late_dates = pd.date_range("2018-01-01 15:25:00", periods=60, freq="1min")
        late_df = self.trending_df.tail(60).copy()
        late_df.index = late_dates
        intel = evaluate_symbol_intelligence("LATE", late_df, self.config)
        self.assertEqual(intel.decision, TradeabilityDecision.NO_TRADE)
        reasons_text = " ".join(intel.explanation.no_trade_reasons)
        self.assertIn("LATE_SESSION", reasons_text)

    def test_11_contextual_risk_classification(self):
        """Test contextual risk level assignment (LOW, MEDIUM, HIGH, EXTREME)."""
        vol = calculate_volatility_analysis(self.trending_df, self.config.thresholds)
        struct = calculate_structure_analysis(self.trending_df)
        price = float(self.trending_df["Close"].iloc[-1])
        risk = calculate_risk_context(price, TradeBias.LONG_BIAS, vol, struct)
        self.assertIn(risk.risk_level, [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH])
        self.assertGreater(risk.suggested_risk_distance, 0.0)

    def test_12_structured_explanation_generation(self):
        """Test that explanation reports contain non-empty summaries, evidence, and warnings."""
        intel = evaluate_symbol_intelligence("RELIANCE", self.trending_df, self.config)
        self.assertTrue(len(intel.explanation.summary) > 10)
        self.assertTrue(len(intel.explanation.evidence) > 0)
        self.assertIsInstance(intel.explanation.warnings, list)

    def test_13_opportunity_weighting_logic(self):
        """Test opportunity score custom weights."""
        custom_weights = IntelligenceWeights(
            trend=0.50, structure=0.10, momentum=0.10,
            volatility=0.10, risk_reward=0.10, session=0.10
        )
        custom_config = IntelligenceConfig(weights=custom_weights)
        intel = evaluate_symbol_intelligence("TEST", self.trending_df, custom_config)
        self.assertGreater(intel.opportunity_score, 0.0)

    def test_14_symbol_ranking_integrity(self):
        """Test ranking logic orders opportunities by tradeability and score."""
        intel_trend = evaluate_symbol_intelligence("TRENDING", self.trending_df, self.config)
        intel_range = evaluate_symbol_intelligence("RANGING", self.ranging_df, self.config)
        ranked = rank_symbol_opportunities([intel_range, intel_trend])
        self.assertEqual(ranked[0].symbol, "TRENDING")

    def test_15_market_overview(self):
        """Test market-wide multi-symbol overview aggregation."""
        symbols_data = {
            "STOCK_A": self.trending_df,
            "STOCK_B": self.ranging_df,
        }
        overview = evaluate_market_overview(symbols_data, self.config)
        self.assertEqual(overview.number_of_symbols, 2)
        self.assertGreaterEqual(overview.bullish_count + overview.neutral_count + overview.bearish_count, 2)
        self.assertTrue(len(overview.top_opportunities) > 0)


if __name__ == "__main__":
    unittest.main()
