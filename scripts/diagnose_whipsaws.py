import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_phase32i_dtp_v3_evaluation import run_dtp_simulation, load_and_resample_21_universe, APPROVED_21_SYMBOLS, EXPANDED_SECTOR_MAP, EXPANDED_ISIN_MAP
from src.strategy.dtp_v2.config import DTPV2Config
from src.strategy.dtp_v2.indicators import calculate_dtp_indicators as calc_ind_v2
from src.strategy.dtp_v3.config import DTPV3Config
from src.strategy.dtp_v3.indicators import calculate_dtp_indicators as calc_ind_v3
import pandas as pd

raw = load_and_resample_21_universe()
trading_dates = list(raw[APPROVED_21_SYMBOLS[0]].index)

cfg_v2 = DTPV2Config(symbol_sector_map=EXPANDED_SECTOR_MAP, symbol_isin_map=EXPANDED_ISIN_MAP)
cfg_v3 = DTPV3Config(symbol_sector_map=EXPANDED_SECTOR_MAP, symbol_isin_map=EXPANDED_ISIN_MAP)

aug_v2 = {s: calc_ind_v2(raw[s], config=cfg_v2) for s in APPROVED_21_SYMBOLS}
aug_v3 = {s: calc_ind_v3(raw[s], config=cfg_v3) for s in APPROVED_21_SYMBOLS}

res_v2 = run_dtp_simulation("DTP-V2", aug_v2, trading_dates, risk_pct=0.01, use_stress_costs=False)
res_v3 = run_dtp_simulation("DTP-V3", aug_v3, trading_dates, risk_pct=0.01, use_stress_costs=False)

t_v2 = res_v2["df_trades"]
t_v3 = res_v3["df_trades"]

v3_keys = set(zip(t_v3["symbol"], t_v3["entry_date"]))
eliminated = []
for idx, r in t_v2.iterrows():
    if (r["symbol"], r["entry_date"]) not in v3_keys:
        eliminated.append(r)

df_elim = pd.DataFrame(eliminated)
print("=" * 80)
print(f"Total Eliminated Trades in DTP-V3: {len(df_elim)}")
print(f"Eliminated Trades Gross P&L: ₹{df_elim['gross_pnl'].sum():.2f}")
print(f"Eliminated Trades Friction Costs: ₹{df_elim['total_costs'].sum():.2f}")
print(f"Eliminated Trades Net P&L: ₹{df_elim['net_pnl'].sum():.2f}")
wins = len(df_elim[df_elim["net_pnl"] > 0])
losses = len(df_elim[df_elim["net_pnl"] <= 0])
print(f"Eliminated Trades: {wins} Wins, {losses} Losses (Win Rate: {wins/len(df_elim)*100:.1f}%)")
print("=" * 80)
print(df_elim[["symbol", "entry_date", "exit_date", "exit_reason", "gross_pnl", "total_costs", "net_pnl"]].to_string())

# Also check why each was eliminated (Chop index vs upper-half close)
print("\n" + "=" * 80)
print("REJECTION ATTRIBUTION FOR ELIMINATED TRADES")
print("=" * 80)
for idx, r in df_elim.iterrows():
    sym = r["symbol"]
    e_date = r["entry_date"]
    # Signal date was 1 trading session prior
    e_idx = trading_dates.index(pd.Timestamp(e_date))
    sig_idx = e_idx - 1
    sig_row = aug_v3[sym].iloc[sig_idx]
    c = float(sig_row["close"])
    h = float(sig_row["high"])
    l = float(sig_row["low"])
    chop = float(sig_row["chop_index"])
    ratio = (c - l) / (h - l) if (h - l) > 0 else 0.0
    reasons = []
    if chop > 60.0:
        reasons.append(f"Chop ({chop:.1f} > 60.0)")
    if ratio < 0.50:
        reasons.append(f"CloseRatio ({ratio:.1%} < 50%)")
    print(f"{sym:<12} | Entry: {e_date} | NetPnL: ₹{r['net_pnl']:>8.2f} | Filter Reason: {', '.join(reasons)}")
