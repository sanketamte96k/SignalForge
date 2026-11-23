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
from src.strategy.dtp_v2.indicators import calculate_dtp_indicators as calculate_dtp_indicators_v2
from scripts.run_phase32e_2_validation import run_strategy_simulation

print('Loading 2017-2019 universe...')
universe_daily = load_and_resample_21_universe()
trading_dates = list(universe_daily[APPROVED_21_SYMBOLS[0]].index)
print(f'Universe loaded: {len(universe_daily)} symbols, {len(trading_dates)} trading sessions ({trading_dates[0].date()} to {trading_dates[-1].date()}).')

cfg_v2 = DTPV2Config(symbol_sector_map=EXPANDED_SECTOR_MAP, symbol_isin_map=EXPANDED_ISIN_MAP)
augmented_v2 = {}
for sym in APPROVED_21_SYMBOLS:
    augmented_v2[sym] = calculate_dtp_indicators_v2(universe_daily[sym], config=cfg_v2)

res_v2_off = run_strategy_simulation('DTP-V2', augmented_v2, trading_dates, use_stress_costs=False, initial_capital=100000.0)
res_v2_str = run_strategy_simulation('DTP-V2', augmented_v2, trading_dates, use_stress_costs=True, initial_capital=100000.0)

s_off = res_v2_off['summary']
s_str = res_v2_str['summary']
print(f"DTP-V2 Official Net Profit: {s_off['net_pnl']:.2f}, Trades: {s_off['total_trades']}, WinRate: {s_off['win_rate_pct']}%, NetPF: {s_off['net_pf']}, MaxDD: {s_off['max_drawdown_pct']}%")
print(f"DTP-V2 Stress Net Profit: {s_str['net_pnl']:.2f}, Trades: {s_str['total_trades']}, WinRate: {s_str['win_rate_pct']}%, NetPF: {s_str['net_pf']}, MaxDD: {s_str['max_drawdown_pct']}%")
