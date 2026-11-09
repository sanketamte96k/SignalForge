# SignalForge — Clean Installation Guide

## 1. System Requirements

- **Operating System:** Windows 10/11, macOS 12+, or Ubuntu 20.04+ Linux
- **Python Version:** Python 3.10 to 3.14 (Validated on 3.12, 3.13, 3.14.3)
- **Node.js Version:** Node.js v18.0.0 or higher (Validated on v20 LTS and v22.14.0)
- **Package Managers:** `pip` (Python) and `npm` (Node.js)
- **Disk Space:** Minimum 500 MB for core repository and dependencies; 2 GB recommended for historical market data.

---

## 2. Step-by-Step Installation

### Step 1: Clone Repository
```bash
git clone https://github.com/sanketamte96k/SignalForge.git
cd SignalForge
```

### Step 2: Configure Python Virtual Environment
It is strongly recommended to isolate dependencies inside a virtual environment:

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**On Linux / macOS (Bash):**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Backend Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Verify backend installation:
```bash
python -c "import fastapi, uvicorn, pydantic, pandas, numpy; print('Backend dependencies successfully installed!')"
```

### Step 4: Install Frontend Dependencies
```bash
cd frontend
npm install
cd ..
```

Verify frontend build:
```bash
cd frontend
npm run build
cd ..
```
Expected Output: `built in <1s` generating chunks into `frontend/dist`.

---

## 3. Local Data Directory Initialization

SignalForge expects standard data directories for historical research and paper trading simulation. If setting up a fresh machine, initialize the directory skeleton:

```bash
mkdir -p data/historical/stocks
mkdir -p data/paper_trading
mkdir -p data/universe
```

Ensure the active paper trading ledger exists (empty array by default):
```bash
# Windows PowerShell
if (!(Test-Path "data\paper_trading\interactive_trades.json")) { "[]" | Out-File -Encoding utf8 "data\paper_trading\interactive_trades.json" }

# Linux / macOS
[ -f data/paper_trading/interactive_trades.json ] || echo "[]" > data/paper_trading/interactive_trades.json
```

