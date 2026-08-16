from __future__ import annotations

from typing import Any

import pandas as pd


def gross_metrics(ledger: pd.DataFrame, bars: pd.DataFrame) -> dict[str, Any]:
    """Return only M0 gross accounting summaries."""
    strategy = bars["strategy_return"].dropna() if "strategy_return" in bars else pd.Series(dtype="float64")
    cumulative = float(bars["cumulative_gross_return"].iloc[-1]) if len(bars) else 0.0
    closed = int(ledger["status"].eq("closed").sum()) if len(ledger) else 0
    opened = int(ledger["status"].eq("open").sum()) if len(ledger) else 0
    return {
        "cumulative_gross_return": cumulative,
        "trade_count": int(len(ledger)),
        "closed_trade_count": closed,
        "open_trade_count": opened,
        "return_count": int(len(strategy)),
        "mean_strategy_return": float(strategy.mean()) if len(strategy) else float("nan"),
        "sum_strategy_return": float(strategy.sum()) if len(strategy) else 0.0,
    }
