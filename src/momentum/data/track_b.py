"""Track B daily OHLC validation and monthly observation construction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import struct
from typing import Any

import numpy as np
import pandas as pd

from momentum.research.track_b_config import TrackBConfig
from momentum.research.track_b_config import SUPPORTED_DATASET_FINGERPRINT_ALGORITHM
from momentum.research.track_b_config import SUPPORTED_STRUCTURAL_SPEC_VERSION
from momentum.research.track_b_config import StructuralValidationSummary
from momentum.research.track_b_config import validate_m1a_real_data_gate

REQUIRED_LONG_DAILY_COLUMNS = ("symbol", "timestamp", "open", "high", "low", "close")


class TrackBDailyValidationError(ValueError):
    """Raised when canonical long-form Track B daily data is invalid."""


@dataclass(frozen=True)
class MonthlyObservationResult:
    observations: pd.DataFrame
    diagnostics: dict[str, Any]


def compute_track_b_daily_fingerprint(data: pd.DataFrame) -> str:
    """Return the v1 SHA-256 identity of canonical Track B daily OHLC rows."""
    missing = [column for column in REQUIRED_LONG_DAILY_COLUMNS if column not in data.columns]
    if missing:
        raise TrackBDailyValidationError(f"missing required columns: {missing}")
    frame = data.loc[:, REQUIRED_LONG_DAILY_COLUMNS].copy()
    if frame["symbol"].isna().any():
        raise TrackBDailyValidationError("symbol must be non-empty")
    if not isinstance(frame["timestamp"].dtype, pd.DatetimeTZDtype):
        raise TrackBDailyValidationError("fingerprint requires timezone-aware UTC timestamps")
    if str(frame["timestamp"].dt.tz) != "UTC":
        raise TrackBDailyValidationError("fingerprint requires UTC timestamps")
    symbols = frame["symbol"].astype(str)
    timestamps = (
        frame["timestamp"]
        .dt.tz_convert("UTC")
        .dt.tz_localize(None)
        .astype("datetime64[ns]")
        .astype("int64")
    )
    numeric_columns = ("open", "high", "low", "close")
    for column in numeric_columns:
        if not pd.api.types.is_numeric_dtype(frame[column]):
            raise TrackBDailyValidationError(f"{column} must be numeric")
        values = frame[column].to_numpy(dtype="float64", na_value=float("nan"))
        if not np.isfinite(values).all():
            raise TrackBDailyValidationError(f"{column} contains non-finite values")
    canonical = pd.DataFrame({
        "symbol": symbols,
        "timestamp_ns": timestamps,
        **{column: frame[column].astype("float64") for column in numeric_columns},
    }).sort_values(["symbol", "timestamp_ns"], kind="mergesort")
    digest = hashlib.sha256()
    digest.update(SUPPORTED_DATASET_FINGERPRINT_ALGORITHM.encode("ascii"))
    digest.update(b"\0")
    digest.update(struct.pack("<Q", len(canonical)))
    for symbol, timestamp_ns, open_, high, low, close in canonical.itertuples(index=False, name=None):
        encoded_symbol = str(symbol).encode("utf-8")
        digest.update(struct.pack("<Q", len(encoded_symbol)))
        digest.update(encoded_symbol)
        digest.update(struct.pack(
            "<qdddd",
            int(timestamp_ns),
            float(open_),
            float(high),
            float(low),
            float(close),
        ))
    return digest.hexdigest()


def validate_track_b_daily(
    data: pd.DataFrame,
    config: TrackBConfig,
    *,
    allow_naive_timestamp: bool = False,
) -> pd.DataFrame:
    """Validate and copy long-form daily OHLC data without filling or sorting."""
    if not isinstance(data, pd.DataFrame):
        raise TrackBDailyValidationError("data must be a pandas DataFrame")
    missing = [column for column in REQUIRED_LONG_DAILY_COLUMNS if column not in data.columns]
    if missing:
        raise TrackBDailyValidationError(f"missing required columns: {missing}")

    frame = data.loc[:, REQUIRED_LONG_DAILY_COLUMNS].copy().reset_index(drop=True)
    if frame["symbol"].isna().any() or (frame["symbol"].astype(str).str.len() == 0).any():
        raise TrackBDailyValidationError("symbol must be non-empty")
    if not pd.api.types.is_datetime64_any_dtype(frame["timestamp"]):
        raise TrackBDailyValidationError("timestamp must have a datetime dtype")
    if frame["timestamp"].isna().any():
        raise TrackBDailyValidationError("timestamp contains missing values")

    if isinstance(frame["timestamp"].dtype, pd.DatetimeTZDtype):
        if str(frame["timestamp"].dt.tz) != "UTC":
            raise TrackBDailyValidationError("timestamp must use UTC timezone")
        frame["timestamp"] = frame["timestamp"].dt.tz_convert("UTC")
    elif allow_naive_timestamp:
        # This is allowed only for explicit synthetic fixtures.
        frame["timestamp"] = frame["timestamp"].dt.tz_localize("UTC")
    else:
        raise TrackBDailyValidationError("timestamp must be timezone-aware UTC")

    if frame.duplicated(["symbol", "timestamp"]).any():
        raise TrackBDailyValidationError("duplicate (symbol, timestamp)")
    for symbol, group in frame.groupby("symbol", sort=False):
        if not group["timestamp"].is_monotonic_increasing:
            raise TrackBDailyValidationError(f"timestamp must be ascending within symbol: {symbol}")

    try:
        boundary_time = datetime.strptime(
            str(config.daily_boundary["boundary_local_time"]), "%H:%M"
        ).time()
    except (KeyError, ValueError) as exc:
        raise TrackBDailyValidationError("invalid daily boundary local time") from exc
    local_timestamp = frame["timestamp"].dt.tz_convert(config.boundary_timezone)
    valid_boundary = (
        (local_timestamp.dt.hour == boundary_time.hour)
        & (local_timestamp.dt.minute == boundary_time.minute)
        & (local_timestamp.dt.second == boundary_time.second)
        & (local_timestamp.dt.microsecond == 0)
    )
    if not valid_boundary.all():
        raise TrackBDailyValidationError("timestamp is not the frozen nominal daily close time")

    for column in ("open", "high", "low", "close"):
        if not pd.api.types.is_numeric_dtype(frame[column]):
            raise TrackBDailyValidationError(f"{column} must be numeric")
        values = frame[column].to_numpy(dtype="float64", na_value=float("nan"))
        if np.isnan(values).any() or not np.isfinite(values).all():
            raise TrackBDailyValidationError(f"{column} contains non-finite values")
        if (frame[column] <= 0).any():
            raise TrackBDailyValidationError(f"{column} must be positive")
    return frame


def _split_for_outcome(config: TrackBConfig, outcome_month: pd.Period) -> str:
    return config.split_for_outcome(outcome_month)


def _universe_role(config: TrackBConfig, symbol: str) -> str:
    if symbol in config.primary_symbols:
        return "primary"
    if symbol in config.secondary_symbols:
        return "secondary_cross_robustness"
    return "unclassified"


def _build_monthly_observations(
    data: pd.DataFrame,
    config: TrackBConfig,
    *,
    max_outcome_month: pd.Period,
    allow_naive_timestamp: bool,
) -> MonthlyObservationResult:
    """Build exact calendar-month M1A observations from canonical daily OHLC."""
    frame = validate_track_b_daily(
        data,
        config,
        allow_naive_timestamp=allow_naive_timestamp,
    )
    local_dates = frame["timestamp"].dt.tz_convert(config.boundary_timezone).dt.date
    frame["calendar_month"] = pd.to_datetime(local_dates).dt.to_period("M")
    requested_start = config.warmup_data_start
    requested_end = max_outcome_month
    in_range = frame["calendar_month"].between(requested_start, requested_end)
    frame = frame.loc[in_range].copy()

    monthly = (
        frame.sort_values(["symbol", "timestamp"], kind="mergesort")
        .drop_duplicates(["symbol", "calendar_month"], keep="last")
        .loc[:, ["symbol", "calendar_month", "close"]]
        .rename(columns={"close": "month_end_close"})
    )
    close_lookup = {
        symbol: group.set_index("calendar_month")["month_end_close"].to_dict()
        for symbol, group in monthly.groupby("symbol", sort=False)
    }
    all_slots = pd.period_range(requested_start, requested_end, freq="M")
    formation_slots = pd.period_range(requested_start, requested_end - 1, freq="M")

    rows: list[dict[str, Any]] = []
    missing_by_symbol: dict[str, list[str]] = {}
    available_by_symbol: dict[str, list[str]] = {}
    excluded_by_reason: dict[str, int] = {}
    symbols = tuple(frame["symbol"].drop_duplicates().tolist())

    for symbol in symbols:
        lookup = close_lookup.get(symbol, {})
        available_by_symbol[str(symbol)] = [str(month) for month in all_slots if month in lookup]
        missing_by_symbol[str(symbol)] = [str(month) for month in all_slots if month not in lookup]
        for formation_month in formation_slots:
            required = {
                "past_12m": formation_month - 12,
                "formation": formation_month,
                "next_1m": formation_month + 1,
            }
            if required["past_12m"] < requested_start:
                excluded_by_reason["pre_sample_history_unavailable"] = (
                    excluded_by_reason.get("pre_sample_history_unavailable", 0) + 1
                )
                continue
            missing = [name for name, month in required.items() if month not in lookup]
            if missing:
                reason = {
                    "formation": "missing_formation_month",
                    "next_1m": "missing_next_month",
                    "past_12m": "missing_past_12m_month",
                }[missing[0]]
                excluded_by_reason[reason] = excluded_by_reason.get(reason, 0) + 1
                continue
            past_return = float(lookup[required["formation"]] / lookup[required["past_12m"]] - 1.0)
            next_return = float(lookup[required["next_1m"]] / lookup[required["formation"]] - 1.0)
            sign = int(np.sign(past_return))
            outcome_month = formation_month + 1
            rows.append({
                "symbol": symbol,
                "universe_role": _universe_role(config, str(symbol)),
                "formation_month": formation_month,
                "outcome_month": outcome_month,
                "past_12m_return": past_return,
                "next_1m_return": next_return,
                "sign": sign,
                "split": _split_for_outcome(config, outcome_month),
            })

    observations = pd.DataFrame(rows, columns=[
        "symbol", "universe_role", "formation_month", "outcome_month", "past_12m_return",
        "next_1m_return", "sign", "split",
    ])
    analysis = observations[observations["split"].isin(config.analysis_splits)].copy()
    diagnostics_by_universe_role = {}
    for role in ("primary", "secondary_cross_robustness"):
        role_analysis = analysis[analysis["universe_role"] == role]
        diagnostics_by_universe_role[role] = {
            "observation_count": int(len(role_analysis)),
            "positive": int((role_analysis["sign"] > 0).sum()),
            "negative": int((role_analysis["sign"] < 0).sum()),
            "zero": int((role_analysis["sign"] == 0).sum()),
        }
    diagnostics = {
        "available_calendar_months": available_by_symbol,
        "missing_calendar_months": missing_by_symbol,
        "excluded_observation_count": int(sum(excluded_by_reason.values())),
        "excluded_observations_by_reason": excluded_by_reason,
        "zero_predictor_observations": int((analysis["sign"] == 0).sum()),
        "positive_predictor_observations": int((analysis["sign"] > 0).sum()),
        "negative_predictor_observations": int((analysis["sign"] < 0).sum()),
        "observations_by_split": {
            str(key): int(value) for key, value in observations["split"].value_counts().items()
        },
        "observations_by_symbol": {
            str(key): int(value) for key, value in analysis["symbol"].value_counts().items()
        },
        "analysis_observation_count": int(len(analysis)),
        "diagnostics_by_universe_role": diagnostics_by_universe_role,
        "freeze_version": config.freeze_version,
    }
    return MonthlyObservationResult(observations=observations, diagnostics=diagnostics)


def _build_synthetic_monthly_observations(
    data: pd.DataFrame,
    config: TrackBConfig,
) -> MonthlyObservationResult:
    """Private test-support builder that may construct holdout split fixtures."""
    return _build_monthly_observations(
        data,
        config,
        max_outcome_month=config.final_holdout.end,
        allow_naive_timestamp=True,
    )


def _build_track_b_monthly_observations(
    data: pd.DataFrame,
    config: TrackBConfig,
    validation_summary: StructuralValidationSummary,
) -> MonthlyObservationResult:
    """Gate, filter, and build only non-holdout Track B observations."""
    if validation_summary.freeze_version != config.freeze_version:
        raise TrackBDailyValidationError(
            "structural validation freeze_version does not match current artifact"
        )
    if validation_summary.dataset_fingerprint_algorithm != SUPPORTED_DATASET_FINGERPRINT_ALGORITHM:
        raise TrackBDailyValidationError(
            "unsupported structural validation dataset fingerprint algorithm"
        )
    if validation_summary.structural_spec_version != SUPPORTED_STRUCTURAL_SPEC_VERSION:
        raise TrackBDailyValidationError(
            "unsupported structural validation spec version"
        )
    try:
        dataset_fingerprint = compute_track_b_daily_fingerprint(data)
    except TrackBDailyValidationError:
        raise
    if dataset_fingerprint != validation_summary.dataset_fingerprint:
        raise TrackBDailyValidationError(
            "structural validation dataset fingerprint does not match input"
        )
    eligible_secondary = validate_m1a_real_data_gate(
        config,
        validation_summary.status_by_symbol,
        validation_summary.freeze_version,
    )
    eligible_symbols = set(config.primary_symbols) | set(eligible_secondary)
    if "symbol" not in data.columns:
        raise TrackBDailyValidationError("missing required columns: ['symbol']")
    selected = data.loc[data["symbol"].astype(str).isin(eligible_symbols)].copy()
    selected_symbols = set(selected["symbol"].dropna().astype(str))
    missing_primary = sorted(set(config.primary_symbols) - selected_symbols)
    if missing_primary:
        raise TrackBDailyValidationError(f"missing frozen primary symbols: {missing_primary}")
    missing_eligible_secondary = sorted(set(eligible_secondary) - selected_symbols)
    if missing_eligible_secondary:
        raise TrackBDailyValidationError(
            f"eligible secondary symbols missing from input: {missing_eligible_secondary}"
        )
    result = _build_monthly_observations(
        selected,
        config,
        max_outcome_month=config.validation.end,
        allow_naive_timestamp=False,
    )
    result.diagnostics.update({
        "structural_spec_version": validation_summary.structural_spec_version,
        "dataset_fingerprint": validation_summary.dataset_fingerprint,
        "dataset_fingerprint_algorithm": validation_summary.dataset_fingerprint_algorithm,
    })
    return result
