"""
SignalForge — Capital Allocation API Routes
============================================
File: src/api/routes/capital_allocation.py

Exposes endpoints for user-selectable capital allocation:
- Presets: ₹10K, ₹25K, ₹50K, ₹1L, ₹2L, and Custom.
- Ring-fencing inspection (Allocated vs Unallocated balance).
- Pre-trade validation against allocated capital.
- Position execution and close within isolated allocation containers.
- Separate telemetry and reporting per allocation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.core.capital_allocation import (
    PRESET_CAPITAL_ALLOCATIONS,
    PRESET_LABELS,
    CapitalAllocation,
    CapitalAllocationManager,
    get_capital_allocation_manager,
)

router = APIRouter(prefix="/api/v1/capital", tags=["Capital Allocation"])


class PresetResponse(BaseModel):
    presets: List[float]
    labels: Dict[str, str]


class AllocateCapitalRequest(BaseModel):
    allocation_id: str = Field(..., description="Unique ID for this capital allocation container")
    total_account_balance: float = Field(..., gt=0, description="Total account equity or balance (e.g. ₹30,000)")
    allocated_capital: float = Field(..., gt=0, description="Capital allocated strictly to SignalForge (e.g. ₹10,000)")
    account_id: str = Field("default_account", description="Associated account identifier")


class ValidateTradeRequest(BaseModel):
    symbol: str
    entry_price: float = Field(..., gt=0)
    quantity: int = Field(..., gt=0)
    estimated_costs: float = Field(0.0, ge=0)


class ExecuteTradeRequest(BaseModel):
    trade_id: str
    symbol: str
    side: str = Field("BUY", pattern="^(BUY|SELL|buy|sell)$")
    quantity: int = Field(..., gt=0)
    entry_price: float = Field(..., gt=0)
    entry_costs: float = Field(0.0, ge=0)
    stop_loss: Optional[float] = None
    target: Optional[float] = None


class CloseTradeRequest(BaseModel):
    symbol: str
    exit_price: float = Field(..., gt=0)
    exit_costs: float = Field(0.0, ge=0)
    exit_reason: str = "TARGET_OR_STOP"


class PositionSizeRequest(BaseModel):
    entry_price: float = Field(..., gt=0)
    stop_loss: float = Field(..., gt=0)
    risk_pct: float = Field(0.01, gt=0, le=0.10)
    max_allocation_pct: float = Field(0.35, gt=0, le=1.0)


@router.get("/presets", response_model=PresetResponse)
def get_presets() -> PresetResponse:
    """Returns supported preset capital allocations and their human-readable labels."""
    str_labels = {str(k): v for k, v in PRESET_LABELS.items()}
    return PresetResponse(presets=PRESET_CAPITAL_ALLOCATIONS, labels=str_labels)


@router.post("/allocate", status_code=status.HTTP_201_CREATED)
def create_allocation(req: AllocateCapitalRequest) -> Dict[str, Any]:
    """
    Creates or registers an isolated capital allocation container.
    Guarantees strategy uses ONLY the allocated capital, strictly ring-fencing unallocated funds.
    """
    mgr = get_capital_allocation_manager()
    try:
        alloc = mgr.get_or_create(
            allocation_id=req.allocation_id,
            total_account_balance=req.total_account_balance,
            allocated_capital=req.allocated_capital,
            account_id=req.account_id,
        )
        return alloc.get_display_summary()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/allocations")
def list_allocations() -> List[Dict[str, Any]]:
    """Returns telemetry summaries for all active capital allocations."""
    mgr = get_capital_allocation_manager()
    return [alloc.get_display_summary() for alloc in mgr.list_allocations()]


@router.get("/allocations/{allocation_id}")
def get_allocation_status(allocation_id: str) -> Dict[str, Any]:
    """Returns telemetry summary for a specific capital allocation container."""
    mgr = get_capital_allocation_manager()
    try:
        alloc = mgr.get_allocation(allocation_id)
        return alloc.get_display_summary()
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Allocation '{allocation_id}' not found",
        )


@router.post("/allocations/{allocation_id}/calculate-size")
def calculate_size(allocation_id: str, req: PositionSizeRequest) -> Dict[str, Any]:
    """
    Calculates integer position size strictly bounded by allocated capital.
    """
    mgr = get_capital_allocation_manager()
    try:
        alloc = mgr.get_allocation(allocation_id)
        shares = alloc.calculate_position_size(
            entry_price=req.entry_price,
            stop_loss_price=req.stop_loss,
            risk_pct=req.risk_pct,
            max_allocation_pct=req.max_allocation_pct,
        )
        return {
            "allocation_id": allocation_id,
            "allocated_equity": alloc.total_equity,
            "available_allocated_cash": alloc.available_cash,
            "entry_price": req.entry_price,
            "stop_loss": req.stop_loss,
            "recommended_shares": shares,
            "total_notional": round(shares * req.entry_price, 2),
        }
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Allocation '{allocation_id}' not found",
        )


@router.post("/allocations/{allocation_id}/validate-trade")
def validate_trade(allocation_id: str, req: ValidateTradeRequest) -> Dict[str, Any]:
    """
    Validates whether an order can be executed within allocated capital limits.
    """
    mgr = get_capital_allocation_manager()
    try:
        alloc = mgr.get_allocation(allocation_id)
        valid, msg = alloc.validate_trade(
            symbol=req.symbol,
            entry_price=req.entry_price,
            quantity=req.quantity,
            estimated_costs=req.estimated_costs,
        )
        return {
            "allocation_id": allocation_id,
            "symbol": req.symbol,
            "approved": valid,
            "message": msg,
            "available_cash": alloc.available_cash,
            "required_capital": round((req.quantity * req.entry_price) + req.estimated_costs, 2),
        }
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Allocation '{allocation_id}' not found",
        )


@router.post("/allocations/{allocation_id}/execute-trade")
def execute_trade(allocation_id: str, req: ExecuteTradeRequest) -> Dict[str, Any]:
    """
    Executes a position entry under the designated capital allocation bucket.
    """
    mgr = get_capital_allocation_manager()
    try:
        alloc = mgr.get_allocation(allocation_id)
        rec = alloc.open_position(
            trade_id=req.trade_id,
            symbol=req.symbol,
            side=req.side,
            quantity=req.quantity,
            entry_price=req.entry_price,
            entry_costs=req.entry_costs,
            stop_loss=req.stop_loss,
            target=req.target,
        )
        return {
            "status": "EXECUTED",
            "trade": rec.to_dict(),
            "allocation_summary": alloc.get_display_summary(),
        }
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Allocation '{allocation_id}' not found",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/allocations/{allocation_id}/close-trade")
def close_trade(allocation_id: str, req: CloseTradeRequest) -> Dict[str, Any]:
    """
    Closes an active position and updates the allocation container's realized P&L.
    """
    mgr = get_capital_allocation_manager()
    try:
        alloc = mgr.get_allocation(allocation_id)
        rec = alloc.close_position(
            symbol=req.symbol,
            exit_price=req.exit_price,
            exit_costs=req.exit_costs,
            exit_reason=req.exit_reason,
        )
        return {
            "status": "CLOSED",
            "trade": rec.to_dict(),
            "allocation_summary": alloc.get_display_summary(),
        }
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
