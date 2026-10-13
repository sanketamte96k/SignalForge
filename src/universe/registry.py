import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

# Configurable Qualification Thresholds for Forward Paper Trading
MIN_FORWARD_TRADES_FOR_APPROVAL: int = 30
PREFERRED_FORWARD_TRADES_FOR_APPROVAL: int = 50


class QualificationStatus(str, Enum):
    NOT_TESTED = "NOT_TESTED"
    IN_PROGRESS = "IN_PROGRESS"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass
class StrategyQualificationRecord:
    symbol: str
    exchange: str
    strategy_id: str
    strategy_version: str
    historical_data_status: str
    backtest_status: str
    backtest_net_profit: Optional[float]
    oos_validation_status: str
    forward_paper_test_status: str
    completed_trade_count: int
    qualification_status: QualificationStatus
    status_reason: Optional[str]
    evidence_reference: Optional[str]
    updated_at: datetime


class UniverseCategory(str, Enum):
    NIFTY_50 = "NIFTY_50"
    NIFTY_NEXT_50 = "NIFTY_NEXT_50"
    CUSTOM = "CUSTOM"


class DataQualityStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    READY = "READY"
    INCOMPLETE = "INCOMPLETE"


@dataclass
class StockRecord:
    symbol: str
    exchange: str
    name: Optional[str]
    category: UniverseCategory
    membership_verified_at: Optional[datetime]
    data_quality_status: DataQualityStatus
    created_at: datetime


class StockUniverseRegistry:
    """Manages the persistent stock universe registry."""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.qual_storage_path = storage_path.parent / (storage_path.stem + "_qualifications.json")
        self._cache: dict[str, StockRecord] = {}
        self._qual_cache: dict[str, dict[str, StrategyQualificationRecord]] = {}
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            self._cache = {}
            return

        with open(self.storage_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}

        for key, record_data in data.items():
            verified_at = record_data.get("membership_verified_at")
            if verified_at:
                verified_at = datetime.fromisoformat(verified_at)
                
            self._cache[key] = StockRecord(
                symbol=record_data["symbol"],
                exchange=record_data["exchange"],
                name=record_data.get("name"),
                category=UniverseCategory(record_data["category"]),
                membership_verified_at=verified_at,
                data_quality_status=DataQualityStatus(record_data.get("data_quality_status", DataQualityStatus.UNKNOWN.value)),
                created_at=datetime.fromisoformat(record_data["created_at"]),
            )

        self._qual_cache = {}
        if self.qual_storage_path.exists():
            with open(self.qual_storage_path, "r", encoding="utf-8") as f:
                try:
                    qual_data = json.load(f)
                except json.JSONDecodeError:
                    qual_data = {}
            for sym, strategies in qual_data.items():
                self._qual_cache[sym] = {}
                for strat_id, qd in strategies.items():
                    self._qual_cache[sym][strat_id] = StrategyQualificationRecord(
                        symbol=qd["symbol"],
                        exchange=qd["exchange"],
                        strategy_id=qd["strategy_id"],
                        strategy_version=qd["strategy_version"],
                        historical_data_status=qd["historical_data_status"],
                        backtest_status=qd["backtest_status"],
                        backtest_net_profit=qd.get("backtest_net_profit"),
                        oos_validation_status=qd["oos_validation_status"],
                        forward_paper_test_status=qd["forward_paper_test_status"],
                        completed_trade_count=qd.get("completed_trade_count", 0),
                        qualification_status=QualificationStatus(qd["qualification_status"]),
                        status_reason=qd.get("status_reason"),
                        evidence_reference=qd.get("evidence_reference"),
                        updated_at=datetime.fromisoformat(qd["updated_at"]),
                    )


    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for key, record in self._cache.items():
            record_dict = asdict(record)
            if record.membership_verified_at:
                record_dict["membership_verified_at"] = record.membership_verified_at.isoformat()
            if record.created_at:
                record_dict["created_at"] = record.created_at.isoformat()
            data[key] = record_dict

        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        qual_data = {}
        for sym, strategies in self._qual_cache.items():
            qual_data[sym] = {}
            for strat_id, q_record in strategies.items():
                qr_dict = asdict(q_record)
                qr_dict["updated_at"] = q_record.updated_at.isoformat()
                qual_data[sym][strat_id] = qr_dict
        with open(self.qual_storage_path, "w", encoding="utf-8") as f:
            json.dump(qual_data, f, indent=2)


    def _normalize_symbol(self, symbol: str) -> str:
        return symbol.strip().upper()

    def register(
        self,
        symbol: str,
        exchange: str,
        category: UniverseCategory,
        name: Optional[str] = None,
    ) -> StockRecord:
        normalized_symbol = self._normalize_symbol(symbol)
        
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")
        
        if not exchange.strip():
            raise ValueError("exchange must not be empty")

        if normalized_symbol in self._cache:
            raise ValueError(f"stock already registered: {normalized_symbol}")

        record = StockRecord(
            symbol=normalized_symbol,
            exchange=exchange.strip().upper(),
            name=name.strip() if name else None,
            category=category,
            membership_verified_at=None,
            data_quality_status=DataQualityStatus.UNKNOWN,
            created_at=datetime.now(timezone.utc),
        )

        self._cache[normalized_symbol] = record
        self._save()
        return record

    def get(self, symbol: str) -> Optional[StockRecord]:
        return self._cache.get(self._normalize_symbol(symbol))

    def list_all(
        self, 
        category: Optional[UniverseCategory] = None,
        search_query: Optional[str] = None
    ) -> list[StockRecord]:
        results = list(self._cache.values())

        if category:
            results = [r for r in results if r.category == category]
            
        if search_query:
            query = search_query.strip().casefold()
            results = [
                r for r in results 
                if query in r.symbol.casefold() or (r.name and query in r.name.casefold())
            ]
            
        return sorted(results, key=lambda r: r.symbol)

    def get_qualifications(self, symbol: str) -> list[StrategyQualificationRecord]:
        normalized_symbol = self._normalize_symbol(symbol)
        if normalized_symbol not in self._cache:
            raise ValueError("Stock not registered")
        return list(self._qual_cache.get(normalized_symbol, {}).values())

    def get_qualification(self, symbol: str, strategy_id: str) -> StrategyQualificationRecord:
        normalized_symbol = self._normalize_symbol(symbol)
        if normalized_symbol not in self._cache:
            raise ValueError("Stock not registered")
            
        stock = self._cache[normalized_symbol]
        
        if normalized_symbol not in self._qual_cache or strategy_id not in self._qual_cache[normalized_symbol]:
            return StrategyQualificationRecord(
                symbol=stock.symbol,
                exchange=stock.exchange,
                strategy_id=strategy_id,
                strategy_version="unknown",
                historical_data_status="UNKNOWN",
                backtest_status="UNKNOWN",
                backtest_net_profit=None,
                oos_validation_status="UNKNOWN",
                forward_paper_test_status="UNKNOWN",
                completed_trade_count=0,
                qualification_status=QualificationStatus.NOT_TESTED,
                status_reason=None,
                evidence_reference=None,
                updated_at=datetime.now(timezone.utc),
            )
        return self._qual_cache[normalized_symbol][strategy_id]

    def update_qualification(
        self,
        symbol: str,
        strategy_id: str,
        strategy_version: str,
        historical_data_status: str,
        backtest_status: str,
        backtest_net_profit: Optional[float],
        oos_validation_status: str,
        forward_paper_test_status: str,
        completed_trade_count: int,
        qualification_status: QualificationStatus,
        status_reason: Optional[str] = None,
        evidence_reference: Optional[str] = None,
    ) -> StrategyQualificationRecord:
        normalized_symbol = self._normalize_symbol(symbol)
        if normalized_symbol not in self._cache:
            raise ValueError("Stock not registered")
            
        stock = self._cache[normalized_symbol]

        # Numeric validations
        if not isinstance(completed_trade_count, int) or completed_trade_count < 0:
            raise ValueError("completed_trade_count must be a non-negative integer")

        if backtest_net_profit is not None:
            if not isinstance(backtest_net_profit, (int, float)) or not math.isfinite(backtest_net_profit):
                raise ValueError("backtest_net_profit must be a finite number")

        # Inconsistent trade counts and status checks
        # If backtest claims PASSED, actual finite net profit metric is required
        if backtest_status == "PASSED" and backtest_net_profit is None:
            raise ValueError("backtest_status 'PASSED' requires evidence of backtest_net_profit")

        # If forward paper test status claims PASSED, trade count cannot be zero
        if forward_paper_test_status == "PASSED" and completed_trade_count == 0:
            raise ValueError("forward_paper_test_status 'PASSED' requires completed forward trades (cannot be 0)")

        # Gate hardening for APPROVED qualification status
        if qualification_status == QualificationStatus.APPROVED:
            if (
                historical_data_status != "READY"
                or backtest_status != "PASSED"
                or oos_validation_status != "PASSED"
                or forward_paper_test_status != "PASSED"
            ):
                raise ValueError("Cannot approve strategy without all validation evidence passing")

            if completed_trade_count < MIN_FORWARD_TRADES_FOR_APPROVAL:
                raise ValueError(
                    f"Cannot approve strategy with fewer than {MIN_FORWARD_TRADES_FOR_APPROVAL} completed forward trades "
                    f"(found {completed_trade_count})"
                )

            if backtest_net_profit is None or not math.isfinite(backtest_net_profit):
                raise ValueError("Cannot approve strategy without valid finite backtest net profit")

        if normalized_symbol not in self._qual_cache:
            self._qual_cache[normalized_symbol] = {}
            
        record = StrategyQualificationRecord(
            symbol=stock.symbol,
            exchange=stock.exchange,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            historical_data_status=historical_data_status,
            backtest_status=backtest_status,
            backtest_net_profit=backtest_net_profit,
            oos_validation_status=oos_validation_status,
            forward_paper_test_status=forward_paper_test_status,
            completed_trade_count=completed_trade_count,
            qualification_status=qualification_status,
            status_reason=status_reason,
            evidence_reference=evidence_reference,
            updated_at=datetime.now(timezone.utc),
        )
        self._qual_cache[normalized_symbol][strategy_id] = record
        self._save()
        return record
