"""Run Track B v2 prepared-Daily structural validation from the repo root.

Usage::

    python scripts/run_structural_validation.py

This script intentionally stops at structural validation. It never invokes
M1A or any predictive/performance calculation.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from momentum.data.structural_validation import (  # noqa: E402
    StructuralValidationResult,
    run_track_b_structural_validation,
)
from momentum.research.track_b_config import load_track_b_config  # noqa: E402


def _display(value: Any) -> str:
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _print_result(result: StructuralValidationResult) -> None:
    summary = result.summary
    for row in result.symbol_diagnostics.to_dict(orient="records"):
        print(f"symbol: {_display(row['symbol'])}")
        print(f"validation_status: {_display(row['validation_status'])}")
        print(f"daily_bar_count: {_display(row['daily_bar_count'])}")
        print(f"first_valid_timestamp: {_display(row['first_valid_timestamp'])}")
        print(f"last_valid_timestamp: {_display(row['last_valid_timestamp'])}")
        print(f"missing_calendar_months: {_display(row['missing_calendar_months'])}")
        print(f"failure_reasons: {_display(row['failure_reasons'])}")
        print(f"freeze_version: {_display(summary.freeze_version)}")
        print(f"structural_spec_version: {_display(summary.structural_spec_version)}")
        print(f"dataset_fingerprint: {_display(summary.dataset_fingerprint)}")
        print(
            "dataset_fingerprint_algorithm: "
            f"{_display(summary.dataset_fingerprint_algorithm)}"
        )
        print()


def main() -> int:
    config_path = REPO_ROOT / "config" / "research_track_b.yaml"
    data_root = REPO_ROOT / "data" / "processed"
    try:
        config = load_track_b_config(config_path)
        result = run_track_b_structural_validation(
            data_root=data_root,
            config_path=config_path,
        )
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"structural validation error: {exc}", file=sys.stderr)
        return 1

    _print_result(result)
    primary_failures = [
        symbol
        for symbol in config.primary_symbols
        if result.summary.status_by_symbol.get(symbol) == "fail"
    ]
    return 1 if primary_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
