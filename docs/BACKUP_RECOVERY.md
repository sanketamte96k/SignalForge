# SignalForge — Backup & Data Recovery Guide

## 1. Data Classification

SignalForge structures data into three distinct tiers:

| Tier | Directory | Sensitivity / Role | Backup Policy |
| :--- | :--- | :--- | :--- |
| **Tier 1: Research Strategy & Invariants** | `research/strategy_evolution_2018/` | Core mathematical IP, reports, frozen V1 hashes. | Tracked in Git. Permanent historical record. |
| **Tier 2: Historical Datasets** | `data/historical/` | 1-minute OHLCV historical CSV files. | Excluded from Git. Backed up to local external cold storage. |
| **Tier 3: Paper Trading & Local State** | `data/paper_trading/` | Active simulation trade ledger and state. | Excluded from Git. Locally backed up before resets. |

---

## 2. Backup Procedure

To take an offline backup of your active simulation state and research outputs:

```bash
# Windows PowerShell
$BackupDir = "backup_" + (Get-Date -Format "yyyyMMdd_HHmmss")
New-Item -ItemType Directory -Path $BackupDir
Copy-Item -Recurse "data\paper_trading" "$BackupDir\paper_trading"
Copy-Item -Recurse "data\universe_registry.json" "$BackupDir\"

# Linux / macOS
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r data/paper_trading "$BACKUP_DIR/"
cp data/universe_registry.json "$BACKUP_DIR/"
```

---

## 3. Recovery Procedure

To restore from a backup archive:

```bash
# Windows PowerShell
Copy-Item -Recurse -Force "$BackupDir\paper_trading\*" "data\paper_trading\"
Copy-Item -Force "$BackupDir\universe_registry.json" "data\"

# Linux / macOS
cp -r "$BACKUP_DIR/paper_trading/"* data/paper_trading/
cp "$BACKUP_DIR/universe_registry.json" data/
```

