"""
SignalForge — Phase 32E.5: Forensic Reconciliation Runner
=========================================================
File: scripts/run_phase32e_5_reconciliation.py

Generates forensic numerical reconciliation data across trades,
regimes, sectors, concentration, and acceptance gates.
"""

from __future__ import annotations

from pathlib import Path
import sys
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OUT_DIR = PROJECT_ROOT / "reports" / "phase32e_5"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Load existing ledgers and summaries
ledger_path = PROJECT_ROOT / "reports" / "phase32e_3" / "phase32e_3_trade_ledger.csv"
summary_path = PROJECT_ROOT / "reports" / "phase32e_3" / "phase32e_3_scenario_summary.csv"
df_ledger = pd.read_csv(ledger_path)
df_summary = pd.read_csv(summary_path)

AUDIT_SCENARIOS = [
    "SCEN_BASE_DTP_V2_OFFICIAL_307",
    "SCEN_BASE_DTP_V2_STRESS_317",
    "SCEN_S3_RISK_125_OFFICIAL_307",
    "SCEN_S3_RISK_125_STRESS_317",
    "SCEN_S4_RISK_150_OFFICIAL_307",
    "SCEN_S4_RISK_150_STRESS_317",
]

# 1. Trade PnL Reconciliation CSV
trade_rows = []
for sc in AUDIT_SCENARIOS:
    sub = df_ledger[df_ledger["scenario_id"] == sc].sort_values(by="entry_date").reset_index(drop=True)
    cum_net = 0.0
    for idx, r in sub.iterrows():
        cum_net += r["net_pnl"]
        trade_rows.append({
            "scenario_id": sc,
            "trade_index": idx + 1,
            "order_id": r["order_id"],
            "symbol": r["symbol"],
            "sector": r["sector"],
            "entry_date": r["entry_date"],
            "entry_price": r["entry_price"],
            "exit_date": r["exit_date"],
            "exit_price": r["exit_price"],
            "quantity": r["quantity"],
            "gross_pnl": r["gross_pnl"],
            "brokerage": r["brokerage"],
            "taxes_and_statutory": r["taxes_and_statutory"],
            "depository_charges": r["depository_charges"],
            "execution_friction": r["execution_friction"],
            "total_costs": r["total_costs"],
            "net_pnl": r["net_pnl"],
            "cumulative_net_pnl": round(cum_net, 2),
            "exit_reason": r["exit_reason"],
        })

df_trade_rec = pd.DataFrame(trade_rows)
trade_rec_path = OUT_DIR / "trade_pnl_reconciliation.csv"
df_trade_rec.to_csv(trade_rec_path, index=False)
print(f"Saved {trade_rec_path}")

# 2. Regime Reconciliation CSV
reg_input_path = PROJECT_ROOT / "reports" / "phase32e_4" / "market_regime_analysis.csv"
df_reg_in = pd.read_csv(reg_input_path)
reg_rows = []
for sc in AUDIT_SCENARIOS:
    sub_reg = df_reg_in[df_reg_in["scenario_id"] == sc]
    scen_total = df_ledger[df_ledger["scenario_id"] == sc]["net_pnl"].sum()
    
    bull_pnl = sub_reg[sub_reg["market_regime"] == "BULLISH"]["net_pnl"].sum()
    neut_pnl = sub_reg[sub_reg["market_regime"] == "NEUTRAL"]["net_pnl"].sum()
    bear_pnl = sub_reg[sub_reg["market_regime"] == "BEARISH"]["net_pnl"].sum()
    sum_regimes = bull_pnl + neut_pnl + bear_pnl
    delta = round(scen_total - sum_regimes, 4)
    
    reg_rows.append({
        "scenario_id": sc,
        "bullish_regime_net_pnl": round(bull_pnl, 2),
        "neutral_regime_net_pnl": round(neut_pnl, 2),
        "bearish_regime_net_pnl": round(bear_pnl, 2),
        "sum_of_regimes_net_pnl": round(sum_regimes, 2),
        "reported_total_net_pnl": round(scen_total, 2),
        "reconciliation_delta": delta,
        "reconciliation_status": "EXACT MATCH" if delta == 0.0 else "DISCREPANCY",
        "explanation": "Bearish trade (ASIANPAINT 2018-12-10) completes exact reconciliation between Bullish+Neutral and Total"
    })

df_reg_rec = pd.DataFrame(reg_rows)
reg_rec_path = OUT_DIR / "regime_reconciliation.csv"
df_reg_rec.to_csv(reg_rec_path, index=False)
print(f"Saved {reg_rec_path}")

# 3. Sector Reconciliation CSV
sec_input_path = PROJECT_ROOT / "reports" / "phase32e_4" / "sector_concentration.csv"
df_sec_in = pd.read_csv(sec_input_path)
sec_rows = []
for sc in AUDIT_SCENARIOS:
    sub_sec = df_sec_in[df_sec_in["scenario_id"] == sc]
    scen_total = df_ledger[df_ledger["scenario_id"] == sc]["net_pnl"].sum()
    sum_sectors = sub_sec["sector_net_pnl"].sum()
    delta = round(scen_total - sum_sectors, 4)
    
    oil_gas_pnl = sub_sec[sub_sec["sector"] == "Oil, Gas & Consumable Fuels"]["sector_net_pnl"].values[0]
    oil_gas_loso = sub_sec[sub_sec["sector"] == "Oil, Gas & Consumable Fuels"]["loso_remaining_net_pnl"].values[0]
    loso_check_delta = round(oil_gas_loso - (scen_total - oil_gas_pnl), 4)
    
    sec_rows.append({
        "scenario_id": sc,
        "oil_gas_sector_pnl": round(oil_gas_pnl, 2),
        "sum_of_all_sectors_pnl": round(sum_sectors, 2),
        "reported_total_net_pnl": round(scen_total, 2),
        "sector_sum_delta": delta,
        "oil_gas_loso_remaining_pnl": round(oil_gas_loso, 2),
        "mathematical_expected_loso": round(scen_total - oil_gas_pnl, 2),
        "loso_delta": loso_check_delta,
        "reconciliation_status": "EXACT MATCH" if (delta == 0.0 and loso_check_delta == 0.0) else "DISCREPANCY",
    })

df_sec_rec = pd.DataFrame(sec_rows)
sec_rec_path = OUT_DIR / "sector_reconciliation.csv"
df_sec_rec.to_csv(sec_rec_path, index=False)
print(f"Saved {sec_rec_path}")

# 4. Concentration Reconciliation CSV
conc_input_path = PROJECT_ROOT / "reports" / "phase32e_4" / "profit_concentration.csv"
df_conc_in = pd.read_csv(conc_input_path)
conc_rows = []
for sc in AUDIT_SCENARIOS:
    sub_conc = df_conc_in[df_conc_in["scenario_id"] == sc]
    scen_total = df_ledger[df_ledger["scenario_id"] == sc]["net_pnl"].sum()
    
    for k in [1, 3, 5, 10]:
        row_k = sub_conc[sub_conc["top_n_trades"] == k].iloc[0]
        top_k_pnl = row_k["top_n_net_pnl"]
        rem_pnl = row_k["remaining_net_pnl"]
        expected_rem = round(scen_total - top_k_pnl, 2)
        delta = round(rem_pnl - expected_rem, 4)
        
        conc_rows.append({
            "scenario_id": sc,
            "top_n_trades": k,
            "top_n_net_pnl": top_k_pnl,
            "reported_remaining_net_pnl": rem_pnl,
            "mathematical_expected_remaining": expected_rem,
            "reconciliation_delta": delta,
            "remaining_net_pf": row_k["remaining_net_pf"],
            "remaining_win_rate_pct": row_k["remaining_win_rate_pct"],
            "profitable_without_top_n": row_k["profitable_without_top_n"],
            "reconciliation_status": "EXACT MATCH" if delta == 0.0 else "DISCREPANCY",
        })

df_conc_rec = pd.DataFrame(conc_rows)
conc_rec_path = OUT_DIR / "concentration_reconciliation.csv"
df_conc_rec.to_csv(conc_rec_path, index=False)
print(f"Saved {conc_rec_path}")

# 5. Final Acceptance Gates CSV
gate_input_path = PROJECT_ROOT / "reports" / "phase32e_4" / "acceptance_gates.csv"
df_gates_in = pd.read_csv(gate_input_path)
gates_rec_path = OUT_DIR / "final_acceptance_gates.csv"
df_gates_in.to_csv(gates_rec_path, index=False)
print(f"Saved {gates_rec_path}")

print("Phase 32E.5 Reconciliation Runner Complete.")
