"""
SignalForge - Phase 27C.2 Production Intraday Risk Integration Tests.

Verifies:
1. BacktestRunRequest exposure & strict validation of intraday risk parameters.
2. Causal ATR(14) stop-loss (1.5x) and take-profit (3.0x) exits.
3. Adverse gap execution through stop price (fill at bar_open).
4. Conservative same-candle collision handling (STOP evaluated before TARGET).
5. Intraday session square-off at 15:15 cutoff (exit_reason="EOD", zero overnight exposure).
6. Volatility-adjusted position sizing with independent 5x leverage cap (max initial exposure Rs 50,000 for Rs 10,000 capital).
7. Initial equity protection floor (Rs 8,000 floor / Rs 2,000 loss limit), blocking new entries upon breach.
8. Open position protection floor breach handling, documenting that gaps, slippage and statutory costs can cause realized loss to exceed Rs 2,000.
9. API response model propagation of risk_config, bankruptcy_reason, and trade exit reasons.
10. Canonical transaction cost engine parity across all intraday exit paths.
11. End-to-end JobManager lifecycle execution under Phase 27C.2 risk controls.
"""

import time
import math
import pytest
import pandas as pd
from pydantic import ValidationError

from src.api.models import BacktestRunRequest, BacktestJobResultResponse
from src.api.routes.strategy import create_backtest_job, get_backtest_job_result, get_backtest_job_status
from src.backtest.engine import IntradayEngineConfig, run_intraday_backtest
from src.backtest.indian_market_costs import get_cost_config
from src.backtest.simulator import Position
from src.strategy.job_manager import get_job_manager, JobStatus


# ============================================================================
# 1. API Request Risk Configuration Defaults & Strict Validation
# ============================================================================

def test_01_api_risk_configuration_defaults():
    """Verify BacktestRunRequest defaults reflect institutional intraday parameters."""
    req = BacktestRunRequest()
    assert req.initial_capital == 10000.0
    assert req.risk_per_trade_pct == 0.01
    assert req.max_leverage == 5.0
    assert req.stop_loss_atr == 1.5
    assert req.take_profit_atr == 3.0
    assert req.session_end_time == "15:15"
    assert req.cost_profile == "DISCOUNT_BROKER_REALISTIC"
    assert req.execution_model == "next_open"


def test_02_api_risk_configuration_validation_errors():
    """Verify BacktestRunRequest strictly validates risk fields and rejects unknown extra fields."""
    # 1. Stop loss ATR <= 0
    with pytest.raises(ValidationError):
        BacktestRunRequest(stop_loss_atr=0.0)
    with pytest.raises(ValidationError):
        BacktestRunRequest(stop_loss_atr=-1.5)

    # 2. Take profit ATR <= 0
    with pytest.raises(ValidationError):
        BacktestRunRequest(take_profit_atr=0.0)

    # 3. Invalid session_end_time format
    for bad_time in ["3pm", "25:00", "15:60", "9:15", "15:15:00", ""]:
        with pytest.raises(ValidationError):
            BacktestRunRequest(session_end_time=bad_time)

    # Valid session_end_time passes
    valid_req = BacktestRunRequest(session_end_time="15:20")
    assert valid_req.session_end_time == "15:20"

    # 4. Risk per trade out of bounds
    with pytest.raises(ValidationError):
        BacktestRunRequest(risk_per_trade_pct=0.0)
    with pytest.raises(ValidationError):
        BacktestRunRequest(risk_per_trade_pct=1.05)

    # 5. Max leverage < 1.0
    with pytest.raises(ValidationError):
        BacktestRunRequest(max_leverage=0.5)

    # 6. Negative capital protection floor
    with pytest.raises(ValidationError):
        BacktestRunRequest(capital_protection_floor=-100.0)

    # 7. Overall loss limit <= 0
    with pytest.raises(ValidationError):
        BacktestRunRequest(overall_loss_limit=0.0)

    # 8. Max exposure <= 0
    with pytest.raises(ValidationError):
        BacktestRunRequest(max_exposure=-500.0)

    # 9. Extra unknown field forbidden
    with pytest.raises(ValidationError):
        BacktestRunRequest(unauthorized_field="malicious")


# ============================================================================
# 2. ATR Stop-Loss Exits (Intrabar and Gap Execution)
# ============================================================================

def test_03_intraday_atr_stop_loss_intrabar_and_gap():
    """
    Verify ATR stop-loss triggers at 1.5x ATR.
    Also verifies adverse gap-through-stop executes at bar_open.
    """
    dates = pd.date_range("2024-01-02 09:15:00", periods=5, freq="min")
    # Entry at bar 1 (100.0). ATR is 2.0 -> stop_dist = 3.0 -> stop_p = 97.0
    # Bar 2 low drops to 96.5 -> triggers stop at 97.0
    df_intrabar = pd.DataFrame(
        {
            "open": [100.0, 100.0, 99.0, 99.0, 99.0],
            "high": [100.5, 100.5, 99.5, 99.5, 99.5],
            "low": [99.5, 100.0, 96.5, 98.0, 98.0],
            "close": [100.0, 100.0, 97.5, 99.0, 99.0],
            "volume": [1000.0] * 5,
            "atr": [2.0] * 5,
        },
        index=dates,
    )
    cfg = IntradayEngineConfig(
        initial_capital=10000.0,
        risk_per_trade=0.01,
        stop_atr_multiplier=1.5,
        target_atr_multiplier=3.0,
        execution_model="same_close",
    )
    res_intrabar = run_intraday_backtest(df_intrabar, [None, Position.LONG, None, None, None], cfg)
    assert len(res_intrabar.trades) == 1
    t = res_intrabar.trades[0]
    assert t.exit_reason == "STOP"
    assert t.exit_price == 97.0

    # Adverse gap down: Bar 2 opens at 95.0 (below stop_p 97.0) -> must fill at 95.0!
    df_gap = pd.DataFrame(
        {
            "open": [100.0, 100.0, 95.0, 95.0, 95.0],
            "high": [100.5, 100.5, 95.5, 95.5, 95.5],
            "low": [99.5, 100.0, 94.0, 94.0, 94.0],
            "close": [100.0, 100.0, 94.5, 95.0, 95.0],
            "volume": [1000.0] * 5,
            "atr": [2.0] * 5,
        },
        index=dates,
    )
    res_gap = run_intraday_backtest(df_gap, [None, Position.LONG, None, None, None], cfg)
    assert len(res_gap.trades) == 1
    t_gap = res_gap.trades[0]
    assert t_gap.exit_reason == "STOP"
    assert t_gap.exit_price == 95.0, f"Expected gap fill at bar_open 95.0, got {t_gap.exit_price}"


# ============================================================================
# 3. Take-Profit Target Exits
# ============================================================================

def test_04_intraday_take_profit_target_exit():
    """Verify take-profit target triggers at entry + (3.0 * ATR) for LONG."""
    dates = pd.date_range("2024-01-02 09:15:00", periods=5, freq="min")
    # Entry at 100.0. ATR = 2.0 -> target_p = 100 + (2.0 * 3.0) = 106.0
    # Bar 2 high reaches 106.5 -> target executed at 106.0
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0, 104.0, 105.0, 105.0],
            "high": [100.5, 100.5, 106.5, 105.5, 105.5],
            "low": [99.5, 100.0, 103.5, 104.5, 104.5],
            "close": [100.0, 100.0, 105.5, 105.0, 105.0],
            "volume": [1000.0] * 5,
            "atr": [2.0] * 5,
        },
        index=dates,
    )
    cfg = IntradayEngineConfig(
        initial_capital=10000.0,
        risk_per_trade=0.01,
        stop_atr_multiplier=1.5,
        target_atr_multiplier=3.0,
        execution_model="same_close",
    )
    res = run_intraday_backtest(df, [None, Position.LONG, None, None, None], cfg)
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_reason == "TARGET"
    assert t.exit_price == 106.0
    assert t.net_pnl > 0


# ============================================================================
# 4. Conservative Same-Candle Ambiguity Handling
# ============================================================================

def test_05_intraday_same_candle_conservative_collision():
    """Verify candle touching both stop and target conservatively executes STOP first."""
    dates = pd.date_range("2024-01-02 09:15:00", periods=5, freq="min")
    # Entry at 100.0. ATR = 2.0 -> stop_p = 97.0, target_p = 106.0
    # Bar 2 has high 107.0 (touches target) and low 96.0 (touches stop)
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0, 100.0, 100.0],
            "high": [100.5, 100.5, 107.0, 100.5, 100.5],
            "low": [99.5, 100.0, 96.0, 99.5, 99.5],
            "close": [100.0, 100.0, 101.0, 100.0, 100.0],
            "volume": [1000.0] * 5,
            "atr": [2.0] * 5,
        },
        index=dates,
    )
    cfg = IntradayEngineConfig(
        initial_capital=10000.0,
        risk_per_trade=0.01,
        stop_atr_multiplier=1.5,
        target_atr_multiplier=3.0,
        conservative_same_candle=True,
        execution_model="same_close",
    )
    res = run_intraday_backtest(df, [None, Position.LONG, None, None, None], cfg)
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_reason == "STOP"
    assert t.exit_price == 97.0


# ============================================================================
# 5. Intraday Session Square-Off at Configured Cutoff (15:15)
# ============================================================================

def test_06_intraday_session_square_off_at_1515():
    """Verify positions square off at 15:15 cutoff and no position is held overnight."""
    # Create intraday series passing 15:15
    dates = pd.date_range("2024-01-02 15:10:00", periods=10, freq="min")
    df = pd.DataFrame(
        {
            "open": [100.0] * 10,
            "high": [100.5] * 10,
            "low": [99.5] * 10,
            "close": [100.0] * 10,
            "volume": [1000.0] * 10,
            "atr": [2.0] * 10,
        },
        index=dates,
    )
    # Signal at 15:12 (bar 2). Session end time configured to 15:15.
    cfg = IntradayEngineConfig(
        initial_capital=10000.0,
        session_end_time="15:15",
        enforce_eod_square_off=True,
        execution_model="same_close",
    )
    signals = [None, None, Position.LONG, None, None, None, None, None, None, None]
    res = run_intraday_backtest(df, signals, cfg)
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_reason == "EOD"
    assert str(t.exit_time).endswith("15:15:00")

    # Signals at or after 15:15 must be rejected
    signals_late = [None, None, None, None, None, Position.LONG, None, None, None, None]
    res_late = run_intraday_backtest(df, signals_late, cfg)
    assert len(res_late.trades) == 0


# ============================================================================
# 6. Risk-Based Position Sizing and 5x Leverage Cap
# ============================================================================

def test_07_risk_based_position_sizing_and_5x_leverage_cap():
    """
    Verify position sizing = min(risk_quantity, leverage_quantity).
    With initial capital Rs 10,000, 5x max leverage caps initial exposure at Rs 50,000.
    """
    dates = pd.date_range("2024-01-02 09:15:00", periods=5, freq="min")
    # Share price Rs 1,000.
    # Capital Rs 10,000 -> 1% risk = Rs 100.
    # ATR = 0.5 -> stop_dist = 0.75 -> risk_qty = 100 / 0.75 = 133 shares.
    # Leverage cap: notional = Rs 50,000 -> max_allowed_qty = 50,000 / 1,000 = 50 shares.
    # Expected final_qty = min(133, 50) = 50 shares!
    df = pd.DataFrame(
        {
            "open": [1000.0] * 5,
            "high": [1005.0] * 5,
            "low": [995.0] * 5,
            "close": [1000.0] * 5,
            "volume": [1000.0] * 5,
            "atr": [0.5] * 5,
        },
        index=dates,
    )
    cfg = IntradayEngineConfig(
        initial_capital=10000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        max_exposure=50000.0,
        stop_atr_multiplier=1.5,
        execution_model="same_close",
    )
    res = run_intraday_backtest(df, [None, Position.LONG, None, None, None], cfg)
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.quantity == 50
    assert t.max_allowed_quantity == 50
    assert t.risk_based_quantity == 133
    # Exposure cannot exceed Rs 50,000
    assert t.entry_price * t.quantity <= 50000.0


# ============================================================================
# 7. Initial Equity Protection Floor (Rs 8,000 Floor / Rs 2,000 Loss Limit)
# ============================================================================

def test_08_equity_protection_floor_blocks_new_entries():
    """
    Verify that when capital drops to or below the Rs 8,000 protection floor,
    subsequent entries are blocked and bankruptcy_reason reports the floor breach.
    """
    dates = pd.date_range("2024-01-02 09:15:00", periods=10, freq="min")
    df = pd.DataFrame(
        {
            "open": [100.0] * 10,
            "high": [101.0] * 10,
            "low": [99.0] * 10,
            "close": [100.0] * 10,
            "volume": [1000.0] * 10,
            "atr": [2.0] * 10,
        },
        index=dates,
    )
    # Configure initial capital Rs 10,000, protection floor Rs 8,000
    # But start capital directly at Rs 7,950 (already below floor)
    cfg = IntradayEngineConfig(
        initial_capital=7950.0,
        capital_protection_floor=8000.0,
        execution_model="same_close",
    )
    res = run_intraday_backtest(df, [None, Position.LONG, None, Position.LONG, None, None, None, None, None, None], cfg)
    # Must immediately block entries
    assert len(res.trades) == 0
    assert res.bankruptcy_reason is not None
    assert "PROTECTION_FLOOR" in res.bankruptcy_reason
    assert res.portfolio.is_bankrupt is True


def test_09_open_position_protection_floor_breach_and_gap_slippage():
    """
    Verify open position price move breaching the protection floor initiates an exit
    with exit_reason='PROTECTION_FLOOR'.
    Documents that adverse gaps, slippage, and transaction costs can cause realized loss to exceed Rs 2,000.
    """
    dates = pd.date_range("2024-01-02 09:15:00", periods=6, freq="min")
    # Initial capital Rs 10,000, protection floor Rs 8,000 (loss limit Rs 2,000).
    # Entry at 100.0 with wide stop (e.g. stop_mult 20.0 so floor binds before stop).
    # Bar 2 gaps down to 75.0 (adverse gap).
    # Unrealized loss = (75 - 100) * 100 = -Rs 2,500.
    # Equity drops to Rs 7,500 (below Rs 8,000 floor).
    # Realistic execution: fills at open 75.0, realized loss = Rs 2,500 + costs > Rs 2,000.
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0, 75.0, 75.0, 75.0, 75.0],
            "high": [100.5, 100.5, 76.0, 76.0, 76.0, 76.0],
            "low": [99.5, 100.0, 74.0, 74.0, 74.0, 74.0],
            "close": [100.0, 100.0, 75.5, 75.0, 75.0, 75.0],
            "volume": [1000.0] * 6,
            "atr": [1.0] * 6,
        },
        index=dates,
    )
    cost_cfg = get_cost_config("DISCOUNT_BROKER_REALISTIC")
    cfg = IntradayEngineConfig(
        initial_capital=10000.0,
        risk_per_trade=0.50,  # 50% risk allows 100 shares so floor_p (80.0) binds before stop_p (50.0)
        max_leverage=5.0,
        stop_atr_multiplier=50.0,  # Wide stop (50.0) so protection floor triggers first
        capital_protection_floor=8000.0,
        cost_config=cost_cfg,
        gap_execution=True,
        execution_model="same_close",
    )
    res = run_intraday_backtest(df, [None, Position.LONG, None, None, None, None], cfg)
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_reason == "PROTECTION_FLOOR"
    assert t.exit_price == 75.0  # Adverse gap fill at bar_open

    # Terminal cash is below Rs 8,000, proving realized loss exceeded Rs 2,000 due to gap + costs
    assert res.portfolio.cash < 8000.0
    total_realized_loss = res.portfolio.initial_capital - res.portfolio.cash
    assert total_realized_loss > 2000.0
    assert res.bankruptcy_reason is not None
    assert "PROTECTION_FLOOR" in res.bankruptcy_reason


# ============================================================================
# 8. API Response Model Propagation of Risk & Bankruptcy Fields
# ============================================================================

def test_10_api_result_fields_propagation():
    """Verify BacktestJobResultResponse correctly parses risk_config, bankruptcy_reason, and exit_reason."""
    raw_payload = {
        "job_id": "job-test123456",
        "status": "COMPLETED",
        "symbol": "NIFTY 50",
        "date_range": {"start": "2024-01-01", "end": "2024-01-15", "total_candles": 4125},
        "execution_model": "next_open",
        "cost_model": {"mode": "CANONICAL", "profile_name": "DISCOUNT_BROKER_REALISTIC"},
        "risk_config": {
            "initial_capital": 10000.0,
            "risk_per_trade_pct": 0.01,
            "max_leverage": 5.0,
            "max_exposure": 50000.0,
            "stop_loss_atr": 1.5,
            "take_profit_atr": 3.0,
            "session_end_time": "15:15",
            "capital_protection_floor": 8000.0,
            "overall_loss_limit": 2000.0,
        },
        "bankruptcy_reason": "PROTECTION_FLOOR: Capital dropped to 7950.00",
        "metrics": {
            "total_trades": 1,
            "winning_trades": 0,
            "losing_trades": 1,
            "breakeven_trades": 0,
            "total_pnl": -2050.0,
            "total_return_pct": -20.5,
            "win_rate_pct": 0.0,
            "average_win": 0.0,
            "average_loss": -2050.0,
            "profit_factor": "0.0",
            "expectancy": -2050.0,
            "max_drawdown_pct": 20.5,
        },
        "portfolio": {
            "initial_capital": 10000.0,
            "final_equity": 7950.0,
            "peak_equity": 10000.0,
            "max_drawdown_pct": 20.5,
            "is_bankrupt": True,
            "bankruptcy_reason": "PROTECTION_FLOOR: Capital dropped to 7950.00",
        },
        "trades": [
            {
                "trade_id": 1,
                "entry_time": "2024-01-02 09:15:00",
                "exit_time": "2024-01-02 11:30:00",
                "side": "LONG",
                "entry_price": 21500.0,
                "exit_price": 21000.0,
                "quantity": 2,
                "gross_pnl": -1000.0,
                "costs": 35.5,
                "net_pnl": -1035.5,
                "return_pct": -2.408,
                "exit_reason": "STOP",
            }
        ],
    }
    model = BacktestJobResultResponse(**raw_payload)
    assert model.job_id == "job-test123456"
    assert model.bankruptcy_reason == "PROTECTION_FLOOR: Capital dropped to 7950.00"
    assert model.risk_config["capital_protection_floor"] == 8000.0
    assert model.risk_config["stop_loss_atr"] == 1.5
    assert model.trades[0].exit_reason == "STOP"
    assert model.portfolio["is_bankrupt"] is True


# ============================================================================
# 9. Canonical Transaction Cost Integration Across All Intraday Exits
# ============================================================================

def test_11_canonical_transaction_costs_integrated_in_intraday_exits():
    """Verify all intraday exits (STOP, TARGET, EOD) accurately deduct canonical statutory costs."""
    dates = pd.date_range("2024-01-02 09:15:00", periods=5, freq="min")
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0, 105.0, 105.0, 105.0],
            "high": [100.5, 100.5, 106.5, 105.5, 105.5],
            "low": [99.5, 100.0, 104.0, 104.5, 104.5],
            "close": [100.0, 100.0, 105.5, 105.0, 105.0],
            "volume": [1000.0] * 5,
            "atr": [2.0] * 5,
        },
        index=dates,
    )
    cost_cfg = get_cost_config("DISCOUNT_BROKER_REALISTIC")
    cfg = IntradayEngineConfig(
        initial_capital=10000.0,
        risk_per_trade=0.01,
        stop_atr_multiplier=1.5,
        target_atr_multiplier=3.0,
        cost_config=cost_cfg,
        execution_model="same_close",
    )
    res = run_intraday_backtest(df, [None, Position.LONG, None, None, None], cfg)
    assert len(res.trades) == 1
    t = res.trades[0]
    # Costs must be strictly positive and accurately separated
    assert t.transaction_cost > 0.0
    assert abs(t.net_pnl - (t.gross_pnl - t.transaction_cost)) < 1e-4
    assert res.cost_model_info["mode"] == "CANONICAL"
    assert res.cost_model_info["profile_name"] == "DISCOUNT_BROKER_REALISTIC"


# ============================================================================
# 10. End-to-End API Job Lifecycle with Production Intraday Risk Integration
# ============================================================================

def test_12_end_to_end_job_lifecycle_with_intraday_risk():
    """
    Verify complete end-to-end API lifecycle via create_backtest_job and get_backtest_job_result
    with Phase 27C.2 risk controls active.
    Uses authentic historical 2024 NIFTY 50 data slice (excluding 2020 holdout).
    """
    req = BacktestRunRequest(
        symbol="NIFTY 50",
        start_date="2024-01-01",
        end_date="2024-01-10",
        initial_capital=10000.0,
        stop_loss_atr=1.5,
        take_profit_atr=3.0,
        session_end_time="15:15",
        risk_per_trade_pct=0.01,
        max_leverage=5.0,
        capital_protection_floor=8000.0,
        overall_loss_limit=2000.0,
        execution_model="next_open",
    )
    job_res = create_backtest_job(req)
    assert job_res.job_id
    assert job_res.status in ("QUEUED", "RUNNING")

    # Await completion
    deadline = time.time() + 20.0
    while time.time() < deadline:
        stat = get_backtest_job_status(job_res.job_id)
        if stat.status == "COMPLETED":
            break
        time.sleep(0.2)

    api_res = get_backtest_job_result(job_res.job_id)
    assert api_res.status == "COMPLETED"
    assert api_res.symbol == "NIFTY 50"

    # Verify risk_config in response
    assert api_res.risk_config is not None
    assert api_res.risk_config["initial_capital"] == 10000.0
    assert api_res.risk_config["stop_loss_atr"] == 1.5
    assert api_res.risk_config["take_profit_atr"] == 3.0
    assert api_res.risk_config["session_end_time"] == "15:15"
    assert api_res.risk_config["capital_protection_floor"] == 8000.0

    # Verify trades have valid intraday exit reasons
    assert isinstance(api_res.trades, list)
    for t in api_res.trades:
        assert t.exit_reason in ("STOP", "TARGET", "EOD", "PROTECTION_FLOOR", "SIGNAL")
        assert t.costs > 0
        assert t.quantity >= 1

    # Verify mathematical return identity preserves Phase 27C.1 fix
    expected_ret = round((api_res.metrics.total_pnl / 10000.0) * 100.0, 2)
    assert abs(api_res.metrics.total_return_pct - expected_ret) < 1e-4
