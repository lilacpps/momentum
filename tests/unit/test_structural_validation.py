from __future__ import annotations

from dataclasses import replace
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
import yaml

from momentum.data.structural_validation import (
    EXNESS_REQUIRED_COLUMNS,
    _session_boundary_utc,
    compute_track_b_daily_fingerprint,
    discover_track_b_source_files,
    iter_exness_ticks,
    run_track_b_structural_validation,
)
from momentum.data.track_b import validate_track_b_daily
from momentum.research.track_b_config import load_track_b_config, validate_m1a_real_data_gate


ROOT = Path(__file__).parents[2]


def _utc_z(local_date: str, local_time: str = "18:00:00") -> str:
    local = datetime.fromisoformat(f"{local_date}T{local_time}").replace(
        tzinfo=ZoneInfo("America/New_York")
    )
    return local.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z")


def _config(tmp_path: Path, *, symbols=("XAUUSD", "EURJPY"), end="2020-03"):
    raw = yaml.safe_load((ROOT / "config" / "research_track_b.yaml").read_text(encoding="utf-8"))
    raw.update({
        "warmup_data_start": "2020-01",
        "development_period": {"start": "2020-01", "end": "2020-01"},
        "validation_period": {"start": "2020-02", "end": "2020-02"},
        "final_holdout_period": {"start": "2020-03", "end": end},
        "symbol_universe": {"primary": [symbols[0]], "secondary_cross_robustness": [symbols[1]]},
    })
    path = tmp_path / "track_b.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def _write_csv(root: Path, symbol: str, filename: str, rows: list[dict]) -> Path:
    directory = root / symbol
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    pd.DataFrame(rows, columns=EXNESS_REQUIRED_COLUMNS).to_csv(path, index=False)
    return path


def _monthly_rows(symbol: str, months=("2020-01-15", "2020-02-15", "2020-03-15")):
    return [
        {"Exness": "exness", "Symbol": symbol, "Timestamp": _utc_z(day), "Bid": price, "Ask": price + 0.1}
        for day, price in zip(months, (1.0, 2.0, 3.0))
    ]


def _complete_rows(symbol: str):
    rows = []
    price = 1.0
    for day in pd.date_range("2020-01-01", "2020-03-31", freq="D"):
        if day.weekday() == 5:  # normal Friday 17:00 -> Sunday 17:00 closure
            continue
        rows.append({
            "Exness": "exness",
            "Symbol": symbol,
            "Timestamp": _utc_z(day.strftime("%Y-%m-%d")),
            "Bid": price,
            "Ask": price + 0.1,
        })
        price += 0.01
    return rows


def test_synthetic_schema_mapping_and_explicit_utc_z_are_fixed(tmp_path):
    sample = _write_csv(tmp_path, "XAUUSD", "sample.csv", [
        {
            "Exness": "exness",
            "Symbol": "XAUUSD",
            "Timestamp": _utc_z("2020-01-15"),
            "Bid": 1.0,
            "Ask": 1.1,
        },
    ])
    header = pd.read_csv(sample, nrows=0).columns.tolist()
    assert header == list(EXNESS_REQUIRED_COLUMNS)
    first = pd.read_csv(sample, nrows=3, dtype=object)
    assert first["Timestamp"].str.endswith("Z").all()
    assert first["Bid"].notna().all()


def test_source_discovery_is_direct_child_and_normalized_lexical(tmp_path):
    _write_csv(tmp_path, "XAUUSD", "z.csv", [])
    _write_csv(tmp_path, "XAUUSD", "a.csv", [])
    (tmp_path / "XAUUSD" / "nested").mkdir()
    assert [p.name for p in discover_track_b_source_files(tmp_path, "XAUUSD")] == ["a.csv", "z.csv"]


def test_source_discovery_supports_annual_monthly_mixed_and_filename_is_not_authority(tmp_path):
    config = _config(tmp_path)
    root = tmp_path / "raw"
    complete = _complete_rows("XAUUSD")
    _write_csv(root, "XAUUSD", "a_annual_2099.csv", complete[:20])
    _write_csv(root, "XAUUSD", "b_monthly_2020_02.csv", complete[20:])
    _write_csv(root, "EURJPY", "annual.csv", _complete_rows("EURJPY"))
    result = run_track_b_structural_validation(root, config, chunksize=1)
    xau = result.symbol_diagnostics.set_index("symbol").loc["XAUUSD"]
    assert xau["available_calendar_months"] == ["2020-01", "2020-02", "2020-03"]
    assert xau["validation_status"] == "pass"


def test_invalid_timestamp_bid_and_zero_based_source_row_are_counted(tmp_path):
    config = _config(tmp_path)
    root = tmp_path / "raw"
    rows = [
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": "bad", "Bid": "nan", "Ask": "1"},
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": "2020-01-15 18:00:00", "Bid": "1", "Ask": "1"},
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": _utc_z("2020-02-15"), "Bid": "nan", "Ask": "1"},
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": _utc_z("2020-03-15"), "Bid": "-1", "Ask": "1"},
    ]
    _write_csv(root, "XAUUSD", "rows.csv", rows)
    _write_csv(root, "EURJPY", "rows.csv", _monthly_rows("EURJPY"))
    result = run_track_b_structural_validation(root, config)
    row = result.symbol_diagnostics.set_index("symbol").loc["XAUUSD"]
    assert row["timestamp_parse_errors"] == 2
    assert row["nonfinite_or_invalid_bid_rows"] == 2


@pytest.mark.parametrize("bid", ["nan", "inf", "-inf", "0", "-1"])
def test_invalid_bid_values_are_excluded(tmp_path, bid):
    path = _write_csv(tmp_path, "XAUUSD", "rows.csv", [
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": _utc_z("2020-01-15"), "Bid": bid, "Ask": 1},
    ])
    diagnostics = {"timestamp_parse_errors": 0, "nonfinite_or_invalid_bid_rows": 0, "source_symbol_mismatch_count": 0}
    assert list(iter_exness_ticks(path, symbol="XAUUSD", source_file_order=3, diagnostics=diagnostics)) == []
    assert diagnostics["nonfinite_or_invalid_bid_rows"] == 1


def test_source_row_number_is_zero_based_original_data_position(tmp_path):
    path = _write_csv(tmp_path, "XAUUSD", "rows.csv", [
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": "bad", "Bid": 1, "Ask": 1},
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": _utc_z("2020-01-15"), "Bid": 2, "Ask": 2},
    ])
    diagnostics = {"timestamp_parse_errors": 0, "nonfinite_or_invalid_bid_rows": 0, "source_symbol_mismatch_count": 0}
    ticks = list(iter_exness_ticks(path, symbol="XAUUSD", source_file_order=3, diagnostics=diagnostics))
    assert ticks[0].source_row_number == 1
    assert ticks[0].source_file_order == 3


def test_same_timestamp_different_bid_retained_and_exact_duplicate_counted(tmp_path):
    config = _config(tmp_path)
    root = tmp_path / "raw"
    rows = [
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": _utc_z("2020-01-15", "18:00:00"), "Bid": 1, "Ask": 1},
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": _utc_z("2020-01-15", "18:00:00"), "Bid": 2, "Ask": 2},
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": _utc_z("2020-01-15", "18:00:00"), "Bid": 2, "Ask": 2},
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": _utc_z("2020-02-15"), "Bid": 3, "Ask": 3},
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": _utc_z("2020-03-15"), "Bid": 4, "Ask": 4},
    ]
    _write_csv(root, "XAUUSD", "rows.csv", rows)
    _write_csv(root, "EURJPY", "rows.csv", _monthly_rows("EURJPY"))
    result = run_track_b_structural_validation(root, config)
    row = result.symbol_diagnostics.set_index("symbol").loc["XAUUSD"]
    assert row["repeated_timestamp_count"] == 2
    assert row["exact_duplicate_row_count"] == 1
    january = result.daily_ohlc.loc[
        (result.daily_ohlc["symbol"] == "XAUUSD")
        & (result.daily_ohlc["timestamp"].dt.month == 1),
        "high",
    ]
    assert january.max() == 2


def test_out_of_order_sqlite_fallback_matches_sorted_fast_path(tmp_path):
    config = _config(tmp_path)
    sorted_root = tmp_path / "sorted"
    fallback_root = tmp_path / "fallback"
    rows = _monthly_rows("XAUUSD")
    _write_csv(sorted_root, "XAUUSD", "ticks.csv", rows)
    _write_csv(fallback_root, "XAUUSD", "ticks.csv", [rows[1], rows[0], rows[2]])
    _write_csv(sorted_root, "EURJPY", "ticks.csv", _monthly_rows("EURJPY"))
    _write_csv(fallback_root, "EURJPY", "ticks.csv", _monthly_rows("EURJPY"))
    first = run_track_b_structural_validation(sorted_root, config, chunksize=1)
    second = run_track_b_structural_validation(fallback_root, config, chunksize=1)
    pd.testing.assert_frame_equal(first.daily_ohlc, second.daily_ohlc)
    assert second.symbol_diagnostics.set_index("symbol").loc["XAUUSD", "out_of_order_detected"]
    expected_first = pd.Timestamp(rows[0]["Timestamp"])
    expected_last = pd.Timestamp(rows[2]["Timestamp"])
    fallback_diagnostics = second.symbol_diagnostics.set_index("symbol").loc["XAUUSD"]
    assert fallback_diagnostics["first_valid_tick"] == expected_first
    assert fallback_diagnostics["last_valid_tick"] == expected_last
    assert first.summary.dataset_fingerprint == second.summary.dataset_fingerprint


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (pd.Timestamp("2020-01-15 22:00", tz="UTC"), pd.Timestamp("2020-01-15 22:00", tz="UTC")),
        (pd.Timestamp("2020-07-15 21:00", tz="UTC"), pd.Timestamp("2020-07-15 21:00", tz="UTC")),
        (pd.Timestamp("2020-03-08 21:00", tz="UTC"), pd.Timestamp("2020-03-08 21:00", tz="UTC")),
    ],
)
def test_ny_17_boundary_uses_iana_dst(value, expected):
    assert _session_boundary_utc(value) == expected


def test_exact_previous_and_current_boundary_and_golden_ohlc(tmp_path):
    config = _config(tmp_path)
    root = tmp_path / "raw"
    rows = [
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": _utc_z("2020-01-14", "17:00:00"), "Bid": 9, "Ask": 9},
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": _utc_z("2020-01-15", "18:00:00"), "Bid": 2, "Ask": 2},
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": _utc_z("2020-01-15", "19:00:00"), "Bid": 5, "Ask": 5},
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": _utc_z("2020-01-15", "20:00:00"), "Bid": 1, "Ask": 1},
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": _utc_z("2020-01-15", "17:00:00"), "Bid": 4, "Ask": 4},
    ]
    # The current-boundary row is intentionally last in raw order; canonical order puts it first.
    _write_csv(root, "XAUUSD", "ticks.csv", rows + [
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": _utc_z("2020-02-15"), "Bid": 3, "Ask": 3},
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": _utc_z("2020-03-15"), "Bid": 3, "Ask": 3},
    ])
    _write_csv(root, "EURJPY", "ticks.csv", _monthly_rows("EURJPY"))
    result = run_track_b_structural_validation(root, config)
    previous_bar = result.daily_ohlc.loc[
        (result.daily_ohlc["symbol"] == "XAUUSD")
        & (result.daily_ohlc["timestamp"] == pd.Timestamp("2020-01-15 22:00", tz="UTC"))
    ].iloc[0]
    next_bar = result.daily_ohlc.loc[
        (result.daily_ohlc["symbol"] == "XAUUSD")
        & (result.daily_ohlc["timestamp"] == pd.Timestamp("2020-01-16 22:00", tz="UTC"))
    ].iloc[0]
    assert previous_bar[["open", "high", "low", "close"]].tolist() == [4.0, 4.0, 4.0, 4.0]
    assert next_bar[["open", "high", "low", "close"]].tolist() == [2.0, 5.0, 1.0, 1.0]


def test_missing_month_and_missing_source_are_failures_without_silent_skip(tmp_path):
    config = _config(tmp_path)
    root = tmp_path / "raw"
    _write_csv(root, "XAUUSD", "ticks.csv", _monthly_rows("XAUUSD")[:1] + _monthly_rows("XAUUSD")[2:])
    result = run_track_b_structural_validation(root, config)
    statuses = result.symbol_diagnostics.set_index("symbol")
    assert statuses.loc["XAUUSD", "validation_status"] == "fail"
    assert "missing_calendar_months" in statuses.loc["XAUUSD", "failure_reasons"]
    assert statuses.loc["EURJPY", "validation_status"] == "fail"
    assert "missing_source_directory" in statuses.loc["EURJPY", "failure_reasons"]


def test_suspicious_gap_is_one_warning_episode(tmp_path):
    config = _config(tmp_path)
    root = tmp_path / "raw"
    rows = [
        row for row in _complete_rows("XAUUSD")
        if not row["Timestamp"].startswith(("2020-01-16", "2020-01-17"))
    ]
    _write_csv(root, "XAUUSD", "ticks.csv", rows)
    _write_csv(root, "EURJPY", "ticks.csv", _complete_rows("EURJPY"))
    result = run_track_b_structural_validation(root, config)
    row = result.symbol_diagnostics.set_index("symbol").loc["XAUUSD"]
    assert row["suspicious_gap_count"] == 1
    assert row["validation_status"] == "pass_with_warning"


def test_clean_status_and_daily_validation_fingerprint_identity(tmp_path):
    config_path = _config(tmp_path)
    root = tmp_path / "raw"
    for symbol in ("XAUUSD", "EURJPY"):
        _write_csv(root, symbol, "annual.csv", _complete_rows(symbol))
    result = run_track_b_structural_validation(root, config_path)
    assert set(result.symbol_diagnostics["validation_status"]) == {"pass"}
    config = load_track_b_config(config_path)
    validated = validate_track_b_daily(result.daily_ohlc, config)
    assert compute_track_b_daily_fingerprint(validated) == result.summary.dataset_fingerprint
    shuffled = validated.sample(frac=1, random_state=7).reset_index(drop=True)
    assert compute_track_b_daily_fingerprint(shuffled) == result.summary.dataset_fingerprint
    changed = validated.copy()
    changed.loc[0, "close"] += 0.001
    assert compute_track_b_daily_fingerprint(changed) != result.summary.dataset_fingerprint


def test_requested_range_excludes_out_of_range_daily_and_fingerprint(tmp_path):
    config_path = _config(tmp_path)
    base_root = tmp_path / "base"
    extra_root = tmp_path / "extra"
    for symbol in ("XAUUSD", "EURJPY"):
        base_rows = _complete_rows(symbol)
        extra = {
            "Exness": "exness",
            "Symbol": symbol,
            "Timestamp": _utc_z("2020-04-15"),
            "Bid": 999.0,
            "Ask": 999.1,
        }
        _write_csv(base_root, symbol, "ticks.csv", base_rows)
        _write_csv(extra_root, symbol, "ticks.csv", base_rows + [extra])

    base = run_track_b_structural_validation(base_root, config_path)
    extra = run_track_b_structural_validation(extra_root, config_path)
    pd.testing.assert_frame_equal(base.daily_ohlc, extra.daily_ohlc)
    assert base.summary.dataset_fingerprint == extra.summary.dataset_fingerprint
    local_months = extra.daily_ohlc["timestamp"].dt.tz_convert("America/New_York").dt.month
    assert local_months.max() == 3


def test_out_of_range_anomalies_do_not_change_daily_fingerprint_or_status(tmp_path):
    config_path = _config(tmp_path)
    base_root = tmp_path / "base"
    anomaly_root = tmp_path / "anomaly"
    for symbol in ("XAUUSD", "EURJPY"):
        base_rows = _complete_rows(symbol)
        _write_csv(base_root, symbol, "ticks.csv", base_rows)
        if symbol == "XAUUSD":
            out_of_range = [
                {"Exness": "exness", "Symbol": symbol, "Timestamp": _utc_z("2020-04-20"), "Bid": 100.0, "Ask": 100.1},
                {"Exness": "exness", "Symbol": symbol, "Timestamp": _utc_z("2020-04-19"), "Bid": 101.0, "Ask": 101.1},
                {"Exness": "exness", "Symbol": symbol, "Timestamp": _utc_z("2020-04-18"), "Bid": 102.0, "Ask": 102.1},
                {"Exness": "exness", "Symbol": symbol, "Timestamp": _utc_z("2020-04-18"), "Bid": 102.0, "Ask": 102.1},
                {"Exness": "exness", "Symbol": "OTHER", "Timestamp": _utc_z("2020-04-17"), "Bid": 103.0, "Ask": 103.1},
                {"Exness": "exness", "Symbol": symbol, "Timestamp": _utc_z("2020-04-16"), "Bid": -1.0, "Ask": -0.9},
                {"Exness": "exness", "Symbol": symbol, "Timestamp": _utc_z("2019-12-20"), "Bid": 777.0, "Ask": 777.1},
            ]
            _write_csv(anomaly_root, symbol, "ticks.csv", base_rows + out_of_range)
        else:
            _write_csv(anomaly_root, symbol, "ticks.csv", base_rows)

    base = run_track_b_structural_validation(base_root, config_path)
    anomaly = run_track_b_structural_validation(anomaly_root, config_path)
    pd.testing.assert_frame_equal(base.daily_ohlc, anomaly.daily_ohlc)
    assert base.summary.dataset_fingerprint == anomaly.summary.dataset_fingerprint
    assert base.summary.status_by_symbol == anomaly.summary.status_by_symbol
    assert anomaly.summary.status_by_symbol["XAUUSD"] == "pass"


def test_timezone_naive_timestamp_is_not_implicitly_utc(tmp_path):
    path = _write_csv(tmp_path, "XAUUSD", "naive.csv", [
        {"Exness": "exness", "Symbol": "XAUUSD", "Timestamp": "2020-01-15 17:00:00", "Bid": 1.0, "Ask": 1.1},
    ])
    diagnostics = {
        "timestamp_parse_errors": 0,
        "nonfinite_or_invalid_bid_rows": 0,
        "source_symbol_mismatch_count": 0,
    }
    assert list(iter_exness_ticks(path, symbol="XAUUSD", source_file_order=0, diagnostics=diagnostics)) == []
    assert diagnostics["timestamp_parse_errors"] == 1
    assert diagnostics["nonfinite_or_invalid_bid_rows"] == 0


def test_generatable_failed_secondary_remains_in_daily_and_fingerprint(tmp_path):
    config_path = _config(tmp_path)
    root = tmp_path / "raw"
    _write_csv(root, "XAUUSD", "ticks.csv", _monthly_rows("XAUUSD"))
    _write_csv(root, "EURJPY", "ticks.csv", _monthly_rows("EURJPY")[:1])
    result = run_track_b_structural_validation(root, config_path)
    assert "EURJPY" in set(result.daily_ohlc["symbol"])
    assert result.summary.status_by_symbol["EURJPY"] == "fail"
    assert result.summary.dataset_fingerprint == compute_track_b_daily_fingerprint(result.daily_ohlc)


def test_structural_summary_is_compatible_with_existing_m1a_gate(tmp_path):
    config_path = _config(tmp_path)
    root = tmp_path / "raw"
    _write_csv(root, "XAUUSD", "ticks.csv", _monthly_rows("XAUUSD"))
    _write_csv(root, "EURJPY", "ticks.csv", _monthly_rows("EURJPY"))
    result = run_track_b_structural_validation(root, config_path)
    config = load_track_b_config(config_path)
    eligible = validate_m1a_real_data_gate(
        config, result.summary.status_by_symbol, result.summary.freeze_version
    )
    assert eligible == ("EURJPY",)
