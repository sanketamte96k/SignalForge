from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.models import (
    UniverseStockResponse,
    UniverseStockAddRequest,
    QualificationResponse,
    QualificationUpdateRequest,
    StockReadinessResponse,
    UniverseReadinessSummaryResponse,
    IngestionRequest,
    PipelineIngestSymbolRequest,
    PipelineBatchIngestRequest,
)
from src.data.historical_pipeline import (
    HistoricalDataPipeline,
    PipelineIngestionRequest,
)
from src.universe.ingestion import (
    load_canonical_source,
    parse_constituent_csv,
    create_ingestion_plan,
    execute_ingestion,
)
from src.universe.readiness import (
    assess_stock_readiness,
    assess_universe_readiness,
)
from src.universe.registry import QualificationStatus, StockUniverseRegistry, UniverseCategory

router = APIRouter(
    prefix="/api/universe/stocks",
    tags=["universe"],
)

# Use a default registry for the API
STORAGE_PATH = Path("data/universe_registry.json")
_registry = StockUniverseRegistry(STORAGE_PATH)
_pipeline = HistoricalDataPipeline(registry=_registry)

def _to_response(record) -> UniverseStockResponse:
    return UniverseStockResponse(
        symbol=record.symbol,
        exchange=record.exchange,
        name=record.name,
        category=record.category.value,
        membership_verified_at=record.membership_verified_at,
        data_quality_status=record.data_quality_status.value,
        created_at=record.created_at,
    )

@router.get("", response_model=list[UniverseStockResponse])
def list_stocks(
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
) -> list[UniverseStockResponse]:
    """List registered stocks, optionally filtered by category or search query."""
    try:
        cat_enum = UniverseCategory(category) if category else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid category")
        
    records = _registry.list_all(category=cat_enum, search_query=q)
    return [_to_response(r) for r in records]

@router.get("/readiness/summary", response_model=UniverseReadinessSummaryResponse)
def get_universe_readiness_summary(
    strategy_id: str = Query("SignalForge_V1"),
) -> UniverseReadinessSummaryResponse:
    """Read-only audit of readiness across the entire registered stock universe."""
    summary = assess_universe_readiness(
        registry=_registry,
        strategy_id=strategy_id,
    )
    return UniverseReadinessSummaryResponse(**summary)

@router.post("/ingest/plan")
def preview_ingestion(request: IngestionRequest) -> dict:
    """Dry-run preview of constituent ingestion from verified canonical source."""
    try:
        cat_enum = UniverseCategory(request.category)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid category")

    try:
        csv_text, provenance = load_canonical_source(cat_enum)
        constituents, parse_errors = parse_constituent_csv(csv_text, cat_enum, provenance)
        plan = create_ingestion_plan(_registry, constituents, cat_enum, provenance)
        return execute_ingestion(_registry, plan, dry_run=True, confirm_removals=request.confirm_removals)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post("/ingest/apply")
def apply_ingestion(request: IngestionRequest) -> dict:
    """Execute constituent ingestion from verified canonical source into registry."""
    try:
        cat_enum = UniverseCategory(request.category)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid category")

    try:
        csv_text, provenance = load_canonical_source(cat_enum)
        constituents, parse_errors = parse_constituent_csv(csv_text, cat_enum, provenance)
        plan = create_ingestion_plan(_registry, constituents, cat_enum, provenance)
        return execute_ingestion(_registry, plan, dry_run=False, confirm_removals=request.confirm_removals)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post("/data/pipeline/symbol")
def ingest_pipeline_symbol(request: PipelineIngestSymbolRequest) -> dict:
    """Execute or dry-run historical market data pipeline for a single stock."""
    try:
        req = PipelineIngestionRequest(
            symbol=request.symbol,
            exchange=request.exchange,
            interval=request.interval,
            provider=request.provider,
            dry_run=request.dry_run,
            confirm_replace=request.confirm_replace,
        )
        result = _pipeline.ingest_symbol(req)
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post("/data/pipeline/batch")
def ingest_pipeline_batch(request: PipelineBatchIngestRequest) -> dict:
    """Execute or dry-run historical market data pipeline for a batch of stocks."""
    try:
        batch_res = _pipeline.ingest_batch(
            symbols=request.symbols,
            exchange=request.exchange,
            interval=request.interval,
            provider=request.provider,
            dry_run=request.dry_run,
            confirm_replace=request.confirm_replace,
            confirm_large_batch=request.confirm_large_batch,
        )
        return batch_res.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/{symbol}", response_model=UniverseStockResponse)
def get_stock(symbol: str) -> UniverseStockResponse:
    """Retrieve one stock by symbol."""
    record = _registry.get(symbol)
    if not record:
        raise HTTPException(status_code=404, detail="Stock not found")
    return _to_response(record)

@router.post("", response_model=UniverseStockResponse, status_code=201)
def add_stock(request: UniverseStockAddRequest) -> UniverseStockResponse:
    """Register a new stock in the universe."""
    try:
        category = UniverseCategory(request.category)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid category")
        
    try:
        record = _registry.register(
            symbol=request.symbol,
            exchange=request.exchange,
            category=category,
            name=request.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
        
    return _to_response(record)

def _to_qual_response(record) -> QualificationResponse:
    return QualificationResponse(
        symbol=record.symbol,
        exchange=record.exchange,
        strategy_id=record.strategy_id,
        strategy_version=record.strategy_version,
        historical_data_status=record.historical_data_status,
        backtest_status=record.backtest_status,
        backtest_net_profit=record.backtest_net_profit,
        oos_validation_status=record.oos_validation_status,
        forward_paper_test_status=record.forward_paper_test_status,
        completed_trade_count=record.completed_trade_count,
        qualification_status=record.qualification_status.value,
        status_reason=record.status_reason,
        evidence_reference=record.evidence_reference,
        updated_at=record.updated_at
    )

@router.get("/{symbol}/qualifications", response_model=list[QualificationResponse])
def list_qualifications(symbol: str) -> list[QualificationResponse]:
    try:
        records = _registry.get_qualifications(symbol)
        return [_to_qual_response(r) for r in records]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{symbol}/qualifications/{strategy_id}", response_model=QualificationResponse)
def get_qualification(symbol: str, strategy_id: str) -> QualificationResponse:
    try:
        record = _registry.get_qualification(symbol, strategy_id)
        return _to_qual_response(record)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{symbol}/readiness", response_model=StockReadinessResponse)
def get_stock_readiness(
    symbol: str,
    strategy_id: str = Query("SignalForge_V1"),
) -> StockReadinessResponse:
    """Retrieve read-only readiness assessment for a stock and strategy."""
    record = _registry.get(symbol)
    if not record:
        raise HTTPException(status_code=404, detail="Stock not found")

    assessment = assess_stock_readiness(
        stock=record,
        strategy_id=strategy_id,
        registry=_registry,
    )
    return StockReadinessResponse(**assessment.to_dict())

@router.put("/{symbol}/qualifications/{strategy_id}", response_model=QualificationResponse)
def update_qualification(symbol: str, strategy_id: str, request: QualificationUpdateRequest) -> QualificationResponse:
    try:
        qual_status = QualificationStatus(request.qualification_status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid qualification status")
        
    try:
        record = _registry.update_qualification(
            symbol=symbol,
            strategy_id=strategy_id,
            strategy_version=request.strategy_version,
            historical_data_status=request.historical_data_status,
            backtest_status=request.backtest_status,
            backtest_net_profit=request.backtest_net_profit,
            oos_validation_status=request.oos_validation_status,
            forward_paper_test_status=request.forward_paper_test_status,
            completed_trade_count=request.completed_trade_count,
            qualification_status=qual_status,
            status_reason=request.status_reason,
            evidence_reference=request.evidence_reference,
        )
        return _to_qual_response(record)
    except ValueError as e:
        if "not registered" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
