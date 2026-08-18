from __future__ import annotations

from typing import Any

import pandas as pd


def gross_metrics(
    ledger: pd.DataFrame,
    bars: pd.DataFrame,
    *,
    sample_start: pd.Timestamp | None = None,
    sample_end: pd.Timestamp | None = None,
) -> dict[str, Any]:
    """Return gross metrics for the full path or one causal sample window.

    With a sample window, returns use ``[sample_start, sample_end)`` while
    execution events use ``[sample_start, sample_end]`` so an exit at the
    terminal boundary is counted without adding a post-boundary return.
    """
    if (sample_start is None) != (sample_end is None):
        raise ValueError("sample_start and sample_end must be provided together")
    windowed = sample_start is not None
    if windowed and sample_start >= sample_end:
        raise ValueError("sample_start must be before sample_end")
    if windowed:
        sample_start = pd.Timestamp(sample_start)
        sample_end = pd.Timestamp(sample_end)
        if sample_start.tzinfo is None:
            sample_start = sample_start.tz_localize("UTC")
        else:
            sample_start = sample_start.tz_convert("UTC")
        if sample_end.tzinfo is None:
            sample_end = sample_end.tz_localize("UTC")
        else:
            sample_end = sample_end.tz_convert("UTC")

    timestamps = (
        pd.to_datetime(bars["timestamp"], utc=True)
        if "timestamp" in bars
        else pd.Series(dtype="datetime64[ns, UTC]")
    )
    if windowed:
        return_window_mask = (timestamps >= sample_start) & (timestamps < sample_end)
        event_mask = (timestamps >= sample_start) & (timestamps <= sample_end)
    else:
        return_window_mask = pd.Series(True, index=bars.index)
        event_mask = return_window_mask

    if "strategy_return" in bars:
        strategy = bars.loc[return_window_mask, "strategy_return"].dropna()
    else:
        strategy = pd.Series(dtype="float64")
    cumulative = float((1.0 + strategy).prod() - 1.0) if len(strategy) else 0.0
    if len(strategy):
        equity = pd.concat([
            pd.Series([1.0], dtype="float64"),
            (1.0 + strategy).cumprod().reset_index(drop=True),
        ], ignore_index=True)
    else:
        equity = pd.Series([1.0], dtype="float64")
    if len(equity):
        max_drawdown = float((equity / equity.cummax() - 1.0).min())
    else:
        max_drawdown = 0.0

    if "executed_position" in bars and len(bars):
        positions = bars["executed_position"].fillna(0).astype(int)
        previous = positions.shift(1, fill_value=0)
        changes = positions.ne(previous) & event_mask
        turnover = float((positions.loc[event_mask] - previous.loc[event_mask]).abs().sum())
        position_change_events = int(changes.sum())
    else:
        positions = pd.Series(dtype="int64")
        previous = pd.Series(dtype="int64")
        turnover = 0.0
        position_change_events = 0

    if len(ledger):
        entry_timestamps = pd.to_datetime(ledger["entry_timestamp"], utc=True)
        exit_timestamps = pd.to_datetime(ledger["exit_timestamp"], utc=True)
    else:
        entry_timestamps = pd.Series(dtype="datetime64[ns, UTC]")
        exit_timestamps = pd.Series(dtype="datetime64[ns, UTC]")

    if windowed:
        started = (entry_timestamps >= sample_start) & (entry_timestamps <= sample_end)
        active_at_start = (entry_timestamps < sample_start) & (
            exit_timestamps.isna() | (exit_timestamps >= sample_start)
        )
        active_after_end = (entry_timestamps <= sample_end) & (
            exit_timestamps.isna() | (exit_timestamps > sample_end)
        )
        metric_ledger = ledger.loc[started]
        closed = int((started & exit_timestamps.notna() & (exit_timestamps <= sample_end)).sum())
        opened = int((started & (exit_timestamps.isna() | (exit_timestamps > sample_end))).sum())
        carry_in_count = int(active_at_start.sum())
        carry_out_count = int(active_after_end.sum())
    else:
        started = pd.Series(True, index=ledger.index)
        active_at_start = pd.Series(False, index=ledger.index)
        active_after_end = pd.Series(False, index=ledger.index)
        metric_ledger = ledger
        closed = int(ledger["status"].eq("closed").sum()) if len(ledger) else 0
        opened = int(ledger["status"].eq("open").sum()) if len(ledger) else 0
        carry_in_count = 0
        carry_out_count = 0

    if len(metric_ledger):
        metric_entries = pd.to_datetime(metric_ledger["entry_timestamp"], utc=True)
        metric_exits = pd.to_datetime(metric_ledger["exit_timestamp"], utc=True)
        if windowed:
            closed_mask = (
                metric_ledger["status"].eq("closed")
                & metric_exits.notna()
                & (metric_entries >= sample_start)
                & (metric_entries <= sample_end)
                & (metric_exits <= sample_end)
            )
        else:
            closed_mask = metric_ledger["status"].eq("closed")
        closed_episodes = metric_ledger.loc[closed_mask].copy()
    else:
        closed_episodes = metric_ledger.copy()
    interval_holdings: list[int] = []
    calendar_holdings: list[float] = []
    if len(closed_episodes) and "timestamp" in bars:
        timestamp_values = pd.Series(pd.to_datetime(bars["timestamp"], utc=True).tolist())
        for row in closed_episodes.itertuples(index=False):
            entry_timestamp = pd.Timestamp(row.entry_timestamp)
            exit_timestamp = pd.Timestamp(row.exit_timestamp)
            if entry_timestamp.tzinfo is None:
                entry_timestamp = entry_timestamp.tz_localize("UTC")
            else:
                entry_timestamp = entry_timestamp.tz_convert("UTC")
            if exit_timestamp.tzinfo is None:
                exit_timestamp = exit_timestamp.tz_localize("UTC")
            else:
                exit_timestamp = exit_timestamp.tz_convert("UTC")
            if windowed:
                entry_timestamp = max(entry_timestamp, pd.Timestamp(sample_start))
            intervals = ((timestamp_values >= entry_timestamp) & (timestamp_values < exit_timestamp)).sum()
            interval_holdings.append(int(intervals))
            delta = exit_timestamp - entry_timestamp
            if delta >= pd.Timedelta(0):
                calendar_holdings.append(float(delta.total_seconds() / 86400.0))

    reversal_count = int(
        (event_mask & bars["reversal_from_episode_id"].notna()).sum()
    ) if len(bars) and "reversal_from_episode_id" in bars else 0
    reversal_frequency = (
        float(reversal_count / position_change_events)
        if position_change_events else None
    )

    if windowed and len(positions):
        carry_in_position = int(previous.loc[event_mask].iloc[0]) if event_mask.any() else 0
        carry_out_position = int(positions.loc[event_mask].iloc[-1]) if event_mask.any() else 0
    else:
        carry_in_position = 0
        carry_out_position = 0

    return {
        "cumulative_gross_return": cumulative,
        "gross_return": cumulative,
        "trade_count": int(len(metric_ledger)) if windowed else int(len(ledger)),
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
        "carry_in_episode_count": carry_in_count,
        "carry_in_position": carry_in_position,
        "carry_out_episode_count": carry_out_count,
        "carry_out_position": carry_out_position,
    }
