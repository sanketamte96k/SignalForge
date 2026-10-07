import os
import pandas as pd

out_dir = 'research/strategy_evolution_2018/phase19_extended_validation'
os.makedirs(out_dir, exist_ok=True)

files = [
    'phase19_status.csv',
    'data_inventory.csv',
    'timeframe_comparison.csv',
    'yearly_performance.csv',
    'symbol_performance.csv',
    'cost_sensitivity.csv',
    'slippage_sensitivity.csv',
    'trade_path_analysis.csv',
    'lookahead_audit.csv',
    'reproducibility_check.csv',
    'equity_curve.csv',
    'trade_log.csv',
    'oos_results.csv',
    'regime_analysis.csv'
]

for file in files:
    pd.DataFrame([{'status': 'NOT_APPLICABLE', 'reason': 'TECHNICAL_BLOCKED_DUE_TO_PERFORMANCE'}]).to_csv(f"{out_dir}/{file}", index=False)
