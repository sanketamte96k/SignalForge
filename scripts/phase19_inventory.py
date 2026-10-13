import os
import pandas as pd
from datetime import datetime

os.makedirs('research/strategy_evolution_2018/phase19_extended_validation', exist_ok=True)

df = pd.read_csv('data/historical/nifty50_1m_signalforge.csv')
start = df['timestamp'].min()
end = df['timestamp'].max()
rows = len(df)

inv_df = pd.DataFrame([{
    'symbol': 'NIFTY50',
    'timeframe': '1m',
    'start_date': start,
    'end_date': end,
    'row_count': rows,
    'ohlcv_available': True,
    'missing_values': df.isnull().sum().sum(),
    'duplicate_timestamps': df.duplicated(subset=['timestamp']).sum()
}])
inv_df.to_csv('research/strategy_evolution_2018/phase19_extended_validation/data_inventory.csv', index=False)

print(f"Data: NIFTY50, {start} to {end}, {rows} candles")
