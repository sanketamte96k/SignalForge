# SignalForge

> **Quantitative Intraday Market Research & Causal Backtesting Platform**  
> *Engineered for systematic research across Indian equities (NSE) with strict zero-lookahead causal verification.*

---

## 1. Overview & Core Philosophy

SignalForge is an offline quantitative research, signal analysis, and backtesting workstation designed for Indian equity markets. It connects a high-performance Python/FastAPI simulation engine to an interactive React 19 frontend terminal.

### Architectural Core Principles
1. **Causal-First Execution:** Enforces strict temporal boundaries. Strategy signals evaluated on candle $t$ execute on the open of candle $t+1$ (`next_open` causal model). Non-causal `same_close` execution is classified and badged as theoretical lookahead.
2. **Zero Data Fabrication:** Equity progression and drawdown curves reflect actual trade executions. No interpolated ticks or synthetic valuations are generated.
3. **Cryptographic Provenance:** Historical strategy baselines are anchored by immutable SHA-256 configuration hashes.
4. **Offline & Self-Contained:** Strict ₹0 budget mandate. Operates completely without paid subscriptions, cloud queues, external CDNs, or tracking scripts.
5. **Human-in-the-Loop:** Designed for research, analysis, and paper-trading simulation. Zero automatic broker order routing.

---

## 2. Key Features

- **Asynchronous Backtest Engine:** Multi-threaded job coordinator supporting non-blocking simulation, bounded memory queues, and cooperative cancellation checkpoints.
- **Interactive Equity & Drawdown Analytics:** High-contrast responsive SVG equity progression curves, underwater drawdown depth tracking, and peak recovery verification.
- **Filterable Trade History:** Complete trade execution log with client-side sorting and filtering by trade direction, profitability, and exit reason.
- **Standalone HTML Tearsheets:** Generates self-contained, offline research reports reproducible directly from saved simulation payloads.
- **Stock Universe Governance:** Strict pipeline qualification tracking (Historical Data $\to$ Backtest $\to$ OOS Validation $\to$ Paper Trading).
- **Interactive Paper Trading:** Real-time simulated execution bracket management, trailing stops, and trade journaling.

---

## 3. Quick Start Guide

### Prerequisites
- Python 3.10 to 3.14 (Validated on 3.12, 3.13, 3.14.3)
- Node.js v18.0.0+ (Validated on v20 LTS and v22.14.0)

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/sanketamte96k/SignalForge.git
cd SignalForge

# Setup Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### 2. Launch Local Servers
**Terminal 1 (FastAPI Backend):**
```bash
uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 (React Frontend Terminal):**
```bash
cd frontend
npm run dev
```

Open **`http://localhost:5173/`** in your browser.

---

## 4. Documentation Index

Complete documentation guides are available in the **[`docs/`](docs/)** directory:

| Guide | Description |
| :--- | :--- |
| **[`docs/INSTALLATION.md`](docs/INSTALLATION.md)** | Step-by-step clean environment installation guide. |
| **[`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)** | Environment variables, `.env.example`, and config reference. |
| **[`docs/STARTUP.md`](docs/STARTUP.md)** | Complete startup walkthrough and backtest verification tutorial. |
| **[`docs/API.md`](docs/API.md)** | REST API endpoint documentation and Swagger UI details. |
| **[`docs/TESTING.md`](docs/TESTING.md)** | Running backend `pytest` and frontend `npm test` suites. |
| **[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)** | Solutions for common setup, network, and port issues. |
| **[`docs/BACKUP_RECOVERY.md`](docs/BACKUP_RECOVERY.md)** | Data classification, backup commands, and state recovery. |
| **[`docs/SECURITY_DEPLOYMENT.md`](docs/SECURITY_DEPLOYMENT.md)** | Security architecture, path traversal guards, and scope boundaries. |

---

## 5. Protected Invariants & Provenance

SignalForge enforces cryptographic protection over core research benchmarks:

- **Frozen V1 Configuration SHA-256:**
  `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`
- **Canonical ADANIPORTS 1m SHA-256:**
  `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9`
- **Canonical NIFTY 50 1m SHA-256:**
  `f5a1047ee65129c52eb8dfb1888a9daf41a2a6f21e1297beefb7b505e4065e2a`
- **2020 Holdout Partition:** Quarantined as `EXPLORATORY / CONTAMINATED` (Zero strategy training access).
- **Hypothesis B Strategy:** Disqualified due to multi-timeframe look-ahead bias confirmed in Phase 24G.24/25.

---

## 6. Research & Academic Protocol Disclaimer

> **DISCLAIMER:** SignalForge is an offline quantitative research and academic analysis software system. It is designed for historical backtesting and simulated paper-trading only. It does NOT provide financial advisory services, investment recommendations, or automated broker order routing. Simulated historical performance does not guarantee future live trading profits. All research adheres to a strict ₹0 budget protocol.
