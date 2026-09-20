"""SignalForge FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.health import router as health_router
from src.api.routes.nifty import router as nifty_router
from src.api.routes.paper_trading import (
    router as paper_trading_router,
)
from src.api.routes.sectors import router as sectors_router
from src.api.routes.stocks import router as stocks_router
from src.api.routes.watchlists import router as watchlists_router
from src.api.intelligence.routes import router as intelligence_router


app = FastAPI(
    title="SignalForge API",
    description="Backend API for the SignalForge trading analysis platform.",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health_router)
app.include_router(nifty_router)
app.include_router(stocks_router)
app.include_router(sectors_router)
app.include_router(watchlists_router)
app.include_router(paper_trading_router)
app.include_router(intelligence_router)


@app.get("/")
def root() -> dict[str, str]:
    """Return basic API information."""

    return {
        "service": "SignalForge API",
        "status": "ok",
        "version": "0.1.0",
    }