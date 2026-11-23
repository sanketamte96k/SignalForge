import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_phase32d_3_dtp_v1_expanded_validation import (
    load_and_resample_21_universe,
    APPROVED_21_SYMBOLS,
    EXPANDED_SECTOR_MAP,
    EXPANDED_ISIN_MAP,
)
from src.strategy.dtp_v2.config import DTPV2Config
from src.strategy.dtp_v2.indicators import calculate_dtp_indicators as calc_ind_v2
from scripts.run_phase32e_2_validation import run_strategy_simulation
from scripts.run_phase32i_dtp_v3_evaluation import run_dtp_simulation
import pandas as pd

raw = load_and_resample_21_universe()
trading_dates = list(raw[APPROVED_21_SYMBOLS[0]].index)

cfg_v2 = DTPV2Config(symbol_sector_map=EXPANDED_SECTOR_MAP, symbol_isin_map=EXPANDED_ISIN_MAP)
aug_v2 = {s: calc_ind_v2(raw[s], config=cfg_v2) for s in APPROVED_21_SYMBOLS}

# Run 1: 32E.2 canonical simulation
res_canonical = run_strategy_simulation("DTP-V2", aug_v2, trading_dates, use_stress_costs=False, initial_capital=100000.0)
df_canon = res_canonical["df_trades"]

# Run 2: 32I evaluation simulation
res_32i = run_dtp_simulation("DTP-V2", aug_v2, trading_dates, risk_pct=0.01, use_stress_costs=False, initial_capital=100000.0)
df_32i = res_32i["df_trades"]

print(f"Canonical Net P&L: {df_canon['net_pnl'].sum():.4f}")
print(f"32I Net P&L:       {df_32i['net_pnl'].sum():.4f}")
diff = df_canon['net_pnl'].sum() - df_32i['net_pnl'].sum()
print(f"Difference:        {diff:.4f}")

# Check trade-by-trade differences
diffs = []
for i in range(len(df_canon)):
    c_row = df_canon.iloc[i]
    i_row = df_32i.iloc[i]
    c_net = float(c_row["net_pnl"])
    i_net = float(i_row["net_pnl"])
    if abs(c_net - i_net) > 0.0001:
        diffs.append({
            "idx": i,
            "symbol": c_row["symbol"],
            "entry_date": c_row["entry_date"],
            "exit_date": c_row["exit_date"],
            "canon_net": c_net,
            "32i_net": i_net,
            "delta": c_net - i_net,
            "canon_gross": float(c_row["gross_pnl"]),
            "32i_gross": float(i_row["gross_pnl"]),
            "canon_costs": float(c_row["total_costs"]),
            "32i_costs": float(i_row["total_costs"]),
        })

print("\nTrade-by-trade discrepancies:")
df_diffs = pd.DataFrame(diffs)
print(df_diffs.to_string())
