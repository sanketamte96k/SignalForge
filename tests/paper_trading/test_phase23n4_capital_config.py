import pytest
import tempfile
import json
from pathlib import Path
from src.paper_trading.interactive_engine import InteractivePaperTradingService

def test_explicit_capital_configuration():
    # Test that a new service correctly uses explicit starting capital
    temp_file = Path(tempfile.mktemp(suffix=".json"))
    
    # Init with explicit 100k
    service = InteractivePaperTradingService(persistence_file=temp_file, starting_capital=100000.0)
    service._save_to_disk() # Manually save state so we can read the file
    
    assert service.starting_capital == 100000.0
    
    state = service.get_account_state()
    assert state["starting_capital"] == 100000.0
    
    # Assert JSON was created with 100k
    data = json.loads(temp_file.read_text())
    assert data["starting_capital"] == 100000.0
    
def test_persistence_reload_protects_capital():
    # Test that reloading an existing ledger preserves its historical capital,
    # ignoring constructor arguments that would silently rewrite history.
    temp_file = Path(tempfile.mktemp(suffix=".json"))
    
    # Step 1: Create a 1M account
    service1 = InteractivePaperTradingService(persistence_file=temp_file, starting_capital=1000000.0)
    service1._save_to_disk() # Force save so service2 can load it
    assert service1.starting_capital == 1000000.0
    
    # Step 2: Attempt to reload with 100k
    service2 = InteractivePaperTradingService(persistence_file=temp_file, starting_capital=100000.0)
    
    # The loaded capital should supersede the constructor to protect history
    assert service2.starting_capital == 1000000.0

    
def test_prevention_of_accidental_resets():
    temp_file = Path(tempfile.mktemp(suffix=".json"))
    service1 = InteractivePaperTradingService(persistence_file=temp_file, starting_capital=100000.0)
    
    # Try to reset the account. Reset should clear trades and optionally change capital,
    # but without explicit arguments, it should preserve the current 100k, not revert to 1M default.
    service1.reset()
    assert service1.starting_capital == 100000.0 # Remains 100k
