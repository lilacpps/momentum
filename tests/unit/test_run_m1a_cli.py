from __future__ import annotations

from pathlib import Path

import pandas as pd

import scripts.run_m1a as cli
from momentum.data.structural_validation import StructuralValidationResult
from momentum.research.m1a import M1AResult
from momentum.research.track_b_config import (
    SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
    SUPPORTED_STRUCTURAL_SPEC_VERSION,
    StructuralValidationSummary,
    load_track_b_config,
)


ROOT = Path(__file__).parents[2]


def _daily_fixture() -> pd.DataFrame:
    return pd.DataFrame({
        "symbol": ["XAUUSD"],
        "timestamp": [pd.Timestamp("2020-01-31", tz="UTC")],
        "open": [99.0],
        "high": [101.0],
        "low": [98.0],
        "close": [100.0],
    })


def _validation(config, *, primary_failure: bool = False):
    statuses = {
        **{symbol: "pass" for symbol in config.primary_symbols},
        **{symbol: "pass" for symbol in config.secondary_symbols},
    }
    if primary_failure:
        statuses[config.primary_symbols[0]] = "fail"
    summary = StructuralValidationSummary(
        freeze_version=config.freeze_version,
        structural_spec_version=SUPPORTED_STRUCTURAL_SPEC_VERSION,
        dataset_fingerprint="synthetic-fingerprint",
        dataset_fingerprint_algorithm=SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
        status_by_symbol=statuses,
    )
    return StructuralValidationResult(
        daily_ohlc=_daily_fixture(),
        symbol_diagnostics=pd.DataFrame([
            {"symbol": symbol, "validation_status": statuses[symbol]}
            for symbol in config.primary_symbols + config.secondary_symbols
        ]),
        summary=summary,
    )


def _m1a_result(*, holdout: bool = False) -> M1AResult:
    outcome = pd.Period("2024-01" if holdout else "2023-12", freq="M")
    split = "final_holdout" if holdout else "validation"
    observations = pd.DataFrame([
        {
            "symbol": "XAUUSD",
            "universe_role": "primary",
            "formation_month": outcome - 1,
            "outcome_month": outcome,
            "past_12m_return": 0.1,
            "next_1m_return": 0.02,
            "sign": 1,
            "split": split,
        }
    ])
    regression = pd.DataFrame([
        {
            "symbol": "__pooled__",
            "universe_role": "primary",
            "result_role": "primary",
            "analysis_name": "continuous_regression",
            "sample_period": "2022-01/2023-12",
            "beta": 0.2,
            "standard_error": 0.1,
            "t_stat": 2.0,
            "ci_lower": 0.0,
            "ci_upper": 0.4,
            "inference_status": "available",
        },
        {
            "symbol": "__pooled__",
            "universe_role": "primary",
            "result_role": "primary",
            "analysis_name": "sign_predictor_regression",
            "sample_period": "2022-01/2023-12",
            "beta": 0.1,
            "standard_error": 0.1,
            "t_stat": 1.0,
            "ci_lower": -0.1,
            "ci_upper": 0.3,
            "inference_status": "available",
        },
    ])
    effects = pd.DataFrame([
        {
            "symbol": "__pooled__",
            "universe_role": "primary",
            "result_role": "primary",
            "metric": "difference",
            "sample_period": "2022-01/2023-12",
            "estimate": 0.05,
            "inference_status": "available",
        }
    ])
    return M1AResult(
        observations=observations,
        sign_conditioned_results=effects,
        regression_results=regression,
        diagnostics={"inference_unavailable_count": 0},
        metadata={
            "spec_version": "m1a-practical-v1",
            "freeze_version": 3,
            "structural_spec_version": SUPPORTED_STRUCTURAL_SPEC_VERSION,
            "dataset_fingerprint": "synthetic-fingerprint",
            "dataset_fingerprint_algorithm": SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
            "final_holdout_included": False,
        },
    )


def _patch_flow(monkeypatch, validation, result):
    seen = {}

    monkeypatch.setattr(cli, "run_track_b_structural_validation", lambda **_: validation)

    def fake_runner(daily, config, summary, *, include_sensitivity):
        seen["daily"] = daily
        seen["summary"] = summary
        seen["include_sensitivity"] = include_sensitivity
        return result

    monkeypatch.setattr(cli, "run_m1a_track_b", fake_runner)
    return seen


def test_cli_normal_completion_writes_outputs_and_preserves_validation_identity(tmp_path, monkeypatch):
    config = load_track_b_config(ROOT / "config" / "research_track_b.yaml")
    validation = _validation(config)
    seen = _patch_flow(monkeypatch, validation, _m1a_result())

    output_root = tmp_path / "results"
    assert cli.main(config_path=config.path, data_root=tmp_path, output_root=output_root) == 0
    run_dirs = list(output_root.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert seen["daily"] is validation.daily_ohlc
    assert seen["summary"] is validation.summary
    assert seen["include_sensitivity"] is True
    for filename in (
        "observations.csv",
        "regression_results.csv",
        "sign_conditioned_results.csv",
        "diagnostics.json",
        "metadata.json",
        "structural_validation_summary.json",
        "structural_validation_diagnostics.csv",
    ):
        assert (run_dir / filename).is_file()
    metadata = pd.read_json(run_dir / "metadata.json", typ="series")
    assert metadata["dataset_fingerprint"] == validation.summary.dataset_fingerprint
    assert metadata["freeze_version"] == validation.summary.freeze_version


def test_cli_primary_structural_failure_returns_one_without_running_or_writing(tmp_path, monkeypatch):
    config = load_track_b_config(ROOT / "config" / "research_track_b.yaml")
    validation = _validation(config, primary_failure=True)
    called = {"runner": False}
    monkeypatch.setattr(cli, "run_track_b_structural_validation", lambda **_: validation)

    def unexpected_runner(*args, **kwargs):
        called["runner"] = True
        raise AssertionError("M1A runner must not be called after primary gate failure")

    monkeypatch.setattr(cli, "run_m1a_track_b", unexpected_runner)
    output_root = tmp_path / "results"
    assert cli.main(config_path=config.path, data_root=tmp_path, output_root=output_root) == 1
    assert called["runner"] is False
    assert not output_root.exists()


def test_cli_holdout_safety_violation_returns_one_without_writing(tmp_path, monkeypatch):
    config = load_track_b_config(ROOT / "config" / "research_track_b.yaml")
    validation = _validation(config)
    _patch_flow(monkeypatch, validation, _m1a_result(holdout=True))

    output_root = tmp_path / "results"
    assert cli.main(config_path=config.path, data_root=tmp_path, output_root=output_root) == 1
    assert not output_root.exists()


def test_cli_structural_identity_mismatch_returns_one_without_writing(tmp_path, monkeypatch):
    config = load_track_b_config(ROOT / "config" / "research_track_b.yaml")
    validation = _validation(config)
    mismatched_summary = StructuralValidationSummary(
        freeze_version=config.freeze_version + 1,
        structural_spec_version=validation.summary.structural_spec_version,
        dataset_fingerprint=validation.summary.dataset_fingerprint,
        dataset_fingerprint_algorithm=validation.summary.dataset_fingerprint_algorithm,
        status_by_symbol=validation.summary.status_by_symbol,
    )
    mismatched = StructuralValidationResult(
        daily_ohlc=validation.daily_ohlc,
        symbol_diagnostics=validation.symbol_diagnostics,
        summary=mismatched_summary,
    )
    monkeypatch.setattr(cli, "run_track_b_structural_validation", lambda **_: mismatched)
    output_root = tmp_path / "results"
    assert cli.main(config_path=config.path, data_root=tmp_path, output_root=output_root) == 1
    assert not output_root.exists()
