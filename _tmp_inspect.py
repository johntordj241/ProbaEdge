import pandas as pd
from pathlib import Path
path = Path('data/prediction_history.csv')
print('exists?', path.exists())
if not path.exists():
    raise SystemExit('prediction_history missing')
df = pd.read_csv(path)
print('rows', len(df))
print('cols', len(df.columns))
print(df.columns.tolist())
print(df.head(3))
