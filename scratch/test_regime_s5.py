import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from src.strategy.dtp_v3_regime_protection.market_filter import NiftyRegimeProtectionFilter

df = pd.read_csv('reports/phase33a/trade_ledger.csv')
s5 = df[df['strategy'].str.contains('Strategy 5')].copy()
s5['entry_date'] = pd.to_datetime(s5['entry_date']).dt.date

nifty_filter = NiftyRegimeProtectionFilter()
df_nifty = nifty_filter._daily_nifty.copy()
df_nifty['sma100_rising'] = df_nifty['sma100'] >= df_nifty['sma100'].shift(1)
df_nifty['above_sma100'] = df_nifty['close'] > df_nifty['sma100']
df_nifty['bull_regime'] = df_nifty['above_sma100'] & df_nifty['sma100_rising']

# Map entry dates
s5['nifty_above_sma100'] = s5['entry_date'].map(df_nifty['above_sma100'])
s5['nifty_sma100_rising'] = s5['entry_date'].map(df_nifty['sma100_rising'])
s5['nifty_bull_regime'] = s5['entry_date'].map(df_nifty['bull_regime'])

print("S5 Trades by Nifty Regime at Entry:")
print(s5.groupby('nifty_bull_regime')['net_pnl'].agg(['count', 'sum', 'mean']))

print("\nMay 2018 trades Nifty Regime:")
s5_may18 = s5[(s5['entry_date'] >= pd.to_datetime('2018-05-01').date()) & (s5['entry_date'] <= pd.to_datetime('2018-05-31').date())]
print(s5_may18[['symbol', 'entry_date', 'exit_date', 'net_pnl', 'nifty_above_sma100', 'nifty_sma100_rising', 'nifty_bull_regime']])
