from datetime import datetime
from pathlib import Path
import tempfile

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from src.api.models import (
    StockAddRequest,
    StockDataReadinessResponse,
    StockImportResponse,
    StockResponse,
    StockScannerItem,
    StockScannerResponse,
    StockSearchResponse,
    StockValidationResponse,
)
from src.data.stock_importer import StockDataImporter
from src.data.stock_provider import StockDataProvider
from src.scanner.engine import StockScannerEngine
from src.universe.manager import UniverseManager
from src.validation.stock_service import StockValidationService
from src.validation.stock_validator import StockValidationRunner


router = APIRouter(
    prefix="/api/stocks",
    tags=["stocks"],
)

_universe = UniverseManager()

DEVELOPMENT_START = "2015-01-01"
DEVELOPMENT_END = "2021-12-31 23:59:59"
OOS_START = "2022-01-01"
OOS_END = "2024-03-26 23:59:59"


def _build_validation_service() -> StockValidationService:
    """
    Build the stock validation service using the frozen validation windows.

    The validation pipeline itself remains owned by StockValidationRunner.
    """
    return StockValidationService(
        provider=StockDataProvider(),
        runner=StockValidationRunner(
            development_start=DEVELOPMENT_START,
            development_end=DEVELOPMENT_END,
            oos_start=OOS_START,
            oos_end=OOS_END,
        ),
        universe=_universe,
    )


def _to_stock_response(instrument) -> StockResponse:
    """Convert a universe instrument to an API response."""
    return StockResponse(
        symbol=instrument.symbol,
        name=instrument.name,
        exchange=instrument.exchange,
        instrument_type=instrument.instrument_type,
        validation_status=instrument.validation_status.value,
        signal_eligible=_universe.is_signal_eligible(
            instrument.symbol
        ),
    )


def _to_validation_response(result) -> StockValidationResponse:
    """Convert a validation result to an API response."""
    approval = result.approval

    return StockValidationResponse(
        symbol=result.symbol,
        status=result.status.value,
        signal_eligible=result.signal_eligible,
        approved=result.approved,
        passed_gates=list(approval.passed_gates),
        failed_gates=list(approval.failed_gates),
        issues=list(approval.issues),
    )


def _to_readiness_response(result) -> StockDataReadinessResponse:
    """Convert a readiness result to an API response."""
    return StockDataReadinessResponse(
        symbol=result.symbol,
        available=result.available,
        ready=result.ready,
        missing=result.missing,
        path=result.path,
        total_rows=result.total_rows,
        first_timestamp=result.first_timestamp,
        last_timestamp=result.last_timestamp,
        required_start=result.required_start,
        required_end=result.required_end,
        covers_required_period=result.covers_required_period,
        issues=list(result.issues),
    )


def _load_signal_eligible_data() -> dict:
    """
    Load real local market data for signal-eligible stocks only.

    Missing local data is intentionally skipped. The scanner engine
    converts missing data into a safe NO_TRADE result and never receives
    synthetic market data.
    """
    provider = StockDataProvider()
    data_by_symbol = {}

    for instrument in _universe.all_instruments():
        if not _universe.is_signal_eligible(
            instrument.symbol
        ):
            continue

        try:
            data_by_symbol[instrument.symbol] = provider.load(
                instrument.symbol
            )
        except FileNotFoundError:
            continue

    return data_by_symbol


@router.get(
    "/search",
    response_model=StockSearchResponse,
)
def search_stocks(
    q: str = Query(..., min_length=1),
) -> StockSearchResponse:
    """Search stocks in the configured universe."""
    try:
        matches = _universe.search_instruments(q)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return StockSearchResponse(
        results=[
            _to_stock_response(instrument)
            for instrument in matches
        ]
    )


@router.post(
    "",
    response_model=StockResponse,
    status_code=201,
)
def add_stock(
    request: StockAddRequest,
) -> StockResponse:
    """Add a stock to the SignalForge universe."""
    try:
        instrument = _universe.add_instrument(
            symbol=request.symbol,
            name=request.name,
            exchange=request.exchange,
            instrument_type=request.instrument_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return _to_stock_response(instrument)


@router.get(
    "/scanner",
    response_model=StockScannerResponse,
)
def scan_stocks() -> StockScannerResponse:
    """
    Scan all configured stocks using real local market data.

    Only VALIDATED stocks are eligible for signal generation.
    Unvalidated stocks are returned as NO_TRADE by the scanner engine.
    """
    universe = _universe
    engine = StockScannerEngine(universe)

    data_by_symbol = _load_signal_eligible_data()
    results = engine.scan(data_by_symbol)

    items = [
        StockScannerItem(
            symbol=result.symbol,
            name=result.name,
            exchange=result.exchange,
            validation_status=universe.get_validation_status(
                result.symbol
            ).value,
            signal_eligible=result.signal_eligible,
            signal=result.signal,
            position=result.position,
            timestamp=result.timestamp,
            price=result.price,
            score=(
                result.signal_result.score
                if result.signal_result is not None
                else None
            ),
            confidence=(
                result.signal_result.confidence
                if result.signal_result is not None
                else None
            ),
            timeframe_alignment=(
                result.signal_result.timeframe_alignment
                if result.signal_result is not None
                else None
            ),
            reason=result.reason,
        )
        for result in results
    ]

    buy_count = sum(
        1
        for result in results
        if result.signal == "BUY"
    )

    sell_count = sum(
        1
        for result in results
        if result.signal == "SELL"
    )

    no_trade_count = sum(
        1
        for result in results
        if result.signal == "NO_TRADE"
    )

    eligible_count = sum(
        1
        for result in results
        if result.signal_eligible
    )

    timestamps = [
        result.timestamp
        for result in results
        if result.timestamp is not None
    ]

    latest_timestamp = (
        max(timestamps)
        if timestamps
        else datetime.now()
    )

    return StockScannerResponse(
        timestamp=latest_timestamp,
        universe="NIFTY 50",
        total_stocks=len(results),
        signal_eligible_stocks=eligible_count,
        buy_count=buy_count,
        sell_count=sell_count,
        no_trade_count=no_trade_count,
        items=items,
    )


@router.get(
    "/{symbol}",
    response_model=StockResponse,
)
def get_stock(
    symbol: str,
) -> StockResponse:
    """Return one stock from the universe."""
    try:
        instrument = _universe.get_instrument(symbol)
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return _to_stock_response(instrument)


@router.get(
    "/{symbol}/readiness",
    response_model=StockDataReadinessResponse,
)
def get_stock_readiness(
    symbol: str,
) -> StockDataReadinessResponse:
    """Return historical-data readiness for one stock."""
    try:
        result = _build_validation_service().check_data_readiness(
            symbol
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return _to_readiness_response(result)


@router.post(
    "/{symbol}/import",
    response_model=StockImportResponse,
)
async def import_stock_data(
    symbol: str,
    file: UploadFile = File(...),
) -> StockImportResponse:
    """
    Import historical CSV market data for an existing stock.

    Importing data does not validate or approve the stock. Validation
    remains a separate explicit operation.
    """
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must have a filename.",
        )

    filename = file.filename.strip()

    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported.",
        )

    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="Uploaded CSV file is empty.",
        )

    temporary_path: Path | None = None

    try:
        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError(
                "symbol must not be empty."
            )

        if not _universe.contains(
            normalized_symbol
        ):
            raise KeyError(
                f"Unknown stock symbol: {normalized_symbol}"
            )

        with tempfile.NamedTemporaryFile(
            suffix=".csv",
            delete=False,
        ) as temporary_file:
            temporary_file.write(contents)
            temporary_path = Path(
                temporary_file.name
            )

        importer = StockDataImporter(
            StockDataProvider()
        )

        imported = importer.import_csv(
            normalized_symbol,
            temporary_path,
        )

        readiness = (
            _build_validation_service()
            .check_data_readiness(
                normalized_symbol
            )
        )

        provider = StockDataProvider()

        return StockImportResponse(
            symbol=normalized_symbol,
            filename=filename,
            imported=True,
            total_rows=len(imported),
            path=str(
                provider.local_path(
                    normalized_symbol
                )
            ),
            readiness=_to_readiness_response(
                readiness
            ),
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    finally:
        if temporary_path is not None:
            temporary_path.unlink(
                missing_ok=True
            )


@router.post(
    "/{symbol}/validate",
    response_model=StockValidationResponse,
)
def validate_stock(
    symbol: str,
) -> StockValidationResponse:
    """Run the complete stock validation pipeline."""
    try:
        result = (
            _build_validation_service()
            .validate_from_local_and_update_universe(
                symbol
            )
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return _to_validation_response(
        result
    )


@router.get(
    "/{symbol}/validation",
    response_model=StockValidationResponse,
)
def get_validation_status(
    symbol: str,
) -> StockValidationResponse:
    """Return the current validation status."""
    try:
        instrument = _universe.get_instrument(
            symbol
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    status = _universe.get_validation_status(
        instrument.symbol
    )

    return StockValidationResponse(
        symbol=instrument.symbol,
        status=status.value,
        signal_eligible=_universe.is_signal_eligible(
            instrument.symbol
        ),
        approved=(status.value == "VALIDATED"),
        passed_gates=[],
        failed_gates=[],
        issues=[],
    )
