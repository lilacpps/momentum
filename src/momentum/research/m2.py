"""Gated Track B M2 execution for one frozen primary symbol."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pandas as pd

from momentum.backtest.engine import BacktestResult, run_target_backtest
from momentum.metrics.gross import gross_metrics
from momentum.data.track_b import (
    TrackBDailyValidationError,
    compute_track_b_daily_fingerprint,
)
from momentum.research.track_b_config import (
    SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
    SUPPORTED_STRUCTURAL_SPEC_VERSION,
    StructuralValidationSummary,
    TrackBConfig,
    validate_m1a_real_data_gate,
)
from momentum.signals.m2 import M2_SPEC_VERSION, generate_m2_signals
from momentum.signals.m0 import generate_m0_signals


def run_m2_track_b(
    daily: pd.DataFrame,
    config: TrackBConfig,
    validation_summary: StructuralValidationSummary,
    *,
    symbol: str,
    sample_start: pd.Timestamp | None = None,
    sample_end: pd.Timestamp | None = None,
) -> BacktestResult:
    """Run M2 independently for one frozen primary symbol.

    Structural identity is checked against the complete prepared Daily input
    before selecting the requested symbol.  This prevents a symbol-local run
    from silently using a different dataset than the validation summary.
    """
    if symbol not in config.primary_symbols:
        raise TrackBDailyValidationError("M2 symbol must be in the frozen primary universe")
    if validation_summary.freeze_version != config.freeze_version:
        raise TrackBDailyValidationError("structural validation freeze_version does not match current artifact")
    if validation_summary.structural_spec_version != SUPPORTED_STRUCTURAL_SPEC_VERSION:
        raise TrackBDailyValidationError("unsupported structural validation spec version")
    if validation_summary.dataset_fingerprint_algorithm != SUPPORTED_DATASET_FINGERPRINT_ALGORITHM:
        raise TrackBDailyValidationError("unsupported structural validation dataset fingerprint algorithm")
    fingerprint = compute_track_b_daily_fingerprint(daily)
    if fingerprint != validation_summary.dataset_fingerprint:
        raise TrackBDailyValidationError("structural validation dataset fingerprint does not match input")
    validate_m1a_real_data_gate(
        config,
        validation_summary.status_by_symbol,
        validation_summary.freeze_version,
    )
    if validation_summary.status_by_symbol.get(symbol) not in {"pass", "pass_with_warning"}:
        raise TrackBDailyValidationError(f"primary structural validation gate failed for {symbol}")
    if "symbol" not in daily.columns:
        raise TrackBDailyValidationError("M2 Track B input requires a symbol column")
    selected_full = daily.loc[daily["symbol"].astype(str).eq(symbol)].copy().reset_index(drop=True)
    if selected_full.empty:
        raise TrackBDailyValidationError(f"missing frozen primary symbol: {symbol}")

    max_month = config.validation.end
    full_timestamp = selected_full["timestamp"]
    if full_timestamp.dt.tz is not None:
        full_calendar = full_timestamp.dt.tz_convert("UTC").dt.tz_localize(None).dt.to_period("M")
    else:
        full_calendar = full_timestamp.dt.to_period("M")
    boundary_month = max_month + 1
    boundary_rows = selected_full.loc[full_calendar == boundary_month]
    if boundary_rows.empty:
        raise TrackBDailyValidationError(
            f"missing terminal execution boundary month: {boundary_month}"
        )
    boundary_timestamp = boundary_rows["timestamp"].iloc[0]
    if sample_end is not None and pd.Timestamp(sample_end) != pd.Timestamp(boundary_timestamp):
        raise TrackBDailyValidationError(
            "M2 sample_end does not match the canonical validation boundary"
        )
    if sample_start is not None:
        sample_start = pd.Timestamp(sample_start)
    execution_mask = (full_calendar >= config.warmup_data_start) & (
        selected_full["timestamp"] <= boundary_timestamp
    )
    selected = selected_full.loc[execution_mask].reset_index(drop=True)
    generated = generate_m2_signals(
        selected,
        config,
        analysis_start=config.development.start,
        analysis_end=max_month,
    )
    metadata: dict[str, Any] = {
        "track": "Track B",
        "workstream": "M2 Practical Monthly Comparator",
        "spec_version": M2_SPEC_VERSION,
        "freeze_version": config.freeze_version,
        "structural_spec_version": validation_summary.structural_spec_version,
        "dataset_fingerprint": validation_summary.dataset_fingerprint,
        "dataset_fingerprint_algorithm": validation_summary.dataset_fingerprint_algorithm,
        "symbol": symbol,
        "split": "development+validation",
        "sample_period": f"{config.development.start}..{max_month}",
        "data_source": config.data_source,
        "price_type": config.price_type,
        "timezone": config.timezone,
        "daily_boundary": dict(config.daily_boundary),
        "result_level": "gross_price_only",
        "academic_mop_replication": False,
        "final_holdout_included": False,
        "construction_rule": "12_calendar_month_formation_next_month_first_open",
        "split_assignment": "holding_month",
        "accounting_engine": "shared_daily_open_to_open_v1",
    }
    result = run_target_backtest(
        selected,
        generated.target_position,
        generated.signal,
        metadata,
    )
    bars = result.bars.copy()
    bars["m2_rebalance"] = generated.rebalance.to_numpy(dtype=bool)
    timestamp = bars["timestamp"]
    if timestamp.dt.tz is not None:
        calendar = timestamp.dt.tz_convert("UTC").dt.tz_localize(None).dt.to_period("M")
    else:
        calendar = timestamp.dt.to_period("M")
    if not (calendar == boundary_month).any():
        raise TrackBDailyValidationError(
            f"missing terminal execution boundary month: {boundary_month}"
        )
    derived_sample_start = timestamp.loc[calendar == config.development.start].iloc[0]
    if sample_start is None:
        sample_start = derived_sample_start
    elif sample_start != derived_sample_start:
        raise TrackBDailyValidationError(
            "M2 sample_start does not match the canonical Development boundary"
        )
    _, m0_target = generate_m0_signals(selected["close"])
    comparable = generated.rebalance & (calendar >= config.development.start) & (calendar <= max_month)
    agreement = float(
        (m0_target.loc[comparable] == generated.target_position.loc[comparable]).mean()
    ) if comparable.any() else None
    metrics = gross_metrics(
        result.ledger,
        bars,
        sample_start=sample_start,
        sample_end=boundary_timestamp,
    )
    metrics["signal_direction_agreement"] = agreement
    result_metadata = dict(result.metadata)
    result_metadata.update({
        "sample_start_timestamp": pd.Timestamp(sample_start).isoformat(),
        "sample_end_timestamp": pd.Timestamp(boundary_timestamp).isoformat(),
    })
    return replace(result, bars=bars, metrics=metrics, metadata=result_metadata)


__all__ = ["run_m2_track_b"]
