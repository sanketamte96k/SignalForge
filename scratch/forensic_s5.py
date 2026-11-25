import pandas as pd
import numpy as np

df = pd.read_csv('reports/phase33a/trade_ledger.csv')
s5 = df[df['strategy'].str.contains('Strategy 5')].copy()
s5['exit_date'] = pd.to_datetime(s5['exit_date'])
s5['entry_date'] = pd.to_datetime(s5['entry_date'])
s5['year'] = s5['exit_date'].dt.year
s5['month'] = s5['exit_date'].dt.to_period('M').astype(str)

print("="*60)
print("S5 OVERALL RECONCILIATION")
print("="*60)
print(f"Total Trades: {len(s5)}")
print(f"Gross PnL: {s5['gross_pnl'].sum():.2f}")
print(f"Total Costs (ledger): {s5['total_costs'].sum():.2f}")
print(f"Slippage: {s5['slippage'].sum():.2f}")
print(f"Statutory + Brokerage: {(s5['total_costs'].sum() - s5['slippage'].sum()):.2f}")
print(f"Net PnL (double slipped): {s5['net_pnl'].sum():.2f}")
print(f"Net PnL (single slipped / cash equity): {(s5['gross_pnl'].sum() - (s5['total_costs'].sum() - s5['slippage'].sum())):.2f}")

print("\n" + "="*60)
print("S5 YEARLY BREAKDOWN")
print("="*60)
yearly = s5.groupby('year').agg({
    'trade_id': 'count',
    'gross_pnl': 'sum',
    'slippage': 'sum',
    'total_costs': 'sum',
    'net_pnl': 'sum'
}).rename(columns={'trade_id': 'trades'})
yearly['statutory_broker'] = yearly['total_costs'] - yearly['slippage']
yearly['single_slipped_net_pnl'] = yearly['gross_pnl'] - yearly['statutory_broker']
print(yearly)

print("\n" + "="*60)
print("2018 LOSS INVESTIGATION")
print("="*60)
s5_2018 = s5[s5['year'] == 2018]
print(f"2018 Trades: {len(s5_2018)}")
wins = s5_2018[s5_2018['net_pnl'] > 0]
losses = s5_2018[s5_2018['net_pnl'] <= 0]
print(f"Wins: {len(wins)}, Losses: {len(losses)}, Win rate: {len(wins)/len(s5_2018)*100:.2f}%")
print(f"Gross Win: {wins['gross_pnl'].sum():.2f}, Gross Loss: {losses['gross_pnl'].sum():.2f}")
print(f"Total Friction: {s5_2018['total_costs'].sum():.2f}")
print(f"Net PnL (double slipped): {s5_2018['net_pnl'].sum():.2f}")
print(f"Net PnL (single slipped): {(s5_2018['gross_pnl'].sum() - (s5_2018['total_costs'].sum() - s5_2018['slippage'].sum())):.2f}")

print("\nExit Reasons in 2018:")
print(s5_2018.groupby('exit_reason')['net_pnl'].agg(['count', 'sum', 'mean']))

print("\nSector Distribution in 2018:")
print(s5_2018.groupby('sector')['net_pnl'].agg(['count', 'sum']))

print("\nTop 5 Losing Trades in 2018:")
print(s5_2018.sort_values(by='net_pnl').head(5)[['symbol', 'entry_date', 'exit_date', 'bars_held', 'exit_reason', 'gross_pnl', 'net_pnl']])

print("\n" + "="*60)
print("TOP 3 TRADE DEPENDENCY AUDIT")
print("="*60)
top3 = s5.sort_values(by='net_pnl', ascending=False).head(3)
print("Top 3 Winners:")
print(top3[['symbol', 'entry_date', 'exit_date', 'bars_held', 'exit_reason', 'gross_pnl', 'net_pnl']])
top3_sum = top3['net_pnl'].sum()
print(f"Top 3 Net PnL Sum: {top3_sum:.2f}")
ex_top3 = s5[~s5.index.isin(top3.index)]
print(f"Ex-Top 3 Net PnL (double slipped): {ex_top3['net_pnl'].sum():.2f}")
ex_top3_single = ex_top3['gross_pnl'].sum() - (ex_top3['total_costs'].sum() - ex_top3['slippage'].sum())
print(f"Ex-Top 3 Net PnL (single slipped): {ex_top3_single:.2f}")

print("\n" + "="*60)
print("MONTHLY BREAKDOWN & ZERO-TRADE MONTHS")
print("="*60)
m_grp = s5.groupby('month').agg({'net_pnl': ['count', 'sum']})
print(m_grp)
