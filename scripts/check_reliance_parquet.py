import pandas as pd

df = pd.read_parquet('RELIANCE_test.parquet')
print('RELIANCE_test.parquet summary:')
print('Shape:', df.shape)
print('Columns:', list(df.columns))
print('Index type:', type(df.index))
print('Min timestamp:', df.index.min() if hasattr(df.index, 'min') else df['date'].min())
print('Max timestamp:', df.index.max() if hasattr(df.index, 'max') else df['date'].max())
print('Sample head:\n', df.head(3))
