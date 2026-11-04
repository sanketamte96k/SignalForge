# SignalForge — Phase 24G.30: Standalone HTML Tearsheet Documentation

## 1. Objectives & Overview

The standalone HTML research tearsheet provides a complete, portable, and permanent artifact representing an experimental backtest simulation.

Key Capabilities:
1. **Zero External Dependencies:** 100% self-contained HTML. Does not load external fonts, CSS frameworks, CDNs, or remote JavaScript libraries.
2. **Deterministic Reproducibility:** Reconstructs the entire visual report, SVG charts, and interactive tables solely from the saved backtest JSON payload without requiring access to raw tick/candle files or re-executing strategy logic.
3. **Cryptographic Provenance:** Embeds the frozen V1 strategy configuration hash and the dataset SHA-256 hash.
4. **Offline Interactivity:** Includes pure vanilla JavaScript for client-side trade filtering and sorting, requiring zero network connectivity.

---

## 2. Tearsheet Document Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <!-- 1. Metadata & Scoped Dark-Theme CSS -->
  <!-- SignalForge Color Palette: #060b11 (Canvas), #0c141d (Cards), #00eaaf (Gains), #ff6876 (Losses) -->
</head>
<body>
  <div class="container">
    <!-- 2. Header & Execution Model Badge (Causal vs Theoretical Warning) -->
    <header class="header"> ... </header>

    <!-- 3. Cryptographic Provenance Card (Config SHA-256, Dataset SHA-256) -->
    <div class="provenance-card"> ... </div>

    <!-- 4. Key Performance Indicators (KPI) Grid (12 Cards) -->
    <div class="grid-kpi"> ... </div>

    <!-- 5. High-Resolution SVG Equity Curve Chart (Gridlines, Baseline, Area Fill) -->
    <div class="section">
      <div class="chart-container">{equity_svg}</div>
    </div>

    <!-- 6. High-Resolution SVG Underwater Drawdown Chart -->
    <div class="section">
      <div class="chart-container">{drawdown_svg}</div>
    </div>

    <!-- 7. Interactive Trade Execution Log Table (Filterable by Category) -->
    <div class="section">
      <div class="table-controls"> ... </div>
      <table id="trades-table"> ... </table>
    </div>

    <!-- 8. Academic & Quantitative Research Disclaimer -->
    <div class="disclaimer-card"> ... </div>
  </div>

  <!-- 9. Embedded Zero-Dependency Vanilla JS (Filter & Sort Engine) -->
  <script> ... </script>
</body>
</html>
```

---

## 3. High-Resolution Vector Charting (SVG Engine)

Rather than embedding heavy raster images (PNG/JPEG) or relying on canvas libraries that fail in headless environments, the tearsheet generates mathematical SVG paths directly:

### Equity Curve SVG (`generate_svg_equity_chart`)
- **Coordinate Mapping:** Linear scaling from discrete trade steps to pixel space:
  $$x = \text{pad}_L + \left(\frac{\text{step}}{N}\right) \times \text{plot}_W$$
  $$y = \text{pad}_T + (1 - \text{norm}) \times \text{plot}_H$$
- **Visual Features:**
  - `#08111a` dark slate backdrop with rounded corners.
  - Dashed `#162838` gridlines with Y-axis currency values (`₹1,00,000`).
  - Dashed `#f0b90b` baseline indicating exact initial capital.
  - Linear SVG gradient (`#eqGrad`) filling the area beneath the equity trajectory.
  - Hoverable `<circle>` elements with `<title>` tags displaying Trade #, timestamp, realized net P&L, and resulting equity.

### Underwater Drawdown SVG (`generate_svg_drawdown_chart`)
- **Underwater Area:**
  - 0.0% ceiling reference line.
  - Crimson red line (`#ff6876`) tracing percentage drawdown from running peak.
  - Semi-transparent gradient fill (`#ddGrad`) shading underwater periods.
  - Trough markers with tooltip inspection.

---

## 4. Reproducibility Contract

The generator function `generate_html_tearsheet(result_dict)` satisfies the strict reproducibility contract:

$$\text{Tearsheet}_{\text{HTML}} = f(\text{BacktestResult}_{\text{JSON}})$$

- Calling `generate_html_tearsheet` on identical input produces identical, byte-for-byte HTML output.
- No strategy re-computation or database queries are invoked.
- Validated by unit test `test_html_tearsheet_reproducibility` in `tests/test_phase24G30_interactive_reporting.py`.
