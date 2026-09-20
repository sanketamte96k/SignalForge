from fastapi import APIRouter, HTTPException, Query

from src.api.models import (
    SectorCreateRequest,
    SectorListResponse,
    SectorResponse,
)
from src.universe.manager import UniverseManager


router = APIRouter(
    prefix="/api/sectors",
    tags=["sectors"],
)

_universe = UniverseManager()


def _to_response(sector) -> SectorResponse:
    return SectorResponse(
        name=sector.name,
        description=sector.description,
        symbols=list(sector.symbols),
    )


@router.get("", response_model=SectorListResponse)
def list_sectors() -> SectorListResponse:
    """Return all configured sectors."""
    return SectorListResponse(
        sectors=[
            _to_response(sector)
            for sector in _universe.all_sectors()
        ]
    )


@router.post(
    "",
    response_model=SectorResponse,
    status_code=201,
)
def create_sector(
    request: SectorCreateRequest,
) -> SectorResponse:
    """Create a new sector."""
    try:
        sector = _universe.create_sector(
            name=request.name,
            description=request.description,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return _to_response(sector)


@router.get(
    "/{sector_name}",
    response_model=SectorResponse,
)
def get_sector(
    sector_name: str,
) -> SectorResponse:
    """Return one sector."""
    try:
        sector = _universe.get_sector(sector_name)
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return _to_response(sector)


@router.delete(
    "/{sector_name}",
    status_code=204,
)
def delete_sector(
    sector_name: str,
) -> None:
    """Delete a sector."""
    try:
        _universe.delete_sector(sector_name)
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post(
    "/{sector_name}/stocks/{symbol}",
    response_model=SectorResponse,
)
def add_stock_to_sector(
    sector_name: str,
    symbol: str,
) -> SectorResponse:
    """Add a stock to a sector."""
    try:
        sector = _universe.add_stock_to_sector(
            sector_name=sector_name,
            symbol=symbol,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return _to_response(sector)


@router.delete(
    "/{sector_name}/stocks/{symbol}",
    response_model=SectorResponse,
)
def remove_stock_from_sector(
    sector_name: str,
    symbol: str,
) -> SectorResponse:
    """Remove a stock from a sector."""
    try:
        sector = _universe.remove_stock_from_sector(
            sector_name=sector_name,
            symbol=symbol,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return _to_response(sector)


@router.get(
    "/{sector_name}/stocks",
    response_model=list[str],
)
def get_sector_stocks(
    sector_name: str,
    search: str | None = Query(default=None),
) -> list[str]:
    """Return stocks in a sector, optionally filtered by symbol."""
    try:
        symbols = _universe.sector_symbols(sector_name)
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    if search is None:
        return list(symbols)

    normalized_search = search.strip().upper()

    if not normalized_search:
        return list(symbols)

    return [
        symbol
        for symbol in symbols
        if normalized_search in symbol
    ]
