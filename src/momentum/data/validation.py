"""Validation for the M0 single-symbol daily OHLC contract."""

from __future__ import annotations

import pandas as pd
import numpy as np

REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close")


class OHLCValidationError(ValueError):
    """Raised when input violates the M0 OHLC contract."""


def validate_ohlc(data: pd.DataFrame) -> pd.DataFrame:
    """Validate and copy OHLC data without sorting or filling missing values.

    A short but otherwise valid dataset is accepted; signal warm-up is handled
    by the signal layer, not treated as malformed input.
    """
    if not isinstance(data, pd.DataFrame):
        raise OHLCValidationError("data must be a pandas DataFrame")
    missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing:
        raise OHLCValidationError(f"missing required columns: {missing}")

    frame = data.loc[:, REQUIRED_COLUMNS].copy().reset_index(drop=True)
    if not pd.api.types.is_datetime64_any_dtype(frame["timestamp"]):
        raise OHLCValidationError("timestamp must have a datetime dtype")
    if frame["timestamp"].isna().any():
        raise OHLCValidationError("timestamp contains missing values")
    if frame["timestamp"].duplicated().any():
        raise OHLCValidationError("duplicate timestamp")
    if not frame["timestamp"].is_monotonic_increasing:
        raise OHLCValidationError("timestamp must be ascending")

    for column in ("open", "high", "low", "close"):
        if not pd.api.types.is_numeric_dtype(frame[column]):
            raise OHLCValidationError(f"{column} must be numeric")
        try:
            values = frame[column].to_numpy(dtype="float64", na_value=float("nan"))
        except (TypeError, ValueError) as exc:
            raise OHLCValidationError(f"{column} contains invalid values") from exc
        if np.isnan(values).any():
            raise OHLCValidationError(f"{column} contains NaN")
        if not np.isfinite(values).all():
            raise OHLCValidationError(f"{column} contains non-finite values")
        if (frame[column] <= 0).any():
            raise OHLCValidationError(f"{column} must be positive")
    return frame
