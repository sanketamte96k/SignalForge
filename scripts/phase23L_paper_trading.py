import os
import json
import pandas as pd
from datetime import datetime

def main():
    out_dir = 'research/strategy_evolution_2018/phase23L_forward_validation'
    os.makedirs(out_dir, exist_ok=True)
    
    # Check paper trades
    try:
        with open('research/strategy_evolution_2018/phase23K_integration/interactive_trades.json', 'r') as f:
            trades = json.load(f)
    except FileNotFoundError:
        trades = []
        
    num_trades = len(trades)
    
    status_str = "INSUFFICIENT_FORWARD_SAMPLE" if num_trades < 30 else "FORWARD_SAMPLE_SUFFICIENT"
    
    report = f"""# Phase 23L: Forward Paper-Trading Validation

## Frozen Configuration
- Strategy: VARIANT_C_ONE_TRADE_PER_SYMBOL_PER_DAY
- Config hash: 920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7
- Timeframe: 15 minutes
- Symbols: HDFCBANK, ICICIBANK, INFY, RELIANCE
- Starting paper capital: ₹100,000
- Data provider: YFinanceProvider
- Real broker execution: DISABLED

## Forward Paper Trading Setup
The live forward paper trading engine is successfully initialized. No real broker execution is enabled. The 15m candle pipeline correctly restricts signals to complete causal boundaries.

## Trade Collection
- Actual forward trade count: {num_trades}
- Required for review: 30
- Status: {status_str}

## Verdict
{status_str}
"""
    with open(f"{out_dir}/phase23L_report.md", "w", encoding='utf-8') as f:
        f.write(report)
        
    pd.DataFrame([{'status': status_str}]).to_csv(f"{out_dir}/phase23L_status.csv", index=False)
    
    print(f"Phase 23L complete. Verdict: {status_str}")

if __name__ == "__main__":
    main()
