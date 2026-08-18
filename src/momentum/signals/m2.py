"""M2 monthly formation with daily target-position output."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from momentum.data.validation import validate_ohlc
from momentum.research.track_b_config import TrackBConfig


M2_SPEC_VERSION = "m2-practical-v1"


class M2SignalError(ValueError):
    """Raised when the M2 calendar-month contract cannot be satisfied."""


@dataclass(frozen=True)
class M2SignalResult:
    """Daily target positions and flags plus the rebalance-level decision table."""

    signal: pd.Series
    target_position: pd.Series
    rebalance: pd.Series
    decision_table: pd.DataFrame


def _calendar_months(frame: pd.DataFrame) -> pd.Series:
    timestamp = frame["timestamp"]
    if timestamp.dt.tz is not None:
        timestamp = timestamp.dt.tz_convert("UTC").dt.tz_localize(None)
    return timestamp.dt.to_period("M")


def _period(value: str | pd.Period) -> pd.Period:
    return value if isinstance(value, pd.Period) else pd.Period(str(value), freq="M")


def generate_m2_signals(
    data: pd.DataFrame,
    config: TrackBConfig,
    *,
    analysis_start: str | pd.Period | None = None,
    analysis_end: str | pd.Period | None = None,
) -> M2SignalResult:
    """Generate M2 targets while preserving the daily accounting interval.

    The returned target is zero outside the requested holding months.  The
    month immediately after ``analysis_end`` is required only as an exit
    boundary and never receives an M2 position.
    """
    frame = validate_ohlc(data)
    if "symbol" in data.columns and data["symbol"].dropna().astype(str).nunique() > 1:
        raise M2SignalError("M2 is single-symbol per run; portfolio pooling is not allowed")

    start = _period(analysis_start or config.development.start)
    end = _period(analysis_end or config.validation.end)
    if start > end:
        raise M2SignalError("analysis_start must not be after analysis_end")
    boundary = end + 1

    months = _calendar_months(frame)
    month_rows: dict[pd.Period, list[int]] = {}
    for index, month in months.items():
        month_rows.setdefault(month, []).append(index)
    # Analysis months must be complete.  Pre-sample history is different: a
    # missing history month makes only the affected signal undefined/Flat.
    required = pd.period_range(start, boundary, freq="M")
    missing = [month for month in required if month not in month_rows]
    if missing:
        raise M2SignalError(
            "missing requested calendar month(s): " + ", ".join(map(str, missing))
        )

    month_end_close = {
        month: float(frame.iloc[indexes[-1]]["close"])
        for month, indexes in month_rows.items()
    }
    signal = pd.Series(np.nan, index=frame.index, dtype="float64", name="signal")
    target = pd.Series(0, index=frame.index, dtype="int8", name="target_position")
    rebalance = pd.Series(False, index=frame.index, dtype=bool, name="rebalance")
    rows: list[dict[str, object]] = []

    first_formable_holding_month = config.warmup_data_start + 13
    for holding_month in pd.period_range(first_formable_holding_month, end, freq="M"):
        if holding_month not in month_rows:
            # A missing pre-sample holding month leaves no target row to
            # construct.  Requested analysis months are checked above.
            continue
        formation_month = holding_month - 1
        past_month = formation_month - 12
        if formation_month in month_end_close and past_month in month_end_close:
            past_return = month_end_close[formation_month] / month_end_close[past_month] - 1.0
            direction = int(np.sign(past_return))
            signal_value = float(direction)
        else:
            past_return = float("nan")
            direction = 0
            signal_value = float("nan")
        first_index = month_rows[holding_month][0]
        target.loc[month_rows[holding_month]] = direction
        signal.iloc[first_index] = signal_value
        rebalance.iloc[first_index] = True
        rows.append({
            "formation_month": formation_month,
            "holding_month": holding_month,
            "signal": signal_value,
            "past_12m_return": float(past_return),
            "split": config.split_for_holding_month(holding_month),
            "entry_timestamp": frame.iloc[first_index]["timestamp"],
        })

    return M2SignalResult(
        signal=signal,
        target_position=target,
        rebalance=rebalance,
        decision_table=pd.DataFrame(rows),
    )


__all__ = ["M2_SPEC_VERSION", "M2SignalError", "M2SignalResult", "generate_m2_signals"]
