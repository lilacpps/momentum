"""Pure M0 return-sign signal generation."""

from __future__ import annotations

import numpy as np
import pandas as pd

LOOKBACK_INTERVALS = 240
REQUIRED_CLOSE_OBSERVATIONS = LOOKBACK_INTERVALS + 1


def generate_m0_signals(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Return (signal, target_position) indexed by execution-bar position."""
    signal = pd.Series(np.nan, index=close.index, dtype="float64", name="signal")
    for t in range(LOOKBACK_INTERVALS + 1, len(close)):
        past_return = float(close.iloc[t - 1] / close.iloc[t - 1 - LOOKBACK_INTERVALS] - 1.0)
        signal.iloc[t] = float(np.sign(past_return))
    target = signal.fillna(0.0).astype("int8").rename("target_position")
    return signal, target
