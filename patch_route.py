import sys

route_path = "src/api/routes/universe.py"
with open(route_path, "r", encoding="utf-8") as f:
    content = f.read()

new_imports = """
from src.api.models import QualificationResponse, QualificationUpdateRequest
from src.universe.registry import QualificationStatus
"""
content = content.replace("from src.api.models import UniverseStockResponse, UniverseStockAddRequest", "from src.api.models import UniverseStockResponse, UniverseStockAddRequest, QualificationResponse, QualificationUpdateRequest\nfrom src.universe.registry import QualificationStatus")

new_endpoints = """
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
            status_reason=request.status_reason
        )
        return _to_qual_response(record)
    except ValueError as e:
        if "not registered" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
"""
content += new_endpoints

with open(route_path, "w", encoding="utf-8") as f:
    f.write(content)
