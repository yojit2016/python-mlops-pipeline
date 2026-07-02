"""
Generates a deterministic, realistic-looking 10,000-row OHLCV sample dataset
(1-minute BTC-style bars) for local testing of run.py.

This is ONLY a sample/dev dataset so the pipeline can be exercised end-to-end.
The actual assessment will supply its own data.csv with the same schema:
timestamp,open,high,low,close,volume_btc,volume_usd
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

SEED = 42
N_ROWS = 10_000
START_PRICE = 45024.68
START_TS = datetime(2024, 1, 1, 0, 0, 0)

rng = np.random.default_rng(SEED)

timestamps = [START_TS + timedelta(minutes=i) for i in range(N_ROWS)]

# Random-walk close prices (deterministic given seed)
returns = rng.normal(loc=0.0, scale=0.0015, size=N_ROWS)
close = START_PRICE * np.cumprod(1 + returns)

open_ = np.empty(N_ROWS)
open_[0] = START_PRICE
open_[1:] = close[:-1]

high = np.maximum(open_, close) * (1 + rng.uniform(0.0, 0.003, size=N_ROWS))
low = np.minimum(open_, close) * (1 - rng.uniform(0.0, 0.003, size=N_ROWS))

volume_btc = rng.lognormal(mean=1.5, sigma=1.3, size=N_ROWS)
volume_usd = volume_btc * close

df = pd.DataFrame({
    "timestamp": [t.strftime("%Y-%m-%d %H:%M:%S") for t in timestamps],
    "open": np.round(open_, 2),
    "high": np.round(high, 2),
    "low": np.round(low, 2),
    "close": np.round(close, 2),
    "volume_btc": np.round(volume_btc, 6),
    "volume_usd": np.round(volume_usd, 2),
})

df.to_csv("data.csv", index=False)
print(f"Wrote {len(df)} rows to data.csv")
