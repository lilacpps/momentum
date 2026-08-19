from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import json
import pandas as pd
import pytest

import scripts.run_m3 as cli
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
            for day in (1, 2, 3):
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


def test_runner_writes_separated_primary_secondary_outputs(tmp_path, monkeypatch, track_b_config):
    daily = _daily_fixture(track_b_config)
    validation = _validation(track_b_config, daily)
    monkeypatch.setattr(cli, "run_track_b_structural_validation", lambda **_: validation)
    output_root = tmp_path / "results"

    assert cli.main(config_path=track_b_config.path, data_root=tmp_path, output_root=output_root) == 0
    run_dir = next(output_root.iterdir())
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    gate = json.loads((run_dir / "gate_m3.json").read_text(encoding="utf-8"))
    assert gate["status"] == "PASS"
    assert metadata["m3_spec_version"] == "m3-multi-symbol-v1"
    assert "config" not in metadata
    assert metadata["tsh_method_role"] == "tsh_track_b_practical"
    assert metadata["final_holdout_included"] is False
    assert metadata["primary_symbols"] == list(track_b_config.primary_symbols)
    assert metadata["secondary_symbols"] == list(track_b_config.secondary_symbols)

    metrics = pd.read_csv(run_dir / "symbol_metrics.csv")
    assert set(metrics["strategy"]) == {"m0", "m2", "tsh"}
    assert set(metrics.loc[metrics["strategy"].eq("m2"), "universe_role"]) == {"primary"}
    comparison = pd.read_csv(run_dir / "tsm_tsh_comparison.csv")
    assert set(comparison["symbol"]) == set(track_b_config.primary_symbols)
    assert len(pd.read_csv(run_dir / "monthly_history.csv")) > 0

    for symbol in track_b_config.primary_symbols + track_b_config.secondary_symbols:
        symbol_metadata = json.loads(
            (run_dir / "symbols" / symbol / "metadata.json").read_text(encoding="utf-8")
        )
        assert symbol_metadata["m0_metadata"].get("method_role") is None
        assert symbol_metadata["tsh_metadata"]["method_role"] == "tsh_track_b_practical"
        if symbol in track_b_config.primary_symbols:
            assert symbol_metadata["m2_metadata"]["spec_version"] == "m2-practical-v1"
        else:
            assert symbol_metadata["m2_metadata"] is None


def test_primary_failure_writes_no_output(tmp_path, monkeypatch, track_b_config):
    daily = _daily_fixture(track_b_config)
    validation = _validation(track_b_config, daily)
    monkeypatch.setattr(cli, "run_track_b_structural_validation", lambda **_: validation)
    original = cli.run_m3_symbol

    def fail_primary(*args, **kwargs):
        if kwargs["symbol"] == track_b_config.primary_symbols[0]:
            raise RuntimeError("synthetic primary failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(cli, "run_m3_symbol", fail_primary)
    output_root = tmp_path / "results"
    assert cli.main(config_path=track_b_config.path, data_root=tmp_path, output_root=output_root) == 1
    assert not output_root.exists()


def test_secondary_failure_is_recorded_without_primary_pooling(tmp_path, monkeypatch, track_b_config):
    daily = _daily_fixture(track_b_config)
    validation = _validation(track_b_config, daily)
    monkeypatch.setattr(cli, "run_track_b_structural_validation", lambda **_: validation)
    original = cli.run_m3_symbol

    def fail_secondary(*args, **kwargs):
        if kwargs["symbol"] == track_b_config.secondary_symbols[0]:
            raise RuntimeError("synthetic secondary failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(cli, "run_m3_symbol", fail_secondary)
    output_root = tmp_path / "results"
    assert cli.main(config_path=track_b_config.path, data_root=tmp_path, output_root=output_root) == 0
    run_dir = next(output_root.iterdir())
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    gate = json.loads((run_dir / "gate_m3.json").read_text(encoding="utf-8"))
    assert gate["status"] == "PASS"
    assert track_b_config.secondary_symbols[0] in gate["failures"]
    assert metadata["primary_symbols"] == list(track_b_config.primary_symbols)
    assert set(metadata["symbols"]) == set(track_b_config.primary_symbols + track_b_config.secondary_symbols[1:])
    assert set(pd.read_csv(run_dir / "tsm_tsh_comparison.csv")["symbol"]) == set(track_b_config.primary_symbols)


def test_fingerprint_mismatch_is_rejected(tmp_path, monkeypatch, track_b_config):
    daily = _daily_fixture(track_b_config)
    validation = _validation(track_b_config, daily)
    broken = replace(
        validation,
        summary=replace(validation.summary, dataset_fingerprint="0" * 64),
    )
    monkeypatch.setattr(cli, "run_track_b_structural_validation", lambda **_: broken)
    output_root = tmp_path / "results"
    assert cli.main(config_path=track_b_config.path, data_root=tmp_path, output_root=output_root) == 1
    assert not output_root.exists()


def test_same_input_produces_deterministic_report_tables(tmp_path, monkeypatch, track_b_config):
    daily = _daily_fixture(track_b_config)
    validation = _validation(track_b_config, daily)
    monkeypatch.setattr(cli, "run_track_b_structural_validation", lambda **_: validation)
    output_root = tmp_path / "results"
    assert cli.main(config_path=track_b_config.path, data_root=tmp_path, output_root=output_root) == 0
    assert cli.main(config_path=track_b_config.path, data_root=tmp_path, output_root=output_root) == 0
    run_dirs = sorted(output_root.iterdir())
    assert len(run_dirs) == 2
    for name in ("symbol_metrics.csv", "symbol_year.csv", "monthly_history.csv", "tsm_tsh_comparison.csv"):
        assert (run_dirs[0] / name).read_bytes() == (run_dirs[1] / name).read_bytes()
    first = json.loads((run_dirs[0] / "gate_m3.json").read_text(encoding="utf-8"))
    second = json.loads((run_dirs[1] / "gate_m3.json").read_text(encoding="utf-8"))
    assert first == second
