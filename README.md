# SignalForge

> **Quantitative Market Research & Causal Backtesting Platform**

SignalForge is an offline-first research platform for **historical market analysis, causal backtesting, paper-trading simulation, and quantitative reporting** for Indian equities.

Built with **Python/FastAPI + React**, with a strong focus on reproducibility, validation, and avoiding future-data leakage.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-Supported-2496ED?logo=docker)](https://www.docker.com/)

---

## 🚀 Key Features

- **Causal Backtesting** — signal at candle `t` executes at `t+1 open`
- **Historical Replay** for research and strategy evaluation
- **Multi-Timeframe Analysis**
- **Paper Trading Simulation**
- **Quantitative Analytics** including equity and drawdown analysis
- **Stock Universe Validation** — data → backtest → OOS validation → paper trading
- **Research Tearsheets** for strategy results and reporting
- **Research Provenance** using SHA-256 hashing
- **Automated Testing** with backend and frontend CI

---

## 🛠️ Tech Stack

### Backend
- Python
- FastAPI
- Uvicorn
- Pydantic

### Data & Research
- Pandas
- NumPy

### Frontend
- React 19
- Vite
- Lightweight Charts

### Testing
- Pytest
- Frontend test runner

### DevOps
- Docker
- Docker Compose
- GitHub Actions

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

The platform focuses on:

- Causal execution
- Future-data leakage detection
- Data-quality validation
- Transaction-cost and slippage modelling
- Reproducible research
- Safe configuration and file handling
- Historical strategy validation

**No automatic broker order execution is implemented.**

---

## 🧪 Testing & CI

SignalForge includes tests covering:

- Strategy causality
- Future-data leakage
- Backtesting
- Paper trading
- Data validation
- Reporting
- Analytics
- API behaviour

GitHub Actions is used to run backend tests, frontend tests, and the production frontend build.

---

## 📚 Documentation

Detailed project documentation is available in the `docs/` directory.

- [Installation](docs/INSTALLATION.md)
- [Configuration](docs/CONFIGURATION.md)
- [API Documentation](docs/API.md)
- [Testing](docs/TESTING.md)
- [Startup Guide](docs/STARTUP.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Security & Deployment](docs/SECURITY_DEPLOYMENT.md)
- [Backup & Recovery](docs/BACKUP_RECOVERY.md)

---

## 💡 Suggestions & Feedback

Have an idea to improve SignalForge?

You can send suggestions, feedback, or improvement ideas directly to:

**📧 [sanketamte6584@gmail.com](mailto:sanketamte6584@gmail.com)**

Please include a clear description of the suggestion and, when possible, explain the problem it would solve.

---

## ⚠️ Disclaimer

SignalForge is an **educational and research project** for historical market analysis and simulated paper trading.

It does **not** provide financial advice and does not guarantee trading performance.

**No live broker order execution is provided.**

---

## 👨‍💻 Author

### Sanket Amte

B.Tech Information Technology Student

[![GitHub](https://img.shields.io/badge/GitHub-sanketamte96k-181717?logo=github)](https://github.com/sanketamte96k)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Sanket%20Amte-0A66C2?logo=linkedin)](https://www.linkedin.com/in/sanket-amte-a55a61332/)
[![Portfolio](https://img.shields.io/badge/Portfolio-Visit-000000?logo=vercel)](https://sanket-portfolio-lemon.vercel.app)
[![Email](https://img.shields.io/badge/Email-Contact-EA4335?logo=gmail)](mailto:sanketamte6584@gmail.com)

---

⭐ **If you find SignalForge useful, consider giving the repository a star.**
