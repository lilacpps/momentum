import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def synthetic_ohlc():
    """Hand-controlled synthetic series; no historical data is used."""
    n = 252
    close = np.full(n, 100.0)
    # t=241 onward targets: +, -, 0, +, +, 0, -, +, 0, -, -.
    requested = [1, -1, 0, 1, 1, 0, -1, 1, 0, -1, -1]
    for t, direction in enumerate(requested, start=241):
        close[t - 1] = 100.0 + direction
    open_ = np.arange(1.0, n + 1.0)
    return pd.DataFrame({
        "timestamp": pd.date_range("2020-01-01", periods=n, freq="D"),
        "open": open_,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
    })
