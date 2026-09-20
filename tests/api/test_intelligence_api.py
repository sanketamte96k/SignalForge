"""
SignalForge API — Intelligence Endpoints Unit Tests
===================================================
Tests for:
 - GET /api/intelligence/overview
 - GET /api/intelligence
 - GET /api/intelligence/{symbol}
 - GET /api/intelligence/{symbol}/explanation
 - GET /api/intelligence/{symbol}/history
"""

import unittest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


class TestIntelligenceAPI(unittest.TestCase):
    def test_01_get_overview(self):
        """GET /api/intelligence/overview should return consolidated market state."""
        response = client.get("/api/intelligence/overview")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("market_condition", data)
        self.assertIn("market_volatility", data)
        self.assertIn("number_of_symbols", data)
        self.assertIn("tradeable_count", data)
        self.assertIn("top_opportunities", data)
        self.assertIsInstance(data["top_opportunities"], list)

    def test_02_get_scanned_opportunities(self):
        """GET /api/intelligence should return ranked opportunities list."""
        response = client.get("/api/intelligence")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("count", data)
        self.assertIn("items", data)
        self.assertGreater(data["count"], 0)

    def test_03_get_symbol_intelligence(self):
        """GET /api/intelligence/{symbol} should return comprehensive analysis."""
        response = client.get("/api/intelligence/RELIANCE")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["symbol"], "RELIANCE")
        self.assertIn("opportunity_score", data)
        self.assertIn("tradeability_score", data)
        self.assertIn("confidence_score", data)
        self.assertIn("decision", data)
        self.assertIn("trend", data)
        self.assertIn("volatility", data)
        self.assertIn("momentum", data)
        self.assertIn("structure", data)
        self.assertIn("session", data)
        self.assertIn("risk", data)
        self.assertIn("explanation", data)

    def test_04_get_symbol_explanation(self):
        """GET /api/intelligence/{symbol}/explanation should return structured reasoning."""
        response = client.get("/api/intelligence/TCS/explanation")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["symbol"], "TCS")
        self.assertIn("summary", data)
        self.assertIn("evidence", data)
        self.assertIn("warnings", data)
        self.assertIn("no_trade_reasons", data)

    def test_05_get_symbol_history(self):
        """GET /api/intelligence/{symbol}/history should return causal time-series points."""
        response = client.get("/api/intelligence/INFY/history?bars=30&step=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["symbol"], "INFY")
        self.assertIn("history", data)
        self.assertGreater(len(data["history"]), 0)
        first_point = data["history"][0]
        self.assertIn("price", first_point)
        self.assertIn("opportunity_score", first_point)
        self.assertIn("decision", first_point)

    def test_06_nonexistent_symbol_404(self):
        """GET /api/intelligence/{symbol} for unknown symbol should return 404."""
        response = client.get("/api/intelligence/NONEXISTENT_XYZ")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
