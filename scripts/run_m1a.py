"""Run the gated Track B M1A real-data execution from the repository root.

Usage::

    python scripts/run_m1a.py

The command re-runs structural validation, passes its canonical Daily dataset
and validation summary directly to ``run_m1a_track_b``, and writes a unique
freeze-versioned result directory only after the M1A holdout safety checks
pass.  This module does not provide a synthetic execution path.
"""

from __future__ import annotations

from dataclasses import asdict
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

from momentum.data.structural_validation import (  # noqa: E402
    StructuralValidationResult,
    run_track_b_structural_validation,
)
from momentum.research import run_m1a_track_b  # noqa: E402
from momentum.research.inference import SPEC_VERSION  # noqa: E402
from momentum.research.m1a import M1AResult  # noqa: E402
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


DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "research_track_b.yaml"
DEFAULT_DATA_ROOT = REPO_ROOT / "data" / "processed"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "results" / "m1a"


class M1AExecutionSafetyError(RuntimeError):
    """Raised when a result violates the frozen M1A execution contract."""


def _json_safe(value: Any) -> Any:
    """Convert pandas/numpy values to strict JSON-compatible native values."""
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
    """Return a copy whose cells are safe and readable in CSV output."""
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


def _validate_structural_identity(
    config: TrackBConfig,
    summary: StructuralValidationSummary,
) -> None:
    if summary.freeze_version != config.freeze_version:
        raise TrackBConfigError(
            "structural validation freeze_version does not match current artifact"
        )
    if summary.structural_spec_version != SUPPORTED_STRUCTURAL_SPEC_VERSION:
        raise TrackBConfigError("unsupported structural validation spec version")
    if summary.dataset_fingerprint_algorithm != SUPPORTED_DATASET_FINGERPRINT_ALGORITHM:
        raise TrackBConfigError("unsupported structural validation dataset fingerprint algorithm")
    if not summary.dataset_fingerprint:
        raise TrackBConfigError("structural validation dataset fingerprint is empty")


def _period_from_value(value: Any) -> pd.Period:
    if isinstance(value, pd.Period):
        return value.asfreq("M")
    return pd.Period(str(value), freq="M")


def _frame_has_holdout(frame: pd.DataFrame, config: TrackBConfig) -> bool:
    if frame.empty:
        return False
    if "split" in frame.columns and (frame["split"].astype(str) == "final_holdout").any():
        return True
    if "sample_period" in frame.columns:
        for value in frame["sample_period"].tolist():
            if pd.isna(value):
                continue
            if any(
                _period_from_value(part) > config.validation.end
                for part in str(value).split("/")
            ):
                return True
    if "outcome_month" not in frame.columns:
        return False
    for value in frame["outcome_month"].tolist():
        if pd.isna(value):
            continue
        if _period_from_value(value) > config.validation.end:
            return True
    return False


def _check_result_safety(
    result: M1AResult,
    config: TrackBConfig,
    summary: StructuralValidationSummary,
) -> None:
    metadata = result.metadata
    violations: list[str] = []
    if metadata.get("final_holdout_included") is not False:
        violations.append("metadata.final_holdout_included is not False")
    if metadata.get("freeze_version") != config.freeze_version:
        violations.append("result freeze_version does not match current artifact")
    if metadata.get("spec_version") != SPEC_VERSION:
        violations.append("result M1A spec_version does not match supported spec")
    if metadata.get("structural_spec_version") != summary.structural_spec_version:
        violations.append("result structural_spec_version does not match validation summary")
    if metadata.get("dataset_fingerprint") != summary.dataset_fingerprint:
        violations.append("result dataset_fingerprint does not match validation summary")
    if metadata.get("dataset_fingerprint_algorithm") != summary.dataset_fingerprint_algorithm:
        violations.append("result dataset_fingerprint_algorithm does not match validation summary")

    for name, frame in (
        ("observations", result.observations),
        ("regression_results", result.regression_results),
        ("sign_conditioned_results", result.sign_conditioned_results),
    ):
        if _frame_has_holdout(frame, config):
            violations.append(f"{name} contains Final Holdout information")

    if violations:
        raise M1AExecutionSafetyError("; ".join(violations))


def _status_line(symbols: tuple[str, ...], statuses: Mapping[str, str]) -> str:
    eligible = sum(statuses.get(symbol) in VALID_STRUCTURAL_STATUSES for symbol in symbols)
    warnings = sum(statuses.get(symbol) == "pass_with_warning" for symbol in symbols)
    line = f"{eligible}/{len(symbols)} pass"
    if warnings:
        line += f" (pass_with_warning: {warnings})"
    return line


def _count_observations(result: M1AResult, split: str, role: str) -> int:
    observations = result.observations
    if observations.empty:
        return 0
    return int(((observations["split"] == split) & (observations["universe_role"] == role)).sum())


def _format_number(value: Any) -> str:
    if value is None:
        return "NA"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(numeric):
        return "NA"
    return f"{numeric:.6g}"


def _find_result_row(frame: pd.DataFrame, *, analysis_name: str, split: str) -> pd.Series | None:
    if frame.empty:
        return None
    period = frame["sample_period"].astype(str).str.startswith(split)
    rows = frame[
        (frame.get("symbol") == "__pooled__")
        & (frame.get("analysis_name") == analysis_name)
        & period
    ]
    return rows.iloc[0] if not rows.empty else None


def _print_pooled_summary(result: M1AResult, split: str) -> None:
    continuous = _find_result_row(
        result.regression_results, analysis_name="continuous_regression", split=split
    )
    sign = _find_result_row(
        result.regression_results, analysis_name="sign_predictor_regression", split=split
    )
    effects = result.sign_conditioned_results
    difference = None
    if not effects.empty:
        rows = effects[
            (effects["symbol"] == "__pooled__")
            & (effects["metric"] == "difference")
            & effects["sample_period"].astype(str).str.startswith(split)
        ]
        if not rows.empty:
            difference = rows.iloc[0]

    print(f"  {split} pooled primary:")
    if continuous is None:
        print("    continuous: unavailable")
    else:
        ci = f"[{_format_number(continuous.get('ci_lower'))}, {_format_number(continuous.get('ci_upper'))}]"
        print(
            "    continuous beta="
            f"{_format_number(continuous.get('beta'))}, "
            f"se={_format_number(continuous.get('standard_error'))}, "
            f"t={_format_number(continuous.get('t_stat'))}, CI={ci}, "
            f"status={continuous.get('inference_status')}"
        )
    if sign is not None:
        print(
            "    sign beta="
            f"{_format_number(sign.get('beta'))}, status={sign.get('inference_status')}"
        )
    if difference is not None:
        print(
            "    sign-conditioned difference="
            f"{_format_number(difference.get('estimate'))}, "
            f"status={difference.get('inference_status')}"
        )


def _print_summary(
    result: M1AResult,
    config: TrackBConfig,
    validation: StructuralValidationResult,
    eligible_secondary: tuple[str, ...],
    output_directory: Path,
) -> None:
    statuses = validation.summary.status_by_symbol
    excluded_secondary = [
        symbol for symbol in config.secondary_symbols if symbol not in eligible_secondary
    ]
    print("M1A REAL EXECUTION COMPLETE")
    print()
    print(f"freeze_version: {config.freeze_version}")
    print(f"structural_spec_version: {validation.summary.structural_spec_version}")
    print(f"m1a_spec_version: {result.metadata.get('spec_version')}")
    print(f"dataset_fingerprint: {validation.summary.dataset_fingerprint}")
    print()
    print("Structural validation:")
    print(f"  Primary: {_status_line(config.primary_symbols, statuses)}")
    print(f"  Secondary: {_status_line(config.secondary_symbols, statuses)}")
    if excluded_secondary:
        print(f"  Secondary excluded from robustness: {', '.join(excluded_secondary)}")
    else:
        print("  Secondary excluded from robustness: none")
    print()
    print("Development:")
    print(f"  primary observations: {_count_observations(result, 'development', 'primary')}")
    print(
        "  secondary observations: "
        f"{_count_observations(result, 'development', 'secondary_cross_robustness')}"
    )
    _print_pooled_summary(result, str(config.development.start))
    print()
    print("Validation:")
    print(f"  primary observations: {_count_observations(result, 'validation', 'primary')}")
    print(
        "  secondary observations: "
        f"{_count_observations(result, 'validation', 'secondary_cross_robustness')}"
    )
    _print_pooled_summary(result, str(config.validation.start))
    print()
    print(f"inference unavailable count: {result.diagnostics.get('inference_unavailable_count', 0)}")
    print(f"final_holdout_included: {result.metadata.get('final_holdout_included')}")
    print()
    print(f"output directory: {output_directory}")


def _save_outputs(
    output_root: Path,
    result: M1AResult,
    validation: StructuralValidationResult,
    metadata: Mapping[str, Any],
    execution_timestamp: datetime,
) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = execution_timestamp.strftime("%Y%m%dT%H%M%S%fZ")
    output_directory = output_root / f"freeze_v{validation.summary.freeze_version}_{stamp}"
    staging = Path(tempfile.mkdtemp(prefix=".m1a-", dir=output_root))
    try:
        _write_csv(staging / "observations.csv", result.observations)
        _write_csv(staging / "regression_results.csv", result.regression_results)
        _write_csv(staging / "sign_conditioned_results.csv", result.sign_conditioned_results)
        _write_json(staging / "diagnostics.json", result.diagnostics)
        _write_json(staging / "metadata.json", metadata)
        _write_json(staging / "structural_validation_summary.json", asdict(validation.summary))
        _write_csv(staging / "structural_validation_diagnostics.csv", validation.symbol_diagnostics)
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
    """Execute the frozen M1A CLI flow and return a process exit code."""
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
        eligible_secondary = validate_m1a_real_data_gate(
            config,
            validation.summary.status_by_symbol,
            validation.summary.freeze_version,
        )
        result = run_m1a_track_b(
            validation.daily_ohlc,
            config,
            validation.summary,
            include_sensitivity=True,
        )
        _check_result_safety(result, config, validation.summary)

        metadata = dict(result.metadata)
        metadata.update({
            "execution_timestamp": execution_timestamp.isoformat(),
            "freeze_version": config.freeze_version,
            "m1a_spec_version": result.metadata.get("spec_version"),
            "structural_spec_version": validation.summary.structural_spec_version,
            "dataset_fingerprint": validation.summary.dataset_fingerprint,
            "dataset_fingerprint_algorithm": validation.summary.dataset_fingerprint_algorithm,
        })
        output_directory = _save_outputs(
            output_root,
            result,
            validation,
            metadata,
            execution_timestamp,
        )
    except Exception as exc:  # pragma: no cover - exercised through focused CLI tests
        print(f"M1A execution error: {exc}", file=sys.stderr)
        return 1

    _print_summary(result, config, validation, eligible_secondary, output_directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
