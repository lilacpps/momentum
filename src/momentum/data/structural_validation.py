"""Track B v2 validation for prepared Exness Daily OHLC.

The prepared Daily file is the research input authority. This module only
loads that file, applies minimal fail-fast structural checks, filters the
requested UTC calendar-month range, and binds the resulting dataset to the
existing v1 SHA-256 fingerprint. It does not aggregate 1m data, inspect raw
ticks, repair malformed rows, or run M1A.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from momentum.data.track_b import (
    REQUIRED_LONG_DAILY_COLUMNS,
    TrackBDailyValidationError,
    compute_track_b_daily_fingerprint,
    validate_track_b_daily,
)
from momentum.research.track_b_config import (
    SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
    SUPPORTED_STRUCTURAL_SPEC_VERSION,
    StructuralValidationSummary,
    TrackBConfig,
    load_track_b_config,
)

DEFAULT_DATA_ROOT = Path("data/processed")
PREPARED_DAILY_FILENAME = "{symbol}_1d.csv"
PREPARED_DAILY_COLUMNS = ("timestamp", "open", "high", "low", "close")
DIAGNOSTIC_COLUMNS = (
    "symbol", "freeze_version", "structural_spec_version", "source_file",
    "requested_start", "requested_end", "first_valid_timestamp",
    "last_valid_timestamp", "timestamp_parse_errors", "duplicate_timestamp_count",
    "nonfinite_or_invalid_ohlc_rows", "out_of_order_detected", "daily_bar_count",
    "available_calendar_months", "missing_calendar_months", "validation_status",
    "warnings", "failure_reasons",
)


class StructuralValidationError(ValueError):
    """Raised for a prepared-file or Track B structural contract failure."""


@dataclass(frozen=True)
class StructuralValidationResult:
    """Validated prepared Daily data, symbol diagnostics, and M1A identity."""

    daily_ohlc: pd.DataFrame
    symbol_diagnostics: pd.DataFrame
    summary: StructuralValidationSummary


def discover_prepared_daily_file(data_root: str | Path, symbol: str) -> Path:
    """Return the frozen prepared Daily path for one symbol."""
    return Path(data_root) / PREPARED_DAILY_FILENAME.format(symbol=symbol)


def _empty_daily() -> pd.DataFrame:
    return pd.DataFrame({
        "symbol": pd.Series(dtype="string"),
        "timestamp": pd.Series(dtype="datetime64[ns, UTC]"),
        "open": pd.Series(dtype="float64"),
        "high": pd.Series(dtype="float64"),
        "low": pd.Series(dtype="float64"),
        "close": pd.Series(dtype="float64"),
    }, columns=REQUIRED_LONG_DAILY_COLUMNS)


def _requested_months(config: TrackBConfig) -> list[str]:
    return [str(month) for month in pd.period_range(
        config.warmup_data_start, config.final_holdout.end, freq="M"
    )]


def _diagnostics(symbol: str, config: TrackBConfig, source_file: Path) -> dict[str, Any]:
    requested = _requested_months(config)
    return {
        "symbol": symbol,
        "freeze_version": config.freeze_version,
        "structural_spec_version": SUPPORTED_STRUCTURAL_SPEC_VERSION,
        "source_file": str(source_file),
        "requested_start": str(config.warmup_data_start),
        "requested_end": str(config.final_holdout.end),
        "first_valid_timestamp": None,
        "last_valid_timestamp": None,
        "timestamp_parse_errors": 0,
        "duplicate_timestamp_count": 0,
        "nonfinite_or_invalid_ohlc_rows": 0,
        "out_of_order_detected": False,
        "daily_bar_count": 0,
        "available_calendar_months": [],
        "missing_calendar_months": requested,
        "validation_status": "fail",
        "warnings": [],
        "failure_reasons": [],
    }


def _read_prepared_daily(path: Path, symbol: str) -> pd.DataFrame:
    """Read one prepared file and attach symbol from its path when needed."""
    try:
        frame = pd.read_csv(path)
    except (OSError, UnicodeError, pd.errors.ParserError) as exc:
        raise StructuralValidationError(f"cannot read prepared Daily CSV: {path}") from exc

    # Existing prepared exports use ``datetime``; this is a loader alias only.
    # The in-memory contract remains the required canonical ``timestamp`` name.
    if "timestamp" not in frame.columns and "datetime" in frame.columns:
        frame = frame.rename(columns={"datetime": "timestamp"})
    missing = [column for column in PREPARED_DAILY_COLUMNS if column not in frame.columns]
    if missing:
        raise StructuralValidationError(f"prepared Daily file is missing required columns: {missing}")
    if "symbol" not in frame.columns:
        frame.insert(0, "symbol", symbol)
    else:
        file_symbols = frame["symbol"].astype("string")
        if file_symbols.isna().any() or (file_symbols != symbol).any():
            raise StructuralValidationError(
                f"prepared Daily symbol column does not match file symbol {symbol}"
            )
    return frame.loc[:, list(REQUIRED_LONG_DAILY_COLUMNS) + [
        column for column in frame.columns if column not in REQUIRED_LONG_DAILY_COLUMNS
    ]]


def _parse_timestamp(frame: pd.DataFrame, diagnostics: dict[str, Any]) -> pd.DataFrame:
    values = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True, format="mixed")
    diagnostics["timestamp_parse_errors"] = int(values.isna().sum())
    if diagnostics["timestamp_parse_errors"]:
        raise StructuralValidationError("timestamp_parse_error")
    frame = frame.copy()
    frame["timestamp"] = values
    return frame


def _validate_ohlc(frame: pd.DataFrame, diagnostics: dict[str, Any]) -> None:
    numeric: dict[str, np.ndarray] = {}
    invalid_cell = np.zeros(len(frame), dtype=bool)
    for column in ("open", "high", "low", "close"):
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype="float64")
        numeric[column] = values
        invalid_cell |= ~np.isfinite(values) | (values <= 0)
    invariants = (
        (numeric["high"] >= numeric["open"])
        & (numeric["high"] >= numeric["close"])
        & (numeric["low"] <= numeric["open"])
        & (numeric["low"] <= numeric["close"])
        & (numeric["high"] >= numeric["low"])
    )
    invalid_row = invalid_cell | ~invariants
    diagnostics["nonfinite_or_invalid_ohlc_rows"] = int(invalid_row.sum())
    if invalid_row.any():
        raise StructuralValidationError("invalid_ohlc")


def _filter_requested_range(frame: pd.DataFrame, config: TrackBConfig) -> pd.DataFrame:
    months = frame["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None).dt.to_period("M")
    selected = months.between(config.warmup_data_start, config.final_holdout.end)
    return frame.loc[selected, REQUIRED_LONG_DAILY_COLUMNS].reset_index(drop=True)


def _validate_prepared_symbol(
    symbol: str,
    path: Path,
    config: TrackBConfig,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    item = _diagnostics(symbol, config, path)
    if not path.is_file():
        item["failure_reasons"].append("missing_prepared_daily_file")
        return _empty_daily(), item
    try:
        frame = _read_prepared_daily(path, symbol)
        frame = _parse_timestamp(frame, item)
        frame = _filter_requested_range(frame, config)
        item["duplicate_timestamp_count"] = int(frame["timestamp"].duplicated().sum())
        if item["duplicate_timestamp_count"]:
            raise StructuralValidationError("duplicate_timestamp")
        item["out_of_order_detected"] = not frame["timestamp"].is_monotonic_increasing
        if item["out_of_order_detected"]:
            raise StructuralValidationError("timestamp_not_ascending")
        # Normalize only requested rows. Values outside the authority range
        # must not determine the in-memory dtype or downstream validation.
        for column in ("open", "high", "low", "close"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        _validate_ohlc(frame, item)
        item["daily_bar_count"] = len(frame)
        if not frame.empty:
            item["first_valid_timestamp"] = frame["timestamp"].iloc[0]
            item["last_valid_timestamp"] = frame["timestamp"].iloc[-1]
        requested = _requested_months(config)
        available = set(
            frame["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None).dt.to_period("M").astype(str)
        )
        item["available_calendar_months"] = [month for month in requested if month in available]
        item["missing_calendar_months"] = [month for month in requested if month not in available]
        if item["missing_calendar_months"]:
            raise StructuralValidationError("missing_calendar_months")
        item["validation_status"] = "pass"
        return frame, item
    except (StructuralValidationError, TrackBDailyValidationError, KeyError, TypeError, ValueError) as exc:
        item["failure_reasons"].append(str(exc) or "structural_validation_failed")
        return _empty_daily(), item


def _finalize_diagnostics(frame: pd.DataFrame) -> pd.DataFrame:
    for column in DIAGNOSTIC_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    return frame.loc[:, DIAGNOSTIC_COLUMNS]


def run_track_b_structural_validation(
    data_root: str | Path = DEFAULT_DATA_ROOT,
    config_path: str | Path = "config/research_track_b.yaml",
) -> StructuralValidationResult:
    """Validate prepared 1d OHLC for the frozen universe without M1A execution."""
    config = load_track_b_config(config_path)
    daily_frames: list[pd.DataFrame] = []
    diagnostics: list[dict[str, Any]] = []
    for symbol in config.primary_symbols + config.secondary_symbols:
        path = discover_prepared_daily_file(data_root, symbol)
        daily, item = _validate_prepared_symbol(symbol, path, config)
        diagnostics.append(item)
        if not daily.empty:
            daily_frames.append(daily)

    daily = pd.concat(daily_frames, ignore_index=True) if daily_frames else _empty_daily()
    try:
        daily = validate_track_b_daily(daily, config)
    except TrackBDailyValidationError as exc:
        raise StructuralValidationError(
            f"validated prepared Daily dataset failed final validation: {exc}"
        ) from exc
    fingerprint = compute_track_b_daily_fingerprint(daily)
    summary = StructuralValidationSummary(
        freeze_version=config.freeze_version,
        structural_spec_version=SUPPORTED_STRUCTURAL_SPEC_VERSION,
        dataset_fingerprint=fingerprint,
        dataset_fingerprint_algorithm=SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
        status_by_symbol={str(item["symbol"]): str(item["validation_status"]) for item in diagnostics},
    )
    return StructuralValidationResult(
        daily_ohlc=daily,
        symbol_diagnostics=_finalize_diagnostics(pd.DataFrame(diagnostics)),
        summary=summary,
    )


__all__ = [
    "DEFAULT_DATA_ROOT", "DIAGNOSTIC_COLUMNS", "PREPARED_DAILY_COLUMNS",
    "PREPARED_DAILY_FILENAME", "StructuralValidationError",
    "StructuralValidationResult", "discover_prepared_daily_file",
    "run_track_b_structural_validation",
]
