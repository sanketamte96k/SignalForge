"""Health-check API routes."""

from fastapi import APIRouter

from src.api.models import HealthResponse


router = APIRouter(
    prefix="/api",
    tags=["health"],
)


@router.get(
    "/health",
    response_model=HealthResponse,
)
def health_check() -> HealthResponse:
    """Return the current API health status."""

    return HealthResponse(
        status="ok",
        service="SignalForge API",
    )
