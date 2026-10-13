import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

# Configurable Qualification Thresholds for Forward Paper Trading
# Configurable Qualification Thresholds for Forward Paper Trading
DEFAULT_MIN_FORWARD_TRADES: int = 30
DEFAULT_PREFERRED_FORWARD_TRADES: int = 50

# Backwards-compatible constants
MIN_FORWARD_TRADES_FOR_APPROVAL: int = DEFAULT_MIN_FORWARD_TRADES
PREFERRED_FORWARD_TRADES_FOR_APPROVAL: int = DEFAULT_PREFERRED_FORWARD_TRADES


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

    @property
    def meets_initial_threshold(self) -> bool:
        """Returns True if completed forward trade sample meets minimum evaluation threshold (30)."""
        return self.completed_trade_count >= DEFAULT_MIN_FORWARD_TRADES

    @property
    def meets_preferred_threshold(self) -> bool:
        """Returns True if completed forward trade sample meets preferred threshold (50+)."""
        return self.completed_trade_count >= DEFAULT_PREFERRED_FORWARD_TRADES

    @property
    def is_approved(self) -> bool:
        """Returns True if stock/strategy combination is APPROVED."""
        return self.qualification_status == QualificationStatus.APPROVED


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
    """Manages the persistent stock universe registry and qualification gates."""

    def __init__(
        self,
        storage_path: Path,
        min_forward_trades: int = DEFAULT_MIN_FORWARD_TRADES,
        preferred_forward_trades: int = DEFAULT_PREFERRED_FORWARD_TRADES,
    ):
        if isinstance(min_forward_trades, bool) or not isinstance(min_forward_trades, int) or min_forward_trades < 0:
            raise ValueError("min_forward_trades must be a non-negative integer")
        if isinstance(preferred_forward_trades, bool) or not isinstance(preferred_forward_trades, int) or preferred_forward_trades < 0:
            raise ValueError("preferred_forward_trades must be a non-negative integer")

        self.storage_path = storage_path
        self.qual_storage_path = storage_path.parent / (storage_path.stem + "_qualifications.json")
        self.min_forward_trades = min_forward_trades
        self.preferred_forward_trades = preferred_forward_trades
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
        min_forward_trades: Optional[int] = None,
    ) -> StrategyQualificationRecord:
        normalized_symbol = self._normalize_symbol(symbol)
        if normalized_symbol not in self._cache:
            raise ValueError("Stock not registered")
            
        stock = self._cache[normalized_symbol]

        # 1. Configurable threshold resolution & validation
        if min_forward_trades is not None:
            if isinstance(min_forward_trades, bool) or not isinstance(min_forward_trades, int) or min_forward_trades < 0:
                raise ValueError("min_forward_trades override must be a non-negative integer")
            effective_min_trades = min_forward_trades
        else:
            effective_min_trades = self.min_forward_trades

        # 2. Strict numeric validations (reject bools, non-integers, negatives, and non-finite numbers)
        if isinstance(completed_trade_count, bool) or not isinstance(completed_trade_count, int) or completed_trade_count < 0:
            raise ValueError("completed_trade_count must be a non-negative integer")

        if backtest_net_profit is not None:
            if isinstance(backtest_net_profit, bool) or not isinstance(backtest_net_profit, (int, float)) or not math.isfinite(backtest_net_profit):
                raise ValueError("backtest_net_profit must be a finite number")

        # 3. Missing or Contradictory Validation Evidence Checks
        # Historical data must be READY before backtesting or OOS validation can claim PASSED
        if backtest_status == "PASSED" and historical_data_status != "READY":
            raise ValueError(f"backtest_status cannot be 'PASSED' when historical_data_status is '{historical_data_status}'")

        if oos_validation_status == "PASSED" and historical_data_status != "READY":
            raise ValueError(f"oos_validation_status cannot be 'PASSED' when historical_data_status is '{historical_data_status}'")

        # Out-Of-Sample validation cannot pass if the backtest did not pass
        if oos_validation_status == "PASSED" and backtest_status != "PASSED":
            raise ValueError(f"oos_validation_status cannot be 'PASSED' when backtest_status is '{backtest_status}'")

        # Unsupported assertion: backtest_status 'PASSED' requires evidence of positive finite net profit
        if backtest_status == "PASSED":
            if backtest_net_profit is None:
                raise ValueError("backtest_status 'PASSED' requires evidence of backtest_net_profit")
            if backtest_net_profit <= 0:
                raise ValueError(f"backtest_status 'PASSED' requires positive backtest_net_profit (found {backtest_net_profit})")

        # Unsupported assertion: forward_paper_test_status 'PASSED' requires actual completed forward trades
        if forward_paper_test_status == "PASSED" and completed_trade_count == 0:
            raise ValueError("forward_paper_test_status 'PASSED' requires completed forward trades (cannot be 0)")

        # Clean/normalize evidence reference and reason
        cleaned_reason = status_reason.strip() if status_reason and status_reason.strip() else None
        cleaned_evidence = evidence_reference.strip() if evidence_reference and evidence_reference.strip() else None

        # 4. Gate hardening for APPROVED qualification status
        if qualification_status == QualificationStatus.APPROVED:
            # All validation evidence gates must explicitly pass
            if (
                historical_data_status != "READY"
                or backtest_status != "PASSED"
                or oos_validation_status != "PASSED"
                or forward_paper_test_status != "PASSED"
            ):
                raise ValueError("Cannot approve strategy without all validation evidence passing")

            # Must satisfy configurable minimum completed forward trades
            if completed_trade_count < effective_min_trades:
                raise ValueError(
                    f"Cannot approve strategy with fewer than {effective_min_trades} completed forward trades "
                    f"(found {completed_trade_count})"
                )

            # Must have valid positive finite net profit
            if backtest_net_profit is None or not math.isfinite(backtest_net_profit) or backtest_net_profit <= 0:
                raise ValueError("Cannot approve strategy without valid positive finite backtest net profit")

            if cleaned_reason is None:
                cleaned_reason = (
                    f"Approved: met all qualification gates with {completed_trade_count} completed forward trades "
                    f"(threshold: {effective_min_trades})"
                )

        if qualification_status == QualificationStatus.REJECTED and cleaned_reason is None:
            cleaned_reason = "Rejected: failed qualification criteria"

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
            status_reason=cleaned_reason,
            evidence_reference=cleaned_evidence,
            updated_at=datetime.now(timezone.utc),
        )
        self._qual_cache[normalized_symbol][strategy_id] = record
        self._save()
        return record
