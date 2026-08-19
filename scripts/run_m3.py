"""Run the gated M3 multi-symbol common-rule execution."""

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
from momentum.data.track_b import compute_track_b_daily_fingerprint  # noqa: E402
from momentum.research.m3 import (  # noqa: E402
    ACCOUNTING_ENGINE,
    M3_SPEC_VERSION,
    TSH_METHOD_ROLE,
    M3SymbolResult,
    run_m3_symbol,
)
from momentum.research.track_b_config import (  # noqa: E402
    SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
    SUPPORTED_STRUCTURAL_SPEC_VERSION,
    StructuralValidationSummary,
    TrackBConfig,
    TrackBConfigError,
    load_track_b_config,
    validate_m1a_real_data_gate,
)
from momentum.signals.m2 import M2_SPEC_VERSION  # noqa: E402
from momentum.signals.tsh import TSH_SPEC_VERSION  # noqa: E402


DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "research_track_b.yaml"
DEFAULT_DATA_ROOT = REPO_ROOT / "data" / "processed"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "results" / "m3"


class M3RunnerError(RuntimeError):
    """Raised when the M3 production contract cannot be satisfied."""


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


def _validate_identity(config: TrackBConfig, summary: StructuralValidationSummary) -> None:
    if summary.freeze_version != config.freeze_version:
        raise TrackBConfigError("structural validation freeze_version does not match config")
    if summary.structural_spec_version != SUPPORTED_STRUCTURAL_SPEC_VERSION:
        raise TrackBConfigError("unsupported structural validation spec version")
    if summary.dataset_fingerprint_algorithm != SUPPORTED_DATASET_FINGERPRINT_ALGORITHM:
        raise TrackBConfigError("unsupported dataset fingerprint algorithm")
    if not summary.dataset_fingerprint:
        raise TrackBConfigError("dataset fingerprint is empty")


def _validate_full_dataset_fingerprint(
    daily: pd.DataFrame,
    summary: StructuralValidationSummary,
) -> None:
    actual = compute_track_b_daily_fingerprint(daily)
    if actual != summary.dataset_fingerprint:
        raise TrackBConfigError("full Track B dataset fingerprint does not match validation summary")


def _strategy_rows(item: M3SymbolResult, config: TrackBConfig, summary: StructuralValidationSummary) -> list[dict[str, Any]]:
    rows = []
    strategies = (("m0", item.m0_metrics), ("tsh", item.tsh_metrics))
    if item.m2_metrics is not None:
        strategies += (("m2", item.m2_metrics),)
    for strategy, metrics in strategies:
        row = {
            "symbol": item.symbol,
            "universe_role": item.universe_role,
            "strategy": strategy,
            "freeze_version": config.freeze_version,
            "structural_spec_version": summary.structural_spec_version,
            "dataset_fingerprint": summary.dataset_fingerprint,
        }
        row.update(metrics)
        rows.append(row)
    return rows


def _monthly_history(item: M3SymbolResult) -> pd.DataFrame:
    history = item.tsh_generated.monthly_history.copy()
    history.insert(1, "universe_role", item.universe_role)
    history["m3_spec_version"] = M3_SPEC_VERSION
    history["tsh_spec_version"] = TSH_SPEC_VERSION
    history["method_role"] = TSH_METHOD_ROLE
    return history


def _comparison_frame(items: list[M3SymbolResult]) -> pd.DataFrame:
    rows = [item.comparison for item in items if item.comparison is not None]
    return pd.DataFrame(rows)


def _gate(
    config: TrackBConfig,
    summary: StructuralValidationSummary,
    items: list[M3SymbolResult],
    failures: Mapping[str, str],
    eligible_secondary: tuple[str, ...],
) -> dict[str, Any]:
    primary_items = [item for item in items if item.universe_role == "primary"]
    secondary_items = [item for item in items if item.universe_role == "secondary_cross_robustness"]
    primary_symbols = [item.symbol for item in primary_items]
    checks = {
        "frozen_track_b_identity_verified": summary.freeze_version == config.freeze_version,
        "structural_validation_gate_satisfied": all(
            summary.status_by_symbol.get(symbol) in {"pass", "pass_with_warning"}
            for symbol in config.primary_symbols
        ),
        "m3_spec_version": M3_SPEC_VERSION == "m3-multi-symbol-v1",
        "tsh_spec_version": TSH_SPEC_VERSION == "tsh-huang-v1",
        "tsh_method_role": TSH_METHOD_ROLE == "tsh_track_b_practical",
        "primary_symbols_all_executed": primary_symbols == list(config.primary_symbols),
        "secondary_role_separated": all(
            item.universe_role == "secondary_cross_robustness" for item in secondary_items
        ),
        "m0_m3_common_rule_verified": all(
            item.m0.metadata.get("lookback_intervals") == 240 for item in items
        ),
        "m2_valid_mask_used": all(item.comparison is not None for item in primary_items),
        "shared_execution_interval_verified": all(
            item.m0.bars["timestamp"].equals(item.tsh.bars["timestamp"])
            and (item.m2 is None or item.m0.bars["timestamp"].equals(item.m2.bars["timestamp"]))
            for item in items
        ),
        "close_to_close_and_open_to_open_separated": all(
            item.tsh_generated.monthly_history["monthly_return"].notna().all()
            and item.tsh.metadata.get("accounting_engine") == ACCOUNTING_ENGINE
            for item in items
        ),
        "final_holdout_sealed": all(
            item.m0.metadata.get("final_holdout_included") is False
            and item.tsh.metadata.get("final_holdout_included") is False
            and (item.m2 is None or item.m2.metadata.get("final_holdout_included") is False)
            for item in items
        ),
        "no_portfolio_aggregation": True,
        "deterministic_symbol_order": [item.symbol for item in items]
        == [symbol for symbol in config.primary_symbols + eligible_secondary if symbol in {item.symbol for item in items}],
        "primary_failures_absent": not any(symbol in failures for symbol in config.primary_symbols),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "primary_symbol_count": len(primary_items),
        "required_primary_symbol_count": len(config.primary_symbols),
        "eligible_secondary_count": len(eligible_secondary),
        "secondary_executed_count": len(secondary_items),
        "failures": dict(failures),
        "performance_not_used_for_gate": True,
    }


def _save_outputs(
    output_root: Path,
    validation: StructuralValidationResult,
    items: list[M3SymbolResult],
    config: TrackBConfig,
    metadata: Mapping[str, Any],
    gate: Mapping[str, Any],
    execution_timestamp: datetime,
) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = execution_timestamp.strftime("%Y%m%dT%H%M%S%fZ")
    output_directory = output_root / f"freeze_v{validation.summary.freeze_version}_{stamp}"
    if output_directory.exists():
        raise M3RunnerError(f"refusing to overwrite existing output: {output_directory}")
    staging = Path(tempfile.mkdtemp(prefix=".m3-", dir=output_root))
    try:
        _write_json(staging / "metadata.json", metadata)
        _write_json(staging / "gate_m3.json", gate)
        _write_json(staging / "structural_validation_summary.json", asdict(validation.summary))
        _write_csv(staging / "structural_validation_diagnostics.csv", validation.symbol_diagnostics)

        metrics = pd.DataFrame([
            row for item in items for row in _strategy_rows(item, config, validation.summary)
        ])
        _write_csv(staging / "symbol_metrics.csv", metrics)
        years = pd.concat([item.year_diagnostics for item in items], ignore_index=True)
        _write_csv(staging / "symbol_year.csv", years)
        histories = pd.concat([_monthly_history(item) for item in items], ignore_index=True)
        _write_csv(staging / "monthly_history.csv", histories)
        _write_csv(staging / "tsm_tsh_comparison.csv", _comparison_frame(items))

        symbols_root = staging / "symbols"
        for item in items:
            symbol_root = symbols_root / item.symbol
            symbol_root.mkdir(parents=True, exist_ok=True)
            _write_json(symbol_root / "metadata.json", {
                "symbol": item.symbol,
                "universe_role": item.universe_role,
                "m0_metadata": item.m0.metadata,
                "m2_metadata": None if item.m2 is None else item.m2.metadata,
                "tsh_metadata": item.tsh.metadata,
            })
            _write_json(symbol_root / "window.json", asdict(item.window))
            for name, result in (("m0", item.m0), ("m2", item.m2), ("tsh", item.tsh)):
                if result is None:
                    continue
                _write_csv(symbol_root / f"{name}_bars.csv", result.bars)
                _write_csv(symbol_root / f"{name}_ledger.csv", result.ledger)
            _write_csv(symbol_root / "monthly_history.csv", _monthly_history(item))
            if item.comparison is not None:
                _write_json(symbol_root / "comparison.json", item.comparison)
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
    config_path = config_path or DEFAULT_CONFIG_PATH
    data_root = data_root or DEFAULT_DATA_ROOT
    output_root = output_root or DEFAULT_OUTPUT_ROOT
    execution_timestamp = datetime.now(timezone.utc)
    try:
        config = load_track_b_config(config_path)
        validation = run_track_b_structural_validation(data_root=data_root, config_path=config_path)
        _validate_identity(config, validation.summary)
        _validate_full_dataset_fingerprint(validation.daily_ohlc, validation.summary)
        eligible_secondary = validate_m1a_real_data_gate(
            config,
            validation.summary.status_by_symbol,
            validation.summary.freeze_version,
        )

        ordered_roles = [(symbol, "primary") for symbol in config.primary_symbols]
        ordered_roles.extend(
            (symbol, "secondary_cross_robustness")
            for symbol in config.secondary_symbols
            if symbol in eligible_secondary
        )
        items: list[M3SymbolResult] = []
        failures: dict[str, str] = {}
        for symbol, role in ordered_roles:
            try:
                items.append(run_m3_symbol(
                    validation.daily_ohlc,
                    config,
                    validation.summary,
                    symbol=symbol,
                    universe_role=role,
                ))
            except Exception as exc:
                failures[symbol] = str(exc)
                if role == "primary":
                    raise M3RunnerError(f"primary symbol {symbol} failed: {exc}") from exc

        gate = _gate(config, validation.summary, items, failures, eligible_secondary)
        if gate["status"] != "PASS":
            raise M3RunnerError(f"Gate M3 failed: {gate}")

        primary_symbols = [item.symbol for item in items if item.universe_role == "primary"]
        secondary_symbols = [item.symbol for item in items if item.universe_role == "secondary_cross_robustness"]
        metadata = {
            "workstream": "M3 Multi-Symbol Common Rule",
            "execution_timestamp": execution_timestamp.isoformat(),
            "m3_spec_version": M3_SPEC_VERSION,
            "freeze_version": config.freeze_version,
            "structural_spec_version": validation.summary.structural_spec_version,
            "dataset_fingerprint": validation.summary.dataset_fingerprint,
            "dataset_fingerprint_algorithm": validation.summary.dataset_fingerprint_algorithm,
            "tsh_spec_version": TSH_SPEC_VERSION,
            "tsh_method_role": TSH_METHOD_ROLE,
            "accounting_engine": ACCOUNTING_ENGINE,
            "final_holdout_included": False,
            "symbols": [item.symbol for item in items],
            "primary_symbols": primary_symbols,
            "secondary_symbols": secondary_symbols,
            "development_period": f"{config.development.start}..{config.development.end}",
            "validation_period": f"{config.validation.start}..{config.validation.end}",
            "gate_m3": gate,
        }
        output_directory = _save_outputs(
            output_root,
            validation,
            items,
            config,
            metadata,
            gate,
            execution_timestamp,
        )
    except Exception as exc:
        print(f"M3 execution error: {exc}", file=sys.stderr)
        return 1

    print("M3 REAL EXECUTION COMPLETE")
    print(f"m3_spec_version: {M3_SPEC_VERSION}")
    print(f"tsh_spec_version: {TSH_SPEC_VERSION}")
    print(f"dataset_fingerprint: {validation.summary.dataset_fingerprint}")
    print(f"symbols: {len(items)}/{len(config.primary_symbols) + len(eligible_secondary)}")
    print(f"Gate M3: {gate['status']}")
    print("final_holdout_included: False")
    print(f"output directory: {output_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
