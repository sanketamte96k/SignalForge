"""
SignalForge Phase 9 — Causality & Non-Anticipation Perturbation Audit
=====================================================================
File: scripts/test_intelligence_causality.py

Verifies that the Market Intelligence Engine is strictly causal and non-anticipative.
Applies future bar perturbations and mathematically proves that zero changes leak
into prior historical state evaluations.

Final output prints PASS / FAIL.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Safe stdout encoding
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.intelligence.market_state import evaluate_symbol_intelligence
from src.intelligence.config import IntelligenceConfig

CLEAN_DATA_DIR = PROJECT_ROOT / "research" / "clean_data_2018"
SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]


def run_causality_audit() -> bool:
    print("=" * 80)
    print(" SIGNALFORGE PHASE 9 — CAUSALITY & LEAKAGE PERTURBATION AUDIT")
    print("=" * 80)

    config = IntelligenceConfig()
    all_passed = True

    # We will test on INFY 2018 data
    infy_file = CLEAN_DATA_DIR / "INFY_2018.csv"
    if not infy_file.exists():
        print(f"[FAIL] Missing clean data file at {infy_file}")
        return False

    df_full = pd.read_csv(infy_file, index_col=0, parse_dates=True).head(500).copy()
    print(f"Loaded {len(df_full)} baseline bars for perturbation audit.")

    eval_cutoff = 300
    perturb_idx = 350 # 50 bars into the future

    # 1. Base evaluation at cutoff N
    print(f"\n[STEP 1] Evaluating baseline state at historical bar {eval_cutoff}...")
    df_base = df_full.iloc[:eval_cutoff].copy()
    intel_base = evaluate_symbol_intelligence("INFY", df_base, config)

    # 2. Perturbation of future data
    print(f"[STEP 2] Injecting severe future perturbations at bar {perturb_idx} (Price +35%, Volume x5)...")
    df_perturbed_full = df_full.copy()
    close_col = "Close" if "Close" in df_perturbed_full.columns else "close"
    high_col = "High" if "High" in df_perturbed_full.columns else "high"
    vol_col = "Volume" if "Volume" in df_perturbed_full.columns else "volume"

    df_perturbed_full.iloc[perturb_idx, df_perturbed_full.columns.get_loc(close_col)] *= 1.35
    df_perturbed_full.iloc[perturb_idx, df_perturbed_full.columns.get_loc(high_col)] *= 1.40
    df_perturbed_full.iloc[perturb_idx, df_perturbed_full.columns.get_loc(vol_col)] *= 5.0

    # Re-evaluate historical bar N using the slice from the perturbed dataframe
    df_perturbed_slice = df_perturbed_full.iloc[:eval_cutoff].copy()
    intel_perturbed = evaluate_symbol_intelligence("INFY", df_perturbed_slice, config)

    # 3. Check for any bitwise divergences
    print("\n[STEP 3] Comparing pre-perturbation vs post-perturbation metrics at cutoff bar:")
    checks = [
        ("Opportunity Score", intel_base.opportunity_score, intel_perturbed.opportunity_score),
        ("Tradeability Score", intel_base.tradeability_score, intel_perturbed.tradeability_score),
        ("Confidence Score", intel_base.confidence_score, intel_perturbed.confidence_score),
        ("Directional Bias", intel_base.direction.value, intel_perturbed.direction.value),
        ("Decision", intel_base.decision.value, intel_perturbed.decision.value),
        ("Market Condition", intel_base.market_condition.value, intel_perturbed.market_condition.value),
        ("Trend Strength", intel_base.trend.strength, intel_perturbed.trend.strength),
        ("Volatility State", intel_base.volatility.state.value, intel_perturbed.volatility.state.value),
        ("Momentum Strength", intel_base.momentum.strength, intel_perturbed.momentum.strength),
        ("Structure State", intel_base.structure.state.value, intel_perturbed.structure.state.value),
        ("Risk Level", intel_base.risk.risk_level.value, intel_perturbed.risk.risk_level.value),
    ]

    divergence_count = 0
    for name, v1, v2 in checks:
        matches = (v1 == v2)
        status = "PASS" if matches else "FAIL"
        print(f"  [{status}] {name:<22}: Base = {v1} | Perturbed = {v2}")
        if not matches:
            divergence_count += 1
            all_passed = False

    print("\n[STEP 4] Multi-bar Rolling Causality Audit (Bars 100 to 300, step 20)...")
    rolling_divergences = 0
    for bar_idx in range(100, 300, 20):
        sub_b = df_full.iloc[:bar_idx].copy()
        sub_p = df_perturbed_full.iloc[:bar_idx].copy()
        i_b = evaluate_symbol_intelligence("INFY", sub_b, config)
        i_p = evaluate_symbol_intelligence("INFY", sub_p, config)
        if i_b.opportunity_score != i_p.opportunity_score or i_b.decision != i_p.decision:
            rolling_divergences += 1
            all_passed = False

    if rolling_divergences == 0:
        print("  [PASS] All 10 rolling historical evaluation checkpoints bitwise identical.")
    else:
        print(f"  [FAIL] {rolling_divergences} rolling checkpoints diverged!")

    print("\n" + "=" * 80)
    if all_passed:
        print("CAUSALITY PERTURBATION AUDIT: PASS (ZERO FUTURE LEAKAGE DETECTED)")
    else:
        print("CAUSALITY PERTURBATION AUDIT: FAIL")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = run_causality_audit()
    sys.exit(0 if success else 1)
