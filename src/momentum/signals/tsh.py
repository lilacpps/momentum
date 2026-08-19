"""Causal Time-Series History (TSH) signal construction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from momentum.data.validation import validate_ohlc
from momentum.research.track_b_config import TrackBConfig


TSH_SPEC_VERSION = "tsh-huang-v1"


class TSHSignalError(ValueError):
    """Raised when the frozen TSH monthly contract cannot be satisfied."""

    def __init__(
        self,
        message: str,
        *,
        symbol: str | None = None,
        missing_months: tuple[str, ...] = (),
        analysis_start: pd.Period | None = None,
        analysis_end: pd.Period | None = None,
    ) -> None:
        self.symbol = symbol
        self.missing_months = tuple(str(month) for month in missing_months)
        self.analysis_start = None if analysis_start is None else str(analysis_start)
        self.analysis_end = None if analysis_end is None else str(analysis_end)
        super().__init__(message)

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "missing_calendar_months": list(self.missing_months),
            "requested_analysis_start": self.analysis_start,
            "requested_analysis_end": self.analysis_end,
        }


@dataclass(frozen=True)
class TSHSignalResult:
    signal: pd.Series
    target_position: pd.Series
    rebalance: pd.Series
    decision_table: pd.DataFrame
    monthly_history: pd.DataFrame


def _period(value: str | pd.Period) -> pd.Period:
    return value if isinstance(value, pd.Period) else pd.Period(str(value), freq="M")


def _calendar_months(frame: pd.DataFrame) -> pd.Series:
    timestamp = frame["timestamp"]
    if timestamp.dt.tz is not None:
        timestamp = timestamp.dt.tz_convert("UTC").dt.tz_localize(None)
    return timestamp.dt.to_period("M")


def _first_timestamp_by_month(frame: pd.DataFrame, months: pd.Series) -> dict[pd.Period, pd.Timestamp]:
    result: dict[pd.Period, pd.Timestamp] = {}
    timestamps = pd.to_datetime(frame["timestamp"], utc=True)
    for index, month in months.items():
        result.setdefault(month, pd.Timestamp(timestamps.iloc[index]))
    return result


def generate_tsh_signals(
    data: pd.DataFrame,
    config: TrackBConfig,
    *,
    analysis_start: str | pd.Period | None = None,
    analysis_end: str | pd.Period | None = None,
) -> TSHSignalResult:
    """Generate causal TSH targets for one symbol's daily OHLC frame.

    ``analysis_start`` and ``analysis_end`` are holding-month bounds.  Signal
    state is built from the first valid monthly return through ``analysis_end``
    so warmup positions remain continuous into the evaluation window.
    """
    symbols = (
        data["symbol"].dropna().astype(str).unique().tolist()
        if "symbol" in data.columns
        else []
    )
    if len(symbols) > 1:
        raise TSHSignalError(
            "TSH is single-symbol per run; multi-symbol input is not allowed"
        )
    symbol = symbols[0] if symbols else None
    frame = validate_ohlc(data)
    if frame.empty:
        raise TSHSignalError("TSH input must not be empty", symbol=symbol)

    start = _period(analysis_start or config.development.start)
    end = _period(analysis_end or config.validation.end)
    if start > end:
        raise TSHSignalError("analysis_start must not be after analysis_end")
    boundary = end + 1

    months = _calendar_months(frame)
    month_indexes: dict[pd.Period, list[int]] = {}
    for index, month in months.items():
        month_indexes.setdefault(month, []).append(index)

    required = pd.period_range(start, boundary, freq="M")
    missing = [month for month in required if month not in month_indexes]
    if missing:
        raise TSHSignalError(
            "missing requested calendar month(s): " + ", ".join(map(str, missing)),
            symbol=symbol,
            missing_months=tuple(str(month) for month in missing),
            analysis_start=start,
            analysis_end=end,
        )

    month_end_close = {
        month: float(frame.iloc[indexes[-1]]["close"])
        for month, indexes in month_indexes.items()
    }
    first_timestamp = _first_timestamp_by_month(frame, months)
    timestamps = pd.to_datetime(frame["timestamp"], utc=True)

    monthly_rows: list[dict[str, object]] = []
    cumulative_sum = 0.0
    valid_return_count = 0
    max_formation_month = end - 1
    for formation_month in sorted(month_end_close):
        if formation_month > max_formation_month:
            continue
        previous_month = formation_month - 1
        monthly_return = np.nan
        if previous_month in month_end_close:
            monthly_return = month_end_close[formation_month] / month_end_close[previous_month] - 1.0
            cumulative_sum += float(monthly_return)
            valid_return_count += 1
        if not np.isfinite(monthly_return):
            continue

        historical_mean = cumulative_sum / valid_return_count
        tsh_signal = 1.0 if historical_mean >= 0.0 else -1.0
        holding_month = formation_month + 1
        if holding_month not in first_timestamp:
            if holding_month >= start:
                raise TSHSignalError(
                    f"missing holding month {holding_month} for TSH formation {formation_month}",
                    symbol=symbol,
                    missing_months=(str(holding_month),),
                    analysis_start=start,
                    analysis_end=end,
                )
            continue
        exit_timestamp = first_timestamp.get(holding_month + 1)
        monthly_rows.append({
            "symbol": symbol,
            "formation_month": formation_month,
            "month_end_close": month_end_close[formation_month],
            "monthly_return": float(monthly_return),
            "historical_mean": float(historical_mean),
            "tsh_signal": tsh_signal,
            "holding_month": holding_month,
            "entry_timestamp": first_timestamp[holding_month],
            "exit_timestamp": exit_timestamp,
            "split": config.split_for_holding_month(holding_month),
        })

    history_columns = [
        "symbol", "formation_month", "month_end_close", "monthly_return",
        "historical_mean", "tsh_signal", "holding_month", "entry_timestamp",
        "exit_timestamp", "split",
    ]
    monthly_history = pd.DataFrame(monthly_rows, columns=history_columns)

    signal = pd.Series(np.nan, index=frame.index, dtype="float64", name="signal")
    target = pd.Series(0, index=frame.index, dtype="int8", name="target_position")
    rebalance = pd.Series(False, index=frame.index, dtype=bool, name="rebalance")
    for row in monthly_rows:
        holding_month = row["holding_month"]
        indexes = [index for index, month in months.items() if month == holding_month]
        if not indexes:
            continue
        first_index = indexes[0]
        signal.iloc[first_index] = float(row["tsh_signal"])
        target.iloc[indexes] = int(row["tsh_signal"])
        rebalance.iloc[first_index] = True

    return TSHSignalResult(
        signal=signal,
        target_position=target,
        rebalance=rebalance,
        decision_table=monthly_history.copy(),
        monthly_history=monthly_history,
    )


__all__ = ["TSH_SPEC_VERSION", "TSHSignalError", "TSHSignalResult", "generate_tsh_signals"]
