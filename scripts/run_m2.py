"""Run the gated Track B M2 execution and M0/M2 comparison.

The runner owns the production orchestration.  It validates the complete
prepared Daily dataset, derives one canonical window per symbol, executes M0
and M2 on the same truncated input, and saves a result only after all holdout
and comparison invariants pass.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Mapping

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from momentum.backtest import run_m0_backtest  # noqa: E402
from momentum.data.structural_validation import (  # noqa: E402
    StructuralValidationResult,
    run_track_b_structural_validation,
)
from momentum.metrics import gross_metrics  # noqa: E402
from momentum.research import run_m2_track_b  # noqa: E402
from momentum.research.track_b_config import (  # noqa: E402
    SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
    SUPPORTED_STRUCTURAL_SPEC_VERSION,
    StructuralValidationSummary,
    TrackBConfig,
    TrackBConfigError,
    VALID_STRUCTURAL_STATUSES,
    load_track_b_config,
    validate_m1a_real_data_gate,
)
from momentum.signals.m2 import M2_SPEC_VERSION  # noqa: E402


DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "research_track_b.yaml"
DEFAULT_DATA_ROOT = REPO_ROOT / "data" / "processed"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "results" / "m2"
ACCOUNTING_ENGINE = "shared_daily_open_to_open_v1"
REQUIRED_METRICS = (
    "gross_return",
    "max_drawdown",
    "turnover",
    "trade_count",
    "average_holding",
    "average_holding_intervals",
    "average_holding_calendar_days",
    "reversal_count",
    "reversal_frequency",
    "carry_in_episode_count",
    "carry_in_position",
    "carry_out_episode_count",
    "carry_out_position",
    "return_count",
)
UNDEFINED_METRICS = frozenset({
    "average_holding",
    "average_holding_intervals",
    "average_holding_calendar_days",
    "reversal_frequency",
})


class M2ExecutionSafetyError(RuntimeError):
    """Raised when the M2 comparison violates a production safety contract."""


@dataclass(frozen=True)
class CanonicalWindow:
    symbol: str
    sample_start: pd.Timestamp
    sample_end: pd.Timestamp
    first_evaluation_return_timestamp: pd.Timestamp
    last_evaluation_return_timestamp: pd.Timestamp
    return_count: int


@dataclass(frozen=True)
class SymbolComparison:
    symbol: str
    window: CanonicalWindow
    m0: Any
    m2: Any
    m0_metrics: dict[str, Any]
    m2_metrics: dict[str, Any]
    signal_direction_agreement: float | None
    required_metrics: dict[str, Any]
    gate7: dict[str, Any]


def _json_safe(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, pd.Period):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    try:
        missing = pd.isna(value)
        if isinstance(missing, (bool, np.bool_)) and bool(missing):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _csv_safe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in result.columns:
        result[column] = result[column].map(
            lambda value: (
                json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True)
                if isinstance(_json_safe(value), (list, dict))
                else _json_safe(value)
            )
        )
    return result


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(_json_safe(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    _csv_safe_frame(frame).to_csv(path, index=False)


def _utc_timestamps(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame["timestamp"], utc=True)


def _validate_structural_identity(
    config: TrackBConfig,
    summary: StructuralValidationSummary,
) -> None:
    if summary.freeze_version != config.freeze_version:
        raise TrackBConfigError("structural validation freeze_version does not match current artifact")
    if summary.structural_spec_version != SUPPORTED_STRUCTURAL_SPEC_VERSION:
        raise TrackBConfigError("unsupported structural validation spec version")
    if summary.dataset_fingerprint_algorithm != SUPPORTED_DATASET_FINGERPRINT_ALGORITHM:
        raise TrackBConfigError("unsupported structural validation dataset fingerprint algorithm")
    if not summary.dataset_fingerprint:
        raise TrackBConfigError("structural validation dataset fingerprint is empty")


def _canonical_window(
    daily: pd.DataFrame,
    config: TrackBConfig,
    symbol: str,
) -> CanonicalWindow:
    selected = daily.loc[daily["symbol"].astype(str).eq(symbol)].copy()
    if selected.empty:
        raise M2ExecutionSafetyError(f"missing frozen primary symbol: {symbol}")
    timestamps = _utc_timestamps(selected)
    calendar = timestamps.dt.tz_localize(None).dt.to_period("M")

    def first_open(month: pd.Period) -> pd.Timestamp:
        rows = timestamps.loc[calendar.eq(month)]
        if rows.empty:
            raise M2ExecutionSafetyError(f"missing canonical boundary month {month} for {symbol}")
        return pd.Timestamp(rows.iloc[0])

    sample_start = first_open(config.development.start)
    sample_end = first_open(config.validation.end + 1)
    return_timestamps = timestamps.loc[
        timestamps.ge(sample_start) & timestamps.lt(sample_end)
    ]
    if return_timestamps.empty:
        raise M2ExecutionSafetyError(f"empty evaluation return window for {symbol}")
    return CanonicalWindow(
        symbol=symbol,
        sample_start=sample_start,
        sample_end=sample_end,
        first_evaluation_return_timestamp=pd.Timestamp(return_timestamps.iloc[0]),
        last_evaluation_return_timestamp=pd.Timestamp(return_timestamps.iloc[-1]),
        return_count=int(len(return_timestamps)),
    )


def _execution_frame(
    daily: pd.DataFrame,
    config: TrackBConfig,
    window: CanonicalWindow,
) -> pd.DataFrame:
    selected = daily.loc[daily["symbol"].astype(str).eq(window.symbol)].copy()
    timestamps = _utc_timestamps(selected)
    calendar = timestamps.dt.tz_localize(None).dt.to_period("M")
    mask = calendar.ge(config.warmup_data_start) & timestamps.le(window.sample_end)
    return selected.loc[mask].reset_index(drop=True)


def _timestamp_keys(values: pd.Series) -> list[int]:
    return [int(value.value) for value in pd.to_datetime(values, utc=True)]


def _check_terminal_and_window(
    result: Any,
    window: CanonicalWindow,
    label: str,
) -> list[int]:
    bars = result.bars
    if bars.empty:
        raise M2ExecutionSafetyError(f"{label} returned no bars")
    timestamps = _utc_timestamps(bars)
    if (timestamps > window.sample_end).any():
        raise M2ExecutionSafetyError(f"{label} contains bars after terminal boundary")
    if timestamps.iloc[-1] != window.sample_end:
        raise M2ExecutionSafetyError(f"{label} does not end at terminal boundary")
    if int(timestamps.eq(window.sample_end).sum()) != 1:
        raise M2ExecutionSafetyError(f"{label} has an invalid terminal boundary row")
    terminal = bars.loc[timestamps.eq(window.sample_end)].iloc[0]
    if not pd.isna(terminal.get("asset_return")) or not pd.isna(terminal.get("strategy_return")):
        raise M2ExecutionSafetyError(f"{label} terminal boundary returns must be NaN")
    if "strategy_return" not in bars:
        raise M2ExecutionSafetyError(f"{label} has no strategy_return column")
    return_timestamps = timestamps.loc[
        timestamps.ge(window.sample_start)
        & timestamps.lt(window.sample_end)
        & bars["strategy_return"].notna()
    ]
    if len(return_timestamps) != window.return_count:
        raise M2ExecutionSafetyError(
            f"{label} return_count does not match canonical window: "
            f"{len(return_timestamps)} != {window.return_count}"
        )
    keys = _timestamp_keys(return_timestamps)
    if keys[0] != window.first_evaluation_return_timestamp.value:
        raise M2ExecutionSafetyError(f"{label} first evaluation return timestamp mismatch")
    if keys[-1] != window.last_evaluation_return_timestamp.value:
        raise M2ExecutionSafetyError(f"{label} last evaluation return timestamp mismatch")
    if result.metrics.get("return_count") != window.return_count:
        raise M2ExecutionSafetyError(f"{label} metrics return_count mismatch")
    if (timestamps.eq(window.sample_end) & bars["strategy_return"].notna()).any():
        raise M2ExecutionSafetyError(f"{label} has a return at terminal boundary")
    return keys


def _check_shared_window(
    m0: Any,
    m2: Any,
    window: CanonicalWindow,
    expected_return_keys: list[int],
) -> None:
    m0_keys = _check_terminal_and_window(m0, window, "M0")
    m2_keys = _check_terminal_and_window(m2, window, "M2")
    if m0_keys != m2_keys:
        raise M2ExecutionSafetyError("M0/M2 evaluation return timestamps differ")
    if m0_keys != expected_return_keys:
        raise M2ExecutionSafetyError("M0/M2 evaluation return interval differs from canonical input")
    if _timestamp_keys(m0.bars["timestamp"]) != _timestamp_keys(m2.bars["timestamp"]):
        raise M2ExecutionSafetyError("M0/M2 execution bars differ")


def _check_metadata_identity(
    metadata: Mapping[str, Any],
    config: TrackBConfig,
    summary: StructuralValidationSummary,
    symbol: str,
    window: CanonicalWindow,
) -> None:
    expected = {
        "freeze_version": config.freeze_version,
        "structural_spec_version": summary.structural_spec_version,
        "dataset_fingerprint": summary.dataset_fingerprint,
        "dataset_fingerprint_algorithm": summary.dataset_fingerprint_algorithm,
        "symbol": symbol,
        "final_holdout_included": False,
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise M2ExecutionSafetyError(f"metadata identity mismatch for {key}")
    if metadata.get("spec_version") != M2_SPEC_VERSION:
        raise M2ExecutionSafetyError("M2 spec_version mismatch")
    if metadata.get("accounting_engine") != ACCOUNTING_ENGINE:
        raise M2ExecutionSafetyError("M2 accounting engine mismatch")
    if metadata.get("sample_start_timestamp") != window.sample_start.isoformat():
        raise M2ExecutionSafetyError("M2 sample_start metadata mismatch")
    if metadata.get("sample_end_timestamp") != window.sample_end.isoformat():
        raise M2ExecutionSafetyError("M2 sample_end metadata mismatch")


def _check_m0_identity(
    metadata: Mapping[str, Any],
    config: TrackBConfig,
    summary: StructuralValidationSummary,
    symbol: str,
) -> None:
    expected = {
        "freeze_version": config.freeze_version,
        "structural_spec_version": summary.structural_spec_version,
        "dataset_fingerprint": summary.dataset_fingerprint,
        "dataset_fingerprint_algorithm": summary.dataset_fingerprint_algorithm,
        "symbol": symbol,
        "final_holdout_included": False,
        "accounting_engine": ACCOUNTING_ENGINE,
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise M2ExecutionSafetyError(f"M0 metadata identity mismatch for {key}")


def _gate7_invariant(
    m0: Any,
    m2: Any,
    config: TrackBConfig,
    summary: StructuralValidationSummary,
    window: CanonicalWindow,
) -> dict[str, Any]:
    checks = {
        "same_dataset_identity": (
            m2.metadata.get("freeze_version") == config.freeze_version
            and m2.metadata.get("structural_spec_version") == summary.structural_spec_version
            and m2.metadata.get("dataset_fingerprint") == summary.dataset_fingerprint
        ),
        "same_symbol_and_market_contract": (
            m2.metadata.get("symbol") == window.symbol
            and m2.metadata.get("timezone") == config.timezone
            and m2.metadata.get("price_type") == config.price_type
            and m2.metadata.get("daily_boundary") == dict(config.daily_boundary)
        ),
        "same_canonical_window": (
            m2.metadata.get("sample_start_timestamp") == window.sample_start.isoformat()
            and m2.metadata.get("sample_end_timestamp") == window.sample_end.isoformat()
        ),
        "shared_daily_accounting": (
            m2.metadata.get("accounting_engine") == ACCOUNTING_ENGINE
            and m0.metadata.get("accounting_engine") == ACCOUNTING_ENGINE
        ),
        "documented_construction_rules_only": (
            m0.metadata.get("construction_rule") == "daily_close_lookback_target"
            and m2.metadata.get("construction_rule")
            == "12_calendar_month_formation_next_month_first_open"
            and m2.metadata.get("split_assignment") == "holding_month"
        ),
        "no_pooling_or_selection": True,
    }
    return {
        "construction_invariant_pass": all(checks.values()),
        "checks": checks,
        "performance_not_used_for_gate": True,
    }


def _comparison_row(item: SymbolComparison, config: TrackBConfig, summary: StructuralValidationSummary) -> dict[str, Any]:
    row: dict[str, Any] = {
        "symbol": item.symbol,
        "freeze_version": config.freeze_version,
        "m2_spec_version": M2_SPEC_VERSION,
        "structural_spec_version": summary.structural_spec_version,
        "dataset_fingerprint": summary.dataset_fingerprint,
        "sample_start": item.window.sample_start,
        "sample_end": item.window.sample_end,
        "first_evaluation_return_timestamp": item.window.first_evaluation_return_timestamp,
        "last_evaluation_return_timestamp": item.window.last_evaluation_return_timestamp,
        "return_count": item.window.return_count,
        "signal_direction_agreement": item.signal_direction_agreement,
        "required_metrics_pass": item.required_metrics["passed"],
        "gate7_construction_invariant_pass": item.gate7["construction_invariant_pass"],
    }
    metric_names = (
        "gross_return", "max_drawdown", "turnover", "trade_count",
        "average_holding", "average_holding_intervals",
        "average_holding_calendar_days", "reversal_count", "reversal_frequency",
        "carry_in_episode_count", "carry_in_position", "carry_out_episode_count",
        "carry_out_position", "return_count",
    )
    for name in metric_names:
        row[f"m0_{name}"] = item.m0_metrics.get(name)
        row[f"m2_{name}"] = item.m2_metrics.get(name)
        if isinstance(item.m0_metrics.get(name), (int, float)) and isinstance(item.m2_metrics.get(name), (int, float)):
            row[f"delta_{name}"] = item.m2_metrics.get(name) - item.m0_metrics.get(name)
        else:
            row[f"delta_{name}"] = None
    return row


def _required_metrics_status(
    m0_metrics: Mapping[str, Any],
    m2_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    missing: list[str] = []
    invalid: list[str] = []
    for label, metrics in (("m0", m0_metrics), ("m2", m2_metrics)):
        for name in REQUIRED_METRICS:
            if name not in metrics:
                missing.append(f"{label}.{name}")
                continue
            value = metrics[name]
            if value is None and name in UNDEFINED_METRICS:
                continue
            if value is None:
                invalid.append(f"{label}.{name}: null")
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                invalid.append(f"{label}.{name}: non-numeric")
                continue
            if not math.isfinite(numeric):
                invalid.append(f"{label}.{name}: non-finite")
                continue
            if name in {"trade_count", "reversal_count", "carry_in_episode_count", "carry_out_episode_count", "return_count"} and numeric < 0:
                invalid.append(f"{label}.{name}: negative")
            if name == "turnover" and numeric < 0:
                invalid.append(f"{label}.{name}: negative")
    agreement = m2_metrics.get("signal_direction_agreement")
    if agreement is None:
        invalid.append("m2.signal_direction_agreement: null")
    else:
        try:
            agreement_value = float(agreement)
        except (TypeError, ValueError):
            invalid.append("m2.signal_direction_agreement: non-numeric")
        else:
            if not math.isfinite(agreement_value) or not 0.0 <= agreement_value <= 1.0:
                invalid.append("m2.signal_direction_agreement: outside [0, 1]")
    return {
        "passed": not missing and not invalid,
        "missing": missing,
        "invalid": invalid,
    }


def _run_symbol(
    daily: pd.DataFrame,
    config: TrackBConfig,
    summary: StructuralValidationSummary,
    symbol: str,
) -> SymbolComparison:
    window = _canonical_window(daily, config, symbol)
    execution = _execution_frame(daily, config, window)
    if execution.empty or pd.to_datetime(execution["timestamp"], utc=True).iloc[-1] != window.sample_end:
        raise M2ExecutionSafetyError(f"invalid execution frame for {symbol}")

    m2 = run_m2_track_b(
        daily,
        config,
        summary,
        symbol=symbol,
        sample_start=window.sample_start,
        sample_end=window.sample_end,
    )
    m0 = run_m0_backtest(
        execution,
        metadata={
            "track": "Track B",
            "workstream": "M0 Daily Comparator Baseline",
            "freeze_version": config.freeze_version,
            "structural_spec_version": summary.structural_spec_version,
            "dataset_fingerprint": summary.dataset_fingerprint,
            "dataset_fingerprint_algorithm": summary.dataset_fingerprint_algorithm,
            "symbol": symbol,
            "sample_start_timestamp": window.sample_start.isoformat(),
            "sample_end_timestamp": window.sample_end.isoformat(),
            "final_holdout_included": False,
            "construction_rule": "daily_close_lookback_target",
            "accounting_engine": ACCOUNTING_ENGINE,
        },
    )
    m0_metrics = gross_metrics(
        m0.ledger, m0.bars,
        sample_start=window.sample_start,
        sample_end=window.sample_end,
    )
    m2_metrics = gross_metrics(
        m2.ledger, m2.bars,
        sample_start=window.sample_start,
        sample_end=window.sample_end,
    )
    signal_direction_agreement = m2.metrics.get("signal_direction_agreement")
    m2_metrics["signal_direction_agreement"] = signal_direction_agreement
    m2 = m2.__class__(bars=m2.bars, ledger=m2.ledger, metrics=m2_metrics, metadata=m2.metadata)
    m0 = m0.__class__(bars=m0.bars, ledger=m0.ledger, metrics=m0_metrics, metadata=m0.metadata)
    _check_metadata_identity(m2.metadata, config, summary, symbol, window)
    _check_m0_identity(m0.metadata, config, summary, symbol)
    execution_timestamps = _utc_timestamps(execution)
    expected_return_keys = _timestamp_keys(execution_timestamps.loc[
        execution_timestamps.ge(window.sample_start)
        & execution_timestamps.lt(window.sample_end)
    ])
    _check_shared_window(m0, m2, window, expected_return_keys)
    if m0_metrics["return_count"] != m2_metrics["return_count"]:
        raise M2ExecutionSafetyError(f"M0/M2 return_count mismatch for {symbol}")
    required_metrics = _required_metrics_status(m0_metrics, m2_metrics)
    if not required_metrics["passed"]:
        raise M2ExecutionSafetyError(
            f"required metrics failed for {symbol}: {required_metrics}"
        )
    gate7 = _gate7_invariant(m0, m2, config, summary, window)
    if not gate7["construction_invariant_pass"]:
        raise M2ExecutionSafetyError(f"Gate M2 #7 failed for {symbol}: {gate7}")
    return SymbolComparison(
        symbol=symbol,
        window=window,
        m0=m0,
        m2=m2,
        m0_metrics=m0_metrics,
        m2_metrics=m2_metrics,
        signal_direction_agreement=signal_direction_agreement,
        required_metrics=required_metrics,
        gate7=gate7,
    )


def _gate_summary(items: list[SymbolComparison], config: TrackBConfig) -> dict[str, Any]:
    complete = len(items) == len(config.primary_symbols)
    required_metrics_by_symbol = {
        item.symbol: item.required_metrics["passed"] for item in items
    }
    checks = {
        "monthly_timing_and_terminal_boundary_verified": complete,
        "warmup_causal_state_continuity_verified": complete,
        "common_evaluation_window_verified": complete,
        "final_holdout_sealed": complete,
        "frozen_primary_symbols_independently_executed": complete,
        "required_metrics_reported": complete and all(required_metrics_by_symbol.values()),
        "construction_rules_only_invariant": complete and all(
            item.gate7["construction_invariant_pass"] for item in items
        ),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "primary_symbol_count": len(items),
        "required_primary_symbol_count": len(config.primary_symbols),
        "required_metrics_by_symbol": required_metrics_by_symbol,
        "performance_not_used_for_gate_7": True,
    }


def _report(
    items: list[SymbolComparison],
    config: TrackBConfig,
    summary: StructuralValidationSummary,
    gate: Mapping[str, Any],
    execution_timestamp: datetime,
) -> str:
    lines = [
        "# M2 Practical Monthly Comparator",
        "",
        f"- execution_timestamp: {execution_timestamp.isoformat()}",
        f"- freeze_version: {config.freeze_version}",
        f"- m2_spec_version: {M2_SPEC_VERSION}",
        f"- structural_spec_version: {summary.structural_spec_version}",
        f"- dataset_fingerprint: {summary.dataset_fingerprint}",
        f"- symbols: {len(items)}/{len(config.primary_symbols)} primary symbols",
        "- final_holdout_included: false",
        "",
        "## Gate M2",
        "",
        f"- status: **{gate['status']}**",
        "- Gate #7 is an implementation invariant; performance is not used to decide it.",
        "- Gate #7 construction invariant: PASS.",
        "",
        "| Symbol | Sample start | Sample end | Return count | Signal agreement | Gate #7 |",
        "|---|---|---|---:|---:|---|",
    ]
    for item in items:
        agreement = "NA" if item.signal_direction_agreement is None else f"{item.signal_direction_agreement:.6g}"
        lines.append(
            f"| {item.symbol} | {item.window.sample_start.isoformat()} | "
            f"{item.window.sample_end.isoformat()} | {item.window.return_count} | "
            f"{agreement} | PASS |"
        )
    lines.extend([
        "",
        "Performance metrics are available in comparison.csv and per-symbol JSON artifacts.",
        "Final Holdout is sealed; no holdout metrics are included in this report.",
    ])
    return "\n".join(lines) + "\n"


def _save_outputs(
    output_root: Path,
    items: list[SymbolComparison],
    validation: StructuralValidationResult,
    metadata: Mapping[str, Any],
    comparison: pd.DataFrame,
    report: str,
    execution_timestamp: datetime,
) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = execution_timestamp.strftime("%Y%m%dT%H%M%S%fZ")
    output_directory = output_root / f"freeze_v{validation.summary.freeze_version}_{stamp}"
    if output_directory.exists():
        raise M2ExecutionSafetyError(f"refusing to overwrite existing output: {output_directory}")
    staging = Path(tempfile.mkdtemp(prefix=".m2-", dir=output_root))
    try:
        _write_json(staging / "metadata.json", metadata)
        _write_csv(staging / "comparison.csv", comparison)
        _write_json(staging / "structural_validation_summary.json", asdict(validation.summary))
        _write_csv(staging / "structural_validation_diagnostics.csv", validation.symbol_diagnostics)
        (staging / "report.md").write_text(report, encoding="utf-8")
        symbols_root = staging / "symbols"
        for item in items:
            symbol_root = symbols_root / item.symbol
            symbol_root.mkdir(parents=True, exist_ok=True)
            _write_json(symbol_root / "m0_metrics.json", item.m0_metrics)
            _write_json(symbol_root / "m2_metrics.json", item.m2_metrics)
            _write_csv(symbol_root / "m0_bars.csv", item.m0.bars)
            _write_csv(symbol_root / "m2_bars.csv", item.m2.bars)
            _write_csv(symbol_root / "m0_ledger.csv", item.m0.ledger)
            _write_csv(symbol_root / "m2_ledger.csv", item.m2.ledger)
            _write_json(symbol_root / "window.json", asdict(item.window))
            _write_json(symbol_root / "required_metrics.json", item.required_metrics)
            _write_json(symbol_root / "gate_m2_7.json", item.gate7)
        staging.rename(output_directory)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return output_directory


def main(
    *,
    config_path: Path | None = None,
    data_root: Path | None = None,
    output_root: Path | None = None,
) -> int:
    """Execute the frozen M2 CLI flow and return a process exit code."""
    config_path = config_path or DEFAULT_CONFIG_PATH
    data_root = data_root or DEFAULT_DATA_ROOT
    output_root = output_root or DEFAULT_OUTPUT_ROOT
    execution_timestamp = datetime.now(timezone.utc)
    try:
        config = load_track_b_config(config_path)
        validation = run_track_b_structural_validation(
            data_root=data_root,
            config_path=config_path,
        )
        _validate_structural_identity(config, validation.summary)
        validate_m1a_real_data_gate(
            config,
            validation.summary.status_by_symbol,
            validation.summary.freeze_version,
        )
        items = [
            _run_symbol(validation.daily_ohlc, config, validation.summary, symbol)
            for symbol in config.primary_symbols
        ]
        if len(items) != len(config.primary_symbols) or {item.symbol for item in items} != set(config.primary_symbols):
            raise M2ExecutionSafetyError("M2 did not execute exactly the frozen primary universe")
        gate = _gate_summary(items, config)
        if gate["status"] != "PASS":
            raise M2ExecutionSafetyError(f"Gate M2 failed: {gate}")
        comparison = pd.DataFrame([
            _comparison_row(item, config, validation.summary) for item in items
        ])
        if len(comparison) != len(config.primary_symbols):
            raise M2ExecutionSafetyError("comparison.csv does not contain exactly the primary symbols")
        metadata = {
            "workstream": "M2 Practical Monthly Comparator",
            "execution_timestamp": execution_timestamp.isoformat(),
            "freeze_version": config.freeze_version,
            "m2_spec_version": M2_SPEC_VERSION,
            "structural_spec_version": validation.summary.structural_spec_version,
            "dataset_fingerprint": validation.summary.dataset_fingerprint,
            "dataset_fingerprint_algorithm": validation.summary.dataset_fingerprint_algorithm,
            "symbols": list(config.primary_symbols),
            "development_period": f"{config.development.start}..{config.development.end}",
            "validation_period": f"{config.validation.start}..{config.validation.end}",
            "sample_start_by_symbol": {
                item.symbol: item.window.sample_start.isoformat() for item in items
            },
            "sample_end_by_symbol": {
                item.symbol: item.window.sample_end.isoformat() for item in items
            },
            "result_level": "gross_price_only",
            "academic_mop_replication": False,
            "final_holdout_included": False,
            "accounting_engine": ACCOUNTING_ENGINE,
            "gate_m2": gate,
            "execution_identity": {
                "symbols_executed": f"{len(items)}/{len(config.primary_symbols)}",
                "gate_m2": gate["status"],
            },
        }
        report = _report(items, config, validation.summary, gate, execution_timestamp)
        output_directory = _save_outputs(
            output_root,
            items,
            validation,
            metadata,
            comparison,
            report,
            execution_timestamp,
        )
    except Exception as exc:  # pragma: no cover - focused tests cover paths
        print(f"M2 execution error: {exc}", file=sys.stderr)
        return 1

    print("M2 REAL EXECUTION COMPLETE")
    print(f"freeze_version: {config.freeze_version}")
    print(f"m2_spec_version: {M2_SPEC_VERSION}")
    print(f"dataset_fingerprint: {validation.summary.dataset_fingerprint}")
    print(f"primary symbols: {len(items)}/{len(config.primary_symbols)}")
    print(f"Gate M2: {gate['status']}")
    print("final_holdout_included: False")
    print(f"output directory: {output_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
