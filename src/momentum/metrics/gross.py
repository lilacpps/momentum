from __future__ import annotations

from typing import Any

import pandas as pd


def gross_metrics(
    ledger: pd.DataFrame,
    bars: pd.DataFrame,
    *,
    return_mask: pd.Series | None = None,
) -> dict[str, Any]:
    """Return gross metrics shared by M0 and M2 daily accounting.

    ``bars`` must contain daily Open-to-Open strategy returns and the executed
    position.  Drawdown is intentionally calculated at daily frequency so a
    monthly signal does not change the comparison frequency.
    """
    if "strategy_return" in bars:
        strategy_source = bars["strategy_return"]
        if return_mask is not None:
            strategy_source = strategy_source.loc[return_mask]
        strategy = strategy_source.dropna()
    else:
        strategy = pd.Series(dtype="float64")
    cumulative = float((1.0 + strategy).prod() - 1.0) if len(strategy) else 0.0
    closed = int(ledger["status"].eq("closed").sum()) if len(ledger) else 0
    opened = int(ledger["status"].eq("open").sum()) if len(ledger) else 0
    equity = (1.0 + strategy).cumprod() if len(strategy) else pd.Series(dtype="float64")
    if len(equity):
        max_drawdown = float((equity / equity.cummax() - 1.0).min())
    else:
        max_drawdown = 0.0

    if "executed_position" in bars and len(bars):
        positions = bars["executed_position"].fillna(0).astype(int)
        previous = positions.shift(1, fill_value=0)
        changes = positions.ne(previous)
        turnover = float((positions - previous).abs().sum())
        position_change_events = int(changes.sum())
    else:
        turnover = 0.0
        position_change_events = 0

    closed_episodes = ledger.loc[ledger["status"].eq("closed")].copy() if len(ledger) else ledger.copy()
    interval_holdings: list[int] = []
    calendar_holdings: list[float] = []
    if len(closed_episodes) and "timestamp" in bars:
        timestamps = pd.Series(bars["timestamp"].tolist())
        for row in closed_episodes.itertuples(index=False):
            entry = timestamps[timestamps == row.entry_timestamp]
            exit_ = timestamps[timestamps == row.exit_timestamp]
            if len(entry) and len(exit_):
                entry_index = int(entry.index[0])
                exit_index = int(exit_.index[0])
                interval_holdings.append(max(0, exit_index - entry_index))
                delta = row.exit_timestamp - row.entry_timestamp
                calendar_holdings.append(float(delta.total_seconds() / 86400.0))

    reversal_count = int(
        ledger["reversal_from_episode_id"].notna().sum()
    ) if len(ledger) and "reversal_from_episode_id" in ledger else 0
    reversal_frequency = (
        float(reversal_count / position_change_events)
        if position_change_events else None
    )

    return {
        "cumulative_gross_return": cumulative,
        "gross_return": cumulative,
        "trade_count": int(len(ledger)),
        "closed_trade_count": closed,
        "open_trade_count": opened,
        "return_count": int(len(strategy)),
        "mean_strategy_return": float(strategy.mean()) if len(strategy) else float("nan"),
        "sum_strategy_return": float(strategy.sum()) if len(strategy) else 0.0,
        "max_drawdown": max_drawdown,
        "turnover": turnover,
        "average_holding": float(sum(interval_holdings) / len(interval_holdings)) if interval_holdings else None,
        "average_holding_intervals": float(sum(interval_holdings) / len(interval_holdings)) if interval_holdings else None,
        "average_holding_calendar_days": float(sum(calendar_holdings) / len(calendar_holdings)) if calendar_holdings else None,
        "reversal_count": reversal_count,
        "reversal_frequency": reversal_frequency,
    }
