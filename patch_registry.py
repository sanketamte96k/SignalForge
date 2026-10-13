import sys

registry_path = "src/universe/registry.py"
with open(registry_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add new Enums and Dataclasses
new_models = """
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
    updated_at: datetime
"""
content = content.replace("class UniverseCategory(str, Enum):", new_models + "\n\nclass UniverseCategory(str, Enum):")

# Add qualification cache to init
init_replace = """    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.qual_storage_path = storage_path.parent / (storage_path.stem + "_qualifications.json")
        self._cache: dict[str, StockRecord] = {}
        self._qual_cache: dict[str, dict[str, StrategyQualificationRecord]] = {}
        self._load()"""
content = content.replace("""    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self._cache: dict[str, StockRecord] = {}
        self._load()""", init_replace)

# Add load/save for qualifications
load_logic_replace = """        for key, record_data in data.items():
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
                        updated_at=datetime.fromisoformat(qd["updated_at"]),
                    )
"""
content = content.replace("""        for key, record_data in data.items():
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
            )""", load_logic_replace)

save_logic_replace = """        with open(self.storage_path, "w", encoding="utf-8") as f:
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
"""
content = content.replace("""        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)""", save_logic_replace)


methods = """
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
                updated_at=datetime.utcnow(),
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
        status_reason: Optional[str]
    ) -> StrategyQualificationRecord:
        normalized_symbol = self._normalize_symbol(symbol)
        if normalized_symbol not in self._cache:
            raise ValueError("Stock not registered")
            
        stock = self._cache[normalized_symbol]

        if qualification_status == QualificationStatus.APPROVED:
            if historical_data_status != "READY" or \\
               backtest_status != "PASSED" or \\
               oos_validation_status != "PASSED" or \\
               forward_paper_test_status != "PASSED":
                raise ValueError("Cannot approve strategy without all evidence passing")
            if completed_trade_count < 1:
                raise ValueError("Cannot approve strategy without completed trade samples")

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
            updated_at=datetime.utcnow()
        )
        self._qual_cache[normalized_symbol][strategy_id] = record
        self._save()
        return record
"""
content += methods

with open(registry_path, "w", encoding="utf-8") as f:
    f.write(content)
