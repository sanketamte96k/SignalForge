"""
SignalForge — Phase 33B: S5 Forensic Research Unit Tests
========================================================
File: tests/test_s5_forensic_research.py
"""

from datetime import date
import numpy as np
import pandas as pd
import pytest

from src.strategy.s5_forensic_research.config import (
    FORENSIC_HYPOTHESIS_CONFIGS,
    S5ForensicConfig,
    S5HypothesisID,
)
from src.strategy.s5_forensic_research.forensic_simulator import (
    run_s5_forensic_simulation,
)
from src.strategy.strategy_research_lab.config import RiskTier, StrategyLabConfig
from src.strategy.strategy_research_lab.indicators import attach_all_indicators


def create_synthetic_breakout_df(n_bars: int = 200) -> pd.DataFrame:
    np.random.seed(42)
    dates = pd.date_range("2018-01-01", periods=n_bars, freq="B").date
    closes = [100.0]
    for i in range(1, n_bars):
        # Create a volatility compression then a breakout
        vol = 0.005 if 100 <= i <= 140 else 0.02
        drift = 0.05 if i > 140 else 0.001
        ret = drift + np.random.normal(0, vol)
        closes.append(closes[-1] * (1.0 + ret))

    closes = np.array(closes)
    highs = closes * 1.01
    lows = closes * 0.99
    opens = (highs + lows) / 2.0
    volumes = np.random.randint(100000, 300000, n_bars).astype(float)
    # Spike volume at breakout
    volumes[141:] *= 2.0

    df = pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    }, index=dates)
    return df


def test_hypotheses_definitions():
    assert len(S5HypothesisID) == 4
    for h_id in S5HypothesisID:
        assert h_id in FORENSIC_HYPOTHESIS_CONFIGS
        cfg = FORENSIC_HYPOTHESIS_CONFIGS[h_id]
        assert cfg.hypothesis_id == h_id


def test_forensic_simulator_reconciliation():
    u_raw = {
        "SYM_1": create_synthetic_breakout_df(180),
        "SYM_2": create_synthetic_breakout_df(180),
    }
    u_aug = {s: attach_all_indicators(df, s) for s, df in u_raw.items()}

    cfg = StrategyLabConfig(
        initial_capital=100000.0,
        max_concurrent_positions=2,
        symbol_sector_map={"SYM_1": "IT", "SYM_2": "Auto"},
        symbol_isin_map={"SYM_1": "INE001", "SYM_2": "INE002"},
    )

    res = run_s5_forensic_simulation(
        hypothesis_id=S5HypothesisID.BASELINE_S5,
        augmented_universe=u_aug,
        risk_tier=RiskTier.E2,
        use_stress_costs=True,
        config=cfg,
    )

    assert res.initial_capital == 100000.0
    for t in res.trades:
        # Check single vs double slippage mathematical invariant
        # double slipped should equal single slipped minus slippage
        assert np.isclose(t.net_pnl_double_slipped, t.net_pnl_single_slipped - t.slippage, atol=0.02)
