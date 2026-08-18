from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

import scripts.run_m2 as cli
from momentum.data.structural_validation import StructuralValidationResult
from momentum.data.track_b import compute_track_b_daily_fingerprint
from momentum.research.track_b_config import (
    SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
    SUPPORTED_STRUCTURAL_SPEC_VERSION,
    StructuralValidationSummary,
    load_track_b_config,
)


ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module")
def track_b_config():
    return load_track_b_config(ROOT / "config" / "research_track_b.yaml")


def _daily_fixture(config) -> pd.DataFrame:
    rows = []
    periods = pd.period_range(config.warmup_data_start, config.validation.end + 1, freq="M")
    symbols = config.primary_symbols + config.secondary_symbols
    for symbol_index, symbol in enumerate(symbols):
        for month_index, month in enumerate(periods):
            close = 100.0 + symbol_index + month_index
            for day in (1, 2):
                timestamp = (month.start_time + pd.Timedelta(days=day - 1)).tz_localize("UTC")
                rows.append({
                    "symbol": symbol,
                    "timestamp": timestamp,
                    "open": close + day / 100.0,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                })
    return pd.DataFrame(rows)


def _validation(config, daily):
    statuses = {
        **{symbol: "pass" for symbol in config.primary_symbols},
        **{symbol: "pass" for symbol in config.secondary_symbols},
    }
    summary = StructuralValidationSummary(
        freeze_version=config.freeze_version,
        structural_spec_version=SUPPORTED_STRUCTURAL_SPEC_VERSION,
        dataset_fingerprint=compute_track_b_daily_fingerprint(daily),
        dataset_fingerprint_algorithm=SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
        status_by_symbol=statuses,
    )
    diagnostics = pd.DataFrame([
        {"symbol": symbol, "validation_status": statuses[symbol]}
        for symbol in config.primary_symbols + config.secondary_symbols
    ])
    return StructuralValidationResult(daily_ohlc=daily, symbol_diagnostics=diagnostics, summary=summary)


def test_cli_writes_exactly_eight_symbols_with_shared_terminal_boundary(tmp_path, monkeypatch, track_b_config):
    daily = _daily_fixture(track_b_config)
    validation = _validation(track_b_config, daily)
    monkeypatch.setattr(cli, "run_track_b_structural_validation", lambda **_: validation)

    output_root = tmp_path / "results"
    assert cli.main(
        config_path=track_b_config.path,
        data_root=tmp_path,
        output_root=output_root,
    ) == 0

    run_dirs = list(output_root.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    comparison = pd.read_csv(run_dir / "comparison.csv")
    assert len(comparison) == 8
    assert set(comparison["symbol"]) == set(track_b_config.primary_symbols)
    metadata = pd.read_json(run_dir / "metadata.json", typ="series")
    assert metadata["final_holdout_included"] is False
    assert metadata["execution_identity"]["symbols_executed"] == "8/8"
    assert metadata["execution_identity"]["gate_m2"] == "PASS"

    for symbol in track_b_config.primary_symbols:
        symbol_dir = run_dir / "symbols" / symbol
        assert symbol_dir.is_dir()
        m0_bars = pd.read_csv(symbol_dir / "m0_bars.csv")
        m2_bars = pd.read_csv(symbol_dir / "m2_bars.csv")
        for bars in (m0_bars, m2_bars):
            assert bars["timestamp"].iloc[-1].startswith("2024-01-01")
            assert pd.isna(bars["asset_return"].iloc[-1])
            assert pd.isna(bars["strategy_return"].iloc[-1])
            timestamps = pd.to_datetime(bars["timestamp"], utc=True)
            assert int((timestamps > pd.Timestamp("2024-01-01", tz="UTC")).sum()) == 0

    report = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "no holdout metrics" in report
    assert "construction invariant" in report


def test_cli_primary_gate_failure_writes_nothing(tmp_path, monkeypatch, track_b_config):
    daily = _daily_fixture(track_b_config)
    validation = _validation(track_b_config, daily)
    statuses = dict(validation.summary.status_by_symbol)
    statuses[track_b_config.primary_symbols[0]] = "fail"
    failed = replace(
        validation,
        summary=replace(validation.summary, status_by_symbol=statuses),
    )
    monkeypatch.setattr(cli, "run_track_b_structural_validation", lambda **_: failed)
    output_root = tmp_path / "results"
    assert cli.main(config_path=track_b_config.path, data_root=tmp_path, output_root=output_root) == 1
    assert not output_root.exists()


def test_cli_symbol_failure_leaves_no_final_or_staging_artifact(tmp_path, monkeypatch, track_b_config):
    daily = _daily_fixture(track_b_config)
    validation = _validation(track_b_config, daily)
    monkeypatch.setattr(cli, "run_track_b_structural_validation", lambda **_: validation)
    original = cli.run_m2_track_b

    def fail_on_second(*args, **kwargs):
        if kwargs["symbol"] == track_b_config.primary_symbols[1]:
            raise RuntimeError("synthetic symbol failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(cli, "run_m2_track_b", fail_on_second)
    output_root = tmp_path / "results"
    assert cli.main(config_path=track_b_config.path, data_root=tmp_path, output_root=output_root) == 1
    assert not output_root.exists()


def test_gate7_is_construction_invariant_not_performance(track_b_config):
    daily = _daily_fixture(track_b_config)
    validation = _validation(track_b_config, daily)
    item = cli._run_symbol(
        daily,
        track_b_config,
        validation.summary,
        track_b_config.primary_symbols[0],
    )
    changed_m0 = replace(item.m0, metrics={**item.m0.metrics, "gross_return": -999.0})
    changed_m2 = replace(item.m2, metrics={**item.m2.metrics, "gross_return": 999.0})
    gate = cli._gate7_invariant(
        changed_m0,
        changed_m2,
        track_b_config,
        validation.summary,
        item.window,
    )
    assert gate["construction_invariant_pass"] is True
    assert gate["performance_not_used_for_gate"] is True


def test_cli_outputs_unique_directories_without_overwrite(tmp_path, monkeypatch, track_b_config):
    daily = _daily_fixture(track_b_config)
    validation = _validation(track_b_config, daily)
    monkeypatch.setattr(cli, "run_track_b_structural_validation", lambda **_: validation)
    output_root = tmp_path / "results"
    assert cli.main(config_path=track_b_config.path, data_root=tmp_path, output_root=output_root) == 0
    assert cli.main(config_path=track_b_config.path, data_root=tmp_path, output_root=output_root) == 0
    assert len(list(output_root.iterdir())) == 2
