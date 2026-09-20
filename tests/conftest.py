"""Shared pytest fixtures for SignalForge tests."""

import pytest

from src.api.routes import stocks
from src.universe.manager import UniverseManager


@pytest.fixture(autouse=True)
def reset_stock_api_universe():
    """
    Give every test a clean stock API universe.

    API tests may intentionally add instruments or change validation
    status. Those mutations must not leak into other tests.
    """
    original_universe = stocks._universe
    stocks._universe = UniverseManager()

    try:
        yield
    finally:
        stocks._universe = original_universe
