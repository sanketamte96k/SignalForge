# SignalForge — Phase 24G.31: Clean Installation & Environment Audit

## 1. Installation Objective

The purpose of this audit is to validate that a clean development environment on Windows, Linux, or macOS can reliably clone, install, configure, build, and run SignalForge without tribal knowledge or undocumented manual hacks.

---

## 2. Environment & Runtime Matrix

| Component | Minimum Version | Validated Production Version | Status |
| :--- | :--- | :--- | :--- |
| **Python** | 3.10.0 | Python 3.14.3 / 3.12.3 | **VALIDATED** |
| **Node.js** | 18.0.0 | Node.js v22.14.0 / v20.11.0 LTS | **VALIDATED** |
| **NPM** | 9.0.0 | NPM 10.9.2 | **VALIDATED** |
| **FastAPI** | 0.110.0 | 0.141.1 | **PINNED** |
| **Uvicorn** | 0.28.0 | 0.52.4 | **PINNED** |
| **Pydantic** | 2.6.0 | 2.13.3 | **PINNED** |
| **Pandas** | 2.1.0 | 3.0.2 / 2.2.2 | **VALIDATED** |
| **NumPy** | 1.25.0 | 2.4.4 / 1.26.4 | **VALIDATED** |
| **React** | 19.0.0 | 19.2.8 | **VALIDATED** |
| **Vite** | 5.0.0 | 8.2.2 | **VALIDATED** |

---

## 3. Dependency Manifest Audit

### A. Python Backend (`requirements.txt`)
All necessary packages are explicitly defined in `requirements.txt`:
```txt
fastapi==0.141.1
uvicorn==0.52.4
pydantic==2.13.3
pandas>=2.2.0
numpy>=1.26.0
python-dotenv>=1.0.0
pytest>=8.0.0
httpx>=0.27.0
yfinance>=0.2.38
```
- Core web framework: `fastapi`, `uvicorn`, `pydantic`.
- Computational modeling: `pandas`, `numpy`.
- Testing harness: `pytest`, `httpx`.
- Environment configuration: `python-dotenv`.
- Zero proprietary, paid, or private packages required.

### B. Node.js Frontend (`frontend/package.json`)
Dependencies cleanly separated into runtime and dev tools:
- Runtime: `react`, `react-dom`, `lightweight-charts`.
- Build/Dev: `vite`, `@vitejs/plugin-react`, `vite-node`, `oxlint`.
- Production bundle builds cleanly in <1 second via `npm run build`.

---

## 4. Local Data Directory Initialization

The platform initializes gracefully when the local `data/` skeleton is present:
```bash
data/
├── universe_registry.json               (Tracked in Git)
├── universe_registry_qualifications.json(Tracked in Git)
├── universe/sources/                    (Tracked in Git)
├── paper_trading/                       (Created on demand, ignored by Git)
└── historical/                          (Local storage, ignored by Git)
```

If data directories are fresh:
```bash
mkdir -p data/historical/stocks data/paper_trading data/universe
```
The active paper trading ledger defaults to an empty JSON array (`[]`) if not present.
