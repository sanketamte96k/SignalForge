from fastapi import APIRouter, HTTPException, Query

from src.api.models import (
    WatchlistCreateRequest,
    WatchlistListResponse,
    WatchlistResponse,
)
from src.universe.manager import UniverseManager


router = APIRouter(
    prefix="/api/watchlists",
    tags=["watchlists"],
)

_universe = UniverseManager()


def _to_response(watchlist) -> WatchlistResponse:
    return WatchlistResponse(
        name=watchlist.name,
        description=watchlist.description,
        symbols=list(watchlist.symbols),
    )


@router.get(
    "",
    response_model=WatchlistListResponse,
)
def list_watchlists() -> WatchlistListResponse:
    """Return all configured watchlists."""
    return WatchlistListResponse(
        watchlists=[
            _to_response(watchlist)
            for watchlist in _universe.all_watchlists()
        ]
    )


@router.post(
    "",
    response_model=WatchlistResponse,
    status_code=201,
)
def create_watchlist(
    request: WatchlistCreateRequest,
) -> WatchlistResponse:
    """Create a new watchlist."""
    try:
        watchlist = _universe.create_watchlist(
            name=request.name,
            description=request.description,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return _to_response(watchlist)


@router.get(
    "/{watchlist_name}",
    response_model=WatchlistResponse,
)
def get_watchlist(
    watchlist_name: str,
) -> WatchlistResponse:
    """Return one watchlist."""
    try:
        watchlist = _universe.get_watchlist(watchlist_name)
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return _to_response(watchlist)


@router.delete(
    "/{watchlist_name}",
    status_code=204,
)
def delete_watchlist(
    watchlist_name: str,
) -> None:
    """Delete a watchlist."""
    try:
        _universe.delete_watchlist(watchlist_name)
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post(
    "/{watchlist_name}/stocks/{symbol}",
    response_model=WatchlistResponse,
)
def add_stock_to_watchlist(
    watchlist_name: str,
    symbol: str,
) -> WatchlistResponse:
    """Add a stock to a watchlist."""
    try:
        watchlist = _universe.add_stock_to_watchlist(
            watchlist_name=watchlist_name,
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

    return _to_response(watchlist)


@router.delete(
    "/{watchlist_name}/stocks/{symbol}",
    response_model=WatchlistResponse,
)
def remove_stock_from_watchlist(
    watchlist_name: str,
    symbol: str,
) -> WatchlistResponse:
    """Remove a stock from a watchlist."""
    try:
        watchlist = _universe.remove_stock_from_watchlist(
            watchlist_name=watchlist_name,
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

    return _to_response(watchlist)


@router.get(
    "/{watchlist_name}/stocks",
    response_model=list[str],
)
def get_watchlist_stocks(
    watchlist_name: str,
    search: str | None = Query(default=None),
) -> list[str]:
    """Return stocks in a watchlist, optionally filtered by symbol."""
    try:
        symbols = _universe.watchlist_symbols(watchlist_name)
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
