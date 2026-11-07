# SignalForge

> **Quantitative Market Research & Causal Backtesting Platform**

SignalForge is an offline-first research platform for **historical market analysis, causal backtesting, paper-trading simulation, and quantitative reporting** for Indian equities.

Built with **Python/FastAPI + React**, with a strong focus on reproducibility, validation, and avoiding future-data leakage.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141.1-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=111111)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)

---

## 🚀 Key Features

- **Causal Backtesting** — `signal(t) → execution(t+1 open)`
- **Historical Replay** — repeatable research over historical market data
- **Multi-Timeframe Analysis** — strategy and indicator evaluation across timeframes
- **Paper Trading** — simulated entries, exits, stops, targets, and trade journaling
- **Quantitative Analytics** — equity curve, drawdown, trade history, and KPIs
- **Stock Universe Validation** — data → backtest → OOS validation → paper trading
- **Research Tearsheets** — standalone HTML reports
- **Research Provenance** — SHA-256 integrity checks for frozen configurations/data
- **Automated Testing** — backend + frontend tests through GitHub Actions

---

## 🛠️ Tech Stack

**Backend:** Python, FastAPI, Uvicorn, Pydantic  
**Data & Research:** Pandas, NumPy  
**Frontend:** React 19, Vite, Lightweight Charts  
**Testing:** Pytest, Node/Vite test runner  
**DevOps:** Docker, Docker Compose, GitHub Actions

---

## 🏗️ Architecture

```text
React 19 Frontend
       │
       │ REST / JSON
       ▼
FastAPI Backend
       │
       ├── Strategy & Indicators
       ├── Backtesting
       ├── Market Data
       ├── Scanner
       ├── Paper Trading
       └── Validation
                │
                ▼
        Historical / Universe Data
```

---

## 📊 Research Integrity

SignalForge is designed for **research and simulation**, not live trading.

The project explicitly focuses on:

- causal execution
- future-data leakage detection
- data quality validation
- transaction-cost/slippage modeling
- reproducible research
- safe file and configuration handling

**No automatic broker order execution is implemented.**

---

## 🧪 Testing & CI

The repository includes tests for:

- strategy causality
- future-data leakage
- backtesting
- paper trading
- data validation
- reporting and analytics
- frontend workflows

GitHub Actions runs backend tests, frontend tests, and the production frontend build.

---

## 📚 Documentation

Detailed guides are available in [`docs/`](docs/):

- [Installation](docs/INSTALLATION.md)
- [Configuration](docs/CONFIGURATION.md)
- [API](docs/API.md)
- [Testing](docs/TESTING.md)
- [Security & Deployment](docs/SECURITY_DEPLOYMENT.md)

---

## ⚠️ Disclaimer

SignalForge is an **educational and research-oriented project** for historical analysis and simulated paper trading.

It does not provide financial advice, guarantee profits, or place live broker orders.

---

## 👨‍💻 Author

**SANKET AMTE**  
*Java Full Stack Developer | Backend Developer*

📧 **Email:** sanketamte6584@gmail.com  |  🔗 **LinkedIn:** LinkedIn Profile  |  💻 **GitHub:** GitHub Profile

> **Research carefully. Validate causally. Build reproducibly.**
