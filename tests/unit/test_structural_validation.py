from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from momentum.data.structural_validation import (
    discover_prepared_daily_file,
    run_track_b_structural_validation,
)
from momentum.data.track_b import compute_track_b_daily_fingerprint
from momentum.research.track_b_config import load_track_b_config, validate_m1a_real_data_gate


def _config_path(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    config = {
        "freeze_version": 2,
        "freeze_date": "2026-08-18",
        "warmup_data_start": "2020-01",
        "development_period": {"start": "2020-01", "end": "2020-01"},
        "validation_period": {"start": "2020-02", "end": "2020-02"},
        "final_holdout_period": {"start": "2020-03", "end": "2020-03"},
        "split_assignment": {"basis": "next_1m_return_outcome_month"},
        "symbol_universe": {
            "primary": ["XAUUSD"],
            "secondary_cross_robustness": ["EURUSD"],
        },
        "data_source": "exness_prepared_bid_ohlc",
        "price_type": "bid",
        "timezone": "UTC",
        "daily_bar_boundary": {
            "convention": "prepared_daily_bar_label",
            "authority": "prepared_ohlc_timestamp",
            "calendar_month_timezone": "UTC",
            "ny17_conversion_required": False,
        },
        "previous_freeze_version": 1,
        "change_reason": "test fixture",
        "changed_fields": ["data_source"],
        "status": "frozen",
    }
    path = tmp_path / "research_track_b.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def _daily_rows(months=("2020-01", "2020-02", "2020-03")) -> pd.DataFrame:
    timestamps = [pd.Timestamp(f"{month}-15 00:00:00+00:00") for month in months]
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": [100.0 + i for i in range(len(months))],
        "high": [101.0 + i for i in range(len(months))],
        "low": [99.0 + i for i in range(len(months))],
        "close": [100.5 + i for i in range(len(months))],
    })


def _write_universe(root: Path, frame: pd.DataFrame, *, primary: pd.DataFrame | None = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "XAUUSD_1d.csv").write_text(
        (frame if primary is None else primary).to_csv(index=False), encoding="utf-8"
    )
    (root / "EURUSD_1d.csv").write_text(frame.to_csv(index=False), encoding="utf-8")


def _run(tmp_path: Path, frame: pd.DataFrame, *, primary: pd.DataFrame | None = None):
    root = tmp_path / "processed"
    config_path = _config_path(tmp_path)
    _write_universe(root, frame, primary=primary)
    return run_track_b_structural_validation(root, config_path)


def test_clean_complete_prepared_daily_passes_and_uses_path_symbol(tmp_path):
    result = _run(tmp_path, _daily_rows())
    assert set(result.symbol_diagnostics["validation_status"]) == {"pass"}
    assert set(result.daily_ohlc["symbol"]) == {"XAUUSD", "EURUSD"}
    assert list(result.daily_ohlc.columns) == ["symbol", "timestamp", "open", "high", "low", "close"]
    assert result.summary.structural_spec_version == "track-b-structural-v2"
    assert discover_prepared_daily_file(tmp_path / "processed", "XAUUSD").name == "XAUUSD_1d.csv"


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda frame: frame.iloc[[1, 0, 2]].reset_index(drop=True), "timestamp_not_ascending"),
        (lambda frame: pd.concat([frame, frame.iloc[[1]]], ignore_index=True), "duplicate_timestamp"),
    ],
)
def test_unsorted_and_duplicate_prepared_daily_fail(tmp_path, mutation, reason):
    result = _run(tmp_path, _daily_rows(), primary=mutation(_daily_rows()))
    row = result.symbol_diagnostics.loc[result.symbol_diagnostics["symbol"] == "XAUUSD"].iloc[0]
    assert row["validation_status"] == "fail"
    assert reason in row["failure_reasons"]


def test_invalid_ohlc_fails_without_repair(tmp_path):
    invalid = _daily_rows()
    invalid.loc[1, "high"] = invalid.loc[1, "low"] - 1
    result = _run(tmp_path, _daily_rows(), primary=invalid)
    row = result.symbol_diagnostics.loc[result.symbol_diagnostics["symbol"] == "XAUUSD"].iloc[0]
    assert row["validation_status"] == "fail"
    assert "invalid_ohlc" in row["failure_reasons"]


def test_production_loader_accepts_naive_csv_timestamp_as_utc_label(tmp_path):
    naive = _daily_rows()
    expected_first = naive["timestamp"].iloc[0]
    naive["timestamp"] = naive["timestamp"].dt.tz_localize(None)
    result = _run(tmp_path, naive)
    timestamp = result.daily_ohlc["timestamp"]
    assert isinstance(timestamp.dtype, pd.DatetimeTZDtype)
    assert str(timestamp.dt.tz) == "UTC"
    assert timestamp.iloc[0] == expected_first


def test_ohlc_diagnostic_counts_unique_invalid_rows(tmp_path):
    invalid = _daily_rows()
    invalid.loc[1, "open"] = 0.0
    invalid.loc[1, "high"] = float("nan")
    invalid.loc[2, "high"] = invalid.loc[2, "low"] - 1.0
    result = _run(tmp_path, _daily_rows(), primary=invalid)
    row = result.symbol_diagnostics.loc[result.symbol_diagnostics["symbol"] == "XAUUSD"].iloc[0]
    assert row["nonfinite_or_invalid_ohlc_rows"] == 2


def test_missing_calendar_month_fails(tmp_path):
    result = _run(tmp_path, _daily_rows(months=("2020-01", "2020-03")))
    row = result.symbol_diagnostics.loc[result.symbol_diagnostics["symbol"] == "XAUUSD"].iloc[0]
    assert row["validation_status"] == "fail"
    assert "missing_calendar_months" in row["failure_reasons"]


def test_range_outside_daily_is_excluded_from_fingerprint(tmp_path):
    inside = _daily_rows()
    outside = _daily_rows(months=("2019-12", "2020-04"))
    extended = pd.concat([outside.iloc[[0]], inside, outside.iloc[[1]]], ignore_index=True)
    base = _run(tmp_path / "base", inside)
    extra = _run(tmp_path / "extra", extended)
    pd.testing.assert_frame_equal(base.daily_ohlc, extra.daily_ohlc)
    assert base.summary.dataset_fingerprint == extra.summary.dataset_fingerprint


def test_fingerprint_identity_is_row_order_invariant(tmp_path):
    result = _run(tmp_path, _daily_rows())
    shuffled = result.daily_ohlc.iloc[[2, 0, 1, 5, 3, 4]].reset_index(drop=True)
    assert compute_track_b_daily_fingerprint(result.daily_ohlc) == compute_track_b_daily_fingerprint(shuffled)


def test_existing_m1a_gate_accepts_v2_structural_summary(tmp_path):
    result = _run(tmp_path, _daily_rows())
    config = load_track_b_config(_config_path(tmp_path))
    eligible = validate_m1a_real_data_gate(
        config, result.summary.status_by_symbol, result.summary.freeze_version
    )
    assert eligible == ("EURUSD",)
