import pytest
import pandas as pd
from src.data.validator import validate_market_data

def test_schema_validation():
    df = pd.DataFrame({'open': [1], 'high': [1], 'low': [1], 'close': [1], 'volume': [1]})
    df['timestamp'] = pd.to_datetime(['2024-01-01 09:15:00'])
    df.set_index('timestamp', inplace=True)
    validate_market_data(df)
