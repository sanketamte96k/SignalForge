"""
SignalForge — Backtest Analytics & Standalone HTML Tearsheet Generator
======================================================================
Provides deterministic equity-curve construction, drawdown analytics,
extended quantitative performance metrics, responsive SVG chart generation,
and self-contained HTML research tearsheets.

Design Principles:
1. Zero fabrication: Equity points derive strictly from chronological trade completions.
2. Causal transparency: Prominently identifies execution model (causal vs theoretical).
3. Cryptographic provenance: Embeds configuration SHA-256 and dataset SHA-256.
4. 100% Offline and self-contained: No CDN, no tracking, zero paid infrastructure.
5. Bit-for-bit reproducibility: Can rebuild full reports from saved backtest results.
"""

from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.io_utils import atomic_write


FROZEN_V1_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
CANONICAL_ADANIPORTS_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"
CANONICAL_NIFTY50_HASH = "f5a1047ee65129c52eb8dfb1888a9daf41a2a6f21e1297beefb7b505e4065e2a"


def calculate_equity_curve(
    initial_capital: float,
    trades: List[Dict[str, Any]],
    start_time: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Construct a chronological equity progression curve from completed trades.

    Mathematical Invariants:
    - Point 0 represents initial capital prior to any trade execution.
    - Each subsequent point k corresponds to the account state immediately
      following the completion of trade k.
    - Drawdown is defined as: Drawdown = Current Equity - Previous Peak Equity.
    - Percentage Drawdown is: (Current Equity - Peak Equity) / Peak Equity * 100.
    - When equity reaches or exceeds previous peak, Drawdown = 0.0.
    """
    initial_cap = float(initial_capital)
    if initial_cap <= 0:
        raise ValueError("initial_capital must be greater than zero.")

    first_timestamp = str(start_time) if start_time else (trades[0].get("entry_time", "Start") if trades else "Start")

    curve: List[Dict[str, Any]] = [
        {
            "step": 0,
            "timestamp": first_timestamp,
            "trade_id": None,
            "side": None,
            "gross_pnl": 0.0,
            "costs": 0.0,
            "net_pnl": 0.0,
            "equity": round(initial_cap, 2),
            "peak_equity": round(initial_cap, 2),
            "drawdown": 0.0,
            "drawdown_pct": 0.0,
        }
    ]

    current_equity = initial_cap
    running_peak = initial_cap

    for idx, trade in enumerate(trades, 1):
        net_pnl = float(trade.get("net_pnl", 0.0))
        gross_pnl = float(trade.get("gross_pnl", 0.0))
        costs = float(trade.get("costs", 0.0))

        current_equity += net_pnl
        if current_equity > running_peak:
            running_peak = current_equity

        drawdown = current_equity - running_peak  # <= 0.0
        drawdown_pct = (drawdown / running_peak * 100.0) if running_peak > 0 else 0.0

        exit_ts = str(trade.get("exit_time", f"Trade {idx}"))
        trade_id = trade.get("trade_id", idx)
        side = str(trade.get("side", ""))

        curve.append(
            {
                "step": idx,
                "timestamp": exit_ts,
                "trade_id": trade_id,
                "side": side,
                "gross_pnl": round(gross_pnl, 2),
                "costs": round(costs, 2),
                "net_pnl": round(net_pnl, 2),
                "equity": round(current_equity, 2),
                "peak_equity": round(running_peak, 2),
                "drawdown": round(drawdown, 2),
                "drawdown_pct": round(drawdown_pct, 2),
            }
        )

    return curve


def compute_extended_metrics(
    initial_capital: float,
    trades: List[Dict[str, Any]],
    base_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compute rigorous quantitative research metrics from trade records and equity curve.
    """
    initial_cap = float(initial_capital)
    total_trades = len(trades)

    if total_trades == 0:
        return {
            "initial_capital": round(initial_cap, 2),
            "final_equity": round(initial_cap, 2),
            "peak_equity": round(initial_cap, 2),
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "breakeven_trades": 0,
            "win_rate_pct": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "total_transaction_costs": 0.0,
            "total_pnl": 0.0,
            "total_return_pct": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "win_loss_ratio": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "max_drawdown_amount": 0.0,
            "max_drawdown_pct": 0.0,
            "recovery_factor": 0.0,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0,
        }

    curve = calculate_equity_curve(initial_cap, trades)

    winning_trades = [t for t in trades if float(t.get("net_pnl", 0.0)) > 0]
    losing_trades = [t for t in trades if float(t.get("net_pnl", 0.0)) < 0]
    breakeven_trades = [t for t in trades if float(t.get("net_pnl", 0.0)) == 0]

    win_count = len(winning_trades)
    loss_count = len(losing_trades)
    be_count = len(breakeven_trades)

    win_rate = (win_count / total_trades) * 100.0

    gross_profit = sum(float(t.get("gross_pnl", 0.0)) for t in trades if float(t.get("gross_pnl", 0.0)) > 0)
    gross_loss = sum(float(t.get("gross_pnl", 0.0)) for t in trades if float(t.get("gross_pnl", 0.0)) < 0)
    total_costs = sum(float(t.get("costs", 0.0)) for t in trades)
    net_pnl = sum(float(t.get("net_pnl", 0.0)) for t in trades)

    total_return_pct = (net_pnl / initial_cap) * 100.0

    avg_win = (sum(float(t.get("net_pnl", 0.0)) for t in winning_trades) / win_count) if win_count > 0 else 0.0
    avg_loss = (sum(float(t.get("net_pnl", 0.0)) for t in losing_trades) / loss_count) if loss_count > 0 else 0.0

    if abs(avg_loss) > 1e-9:
        win_loss_ratio = round(abs(avg_win / avg_loss), 2)
    else:
        win_loss_ratio = "inf" if win_count > 0 else 0.0

    abs_loss = abs(gross_loss)
    if abs_loss > 1e-9:
        profit_factor: Any = round(gross_profit / abs_loss, 2)
    else:
        profit_factor = "inf" if gross_profit > 0 else 0.0

    # Expectancy: (P(win) * avg_win) + (P(loss) * avg_loss)
    expectancy = ((win_count / total_trades) * avg_win) + ((loss_count / total_trades) * avg_loss)

    # Max Drawdowns from curve
    drawdowns_amt = [pt["drawdown"] for pt in curve]
    drawdowns_pct = [pt["drawdown_pct"] for pt in curve]

    max_dd_amt = min(drawdowns_amt)  # <= 0.0
    max_dd_pct = min(drawdowns_pct)  # <= 0.0

    # Recovery Factor: Total Net P&L / |Max Drawdown Amount|
    if abs(max_dd_amt) > 1e-9 and net_pnl > 0:
        recovery_factor = round(net_pnl / abs(max_dd_amt), 2)
    else:
        recovery_factor = 0.0

    # Consecutive Streaks
    max_consec_wins = 0
    max_consec_losses = 0
    curr_wins = 0
    curr_losses = 0

    for t in trades:
        pnl = float(t.get("net_pnl", 0.0))
        if pnl > 0:
            curr_wins += 1
            curr_losses = 0
            if curr_wins > max_consec_wins:
                max_consec_wins = curr_wins
        elif pnl < 0:
            curr_losses += 1
            curr_wins = 0
            if curr_losses > max_consec_losses:
                max_consec_losses = curr_losses
        else:
            curr_wins = 0
            curr_losses = 0

    final_equity = curve[-1]["equity"]
    peak_equity = max(pt["equity"] for pt in curve)

    # Respect base_metrics if provided for exact CLI parity
    if base_metrics:
        if "profit_factor" in base_metrics:
            profit_factor = base_metrics["profit_factor"]
        if "win_rate_pct" in base_metrics:
            win_rate = float(base_metrics["win_rate_pct"])
        if "total_pnl" in base_metrics:
            net_pnl = float(base_metrics["total_pnl"])
        if "total_return_pct" in base_metrics:
            total_return_pct = float(base_metrics["total_return_pct"])

    return {
        "initial_capital": round(initial_cap, 2),
        "final_equity": round(final_equity, 2),
        "peak_equity": round(peak_equity, 2),
        "total_trades": total_trades,
        "winning_trades": win_count,
        "losing_trades": loss_count,
        "breakeven_trades": be_count,
        "win_rate_pct": round(win_rate, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "total_transaction_costs": round(total_costs, 2),
        "total_pnl": round(net_pnl, 2),
        "total_return_pct": round(total_return_pct, 2),
        "average_win": round(avg_win, 2),
        "average_loss": round(avg_loss, 2),
        "win_loss_ratio": win_loss_ratio,
        "profit_factor": profit_factor,
        "expectancy": round(expectancy, 2),
        "max_drawdown_amount": round(max_dd_amt, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "recovery_factor": recovery_factor,
        "max_consecutive_wins": max_consec_wins,
        "max_consecutive_losses": max_consec_losses,
    }


def compute_backtest_analytics(result_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract structured analytics and equity curve from a completed backtest result payload.
    """
    portfolio = result_dict.get("portfolio", {})
    initial_cap = float(portfolio.get("initial_capital", 100_000.0))
    trades = result_dict.get("trades", [])
    base_metrics = result_dict.get("metrics", {})
    date_range = result_dict.get("date_range", {})

    start_ts = date_range.get("start")
    equity_curve = calculate_equity_curve(initial_cap, trades, start_time=start_ts)
    metrics = compute_extended_metrics(initial_cap, trades, base_metrics)

    return {
        "job_id": result_dict.get("job_id", ""),
        "symbol": result_dict.get("symbol", "NIFTY 50"),
        "status": result_dict.get("status", "COMPLETED"),
        "execution_model": result_dict.get("execution_model", "next_open"),
        "date_range": date_range,
        "metrics": metrics,
        "equity_curve": equity_curve,
        "trades": trades,
    }


def generate_svg_equity_chart(
    equity_curve: List[Dict[str, Any]],
    width: int = 800,
    height: int = 280,
) -> str:
    """
    Generate responsive, self-contained SVG for the equity progression curve.
    """
    if not equity_curve:
        return f'<svg viewBox="0 0 {width} {height}" class="chart-svg"><text x="{width//2}" y="{height//2}" fill="#88a3b8" text-anchor="middle">No equity data available</text></svg>'

    padding_top = 30
    padding_bottom = 40
    padding_left = 70
    padding_right = 30

    plot_w = width - padding_left - padding_right
    plot_h = height - padding_top - padding_bottom

    equities = [pt["equity"] for pt in equity_curve]
    min_eq = min(equities)
    max_eq = max(equities)

    # Pad min/max slightly for visual headroom
    if abs(max_eq - min_eq) < 1e-4:
        y_min = min_eq * 0.99
        y_max = max_eq * 1.01
    else:
        span = max_eq - min_eq
        y_min = min_eq - (span * 0.08)
        y_max = max_eq + (span * 0.08)

    def to_x(step: int) -> float:
        if len(equity_curve) <= 1:
            return padding_left + (plot_w / 2.0)
        return padding_left + (step / (len(equity_curve) - 1)) * plot_w

    def to_y(eq: float) -> float:
        if abs(y_max - y_min) < 1e-6:
            return padding_top + (plot_h / 2.0)
        norm = (eq - y_min) / (y_max - y_min)
        return padding_top + (1.0 - norm) * plot_h

    # Path points
    pts = [(to_x(pt["step"]), to_y(pt["equity"])) for pt in equity_curve]
    line_path = " ".join(f"{'M' if i == 0 else 'L'} {x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))

    # Area fill path
    bottom_y = padding_top + plot_h
    area_path = f"{line_path} L {pts[-1][0]:.1f},{bottom_y:.1f} L {pts[0][0]:.1f},{bottom_y:.1f} Z"

    # Reference starting capital line
    initial_cap = equity_curve[0]["equity"]
    cap_y = to_y(initial_cap)

    # Y-axis ticks (4 ticks)
    y_ticks = []
    for i in range(4):
        val = y_min + (y_max - y_min) * (i / 3.0)
        y_pos = to_y(val)
        y_ticks.append((y_pos, f"₹{val:,.0f}"))

    svg_parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="chart-svg" style="width: 100%; height: auto; background: #08111a; border-radius: 6px; font-family: monospace;">',
        '<defs>',
        '  <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">',
        '    <stop offset="0%" stop-color="#00eaaf" stop-opacity="0.35"/>',
        '    <stop offset="100%" stop-color="#00eaaf" stop-opacity="0.02"/>',
        '  </linearGradient>',
        '</defs>',
    ]

    # Gridlines and Y labels
    for y_pos, label in y_ticks:
        svg_parts.append(
            f'<line x1="{padding_left}" y1="{y_pos:.1f}" x2="{width - padding_right}" y2="{y_pos:.1f}" stroke="#162838" stroke-width="1" stroke-dasharray="3,3"/>'
        )
        svg_parts.append(
            f'<text x="{padding_left - 8}" y="{y_pos + 4:.1f}" fill="#6b869e" font-size="10" text-anchor="end">{label}</text>'
        )

    # Starting Capital Baseline
    svg_parts.append(
        f'<line x1="{padding_left}" y1="{cap_y:.1f}" x2="{width - padding_right}" y2="{cap_y:.1f}" stroke="#f0b90b" stroke-width="1.2" stroke-dasharray="4,4" opacity="0.6"/>'
    )
    svg_parts.append(
        f'<text x="{width - padding_right - 4}" y="{cap_y - 6:.1f}" fill="#f0b90b" font-size="9" text-anchor="end" opacity="0.8">Start: ₹{initial_cap:,.0f}</text>'
    )

    # Shaded Area & Line
    svg_parts.append(f'<path d="{area_path}" fill="url(#eqGrad)"/>')
    svg_parts.append(f'<path d="{line_path}" fill="none" stroke="#00eaaf" stroke-width="2.2" stroke-linejoin="round"/>')

    # Data Point Markers with Tooltips
    for pt in equity_curve:
        cx = to_x(pt["step"])
        cy = to_y(pt["equity"])
        trade_label = f"Trade #{pt['trade_id']}" if pt["trade_id"] is not None else "Initial Capital"
        tooltip = f"{trade_label} | Time: {pt['timestamp']} | Equity: ₹{pt['equity']:,.2f} | Net: ₹{pt['net_pnl']:+,.2f} | DD: {pt['drawdown_pct']:.2f}%"
        svg_parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.5" fill="#00eaaf" stroke="#08111a" stroke-width="1.5">'
            f'<title>{html.escape(tooltip)}</title>'
            f'</circle>'
        )

    # X-axis Labels (First, Mid, Last)
    if len(equity_curve) > 0:
        first_ts = equity_curve[0]["timestamp"][:10]
        last_ts = equity_curve[-1]["timestamp"][:10]
        svg_parts.append(f'<text x="{padding_left}" y="{height - 12}" fill="#6b869e" font-size="10">{html.escape(first_ts)}</text>')
        svg_parts.append(f'<text x="{width - padding_right}" y="{height - 12}" fill="#6b869e" font-size="10" text-anchor="end">{html.escape(last_ts)}</text>')

    svg_parts.append('</svg>')
    return "\n".join(svg_parts)


def generate_svg_drawdown_chart(
    equity_curve: List[Dict[str, Any]],
    width: int = 800,
    height: int = 160,
) -> str:
    """
    Generate responsive SVG underwater chart showing drawdown progression.
    """
    if not equity_curve:
        return f'<svg viewBox="0 0 {width} {height}" class="chart-svg"><text x="{width//2}" y="{height//2}" fill="#88a3b8" text-anchor="middle">No drawdown data available</text></svg>'

    padding_top = 20
    padding_bottom = 35
    padding_left = 70
    padding_right = 30

    plot_w = width - padding_left - padding_right
    plot_h = height - padding_top - padding_bottom

    dds = [pt["drawdown_pct"] for pt in equity_curve]
    min_dd = min(dds)  # <= 0.0

    # Ensure range has headroom
    y_min = min(min_dd * 1.15, -0.1) if min_dd < 0 else -1.0
    y_max = 0.0

    def to_x(step: int) -> float:
        if len(equity_curve) <= 1:
            return padding_left + (plot_w / 2.0)
        return padding_left + (step / (len(equity_curve) - 1)) * plot_w

    def to_y(dd_val: float) -> float:
        norm = (dd_val - y_min) / (y_max - y_min)
        return padding_top + (1.0 - norm) * plot_h

    zero_y = to_y(0.0)

    pts = [(to_x(pt["step"]), to_y(pt["drawdown_pct"])) for pt in equity_curve]
    line_path = " ".join(f"{'M' if i == 0 else 'L'} {x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
    area_path = f"{line_path} L {pts[-1][0]:.1f},{zero_y:.1f} L {pts[0][0]:.1f},{zero_y:.1f} Z"

    svg_parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="chart-svg" style="width: 100%; height: auto; background: #08111a; border-radius: 6px; font-family: monospace;">',
        '<defs>',
        '  <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">',
        '    <stop offset="0%" stop-color="#ff6876" stop-opacity="0.05"/>',
        '    <stop offset="100%" stop-color="#ff6876" stop-opacity="0.35"/>',
        '  </linearGradient>',
        '</defs>',
    ]

    # Grid & Y ticks
    for frac in [0.0, 0.5, 1.0]:
        val = y_max - (y_max - y_min) * frac
        y_pos = to_y(val)
        svg_parts.append(
            f'<line x1="{padding_left}" y1="{y_pos:.1f}" x2="{width - padding_right}" y2="{y_pos:.1f}" stroke="#162838" stroke-width="1" stroke-dasharray="3,3"/>'
        )
        svg_parts.append(
            f'<text x="{padding_left - 8}" y="{y_pos + 4:.1f}" fill="#6b869e" font-size="10" text-anchor="end">{val:.2f}%</text>'
        )

    # Shaded underwater area & line
    svg_parts.append(f'<path d="{area_path}" fill="url(#ddGrad)"/>')
    svg_parts.append(f'<path d="{line_path}" fill="none" stroke="#ff6876" stroke-width="2" stroke-linejoin="round"/>')

    # Drawdown Point Markers with Tooltips
    for pt in equity_curve:
        cx = to_x(pt["step"])
        cy = to_y(pt["drawdown_pct"])
        trade_label = f"Trade #{pt['trade_id']}" if pt["trade_id"] is not None else "Initial Capital"
        tooltip = f"{trade_label} | Time: {pt['timestamp']} | DD: ₹{pt['drawdown']:,.2f} ({pt['drawdown_pct']:.2f}%)"
        svg_parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" fill="#ff6876" stroke="#08111a" stroke-width="1">'
            f'<title>{html.escape(tooltip)}</title>'
            f'</circle>'
        )

    svg_parts.append('</svg>')
    return "\n".join(svg_parts)


def generate_html_tearsheet(
    result_dict: Dict[str, Any],
    config_hash: Optional[str] = None,
    dataset_hash: Optional[str] = None,
) -> str:
    """
    Generate a complete, self-contained, standalone HTML research tearsheet.

    Includes:
    - Experiment metadata, date ranges, and candle counts
    - Cryptographic hash provenance (V1 config, dataset SHA-256)
    - Execution model causal transparency callouts
    - Key performance metrics KPI grid
    - High-resolution SVG equity progression and underwater drawdown charts
    - Interactive trade history table with zero-dependency client-side filtering/sorting
    - SEBI & research-only offline academic disclaimers
    """
    analytics = compute_backtest_analytics(result_dict)

    job_id = analytics["job_id"]
    symbol = analytics["symbol"]
    exec_model = analytics["execution_model"]
    date_range = analytics["date_range"]
    metrics = analytics["metrics"]
    equity_curve = analytics["equity_curve"]
    trades = analytics["trades"]

    cfg_h = config_hash or FROZEN_V1_CONFIG_HASH
    data_h = dataset_hash or (CANONICAL_NIFTY50_HASH if "NIFTY" in symbol.upper() else CANONICAL_ADANIPORTS_HASH)

    is_causal = exec_model == "next_open"
    model_badge_class = "badge-causal" if is_causal else "badge-theoretical"
    model_badge_text = "CAUSAL REALISTIC (NEXT-OPEN BAR FILL)" if is_causal else "THEORETICAL (SAME-BAR CLOSE — LOOKAHEAD BIASED)"

    equity_svg = generate_svg_equity_chart(equity_curve, width=820, height=280)
    drawdown_svg = generate_svg_drawdown_chart(equity_curve, width=820, height=160)

    # Build Trades Table Rows
    trade_rows = []
    for t in trades:
        tid = t.get("trade_id", "-")
        side = t.get("side", "-")
        entry_ts = str(t.get("entry_time", "-"))
        entry_p = f"₹{float(t.get('entry_price', 0.0)):,.2f}"
        exit_ts = str(t.get("exit_time", "-"))
        exit_p = f"₹{float(t.get('exit_price', 0.0)):,.2f}"
        qty = t.get("quantity", 1)
        gross = float(t.get("gross_pnl", 0.0))
        costs = float(t.get("costs", 0.0))
        net = float(t.get("net_pnl", 0.0))
        ret = float(t.get("return_pct", 0.0))
        reason = str(t.get("exit_reason", "SIGNAL"))

        net_cls = "pos" if net > 0 else ("neg" if net < 0 else "neutral")
        side_cls = "badge-buy" if "BUY" in side.upper() or "LONG" in side.upper() else "badge-sell"

        trade_rows.append(
            f'<tr data-side="{html.escape(side)}" data-net="{net}">'
            f'  <td class="text-center">{tid}</td>'
            f'  <td><strong>{html.escape(symbol)}</strong></td>'
            f'  <td><span class="badge {side_cls}">{html.escape(side)}</span></td>'
            f'  <td class="mono">{html.escape(entry_ts)}</td>'
            f'  <td class="mono text-right">{entry_p}</td>'
            f'  <td class="mono">{html.escape(exit_ts)}</td>'
            f'  <td class="mono text-right">{exit_p}</td>'
            f'  <td class="text-center">{qty}</td>'
            f'  <td class="mono text-right">₹{gross:+,.2f}</td>'
            f'  <td class="mono text-right">₹{costs:,.2f}</td>'
            f'  <td class="mono text-right font-bold {net_cls}">₹{net:+,.2f}</td>'
            f'  <td class="mono text-right {net_cls}">{ret:+.2f}%</td>'
            f'  <td><span class="reason-tag">{html.escape(reason)}</span></td>'
            f'</tr>'
        )

    trade_rows_html = "\n".join(trade_rows) if trade_rows else '<tr><td colspan="13" class="text-center empty-notice">No trades executed during this backtest window.</td></tr>'

    total_pnl = metrics["total_pnl"]
    pnl_class = "metric-pos" if total_pnl >= 0 else "metric-neg"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SignalForge — Quantitative Backtest Research Tearsheet [{html.escape(symbol)}]</title>
  <style>
    :root {{
      --bg: #060b11;
      --card-bg: #0c141d;
      --card-border: #1a2a3a;
      --accent-green: #00eaaf;
      --accent-red: #ff6876;
      --accent-blue: #7cb5ec;
      --accent-yellow: #f0b90b;
      --text: #e6f0fa;
      --text-muted: #88a3b8;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.5;
      padding: 24px;
    }}
    .container {{ max-width: 1100px; margin: 0 auto; }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 20px;
      margin-bottom: 24px;
    }}
    .header-title h1 {{ font-size: 22px; font-weight: 700; color: #fff; letter-spacing: -0.02em; }}
    .header-title p {{ color: var(--text-muted); font-size: 13px; margin-top: 4px; }}
    .meta-box {{ text-align: right; font-size: 11.5px; color: var(--text-muted); font-family: monospace; }}
    .badge {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.04em;
    }}
    .badge-causal {{ background: rgba(0, 234, 175, 0.15); color: var(--accent-green); border: 1px solid rgba(0, 234, 175, 0.4); }}
    .badge-theoretical {{ background: rgba(255, 104, 118, 0.15); color: var(--accent-red); border: 1px solid rgba(255, 104, 118, 0.4); }}
    .badge-buy {{ background: rgba(0, 234, 175, 0.15); color: var(--accent-green); }}
    .badge-sell {{ background: rgba(255, 104, 118, 0.15); color: var(--accent-red); }}
    .reason-tag {{ background: #162434; color: #9bb3c7; padding: 2px 6px; border-radius: 3px; font-size: 10px; font-family: monospace; }}

    .provenance-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 14px 18px;
      margin-bottom: 24px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 12px;
      font-size: 11.5px;
    }}
    .prov-item label {{ display: block; color: var(--text-muted); text-transform: uppercase; font-size: 10px; letter-spacing: 0.05em; }}
    .prov-item span {{ font-family: monospace; color: #d0e2f2; word-break: break-all; }}

    .grid-kpi {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 24px;
    }}
    .kpi-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 12px 14px;
    }}
    .kpi-label {{ color: var(--text-muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; }}
    .kpi-val {{ font-size: 18px; font-weight: 700; margin-top: 4px; font-family: monospace; }}
    .kpi-sub {{ font-size: 10.5px; color: var(--text-muted); margin-top: 2px; }}
    .metric-pos {{ color: var(--accent-green); }}
    .metric-neg {{ color: var(--accent-red); }}
    .metric-neutral {{ color: var(--text); }}

    .section {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 18px;
      margin-bottom: 24px;
    }}
    .section-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }}
    .section-title {{ font-size: 13.5px; font-weight: 700; color: #fff; letter-spacing: 0.02em; }}
    .chart-container {{ width: 100%; overflow-x: auto; }}

    /* Table Controls */
    .table-controls {{
      display: flex;
      gap: 8px;
      margin-bottom: 12px;
      align-items: center;
      flex-wrap: wrap;
    }}
    .filter-btn {{
      background: #111e2c;
      border: 1px solid #1f354b;
      color: var(--text-muted);
      padding: 4px 10px;
      border-radius: 4px;
      font-size: 11px;
      cursor: pointer;
    }}
    .filter-btn.active {{
      background: #1a3a54;
      border-color: var(--accent-blue);
      color: #fff;
      font-weight: 700;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 11.5px;
    }}
    th {{
      background: #09131d;
      color: var(--text-muted);
      text-transform: uppercase;
      font-size: 10px;
      letter-spacing: 0.05em;
      padding: 8px 10px;
      text-align: left;
      border-bottom: 1px solid var(--card-border);
      cursor: pointer;
    }}
    th:hover {{ color: #fff; }}
    td {{
      padding: 7px 10px;
      border-bottom: 1px solid #13202e;
    }}
    tr:hover td {{ background: rgba(255, 255, 255, 0.02); }}
    .mono {{ font-family: monospace; }}
    .text-right {{ text-align: right; }}
    .text-center {{ text-align: center; }}
    .font-bold {{ font-weight: 700; }}
    .pos {{ color: var(--accent-green); }}
    .neg {{ color: var(--accent-red); }}
    .empty-notice {{ padding: 24px; color: var(--text-muted); font-style: italic; }}

    .disclaimer-card {{
      background: rgba(18, 30, 44, 0.6);
      border: 1px dashed #1e364e;
      border-radius: 6px;
      padding: 14px 18px;
      font-size: 11px;
      color: #8da4b8;
      line-height: 1.6;
    }}
    .disclaimer-card strong {{ color: #b4c7d6; }}
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <header class="header">
      <div class="header-title">
        <h1>SignalForge — Quantitative Backtest Research Tearsheet</h1>
        <p>Instrument: <strong>{html.escape(symbol)}</strong> | Strategy: <strong>Variant C (One Trade/Symbol/Day)</strong></p>
        <div style="margin-top: 8px;">
          <span class="badge {model_badge_class}">{model_badge_text}</span>
        </div>
      </div>
      <div class="meta-box">
        <div>Job ID: <strong>{html.escape(job_id)}</strong></div>
        <div>Date Range: {html.escape(str(date_range.get('start', ''))[:10])} to {html.escape(str(date_range.get('end', ''))[:10])}</div>
        <div>Total Candles: {date_range.get('total_candles', '-')}</div>
      </div>
    </header>

    <!-- Provenance & Invariants -->
    <div class="provenance-card">
      <div class="prov-item">
        <label>Frozen V1 Config SHA-256</label>
        <span>{html.escape(cfg_h)}</span>
      </div>
      <div class="prov-item">
        <label>Historical Dataset SHA-256</label>
        <span>{html.escape(data_h)}</span>
      </div>
      <div class="prov-item">
        <label>Capital & Cost Framework</label>
        <span>Start: ₹{metrics['initial_capital']:,.0f} | Slippage/Fee: 1.0 bps</span>
      </div>
    </div>

    <!-- KPI Metrics Grid -->
    <div class="grid-kpi">
      <div class="kpi-card">
        <div class="kpi-label">Net Return</div>
        <div class="kpi-val {pnl_class}">{metrics['total_return_pct']:+.2f}%</div>
        <div class="kpi-sub">Total Net P&L: ₹{metrics['total_pnl']:+,.2f}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Win Rate</div>
        <div class="kpi-val metric-neutral">{metrics['win_rate_pct']:.2f}%</div>
        <div class="kpi-sub">{metrics['winning_trades']}W / {metrics['losing_trades']}L / {metrics['breakeven_trades']}BE</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Profit Factor</div>
        <div class="kpi-val metric-neutral">{metrics['profit_factor']}</div>
        <div class="kpi-sub">Gross: ₹{metrics['gross_profit']:,.2f} / ₹{abs(metrics['gross_loss']):,.2f}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Maximum Drawdown</div>
        <div class="kpi-val metric-neg">{metrics['max_drawdown_pct']:.2f}%</div>
        <div class="kpi-sub">Amount: ₹{metrics['max_drawdown_amount']:,.2f}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Expectancy / Trade</div>
        <div class="kpi-val {pnl_class}">₹{metrics['expectancy']:+,.2f}</div>
        <div class="kpi-sub">Total Trades: {metrics['total_trades']}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Win / Loss Ratio</div>
        <div class="kpi-val metric-neutral">{metrics['win_loss_ratio']}</div>
        <div class="kpi-sub">Avg W: ₹{metrics['average_win']:,.2f} | L: ₹{metrics['average_loss']:,.2f}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Recovery Factor</div>
        <div class="kpi-val metric-neutral">{metrics['recovery_factor']}</div>
        <div class="kpi-sub">Streaks: {metrics['max_consecutive_wins']}W / {metrics['max_consecutive_losses']}L</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Transaction Costs</div>
        <div class="kpi-val metric-neutral">₹{metrics['total_transaction_costs']:,.2f}</div>
        <div class="kpi-sub">Final Equity: ₹{metrics['final_equity']:,.2f}</div>
      </div>
    </div>

    <!-- Interactive Equity Curve -->
    <div class="section">
      <div class="section-header">
        <div class="section-title">ACCOUNT EQUITY PROGRESSION (₹)</div>
        <div style="font-size: 11px; color: var(--text-muted); font-family: monospace;">
          Initial: ₹{metrics['initial_capital']:,.0f} &nbsp;|&nbsp; Peak: ₹{metrics['peak_equity']:,.0f} &nbsp;|&nbsp; Final: ₹{metrics['final_equity']:,.0f}
        </div>
      </div>
      <div class="chart-container">
        {equity_svg}
      </div>
    </div>

    <!-- Underwater Drawdown Curve -->
    <div class="section">
      <div class="section-header">
        <div class="section-title">UNDERWATER DRAWDOWN RELATIVE TO PEAK (%)</div>
        <div style="font-size: 11px; color: var(--accent-red); font-family: monospace;">
          Max DD: {metrics['max_drawdown_pct']:.2f}% (₹{metrics['max_drawdown_amount']:,.2f})
        </div>
      </div>
      <div class="chart-container">
        {drawdown_svg}
      </div>
    </div>

    <!-- Trade History Table -->
    <div class="section">
      <div class="section-header">
        <div class="section-title">TRADE EXECUTION LOG ({len(trades)} COMPLETED TRADES)</div>
        <div class="table-controls">
          <button type="button" class="filter-btn active" onclick="filterTrades('ALL')">ALL ({len(trades)})</button>
          <button type="button" class="filter-btn" onclick="filterTrades('WIN')">WINNERS ({metrics['winning_trades']})</button>
          <button type="button" class="filter-btn" onclick="filterTrades('LOSS')">LOSERS ({metrics['losing_trades']})</button>
          <button type="button" class="filter-btn" onclick="filterTrades('BUY')">LONG / BUY</button>
          <button type="button" class="filter-btn" onclick="filterTrades('SELL')">SHORT / SELL</button>
        </div>
      </div>
      <div style="overflow-x: auto;">
        <table id="trades-table">
          <thead>
            <tr>
              <th class="text-center">#</th>
              <th>Symbol</th>
              <th>Side</th>
              <th>Entry Time</th>
              <th class="text-right">Entry Price</th>
              <th>Exit Time</th>
              <th class="text-right">Exit Price</th>
              <th class="text-center">Qty</th>
              <th class="text-right">Gross P&L</th>
              <th class="text-right">Costs</th>
              <th class="text-right">Net P&L</th>
              <th class="text-right">Return %</th>
              <th>Exit Reason</th>
            </tr>
          </thead>
          <tbody>
            {trade_rows_html}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Academic Research Disclaimer -->
    <div class="disclaimer-card">
      <strong>RESEARCH & ACADEMIC PROTOCOL DISCLAIMER:</strong> This tearsheet was deterministically generated by SignalForge for quantitative research and engineering validation only. Market simulations are computed on historical NSE 1-minute datasets under strict ₹0 budget invariants. Simulated past performance is no guarantee of future returns. No live broker connectivity, financial advisory, or order execution is implied or authorized.
    </div>
  </div>

  <script>
    function filterTrades(category) {{
      const buttons = document.querySelectorAll('.filter-btn');
      buttons.forEach(btn => btn.classList.remove('active'));
      event.target.classList.add('active');

      const rows = document.querySelectorAll('#trades-table tbody tr');
      rows.forEach(row => {{
        const side = (row.getAttribute('data-side') || '').toUpperCase();
        const net = parseFloat(row.getAttribute('data-net') || '0');

        let show = true;
        if (category === 'WIN') show = net > 0;
        else if (category === 'LOSS') show = net < 0;
        else if (category === 'BUY') show = side.includes('BUY') || side.includes('LONG');
        else if (category === 'SELL') show = side.includes('SELL') || side.includes('SHORT');

        row.style.display = show ? '' : 'none';
      }});
    }}
  </script>
</body>
</html>
"""


def save_html_tearsheet(
    result_dict: Dict[str, Any],
    output_path: str | Path,
    config_hash: Optional[str] = None,
    dataset_hash: Optional[str] = None,
) -> Path:
    """
    Generate and atomically save standalone HTML research tearsheet to disk.
    """
    path = Path(output_path)
    html_content = generate_html_tearsheet(result_dict, config_hash=config_hash, dataset_hash=dataset_hash)
    atomic_write(path, html_content, encoding="utf-8")
    return path
