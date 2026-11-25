import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
from datetime import date
from src.strategy.dtp_v3.indicators import calculate_atr, calculate_adx

# 1. Load 2019 Trades from Fixed Max 2 E2
df = pd.read_csv('reports/phase32j_5/trade_ledger.csv')
max2_e2 = df[(df['scenario_id'].str.contains('MAX2')) & (df['scenario_id'].str.contains('2pct_STRESS'))].copy()
max2_e2['entry_date_dt'] = pd.to_datetime(max2_e2['entry_date']).dt.date
t2019 = max2_e2[max2_e2['entry_date_dt'] >= date(2019, 1, 1)].copy()

print(f"Total 2019 Trades: {len(t2019)}")
print(t2019[['symbol', 'entry_date', 'exit_date', 'entry_price', 'exit_price', 'net_pnl', 'exit_reason']])

# 2. Load Nifty indicators
res_path = 'data/historical/nifty50_1m_research.csv'
canon_path = 'temp_nse_data/NSE Minute Data/NSE_Index_Data/NIFTY_50__EQ__INDICES__NSE__MINUTE.csv'

df_res = pd.read_csv(res_path)
df_res['date'] = pd.to_datetime(df_res['timestamp']).dt.date
daily_pre = df_res[df_res['date'] < date(2017, 1, 2)].groupby('date').agg({
    'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'
})
daily_pre.columns = ['open', 'high', 'low', 'close']

df_idx = pd.read_csv(canon_path)
df_idx['date'] = pd.to_datetime(df_idx['timestamp']).dt.date
daily_main = df_idx[(df_idx['date'] >= date(2017, 1, 2)) & (df_idx['date'] <= date(2019, 12, 31))].groupby('date').agg({
    'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
})

combined = pd.concat([daily_pre, daily_main]).sort_index()
combined['sma100'] = combined['close'].rolling(window=100).mean()
combined['sma100_slope'] = combined['sma100'] - combined['sma100'].shift(1)
combined['dist_sma100'] = (combined['close'] - combined['sma100']) / combined['sma100']

adx, p_di, m_di = calculate_adx(combined['high'], combined['low'], combined['close'], period=14)
combined['adx14'] = adx

atr = calculate_atr(combined['high'], combined['low'], combined['close'], period=14)
combined['atr14'] = atr
combined['natr'] = combined['atr14'] / combined['close']
combined['natr_p75'] = combined['natr'].rolling(window=60).quantile(0.75)
combined['natr_p90'] = combined['natr'].rolling(window=60).quantile(0.90)

combined['abs_ret'] = ((combined['close'] - combined['close'].shift(1)) / combined['close'].shift(1)).abs()
combined['abs_ret_p90'] = combined['abs_ret'].rolling(window=60).quantile(0.90)

print("\n--- NIFTY CONDITIONS ON SIGNAL DATES (Day before entry) ---")
# Remember: Signal is generated at EOD of Day T, and entry executes on open of Day T+1!
trading_dates = list(daily_main.index)
for _, r in t2019.iterrows():
    e_dt = r['entry_date_dt']
    e_idx = trading_dates.index(e_dt)
    sig_dt = trading_dates[e_idx - 1]
    n_row = combined.loc[sig_dt]
    print(f"\nTrade {r['symbol']} | Entry: {e_dt} | Signal EOD: {sig_dt}")
    print(f"  Nifty Close: {n_row['close']:.1f} | SMA100: {n_row['sma100']:.1f} | Dist: {n_row['dist_sma100']*100:.2f}% | Slope: {n_row['sma100_slope']:.2f}")
    print(f"  ADX(14): {n_row['adx14']:.2f} (>=20? {n_row['adx14']>=20}, >=25? {n_row['adx14']>=25})")
    print(f"  NATR: {n_row['natr']:.4f} vs P75: {n_row['natr_p75']:.4f} (<P75? {n_row['natr'] < n_row['natr_p75']}), vs P90: {n_row['natr_p90']:.4f} (<P90? {n_row['natr'] < n_row['natr_p90']})")
    print(f"  AbsRet: {n_row['abs_ret']:.4f} vs P90: {n_row['abs_ret_p90']:.4f} (<P90? {n_row['abs_ret'] < n_row['abs_ret_p90']})")
