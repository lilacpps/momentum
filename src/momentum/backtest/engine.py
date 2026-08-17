"""Causal M0 execution, episode ledger, and open-to-next-open accounting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from momentum.data.validation import validate_ohlc
from momentum.metrics.gross import gross_metrics
from momentum.signals.m0 import LOOKBACK_INTERVALS, REQUIRED_CLOSE_OBSERVATIONS, generate_m0_signals


METADATA = {
    "baseline_type": "simplified_daily_tsmom",
    "academic_mop_replication": False,
    "signal_return_type": "spot_price_return",
    "result_level": "gross_price_only",
    "lookback_intervals": LOOKBACK_INTERVALS,
    "required_close_observations": REQUIRED_CLOSE_OBSERVATIONS,
}


@dataclass(frozen=True)
class BacktestResult:
    bars: pd.DataFrame
    ledger: pd.DataFrame
    metrics: dict[str, Any]
    metadata: dict[str, Any]


def _event(old: int, new: int) -> str:
    if old == 0 and new == 1:
        return "enter_long"
    if old == 0 and new == -1:
        return "enter_short"
    if old == 1 and new == 0:
        return "exit_long"
    if old == -1 and new == 0:
        return "exit_short"
    if old == 1 and new == -1:
        return "reverse_long_to_short"
    if old == -1 and new == 1:
        return "reverse_short_to_long"
    return "hold"


def run_m0_backtest(data: pd.DataFrame, metadata: dict[str, Any] | None = None) -> BacktestResult:
    """Run the deterministic single-symbol M0 engine on validated OHLC data."""
    frame = validate_ohlc(data)
    signal, target = generate_m0_signals(frame["close"])
    n = len(frame)
    position = 0
    ledger_rows: list[dict[str, Any]] = []
    active_index: int | None = None
    bar_rows: list[dict[str, Any]] = []
    cumulative = 0.0

    for t in range(n):
        target_position = int(target.iloc[t])
        old_position = position
        execution_event = _event(old_position, target_position)
        entry_timestamp = entry_price = exit_timestamp = exit_price = None
        reversal_from = None

        if target_position != position:
            if position != 0:
                assert active_index is not None
                ledger_rows[active_index]["exit_timestamp"] = frame.at[t, "timestamp"]
                ledger_rows[active_index]["exit_price"] = float(frame.at[t, "open"])
                ledger_rows[active_index]["status"] = "closed"
                exit_timestamp = frame.at[t, "timestamp"]
                exit_price = float(frame.at[t, "open"])
                if target_position != 0:
                    reversal_from = ledger_rows[active_index]["episode_id"]
                active_index = None
            if target_position != 0:
                episode_id = len(ledger_rows)
                ledger_rows.append({
                    "episode_id": episode_id,
                    "entry_timestamp": frame.at[t, "timestamp"],
                    "entry_price": float(frame.at[t, "open"]),
                    "direction": target_position,
                    "exit_timestamp": None,
                    "exit_price": None,
                    "status": "open",
                    "reversal_from_episode_id": reversal_from,
                })
                active_index = episode_id
                entry_timestamp = frame.at[t, "timestamp"]
                entry_price = float(frame.at[t, "open"])
            position = target_position

        asset_return = strategy_return = np.nan
        if t < n - 1:
            asset_return = float(frame.at[t + 1, "open"] / frame.at[t, "open"] - 1.0)
            strategy_return = float(position * asset_return)
            cumulative = (1.0 + cumulative) * (1.0 + strategy_return) - 1.0

        bar_rows.append({
            "timestamp": frame.at[t, "timestamp"],
            "signal": signal.iloc[t],
            "target_position": target_position,
            "executed_position": position,
            "execution_event": execution_event,
            "entry_timestamp": entry_timestamp,
            "entry_price": entry_price,
            "exit_timestamp": exit_timestamp,
            "exit_price": exit_price,
            "reversal_from_episode_id": reversal_from,
            "asset_return": asset_return,
            "strategy_return": strategy_return,
            "cumulative_gross_return": cumulative,
        })

    bars = pd.DataFrame(bar_rows)
    if not len(bars):
        bars = pd.DataFrame(columns=[
            "timestamp", "signal", "target_position", "executed_position",
            "execution_event", "entry_timestamp", "entry_price", "exit_timestamp",
            "exit_price", "reversal_from_episode_id", "asset_return",
            "strategy_return", "cumulative_gross_return",
        ])
    ledger = pd.DataFrame(ledger_rows, columns=[
        "episode_id", "entry_timestamp", "entry_price", "direction",
        "exit_timestamp", "exit_price", "status", "reversal_from_episode_id",
    ])
    result_metadata = dict(metadata or {})
    # M0 identity and accounting level are reserved: callers may add context,
    # but cannot relabel a result as another research specification.
    result_metadata.update(METADATA)
    return BacktestResult(bars=bars, ledger=ledger, metrics=gross_metrics(ledger, bars), metadata=result_metadata)
