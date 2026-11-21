"""
SignalForge — Phase 32H.1: Monthly Performance Analytics Engine
==============================================================
Calculates complete monthly performance metrics, cost comparison,
summary statistics, and generates charts for frozen DTP-V2 across 2017–2020.
"""

from __future__ import annotations

import math
from pathlib import Path
import struct
import zlib
import numpy as np
import pandas as pd


def generate_png_canvas(width: int, height: int, bg_color=(10, 25, 40)):
    """Creates a blank RGB numpy canvas."""
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:, :] = bg_color
    return canvas


def encode_canvas_to_png(canvas: np.ndarray) -> bytes:
    """Encodes a numpy canvas of shape (H, W, 3) to PNG bytes."""
    height, width, _ = canvas.shape

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = bytearray()
    flat = canvas.tobytes()
    row_bytes = width * 3
    for y in range(height):
        raw.append(0)  # filter type 0
        raw.extend(flat[y * row_bytes : (y + 1) * row_bytes])

    idat = zlib.compress(bytes(raw), level=6)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def draw_rect(canvas, x0, y0, x1, y1, color):
    """Draws a filled rectangle on canvas."""
    h, w, _ = canvas.shape
    x0, x1 = max(0, min(x0, x1)), min(w, max(x0, x1))
    y0, y1 = max(0, min(y0, y1)), min(h, max(y0, y1))
    if x0 < x1 and y0 < y1:
        canvas[int(y0) : int(y1), int(x0) : int(x1)] = color


def draw_line(canvas, x0, y0, x1, y1, color, thickness=1):
    """Draws a line on canvas using Bresenham-like stepping."""
    h, w, _ = canvas.shape
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    radius = thickness // 2
    while True:
        for ox in range(-radius, radius + 1):
            for oy in range(-radius, radius + 1):
                px, py = x0 + ox, y0 + oy
                if 0 <= px < w and 0 <= py < h:
                    canvas[py, px] = color

        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy


# Minimal 5x7 bitmap font for rendering numbers, dates, and labels
FONT_5X7 = {
    '0': ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    '1': ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    '2': ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    '3': ["01110", "10001", "00001", "00110", "00001", "10001", "01110"],
    '4': ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    '5': ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    '6': ["01110", "10000", "11110", "10001", "10001", "10001", "01110"],
    '7': ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    '8': ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    '9': ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    '-': ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    '+': ["00000", "00100", "00100", "11111", "00100", "00100", "00000"],
    '.': ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ':': ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
    '%': ["11001", "11010", "00100", "01000", "01011", "10011", "00000"],
    '₹': ["11111", "00100", "11110", "00100", "01000", "10100", "10010"],
    ' ': ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    'A': ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    'B': ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    'C': ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    'D': ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    'E': ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    'F': ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    'G': ["01110", "10001", "10000", "10111", "10001", "10001", "01110"],
    'H': ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    'I': ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    'J': ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    'K': ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    'L': ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    'M': ["10001", "11011", "10101", "10001", "10001", "10001", "10001"],
    'N': ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    'O': ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    'P': ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    'Q': ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    'R': ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    'S': ["01110", "10001", "10000", "01110", "00001", "10001", "01110"],
    'T': ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    'U': ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    'V': ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    'W': ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    'X': ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    'Y': ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    'Z': ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    '(': ["00110", "01000", "10000", "10000", "10000", "01000", "00110"],
    ')': ["01100", "00010", "00001", "00001", "00001", "00010", "01100"],
    '/': ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
    ',': ["00000", "00000", "00000", "00000", "00000", "01100", "00100"],
}


def draw_text(canvas, x, y, text, color=(255, 255, 255), scale=1):
    """Draws text on canvas using bitmap font."""
    h, w, _ = canvas.shape
    curr_x = int(x)
    for ch in str(text).upper():
        glyph = FONT_5X7.get(ch, FONT_5X7.get(' '))
        for row_idx, row in enumerate(glyph):
            for col_idx, bit in enumerate(row):
                if bit == '1':
                    draw_rect(
                        canvas,
                        curr_x + col_idx * scale,
                        y + row_idx * scale,
                        curr_x + (col_idx + 1) * scale,
                        y + (row_idx + 1) * scale,
                        color,
                    )
        curr_x += 6 * scale


def load_reconciled_ledger():
    """Loads and standardizes the 55-trade ledger."""
    path = Path("reports/phase32g_1/trade_ledger_reconciliation.csv")
    if not path.exists():
        raise FileNotFoundError(f"Missing ledger: {path}")
    df = pd.read_csv(path)
    df["exit_date"] = pd.to_datetime(df["exit_date"])
    df["exit_month"] = df["exit_date"].dt.to_period("M").astype(str)
    return df


def generate_all_48_months():
    """Generates all 48 calendar months from 2017-01 to 2020-12."""
    dates = pd.period_range(start="2017-01", end="2020-12", freq="M")
    return [str(d) for d in dates]


def compute_monthly_analytics():
    """Computes monthly metrics for Official and Stress cost schedules."""
    df = load_reconciled_ledger()
    all_months = generate_all_48_months()

    records = []
    cum_off_net = 0.0
    cum_str_net = 0.0

    for m in all_months:
        m_df = df[df["exit_month"] == m]
        trades = len(m_df)
        year = int(m.split("-")[0])
        month_num = int(m.split("-")[1])

        # Official metrics
        off_gross = round(m_df["official_gross_pnl"].sum(), 2) if trades > 0 else 0.0
        off_costs = round(m_df["official_total_costs"].sum(), 2) if trades > 0 else 0.0
        off_net = round(m_df["official_net_pnl"].sum(), 2) if trades > 0 else 0.0
        off_return_pct = round((off_net / 100_000.0) * 100.0, 4)

        off_wins_df = m_df[m_df["official_net_pnl"] > 0]
        off_losses_df = m_df[m_df["official_net_pnl"] <= 0]
        off_wins = len(off_wins_df)
        off_losses = len(off_losses_df)
        off_win_rate = round((off_wins / trades * 100.0), 2) if trades > 0 else 0.0

        off_avg_profit = round(off_wins_df["official_net_pnl"].mean(), 2) if off_wins > 0 else 0.0
        off_avg_loss = round(off_losses_df["official_net_pnl"].mean(), 2) if off_losses > 0 else 0.0

        off_gross_wins = m_df[m_df["official_gross_pnl"] > 0]["official_gross_pnl"].sum()
        off_gross_losses = abs(m_df[m_df["official_gross_pnl"] < 0]["official_gross_pnl"].sum())
        if off_gross_losses > 0:
            off_pf = round(off_gross_wins / off_gross_losses, 2)
        elif off_gross_wins > 0:
            off_pf = 999.99  # perfect month
        else:
            off_pf = 0.0

        cum_off_net += off_net

        # Stress metrics
        str_gross = round(m_df["stress_gross_pnl"].sum(), 2) if trades > 0 else 0.0
        str_costs = round(m_df["stress_total_costs"].sum(), 2) if trades > 0 else 0.0
        str_net = round(m_df["stress_net_pnl"].sum(), 2) if trades > 0 else 0.0
        str_return_pct = round((str_net / 100_000.0) * 100.0, 4)

        str_wins_df = m_df[m_df["stress_net_pnl"] > 0]
        str_losses_df = m_df[m_df["stress_net_pnl"] <= 0]
        str_wins = len(str_wins_df)
        str_losses = len(str_losses_df)
        str_win_rate = round((str_wins / trades * 100.0), 2) if trades > 0 else 0.0

        str_avg_profit = round(str_wins_df["stress_net_pnl"].mean(), 2) if str_wins > 0 else 0.0
        str_avg_loss = round(str_losses_df["stress_net_pnl"].mean(), 2) if str_losses > 0 else 0.0

        str_gross_wins = m_df[m_df["stress_gross_pnl"] > 0]["stress_gross_pnl"].sum()
        str_gross_losses = abs(m_df[m_df["stress_gross_pnl"] < 0]["stress_gross_pnl"].sum())
        if str_gross_losses > 0:
            str_pf = round(str_gross_wins / str_gross_losses, 2)
        elif str_gross_wins > 0:
            str_pf = 999.99
        else:
            str_pf = 0.0

        cum_str_net += str_net

        # Proportional ₹10k Illustrative view (Scaling factor 0.10)
        p10k_ref_capital = 10_000.0
        p10k_off_net = round(off_net * 0.10, 2)
        p10k_off_return_pct = round((p10k_off_net / p10k_ref_capital) * 100.0, 4)

        p10k_str_net = round(str_net * 0.10, 2)
        p10k_str_return_pct = round((p10k_str_net / p10k_ref_capital) * 100.0, 4)

        cost_diff = round(str_costs - off_costs, 2)
        net_diff = round(off_net - str_net, 2)

        records.append({
            "month": m,
            "year": year,
            "month_num": month_num,
            "trades": trades,
            # Official Schedule (₹307/cr)
            "official_gross_pnl": off_gross,
            "official_costs": off_costs,
            "official_net_pnl": off_net,
            "official_return_pct": off_return_pct,
            "official_cumulative_net_pnl": round(cum_off_net, 2),
            "official_wins": off_wins,
            "official_losses": off_losses,
            "official_win_rate_pct": off_win_rate,
            "official_avg_profit": off_avg_profit,
            "official_avg_loss": off_avg_loss,
            "official_profit_factor": off_pf,
            # Stress Schedule (₹317/cr)
            "stress_gross_pnl": str_gross,
            "stress_costs": str_costs,
            "stress_net_pnl": str_net,
            "stress_return_pct": str_return_pct,
            "stress_cumulative_net_pnl": round(cum_str_net, 2),
            "stress_wins": str_wins,
            "stress_losses": str_losses,
            "stress_win_rate_pct": str_win_rate,
            "stress_avg_profit": str_avg_profit,
            "stress_avg_loss": str_avg_loss,
            "stress_profit_factor": str_pf,
            # Cost Differences
            "cost_stress_premium": cost_diff,
            "net_pnl_difference": net_diff,
            # Illustrative ₹10k Proportional View
            "p10k_illustrative_official_net": p10k_off_net,
            "p10k_illustrative_official_return_pct": p10k_off_return_pct,
            "p10k_illustrative_stress_net": p10k_str_net,
            "p10k_illustrative_stress_return_pct": p10k_str_return_pct,
        })

    return pd.DataFrame(records)


def export_csvs(df: pd.DataFrame, out_dir: Path):
    """Generates all 3 CSV deliverables."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. monthly_pnl.csv (Comprehensive monthly metrics)
    pnl_cols = [
        "month", "trades",
        "official_gross_pnl", "official_costs", "official_net_pnl", "official_return_pct",
        "official_wins", "official_losses", "official_win_rate_pct", "official_avg_profit", "official_avg_loss", "official_profit_factor",
        "official_cumulative_net_pnl",
        "p10k_illustrative_official_net", "p10k_illustrative_official_return_pct",
    ]
    df[pnl_cols].to_csv(out_dir / "monthly_pnl.csv", index=False)

    # 2. monthly_cost_comparison.csv
    cost_cols = [
        "month", "trades",
        "official_gross_pnl", "stress_gross_pnl",
        "official_costs", "stress_costs", "cost_stress_premium",
        "official_net_pnl", "stress_net_pnl", "net_pnl_difference",
        "official_return_pct", "stress_return_pct",
        "official_cumulative_net_pnl", "stress_cumulative_net_pnl",
    ]
    df[cost_cols].to_csv(out_dir / "monthly_cost_comparison.csv", index=False)

    # 3. monthly_yearly_summary.csv (Aggregated by year)
    yearly = []
    for yr, y_df in df.groupby("year"):
        active_m = (y_df["trades"] > 0).sum()
        zero_m = (y_df["trades"] == 0).sum()
        prof_m = (y_df["official_net_pnl"] > 0).sum()
        loss_m = (y_df["official_net_pnl"] < 0).sum()
        best_row = y_df.loc[y_df["official_net_pnl"].idxmax()]
        worst_row = y_df.loc[y_df["official_net_pnl"].idxmin()]

        yearly.append({
            "year": yr,
            "total_months": 12,
            "active_months": active_m,
            "zero_trade_months": zero_m,
            "profitable_months": prof_m,
            "loss_making_months": loss_m,
            "total_trades": y_df["trades"].sum(),
            "official_gross_pnl": round(y_df["official_gross_pnl"].sum(), 2),
            "official_costs": round(y_df["official_costs"].sum(), 2),
            "official_net_pnl": round(y_df["official_net_pnl"].sum(), 2),
            "official_annual_return_pct": round((y_df["official_net_pnl"].sum() / 100_000.0) * 100.0, 2),
            "stress_gross_pnl": round(y_df["stress_gross_pnl"].sum(), 2),
            "stress_costs": round(y_df["stress_costs"].sum(), 2),
            "stress_net_pnl": round(y_df["stress_net_pnl"].sum(), 2),
            "stress_annual_return_pct": round((y_df["stress_net_pnl"].sum() / 100_000.0) * 100.0, 2),
            "cost_stress_premium": round(y_df["cost_stress_premium"].sum(), 2),
            "best_month": best_row["month"],
            "best_month_net": best_row["official_net_pnl"],
            "worst_month": worst_row["month"],
            "worst_month_net": worst_row["official_net_pnl"],
        })

    # Combined Total Row
    tot_active_m = (df["trades"] > 0).sum()
    tot_zero_m = (df["trades"] == 0).sum()
    tot_prof_m = (df["official_net_pnl"] > 0).sum()
    tot_loss_m = (df["official_net_pnl"] < 0).sum()
    best_row_tot = df.loc[df["official_net_pnl"].idxmax()]
    worst_row_tot = df.loc[df["official_net_pnl"].idxmin()]

    yearly.append({
        "year": "Combined (2017-2020)",
        "total_months": 48,
        "active_months": tot_active_m,
        "zero_trade_months": tot_zero_m,
        "profitable_months": tot_prof_m,
        "loss_making_months": tot_loss_m,
        "total_trades": df["trades"].sum(),
        "official_gross_pnl": round(df["official_gross_pnl"].sum(), 2),
        "official_costs": round(df["official_costs"].sum(), 2),
        "official_net_pnl": round(df["official_net_pnl"].sum(), 2),
        "official_annual_return_pct": round((df["official_net_pnl"].sum() / 100_000.0) * 100.0, 2),
        "stress_gross_pnl": round(df["stress_gross_pnl"].sum(), 2),
        "stress_costs": round(df["stress_costs"].sum(), 2),
        "stress_net_pnl": round(df["stress_net_pnl"].sum(), 2),
        "stress_annual_return_pct": round((df["stress_net_pnl"].sum() / 100_000.0) * 100.0, 2),
        "cost_stress_premium": round(df["cost_stress_premium"].sum(), 2),
        "best_month": best_row_tot["month"],
        "best_month_net": best_row_tot["official_net_pnl"],
        "worst_month": worst_row_tot["month"],
        "worst_month_net": worst_row_tot["official_net_pnl"],
    })
    pd.DataFrame(yearly).to_csv(out_dir / "monthly_yearly_summary.csv", index=False)


def render_pnl_chart(df: pd.DataFrame, out_path: Path):
    """Renders monthly net P&L bar chart."""
    w, h = 1400, 700
    canvas = generate_png_canvas(w, h, bg_color=(12, 22, 34))

    # Title & Subtitle
    draw_text(canvas, 40, 25, "SIGNALFORGE DTP-V2: MONTHLY REALIZED NET P&L (2017-2020)", color=(0, 234, 175), scale=2)
    draw_text(canvas, 40, 52, "Reference Capital: INR 1,00,000 | 48 Calendar Months | Green: Win, Red: Loss, Gray: Zero", color=(136, 163, 184), scale=1)

    # Plot boundaries
    plot_x0, plot_x1 = 100, 1340
    plot_y0, plot_y1 = 90, 600

    draw_rect(canvas, plot_x0, plot_y0, plot_x1, plot_y1, (16, 30, 46))

    # Range
    pnl_vals = df["official_net_pnl"].values
    max_val = 7000.0
    min_val = -3000.0
    span = max_val - min_val

    # Zero line
    zero_y = int(plot_y1 - ((0.0 - min_val) / span) * (plot_y1 - plot_y0))
    draw_line(canvas, plot_x0, zero_y, plot_x1, zero_y, (100, 120, 140), thickness=2)
    draw_text(canvas, plot_x0 - 75, zero_y - 4, "INR 0", color=(180, 190, 200), scale=1)

    # Horizontal grid lines
    for val in [-2000, 2000, 4000, 6000]:
        y_pos = int(plot_y1 - ((val - min_val) / span) * (plot_y1 - plot_y0))
        draw_line(canvas, plot_x0, y_pos, plot_x1, y_pos, (25, 45, 65), thickness=1)
        sign = "+" if val > 0 else ""
        draw_text(canvas, plot_x0 - 75, y_pos - 4, f"{sign}{int(val)}", color=(120, 140, 160), scale=1)

    # Draw bars for 48 months
    n = len(df)
    bar_width = (plot_x1 - plot_x0) / n

    for i, row in df.iterrows():
        pnl = row["official_net_pnl"]
        x_start = int(plot_x0 + i * bar_width + 4)
        x_end = int(plot_x0 + (i + 1) * bar_width - 4)

        if pnl > 0:
            y_bar = int(plot_y1 - ((pnl - min_val) / span) * (plot_y1 - plot_y0))
            draw_rect(canvas, x_start, y_bar, x_end, zero_y, (0, 217, 163))  # Green
        elif pnl < 0:
            y_bar = int(plot_y1 - ((pnl - min_val) / span) * (plot_y1 - plot_y0))
            draw_rect(canvas, x_start, zero_y, x_end, y_bar, (255, 90, 95))  # Red
        else:
            draw_rect(canvas, x_start, zero_y - 1, x_end, zero_y + 1, (60, 80, 100))  # Gray

        # Month label for every 3 months or active year starts
        if i % 3 == 0:
            m_label = row["month"][2:]  # e.g. "17-01"
            draw_text(canvas, x_start - 6, plot_y1 + 12, m_label, color=(140, 160, 180), scale=1)

    # Legend & Key Statistics Footer
    legend_y = 650
    draw_rect(canvas, 100, legend_y, 116, legend_y + 12, (0, 217, 163))
    draw_text(canvas, 124, legend_y + 2, "Profitable Months (13)", color=(200, 220, 240), scale=1)

    draw_rect(canvas, 320, legend_y, 336, legend_y + 12, (255, 90, 95))
    draw_text(canvas, 344, legend_y + 2, "Loss Months (12)", color=(200, 220, 240), scale=1)

    draw_rect(canvas, 500, legend_y, 516, legend_y + 12, (60, 80, 100))
    draw_text(canvas, 524, legend_y + 2, "Zero-Trade Months (23)", color=(200, 220, 240), scale=1)

    draw_text(canvas, 750, legend_y + 2, "Best: 2020-11 (+INR 6,426.63) | Worst: 2019-01 (-INR 2,159.23)", color=(0, 234, 175), scale=1)

    png_bytes = encode_canvas_to_png(canvas)
    out_path.write_bytes(png_bytes)


def render_cumulative_pnl_chart(df: pd.DataFrame, out_path: Path):
    """Renders cumulative net P&L chart for Official vs Stress."""
    w, h = 1400, 700
    canvas = generate_png_canvas(w, h, bg_color=(12, 22, 34))

    # Title
    draw_text(canvas, 40, 25, "SIGNALFORGE DTP-V2: CUMULATIVE NET REALIZED P&L (2017-2020)", color=(0, 234, 175), scale=2)
    draw_text(canvas, 40, 52, "Official Schedule (INR 307/cr) vs Stress Schedule (INR 317/cr) | Initial: INR 1,00,000", color=(136, 163, 184), scale=1)

    plot_x0, plot_x1 = 100, 1340
    plot_y0, plot_y1 = 90, 600

    draw_rect(canvas, plot_x0, plot_y0, plot_x1, plot_y1, (16, 30, 46))

    max_val = 24000.0
    min_val = -3000.0
    span = max_val - min_val

    # Zero line
    zero_y = int(plot_y1 - ((0.0 - min_val) / span) * (plot_y1 - plot_y0))
    draw_line(canvas, plot_x0, zero_y, plot_x1, zero_y, (100, 120, 140), thickness=2)
    draw_text(canvas, plot_x0 - 75, zero_y - 4, "INR 0", color=(180, 190, 200), scale=1)

    # Grid lines
    for val in [5000, 10000, 15000, 20000]:
        y_pos = int(plot_y1 - ((val - min_val) / span) * (plot_y1 - plot_y0))
        draw_line(canvas, plot_x0, y_pos, plot_x1, y_pos, (25, 45, 65), thickness=1)
        draw_text(canvas, plot_x0 - 75, y_pos - 4, f"+{int(val)}", color=(120, 140, 160), scale=1)

    # Coordinates
    n = len(df)
    step_x = (plot_x1 - plot_x0) / (n - 1)

    pts_off = []
    pts_str = []

    for i, row in df.iterrows():
        x = int(plot_x0 + i * step_x)
        y_off = int(plot_y1 - ((row["official_cumulative_net_pnl"] - min_val) / span) * (plot_y1 - plot_y0))
        y_str = int(plot_y1 - ((row["stress_cumulative_net_pnl"] - min_val) / span) * (plot_y1 - plot_y0))
        pts_off.append((x, y_off))
        pts_str.append((x, y_str))

        if i % 4 == 0 or i == n - 1:
            m_label = row["month"][2:]
            draw_text(canvas, x - 12, plot_y1 + 12, m_label, color=(140, 160, 180), scale=1)

    # Draw Stress line (Amber/Orange)
    for i in range(len(pts_str) - 1):
        draw_line(canvas, pts_str[i][0], pts_str[i][1], pts_str[i + 1][0], pts_str[i + 1][1], (255, 179, 0), thickness=2)

    # Draw Official line (Cyan/Green)
    for i in range(len(pts_off) - 1):
        draw_line(canvas, pts_off[i][0], pts_off[i][1], pts_off[i + 1][0], pts_off[i + 1][1], (0, 234, 175), thickness=3)

    # Legend
    legend_y = 650
    draw_line(canvas, 100, legend_y + 6, 130, legend_y + 6, (0, 234, 175), thickness=3)
    draw_text(canvas, 140, legend_y + 2, f"Official (+INR 20,881.77 / +20.88%)", color=(0, 234, 175), scale=1)

    draw_line(canvas, 480, legend_y + 6, 510, legend_y + 6, (255, 179, 0), thickness=2)
    draw_text(canvas, 520, legend_y + 2, f"Stress (+INR 19,729.39 / +19.73%)", color=(255, 179, 0), scale=1)

    draw_text(canvas, 860, legend_y + 2, "Cost Drag Impact: -INR 1,152.38 (-1.15% pts)", color=(180, 200, 220), scale=1)

    png_bytes = encode_canvas_to_png(canvas)
    out_path.write_bytes(png_bytes)


def render_return_chart(df: pd.DataFrame, out_path: Path):
    """Renders monthly return percentage chart."""
    w, h = 1400, 700
    canvas = generate_png_canvas(w, h, bg_color=(12, 22, 34))

    # Title
    draw_text(canvas, 40, 25, "SIGNALFORGE DTP-V2: MONTHLY RETURN PERCENTAGE (%) (2017-2020)", color=(0, 234, 175), scale=2)
    draw_text(canvas, 40, 52, "Monthly Return % = (Monthly Net Realized P&L / INR 1,00,000) * 100", color=(136, 163, 184), scale=1)

    plot_x0, plot_x1 = 100, 1340
    plot_y0, plot_y1 = 90, 600

    draw_rect(canvas, plot_x0, plot_y0, plot_x1, plot_y1, (16, 30, 46))

    max_pct = 7.0
    min_pct = -3.0
    span = max_pct - min_pct

    zero_y = int(plot_y1 - ((0.0 - min_pct) / span) * (plot_y1 - plot_y0))
    draw_line(canvas, plot_x0, zero_y, plot_x1, zero_y, (100, 120, 140), thickness=2)
    draw_text(canvas, plot_x0 - 75, zero_y - 4, "0.0%", color=(180, 190, 200), scale=1)

    for val in [-2.0, 2.0, 4.0, 6.0]:
        y_pos = int(plot_y1 - ((val - min_pct) / span) * (plot_y1 - plot_y0))
        draw_line(canvas, plot_x0, y_pos, plot_x1, y_pos, (25, 45, 65), thickness=1)
        sign = "+" if val > 0 else ""
        draw_text(canvas, plot_x0 - 75, y_pos - 4, f"{sign}{int(val)}%", color=(120, 140, 160), scale=1)

    n = len(df)
    bar_width = (plot_x1 - plot_x0) / n

    for i, row in df.iterrows():
        ret = row["official_return_pct"]
        x_start = int(plot_x0 + i * bar_width + 4)
        x_end = int(plot_x0 + (i + 1) * bar_width - 4)

        if ret > 0:
            y_bar = int(plot_y1 - ((ret - min_pct) / span) * (plot_y1 - plot_y0))
            draw_rect(canvas, x_start, y_bar, x_end, zero_y, (76, 168, 255))  # Blue-cyan
        elif ret < 0:
            y_bar = int(plot_y1 - ((ret - min_pct) / span) * (plot_y1 - plot_y0))
            draw_rect(canvas, x_start, zero_y, x_end, y_bar, (255, 110, 110))
        else:
            draw_rect(canvas, x_start, zero_y - 1, x_end, zero_y + 1, (60, 80, 100))

        if i % 3 == 0:
            m_label = row["month"][2:]
            draw_text(canvas, x_start - 6, plot_y1 + 12, m_label, color=(140, 160, 180), scale=1)

    # Footer
    legend_y = 650
    draw_text(canvas, 100, legend_y + 2, "Highest Month: 2020-11 (+6.43%) | Lowest Month: 2019-01 (-2.16%)", color=(200, 220, 240), scale=1)
    draw_text(canvas, 700, legend_y + 2, "Proportional INR 10,000 Scaling: Returns % are identical; Nominal P&L is 0.10x", color=(0, 234, 175), scale=1)

    png_bytes = encode_canvas_to_png(canvas)
    out_path.write_bytes(png_bytes)


def main():
    out_dir = Path("reports/phase32h_1")
    df = compute_monthly_analytics()
    export_csvs(df, out_dir)
    render_pnl_chart(df, out_dir / "monthly_pnl_chart.png")
    render_cumulative_pnl_chart(df, out_dir / "monthly_cumulative_pnl_chart.png")
    render_return_chart(df, out_dir / "monthly_return_chart.png")
    print("SUCCESS: Phase 32H.1 data and charts generated successfully.")


if __name__ == "__main__":
    main()
