import pandas as pd

df_trades = pd.read_csv('reports/phase32j_7/trade_ledger.csv')
base_trades = df_trades[df_trades['scenario_id'] == 'BASELINE_BASELINE_SMA100_2pct_STRESS']
a3_trades = df_trades[df_trades['scenario_id'] == 'EXP_A_A3_RISING_SMA100_A3_RISING_SMA100_2pct_STRESS']

print(f"Base trade count: {len(base_trades)}")
print(f"A3 trade count: {len(a3_trades)}")

base_keys = set(zip(base_trades['symbol'], base_trades['entry_date']))
a3_keys = set(zip(a3_trades['symbol'], a3_trades['entry_date']))

diff = base_keys - a3_keys
print(f"Trades in Baseline but blocked by A3 (Rising SMA100): {len(diff)}")
for sym, e_dt in sorted(diff):
    t_row = base_trades[(base_trades['symbol'] == sym) & (base_trades['entry_date'] == e_dt)].iloc[0]
    print(f"{sym} | Entry: {e_dt} | Exit: {t_row['exit_date']} | Net PnL: Rs {t_row['net_pnl']:.2f} | Reason: {t_row['exit_reason']}")

print("\nTrades in A3 but not in Baseline:")
diff_a3 = a3_keys - base_keys
print(f"Count: {len(diff_a3)}")
for sym, e_dt in sorted(diff_a3):
    t_row = a3_trades[(a3_trades['symbol'] == sym) & (a3_trades['entry_date'] == e_dt)].iloc[0]
    print(f"{sym} | Entry: {e_dt} | Exit: {t_row['exit_date']} | Net PnL: Rs {t_row['net_pnl']:.2f} | Reason: {t_row['exit_reason']}")
