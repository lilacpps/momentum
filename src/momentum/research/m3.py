"""M3 symbol-level orchestration for M0, M2, and TSH."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import pandas as pd

from momentum.backtest.engine import BacktestResult, run_m0_backtest, run_target_backtest
from momentum.data.track_b import compute_track_b_daily_fingerprint
from momentum.metrics.gross import gross_metrics
from momentum.research.m2 import run_m2_track_b
from momentum.research.track_b_config import (
    SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
    TrackBConfig,
    StructuralValidationSummary,
)
from momentum.signals.m2 import M2SignalResult, generate_m2_signals
from momentum.signals.tsh import TSHSignalResult, TSH_SPEC_VERSION, generate_tsh_signals


M3_SPEC_VERSION = "m3-multi-symbol-v1"
ACCOUNTING_ENGINE = "shared_daily_open_to_open_v1"
TSH_METHOD_ROLE = "tsh_track_b_practical"


class M3ExecutionError(RuntimeError):
    """Raised when one symbol cannot satisfy the M3 execution contract."""


@dataclass(frozen=True)
class M3Window:
    symbol: str
    sample_start: pd.Timestamp
    sample_end: pd.Timestamp
    return_timestamps: tuple[pd.Timestamp, ...]


@dataclass(frozen=True)
class M3SymbolResult:
    symbol: str
    universe_role: str
    window: M3Window
    m0: BacktestResult
    m2: BacktestResult | None
    tsh: BacktestResult
    m2_generated: M2SignalResult | None
    tsh_generated: TSHSignalResult
    m0_metrics: dict[str, Any]
    m2_metrics: dict[str, Any] | None
    tsh_metrics: dict[str, Any]
    comparison: dict[str, Any] | None
    year_diagnostics: pd.DataFrame


def _utc_timestamps(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame["timestamp"], utc=True)


def _calendar_months(frame: pd.DataFrame) -> pd.Series:
    return _utc_timestamps(frame).dt.tz_localize(None).dt.to_period("M")


def _canonical_window(full_daily: pd.DataFrame, config: TrackBConfig, symbol: str) -> M3Window:
    selected = full_daily.loc[full_daily["symbol"].astype(str).eq(symbol)].copy()
    if selected.empty:
        raise M3ExecutionError(f"missing frozen symbol: {symbol}")
    timestamps = _utc_timestamps(selected)
    calendar = timestamps.dt.tz_localize(None).dt.to_period("M")

    def first_open(month: pd.Period) -> pd.Timestamp:
        rows = timestamps.loc[calendar.eq(month)]
        if rows.empty:
            raise M3ExecutionError(f"missing canonical boundary month {month} for {symbol}")
        return pd.Timestamp(rows.iloc[0])

    sample_start = first_open(config.development.start)
    sample_end = first_open(config.validation.end + 1)
    return_timestamps = tuple(
        pd.Timestamp(value)
        for value in timestamps.loc[
            timestamps.ge(sample_start) & timestamps.lt(sample_end)
        ]
    )
    if not return_timestamps:
        raise M3ExecutionError(f"empty evaluation return window for {symbol}")
    return M3Window(symbol, sample_start, sample_end, return_timestamps)


def _execution_frame(full_daily: pd.DataFrame, config: TrackBConfig, window: M3Window) -> pd.DataFrame:
    selected = full_daily.loc[full_daily["symbol"].astype(str).eq(window.symbol)].copy()
    timestamps = _utc_timestamps(selected)
    calendar = timestamps.dt.tz_localize(None).dt.to_period("M")
    mask = calendar.ge(config.warmup_data_start) & timestamps.le(window.sample_end)
    return selected.loc[mask].reset_index(drop=True)


def _timestamp_keys(values: pd.Series | pd.Index) -> list[int]:
    return [int(value.value) for value in pd.to_datetime(values, utc=True)]


def _validate_result_frame(result: BacktestResult, execution: pd.DataFrame, window: M3Window, label: str) -> None:
    bars = result.bars
    expected = _timestamp_keys(execution["timestamp"])
    actual = _timestamp_keys(bars["timestamp"])
    if actual != expected:
        raise M3ExecutionError(f"{label} bars do not match canonical execution frame")
    timestamps = pd.to_datetime(bars["timestamp"], utc=True)
    if timestamps.iloc[-1] != window.sample_end:
        raise M3ExecutionError(f"{label} does not end at terminal boundary")
    terminal = bars.iloc[-1]
    if not pd.isna(terminal["asset_return"]) or not pd.isna(terminal["strategy_return"]):
        raise M3ExecutionError(f"{label} terminal boundary must not have a return")
    return_keys = _timestamp_keys(
        timestamps.loc[
            timestamps.ge(window.sample_start)
            & timestamps.lt(window.sample_end)
            & bars["strategy_return"].notna()
        ]
    )
    if return_keys != _timestamp_keys(window.return_timestamps):
        raise M3ExecutionError(f"{label} return timestamps differ from canonical window")


def _metadata_context(
    config: TrackBConfig,
    summary: StructuralValidationSummary,
    symbol: str,
    universe_role: str,
) -> dict[str, Any]:
    return {
        "freeze_version": config.freeze_version,
        "structural_spec_version": summary.structural_spec_version,
        "dataset_fingerprint": summary.dataset_fingerprint,
        "dataset_fingerprint_algorithm": summary.dataset_fingerprint_algorithm,
        "symbol": symbol,
        "universe_role": universe_role,
        "m3_spec_version": M3_SPEC_VERSION,
        "final_holdout_included": False,
        "accounting_engine": ACCOUNTING_ENGINE,
    }


def _validate_full_identity(
    full_daily: pd.DataFrame,
    config: TrackBConfig,
    summary: StructuralValidationSummary,
) -> None:
    if summary.freeze_version != config.freeze_version:
        raise M3ExecutionError("freeze_version does not match M3 config")
    if summary.dataset_fingerprint_algorithm != SUPPORTED_DATASET_FINGERPRINT_ALGORITHM:
        raise M3ExecutionError("unsupported M3 dataset fingerprint algorithm")
    if compute_track_b_daily_fingerprint(full_daily) != summary.dataset_fingerprint:
        raise M3ExecutionError("full Track B dataset fingerprint mismatch")


def _valid_holding_months(
    generated: M2SignalResult,
    config: TrackBConfig,
) -> tuple[pd.Period, ...]:
    table = generated.decision_table
    if table.empty:
        return ()
    valid = table.loc[
        table["signal"].notna()
        & table["holding_month"].map(
            lambda month: config.development.contains(month) or config.validation.contains(month)
        )
    ]
    return tuple(valid["holding_month"].tolist())


def _assert_m2_mask_matches_result(
    generated: M2SignalResult,
    m2: BacktestResult,
    valid_months: tuple[pd.Period, ...],
) -> None:
    expected = generated.decision_table.loc[
        generated.decision_table["holding_month"].isin(valid_months)
        & generated.decision_table["signal"].notna(),
        "entry_timestamp",
    ]
    m2_timestamps = pd.to_datetime(m2.bars["timestamp"], utc=True)
    m2_months = m2_timestamps.dt.tz_localize(None).dt.to_period("M")
    actual = m2_timestamps.loc[
        m2.bars["signal"].notna() & m2_months.isin(valid_months)
    ]
    if _timestamp_keys(expected) != _timestamp_keys(actual):
        raise M3ExecutionError("M2 decision-table mask does not match M2 result bars")


def _masked_metrics(
    result: BacktestResult,
    valid_months: tuple[pd.Period, ...],
    window: M3Window,
) -> dict[str, Any]:
    bars = result.bars
    timestamps = pd.to_datetime(bars["timestamp"], utc=True)
    months = timestamps.dt.tz_localize(None).dt.to_period("M")
    valid = months.isin(valid_months)
    return_mask = (
        timestamps.ge(window.sample_start)
        & timestamps.lt(window.sample_end)
        & valid
        & bars["strategy_return"].notna()
    )
    strategy = bars.loc[return_mask, "strategy_return"].astype(float)
    equity = pd.concat([
        pd.Series([1.0], dtype="float64"),
        (1.0 + strategy).cumprod().reset_index(drop=True),
    ], ignore_index=True)
    max_drawdown = float((equity / equity.cummax() - 1.0).min()) if len(equity) else 0.0

    event_mask = (
        timestamps.ge(window.sample_start)
        & timestamps.le(window.sample_end)
        & (valid | timestamps.eq(window.sample_end))
    )
    positions = bars["executed_position"].fillna(0).astype(int)
    previous = positions.shift(1, fill_value=0)
    turnover = float((positions.loc[event_mask] - previous.loc[event_mask]).abs().sum())
    reversal_count = int((event_mask & bars["reversal_from_episode_id"].notna()).sum())
    entry_timestamps = pd.to_datetime(result.ledger["entry_timestamp"], utc=True)
    entry_months = entry_timestamps.dt.tz_localize(None).dt.to_period("M")
    trade_mask = (
        entry_timestamps.ge(window.sample_start)
        & entry_timestamps.le(window.sample_end)
        & entry_months.isin(valid_months)
    )
    return {
        "gross_return": float((1.0 + strategy).prod() - 1.0) if len(strategy) else 0.0,
        "max_drawdown": max_drawdown,
        "turnover": turnover,
        "trade_count": int(trade_mask.sum()),
        "reversal_count": reversal_count,
        "return_count": int(len(strategy)),
    }


def _year_diagnostics(
    symbol: str,
    universe_role: str,
    strategy_results: dict[str, BacktestResult],
    window: M3Window,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for strategy, result in strategy_results.items():
        bars = result.bars.copy()
        timestamps = pd.to_datetime(bars["timestamp"], utc=True)
        mask = timestamps.ge(window.sample_start) & timestamps.lt(window.sample_end)
        bars = bars.loc[mask & bars["strategy_return"].notna()].copy()
        bars["year"] = timestamps.loc[bars.index].dt.year
        for year, group in bars.groupby("year", sort=True):
            returns = group["strategy_return"].astype(float)
            rows.append({
                "symbol": symbol,
                "universe_role": universe_role,
                "strategy": strategy,
                "year": int(year),
                "return_count": int(len(returns)),
                "gross_return": float((1.0 + returns).prod() - 1.0),
                "mean_strategy_return": float(returns.mean()),
            })
    return pd.DataFrame(rows, columns=[
        "symbol", "universe_role", "strategy", "year", "return_count",
        "gross_return", "mean_strategy_return",
    ])


def run_m3_symbol(
    full_daily: pd.DataFrame,
    config: TrackBConfig,
    validation_summary: StructuralValidationSummary,
    *,
    symbol: str,
    universe_role: str,
) -> M3SymbolResult:
    """Run one symbol while preserving the M2 full-dataset fingerprint gate."""
    _validate_full_identity(full_daily, config, validation_summary)
    window = _canonical_window(full_daily, config, symbol)
    execution = _execution_frame(full_daily, config, window)
    context = _metadata_context(config, validation_summary, symbol, universe_role)

    m0 = run_m0_backtest(execution, metadata=context)
    m2: BacktestResult | None = None
    m2_generated: M2SignalResult | None = None

    if universe_role == "primary":
        m2 = run_m2_track_b(
            full_daily,
            config,
            validation_summary,
            symbol=symbol,
            sample_start=window.sample_start,
            sample_end=window.sample_end,
        )
        m2_metadata = dict(m2.metadata)
        m2_metadata.update({"universe_role": universe_role, "m3_spec_version": M3_SPEC_VERSION})
        m2 = replace(m2, metadata=m2_metadata)
        m2_generated = generate_m2_signals(
            execution,
            config,
            analysis_start=config.development.start,
            analysis_end=config.validation.end,
        )
        valid_months = _valid_holding_months(m2_generated, config)
        _assert_m2_mask_matches_result(m2_generated, m2, valid_months)
    else:
        valid_months = ()

    tsh_generated = generate_tsh_signals(
        execution,
        config,
        analysis_start=config.development.start,
        analysis_end=config.validation.end,
    )
    tsh_metadata = {
        **context,
        "tsh_spec_version": TSH_SPEC_VERSION,
        "method_role": TSH_METHOD_ROLE,
    }
    tsh = run_target_backtest(
        execution,
        tsh_generated.target_position,
        tsh_generated.signal,
        tsh_metadata,
    )

    for label, result in (("M0", m0), ("TSH", tsh)):
        _validate_result_frame(result, execution, window, label)
    if m2 is not None:
        _validate_result_frame(m2, execution, window, "M2")

    m0_metrics = gross_metrics(m0.ledger, m0.bars, sample_start=window.sample_start, sample_end=window.sample_end)
    tsh_metrics = gross_metrics(tsh.ledger, tsh.bars, sample_start=window.sample_start, sample_end=window.sample_end)
    m2_metrics = (
        gross_metrics(m2.ledger, m2.bars, sample_start=window.sample_start, sample_end=window.sample_end)
        if m2 is not None else None
    )
    comparison = None
    if m2 is not None:
        tsm_masked = _masked_metrics(m2, valid_months, window)
        tsh_masked = _masked_metrics(tsh, valid_months, window)
        comparison = {
            "symbol": symbol,
            "universe_role": universe_role,
            "holding_month_count": len(valid_months),
            "tsm_gross_return": tsm_masked["gross_return"],
            "tsh_gross_return": tsh_masked["gross_return"],
            "tsm_minus_tsh": tsm_masked["gross_return"] - tsh_masked["gross_return"],
            "tsm_max_drawdown": tsm_masked["max_drawdown"],
            "tsh_max_drawdown": tsh_masked["max_drawdown"],
            "tsm_turnover": tsm_masked["turnover"],
            "tsh_turnover": tsh_masked["turnover"],
            "tsm_trade_count": tsm_masked["trade_count"],
            "tsh_trade_count": tsh_masked["trade_count"],
            "tsm_reversal_count": tsm_masked["reversal_count"],
            "tsh_reversal_count": tsh_masked["reversal_count"],
            "tsm_return_count": tsm_masked["return_count"],
            "tsh_return_count": tsh_masked["return_count"],
        }

    strategy_results = {"m0": m0, "tsh": tsh}
    if m2 is not None:
        strategy_results["m2"] = m2
    years = _year_diagnostics(symbol, universe_role, strategy_results, window)
    return M3SymbolResult(
        symbol=symbol,
        universe_role=universe_role,
        window=window,
        m0=m0,
        m2=m2,
        tsh=tsh,
        m2_generated=m2_generated,
        tsh_generated=tsh_generated,
        m0_metrics=m0_metrics,
        m2_metrics=m2_metrics,
        tsh_metrics=tsh_metrics,
        comparison=comparison,
        year_diagnostics=years,
    )


__all__ = ["M3_SPEC_VERSION", "M3ExecutionError", "M3SymbolResult", "run_m3_symbol"]
