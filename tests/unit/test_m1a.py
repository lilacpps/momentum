from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from momentum.data.track_b import (
    TrackBDailyValidationError,
    _build_synthetic_monthly_observations,
    compute_track_b_daily_fingerprint,
    validate_track_b_daily,
)
from momentum.research.inference import moving_block_bootstrap, outcome_months_are_consecutive
from momentum.research.m1a import _run_m1a_synthetic
from momentum.research import run_m1a_track_b
from momentum.research.track_b_config import (
    SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
    SUPPORTED_STRUCTURAL_SPEC_VERSION,
    StructuralValidationSummary,
    TrackBConfigError,
    load_track_b_config,
    validate_m1a_real_data_gate,
)


ROOT = Path(__file__).parents[2]


def _session_close(month: pd.Period) -> pd.Timestamp:
    local = month.start_time.tz_localize("America/New_York").replace(hour=17)
    return local.tz_convert("UTC")


def _daily_fixture(start: str = "2015-09", end: str = "2024-01", symbols=("XAUUSD", "EURUSD")) -> pd.DataFrame:
    periods = pd.period_range(start, end, freq="M")
    rows = []
    for symbol_index, symbol in enumerate(symbols):
        for index, month in enumerate(periods):
            close = 100.0 + symbol_index * 10.0 + index * 0.5
            rows.append({
                "symbol": symbol,
                "timestamp": _session_close(month),
                "open": close - 0.1,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
            })
    return pd.DataFrame(rows)


def _varying_daily_fixture() -> pd.DataFrame:
    data = _daily_fixture()
    month_index = data.groupby("symbol", sort=False).cumcount().to_numpy(dtype="float64")
    close = 100.0 + 12.0 * np.sin(month_index / 4.0)
    data["close"] = close
    data["open"] = close - 0.1
    data["high"] = close + 0.2
    data["low"] = close - 0.2
    return data


def _validation_summary(
    config,
    daily: pd.DataFrame,
    *,
    status_by_symbol: dict[str, str] | None = None,
    freeze_version: int | None = None,
    algorithm: str = SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
    structural_spec_version: str = SUPPORTED_STRUCTURAL_SPEC_VERSION,
) -> StructuralValidationSummary:
    if status_by_symbol is None:
        status_by_symbol = {
            **{symbol: "pass" for symbol in config.primary_symbols},
            **{symbol: "fail" for symbol in config.secondary_symbols},
        }
    return StructuralValidationSummary(
        freeze_version=config.freeze_version if freeze_version is None else freeze_version,
        structural_spec_version=structural_spec_version,
        dataset_fingerprint=compute_track_b_daily_fingerprint(daily),
        dataset_fingerprint_algorithm=algorithm,
        status_by_symbol=status_by_symbol,
    )


@pytest.fixture(scope="module")
def track_b_config():
    return load_track_b_config(ROOT / "config" / "research_track_b.yaml")


def test_config_loader_validates_current_frozen_artifact(track_b_config):
    assert track_b_config.status == "frozen"
    assert track_b_config.freeze_version == 3
    assert track_b_config.warmup_data_start == pd.Period("2015-09")
    assert track_b_config.raw["previous_freeze_version"] == 2
    assert track_b_config.raw["change_reason"] == (
        "2015-01 through 2015-08 prepared historical OHLC is unavailable; "
        "the earliest consistently available prepared data begins in 2015-09. "
        "This change is made before viewing Track B predictive or performance results."
    )
    assert track_b_config.split_assignment_basis == "next_1m_return_outcome_month"
    assert track_b_config.boundary_timezone == "UTC"
    assert "price_type" in track_b_config.raw


def test_config_loader_rejects_non_frozen_status(tmp_path, track_b_config):
    artifact = dict(track_b_config.raw)
    artifact["status"] = "draft"
    path = tmp_path / "track_b.yaml"
    path.write_text(yaml.safe_dump(artifact, sort_keys=False), encoding="utf-8")
    with pytest.raises(TrackBConfigError, match="status"):
        load_track_b_config(path)


def test_long_daily_validation_is_symbol_local_and_non_mutating():
    data = _daily_fixture(start="2019-01", end="2019-02", symbols=("XAUUSD", "EURUSD"))
    original = data.copy(deep=True)
    config = load_track_b_config(ROOT / "config" / "research_track_b.yaml")
    validated = validate_track_b_daily(data, config, allow_naive_timestamp=True)
    assert validated["timestamp"].dt.tz is not None
    pd.testing.assert_frame_equal(data, original)

    duplicate = pd.concat([data, data.iloc[[0]]], ignore_index=True)
    with pytest.raises(TrackBDailyValidationError, match="duplicate"):
        validate_track_b_daily(duplicate, config, allow_naive_timestamp=True)


def test_track_b_timestamp_requires_utc_aware_prepared_label(track_b_config):
    winter = _daily_fixture(start="2020-01", end="2020-01", symbols=("XAUUSD",))
    summer = _daily_fixture(start="2020-07", end="2020-07", symbols=("XAUUSD",))
    valid = pd.concat([winter, summer], ignore_index=True)
    assert len(validate_track_b_daily(valid, track_b_config)) == 2

    naive = valid.copy()
    naive["timestamp"] = naive["timestamp"].dt.tz_localize(None)
    with pytest.raises(TrackBDailyValidationError, match="timezone-aware"):
        validate_track_b_daily(naive, track_b_config)

    non_utc = valid.copy()
    non_utc["timestamp"] = non_utc["timestamp"].dt.tz_convert("Asia/Tokyo")
    with pytest.raises(TrackBDailyValidationError, match="UTC"):
        validate_track_b_daily(non_utc, track_b_config)

    prepared_label = valid.copy()
    prepared_label.loc[0, "timestamp"] += pd.Timedelta(hours=1)
    assert len(validate_track_b_daily(prepared_label, track_b_config)) == 2


def test_monthly_builder_uses_last_close_and_exact_calendar_month_arithmetic(track_b_config):
    data = _daily_fixture()
    prior = data.loc[
        (data["symbol"] == "XAUUSD")
        & (data["timestamp"] == _session_close(pd.Period("2019-06"))),
        "close",
    ].iloc[0]
    next_close = data.loc[
        (data["symbol"] == "XAUUSD")
        & (data["timestamp"] == _session_close(pd.Period("2020-07"))),
        "close",
    ].iloc[0]
    extra = data.loc[(data["symbol"] == "XAUUSD") & (data["timestamp"] == _session_close(pd.Period("2020-06")))].copy()
    extra["timestamp"] = pd.Timestamp("2020-06-30 17:00", tz="America/New_York").tz_convert("UTC")
    extra["close"] = 999.0
    extra["open"] = 998.9
    extra["high"] = 999.2
    extra["low"] = 998.8
    data = pd.concat([data, extra], ignore_index=True).sort_values(["symbol", "timestamp"]).reset_index(drop=True)

    built = _build_synthetic_monthly_observations(data, track_b_config)
    row = built.observations.loc[
        (built.observations["symbol"] == "XAUUSD")
        & (built.observations["formation_month"] == pd.Period("2020-06"))
    ].iloc[0]
    assert row["past_12m_return"] == pytest.approx(999.0 / prior - 1.0)
    assert row["next_1m_return"] == pytest.approx(next_close / 999.0 - 1.0)


def test_calendar_month_uses_prepared_utc_label(track_b_config):
    data = _daily_fixture(start="2019-01", end="2020-07", symbols=("XAUUSD",))
    may_close = data.loc[
        data["timestamp"] == _session_close(pd.Period("2020-05")), "close"
    ].iloc[0]
    june = data["timestamp"] == _session_close(pd.Period("2020-06"))
    data = data.loc[~june].copy()
    replacement = data.iloc[0].copy()
    replacement["timestamp"] = pd.Timestamp("2020-07-01 00:00:00", tz="UTC")
    replacement["close"] = 777.0
    replacement["open"] = 776.9
    replacement["high"] = 777.2
    replacement["low"] = 776.8
    data = pd.concat([data, pd.DataFrame([replacement])], ignore_index=True).sort_values("timestamp")
    built = _build_synthetic_monthly_observations(data, track_b_config)
    assert "2020-06" in built.diagnostics["missing_calendar_months"]["XAUUSD"]


def test_missing_calendar_month_is_excluded_without_fill(track_b_config):
    data = _daily_fixture()
    missing = _session_close(pd.Period("2019-06"))
    data = data.loc[~((data["symbol"] == "XAUUSD") & (data["timestamp"] == missing))].copy()
    built = _build_synthetic_monthly_observations(data, track_b_config)
    assert len(built.observations.loc[
        (built.observations["symbol"] == "XAUUSD")
        & (built.observations["formation_month"] == pd.Period("2019-06"))
    ]) == 0
    assert "2019-06" in built.diagnostics["missing_calendar_months"]["XAUUSD"]
    assert built.diagnostics["excluded_observation_count"] > 0
    assert built.diagnostics["excluded_observations_by_reason"]["pre_sample_history_unavailable"] == 24
    assert built.diagnostics["excluded_observations_by_reason"]["missing_formation_month"] > 0


def test_outcome_month_split_and_final_holdout_is_not_returned_by_analysis(track_b_config):
    data = _daily_fixture()
    built = _build_synthetic_monthly_observations(data, track_b_config)
    final_row = built.observations.loc[
        (built.observations["symbol"] == "XAUUSD")
        & (built.observations["formation_month"] == pd.Period("2023-12"))
    ].iloc[0]
    assert final_row["outcome_month"] == pd.Period("2024-01")
    assert final_row["split"] == "final_holdout"
    result = _run_m1a_synthetic(data, track_b_config, include_sensitivity=False)
    assert "final_holdout" not in set(result.observations["split"])
    assert (result.observations["outcome_month"] < pd.Period("2024-01")).all()


def test_warmup_is_history_but_first_development_outcome_is_assigned_by_outcome_month(track_b_config):
    data = _daily_fixture()
    built = _build_synthetic_monthly_observations(data, track_b_config)
    first_development = built.observations.loc[
        (built.observations["symbol"] == "XAUUSD")
        & (built.observations["outcome_month"] == pd.Period("2017-01"))
    ].iloc[0]
    assert first_development["formation_month"] == pd.Period("2016-12")
    assert first_development["split"] == "development"
    past_12m_price = data.loc[
        (data["symbol"] == "XAUUSD")
        & (data["timestamp"] == _session_close(pd.Period("2015-12"))),
        "close",
    ].iloc[0]
    formation_price = data.loc[
        (data["symbol"] == "XAUUSD")
        & (data["timestamp"] == _session_close(pd.Period("2016-12"))),
        "close",
    ].iloc[0]
    assert first_development["past_12m_return"] == pytest.approx(
        formation_price / past_12m_price - 1.0
    )
    warmup = built.observations.loc[
        (built.observations["symbol"] == "XAUUSD")
        & (built.observations["outcome_month"] == pd.Period("2016-12"))
    ].iloc[0]
    assert warmup["split"] == "warmup"


def test_m1a_results_have_primary_metadata_and_zero_semantics(track_b_config):
    data = _daily_fixture()
    result = _run_m1a_synthetic(data, track_b_config, include_sensitivity=False)
    regression = result.regression_results
    assert set(regression["result_role"]) == {"primary"}
    assert set(regression["spec_version"]) == {"m1a-practical-v1"}
    symbol = regression.loc[
        (regression["symbol"] == "XAUUSD")
        & (regression["analysis_name"] == "continuous_regression")
        & (regression["sample_period"].str.startswith("2017-01"))
    ].iloc[0]
    assert symbol["hac_lag"] == 12
    assert symbol["covariance_options"]["kernel"] == "bartlett"
    assert symbol["covariance_options"]["use_t"] is True
    pooled = regression.loc[
        (regression["symbol"] == "__pooled__")
        & (regression["analysis_name"] == "continuous_regression")
        & (regression["sample_period"].str.startswith("2017-01"))
    ].iloc[0]
    assert pooled["covariance_method"] == "calendar_month_clustered"
    assert pooled["cluster_variable"] == "outcome_month"
    assert pooled["covariance_options"]["df_correction"] is True

    sign_effect = result.sign_conditioned_results
    assert set(sign_effect["metric"]) == {"positive_mean", "negative_mean", "difference"}
    assert result.diagnostics["zero_predictor_observations"] == 0
    assert pooled["outcome_month_cluster_count"] == 60
    assert pooled["degrees_of_freedom_expected"] == 59
    assert pooled["statsmodels_df_resid_inference"] == 59
    assert pooled["df_validation_status"] == "match"


def test_rank_deficient_design_is_unavailable(track_b_config):
    result = _run_m1a_synthetic(_daily_fixture(), track_b_config, include_sensitivity=False)
    sign = result.regression_results.loc[
        (result.regression_results["symbol"] == "XAUUSD")
        & (result.regression_results["analysis_name"] == "sign_predictor_regression")
        & (result.regression_results["sample_period"].str.startswith("2017-01"))
    ].iloc[0]
    assert sign["inference_status"] == "unavailable"
    assert sign["inference_unavailable_reason"] == "rank_deficient_design"
    effects = result.sign_conditioned_results.loc[
        (result.sign_conditioned_results["symbol"] == "XAUUSD")
        & (result.sign_conditioned_results["sample_period"].str.startswith("2017-01"))
    ]
    assert set(effects["inference_unavailable_reason"]) == {"rank_deficient_design"}


def test_zero_return_is_retained_for_sign_regression_but_excluded_from_group_effect(track_b_config):
    data = _varying_daily_fixture()
    prior = data.loc[
        (data["symbol"] == "XAUUSD")
        & (data["timestamp"] == _session_close(pd.Period("2015-12"))),
        "close",
    ].iloc[0]
    target = (data["symbol"] == "XAUUSD") & (data["timestamp"] == _session_close(pd.Period("2016-12")))
    data.loc[target, "close"] = prior
    data.loc[target, "open"] = prior - 0.1
    data.loc[target, "high"] = prior + 0.2
    data.loc[target, "low"] = prior - 0.2

    result = _run_m1a_synthetic(data, track_b_config, include_sensitivity=False)
    zero_rows = result.observations.loc[
        (result.observations["symbol"] == "XAUUSD")
        & (result.observations["formation_month"] == pd.Period("2016-12"))
    ]
    assert len(zero_rows) == 1
    assert zero_rows.iloc[0]["sign"] == 0
    assert result.diagnostics["zero_predictor_observations"] > 0
    sign_regression = result.regression_results.loc[
        (result.regression_results["symbol"] == "XAUUSD")
        & (result.regression_results["analysis_name"] == "sign_predictor_regression")
        & (result.regression_results["sample_period"].str.startswith("2017-01"))
    ]
    assert (sign_regression["nobs"] >= 1).all()
    effects = result.sign_conditioned_results.loc[
        (result.sign_conditioned_results["symbol"] == "XAUUSD")
        & (result.sign_conditioned_results["sample_period"].str.startswith("2017-01"))
    ]
    assert (effects["zero_nobs"] > 0).all()
    for sample_period in effects["sample_period"].unique():
        effect_nobs = effects.loc[effects["sample_period"] == sample_period, "nobs"].iloc[0]
        regression_nobs = sign_regression.loc[sign_regression["sample_period"] == sample_period, "nobs"].iloc[0]
        assert effect_nobs < regression_nobs


def test_m1a_sensitivity_results_are_separate_and_explicit(track_b_config):
    result = _run_m1a_synthetic(_varying_daily_fixture(), track_b_config, include_sensitivity=True)
    sensitivity = result.regression_results.loc[result.regression_results["result_role"] == "sensitivity"]
    assert {"two_way_clustered", "moving_block_bootstrap"}.issubset(set(sensitivity["covariance_method"]))
    bootstrap = sensitivity.loc[sensitivity["covariance_method"] == "moving_block_bootstrap"].iloc[0]
    assert bootstrap["bootstrap_replications"] == 5000
    assert bootstrap["bootstrap_seed"] == 20260817
    assert bootstrap["block_length_months"] == 12
    two_way = sensitivity.loc[sensitivity["covariance_method"] == "two_way_clustered"].iloc[0]
    assert two_way["symbol_cluster_count"] == 2
    assert two_way["outcome_month_cluster_count"] == 60
    assert two_way["degrees_of_freedom"] == 1
    assert two_way["statsmodels_covariance_kwargs"] == {"use_correction": True}


def test_rank_deficient_bootstrap_returns_unavailable_row(track_b_config):
    result = _run_m1a_synthetic(_daily_fixture(), track_b_config, include_sensitivity=True)
    rows = result.regression_results.loc[
        (result.regression_results["covariance_method"] == "moving_block_bootstrap")
        & (result.regression_results["analysis_name"] == "sign_predictor_regression")
    ]
    assert len(rows) == 2
    assert set(rows["inference_status"]) == {"unavailable"}
    assert set(rows["inference_unavailable_reason"]) == {"rank_deficient_design"}
    assert set(rows["bootstrap_executed"]) == {False}
    assert set(rows["attempted_draws"]) == {0}
    assert set(rows["successful_draws"]) == {0}
    assert set(rows["failed_draws"]) == {0}
    assert set(rows["skipped_draws"]) == {5000}


def test_secondary_robustness_does_not_change_primary_pool(track_b_config):
    symbols = track_b_config.primary_symbols + (track_b_config.secondary_symbols[0],)
    data = _daily_fixture(start="2015-09", end="2024-01", symbols=symbols)
    primary_statuses = {symbol: "pass" for symbol in track_b_config.primary_symbols}
    failed_secondary = {**primary_statuses, **{
        symbol: "fail" for symbol in track_b_config.secondary_symbols
    }}
    eligible_secondary = {
        **failed_secondary,
        track_b_config.secondary_symbols[0]: "pass",
    }
    without_secondary = run_m1a_track_b(
        data, track_b_config, _validation_summary(track_b_config, data, status_by_symbol=failed_secondary),
        include_sensitivity=False,
    )
    with_secondary = run_m1a_track_b(
        data, track_b_config, _validation_summary(track_b_config, data, status_by_symbol=eligible_secondary),
        include_sensitivity=False,
    )
    selector = (
        (without_secondary.regression_results["symbol"] == "__pooled__")
        & (without_secondary.regression_results["analysis_name"] == "continuous_regression")
        & (without_secondary.regression_results["sample_period"].str.startswith("2017-01"))
    )
    primary_without = without_secondary.regression_results.loc[selector].iloc[0]
    selector_with = (
        (with_secondary.regression_results["symbol"] == "__pooled__")
        & (with_secondary.regression_results["analysis_name"] == "continuous_regression")
        & (with_secondary.regression_results["sample_period"].str.startswith("2017-01"))
    )
    primary_with = with_secondary.regression_results.loc[selector_with].iloc[0]
    assert primary_with["nobs"] == primary_without["nobs"]
    assert primary_with["beta"] == pytest.approx(primary_without["beta"])
    assert set(with_secondary.regression_results["universe_role"]) == {
        "primary", "secondary_cross_robustness",
    }
    primary_diagnostics = with_secondary.diagnostics["diagnostics_by_universe_role"]["primary"]
    secondary_diagnostics = with_secondary.diagnostics["diagnostics_by_universe_role"]["secondary_cross_robustness"]
    assert primary_diagnostics["observation_count"] > 0
    assert secondary_diagnostics["observation_count"] > 0
    assert with_secondary.diagnostics["analysis_observation_count"] == (
        primary_diagnostics["observation_count"] + secondary_diagnostics["observation_count"]
    )
    assert not ((with_secondary.regression_results["result_role"] == "primary")
                & (with_secondary.regression_results["universe_role"] == "secondary_cross_robustness")).any()
    assert not ((with_secondary.regression_results["symbol"] == "__pooled__")
                & (with_secondary.regression_results["universe_role"] == "secondary_cross_robustness")).any()


def test_eligible_secondary_missing_from_input_fails_fast(track_b_config):
    data = _daily_fixture(start="2015-09", end="2024-01", symbols=track_b_config.primary_symbols)
    statuses = {symbol: "pass" for symbol in track_b_config.primary_symbols}
    statuses.update({symbol: "fail" for symbol in track_b_config.secondary_symbols})
    statuses[track_b_config.secondary_symbols[0]] = "pass"
    with pytest.raises(TrackBDailyValidationError, match="eligible secondary symbols missing from input"):
        run_m1a_track_b(
            data,
            track_b_config,
            _validation_summary(track_b_config, data, status_by_symbol=statuses),
            include_sensitivity=False,
        )


def test_symbol_hac_is_unavailable_for_calendar_gap(track_b_config):
    data = _daily_fixture()
    missing = _session_close(pd.Period("2020-06"))
    data = data.loc[~((data["symbol"] == "XAUUSD") & (data["timestamp"] == missing))].copy()
    result = _run_m1a_synthetic(data, track_b_config, include_sensitivity=False)
    rows = result.regression_results.loc[
        (result.regression_results["symbol"] == "XAUUSD")
        & (result.regression_results["analysis_name"] == "continuous_regression")
        & (result.regression_results["sample_period"].str.startswith("2017-01"))
    ]
    assert len(rows) == 1
    assert rows.iloc[0]["inference_status"] == "unavailable"
    assert rows.iloc[0]["inference_unavailable_reason"] == "non_consecutive_calendar_months"


def test_bootstrap_uses_calendar_slots_and_is_deterministic(track_b_config):
    observations = _build_synthetic_monthly_observations(_daily_fixture(), track_b_config).observations
    sample = observations.loc[observations["split"] == "development"].copy()
    first = moving_block_bootstrap(
        sample, "past_12m_return", "next_1m_return",
        track_b_config.development.start, track_b_config.development.end,
        iterations=25, seed=20260817, block_length=12,
    )
    second = moving_block_bootstrap(
        sample, "past_12m_return", "next_1m_return",
        track_b_config.development.start, track_b_config.development.end,
        iterations=25, seed=20260817, block_length=12,
    )
    assert first.metadata == second.metadata
    assert first.ci_lower == second.ci_lower
    assert first.ci_upper == second.ci_upper
    assert first.metadata["block_length_months"] == 12
    assert first.metadata["bootstrap_unit"] == "calendar_month"


def test_gate_primary_failure_blocks_but_secondary_failure_does_not(track_b_config):
    statuses = {symbol: "pass" for symbol in track_b_config.primary_symbols}
    statuses.update({symbol: "fail" for symbol in track_b_config.secondary_symbols})
    eligible = validate_m1a_real_data_gate(track_b_config, statuses, track_b_config.freeze_version)
    assert eligible == ()

    statuses[track_b_config.primary_symbols[0]] = "fail"
    with pytest.raises(TrackBConfigError, match="primary structural validation gate"):
        validate_m1a_real_data_gate(track_b_config, statuses, track_b_config.freeze_version)


def test_public_surface_only_exposes_track_b_runner(track_b_config):
    import momentum.research as research

    assert research.__all__ == ["run_m1a_track_b"]
    assert callable(run_m1a_track_b)
    assert not hasattr(research, "run_m1a_synthetic")
    assert not hasattr(research, "build_monthly_observations")


def test_track_b_runner_gates_and_excludes_holdout_and_failed_secondary(track_b_config):
    symbols = track_b_config.primary_symbols + track_b_config.secondary_symbols + ("EXTRA",)
    data = _daily_fixture(start="2015-09", end="2024-01", symbols=symbols)
    statuses = {symbol: "pass" for symbol in track_b_config.primary_symbols}
    statuses.update({symbol: "fail" for symbol in track_b_config.secondary_symbols})
    result = run_m1a_track_b(
        data,
        track_b_config,
        _validation_summary(track_b_config, data, status_by_symbol=statuses),
        include_sensitivity=False,
    )
    assert "final_holdout" not in set(result.observations["split"])
    assert set(result.observations["symbol"]) == set(track_b_config.primary_symbols)
    assert "EXTRA" not in result.diagnostics["observations_by_symbol"]
    with pytest.raises(TrackBConfigError, match="primary structural validation gate"):
        run_m1a_track_b(
            data,
            track_b_config,
            _validation_summary(
                track_b_config,
                data,
                status_by_symbol={**statuses, track_b_config.primary_symbols[0]: "fail"},
            ),
            include_sensitivity=False,
        )


def test_track_b_summary_binds_daily_fingerprint_and_freeze(track_b_config):
    data = _daily_fixture(start="2015-09", end="2024-01", symbols=track_b_config.primary_symbols)
    statuses = {symbol: "pass" for symbol in track_b_config.primary_symbols}
    summary = _validation_summary(track_b_config, data, status_by_symbol=statuses)
    result = run_m1a_track_b(data, track_b_config, summary, include_sensitivity=False)
    assert result.metadata["freeze_version"] == track_b_config.freeze_version
    assert result.metadata["dataset_fingerprint"] == summary.dataset_fingerprint
    assert result.metadata["dataset_fingerprint_algorithm"] == SUPPORTED_DATASET_FINGERPRINT_ALGORITHM

    mutated_close = data.copy()
    mutated_close.loc[0, "close"] += 0.01
    with pytest.raises(TrackBDailyValidationError, match="fingerprint"):
        run_m1a_track_b(mutated_close, track_b_config, summary, include_sensitivity=False)

    mutated_timestamp = data.copy()
    mutated_timestamp.loc[0, "timestamp"] += pd.Timedelta(minutes=1)
    with pytest.raises(TrackBDailyValidationError, match="fingerprint"):
        run_m1a_track_b(mutated_timestamp, track_b_config, summary, include_sensitivity=False)

    with pytest.raises(TrackBDailyValidationError, match="fingerprint"):
        run_m1a_track_b(data.iloc[:-1].copy(), track_b_config, summary, include_sensitivity=False)
    with pytest.raises(TrackBDailyValidationError, match="fingerprint"):
        run_m1a_track_b(
            pd.concat([data, data.iloc[[0]]], ignore_index=True),
            track_b_config,
            summary,
            include_sensitivity=False,
        )

    with pytest.raises(TrackBDailyValidationError, match="freeze_version"):
        run_m1a_track_b(
            data,
            track_b_config,
            _validation_summary(
                track_b_config, data, status_by_symbol=statuses,
                freeze_version=track_b_config.freeze_version + 1,
            ),
            include_sensitivity=False,
        )
    with pytest.raises(TrackBDailyValidationError, match="unsupported.*algorithm"):
        run_m1a_track_b(
            data,
            track_b_config,
            _validation_summary(
                track_b_config, data, status_by_symbol=statuses,
                algorithm="unsupported-v0",
            ),
            include_sensitivity=False,
        )
    with pytest.raises(TrackBDailyValidationError, match="unsupported.*spec version"):
        run_m1a_track_b(
            data,
            track_b_config,
            _validation_summary(
                track_b_config,
                data,
                status_by_symbol=statuses,
                structural_spec_version="track-b-structural-v0",
            ),
            include_sensitivity=False,
        )


def test_daily_fingerprint_is_invariant_to_datetime_resolution(track_b_config):
    data = _daily_fixture(start="2020-01", end="2020-03", symbols=("XAUUSD",))
    nanosecond_data = data.copy()
    microsecond_data = data.copy()
    microsecond_data["timestamp"] = microsecond_data["timestamp"].astype("datetime64[us, UTC]")
    assert compute_track_b_daily_fingerprint(nanosecond_data) == compute_track_b_daily_fingerprint(
        microsecond_data
    )


def test_future_month_mutation_does_not_change_prior_observations(track_b_config):
    data = _daily_fixture()
    mutated = data.copy()
    cutoff = _session_close(pd.Period("2021-01"))
    mutated.loc[mutated["timestamp"] > cutoff, "close"] *= 5.0
    before = _run_m1a_synthetic(data, track_b_config, include_sensitivity=False).observations
    after = _run_m1a_synthetic(mutated, track_b_config, include_sensitivity=False).observations
    before = before.loc[before["outcome_month"] < pd.Period("2021-01")].reset_index(drop=True)
    after = after.loc[after["outcome_month"] < pd.Period("2021-01")].reset_index(drop=True)
    pd.testing.assert_frame_equal(before, after)


def test_consecutive_month_helper_does_not_compress_gaps():
    assert outcome_months_are_consecutive([pd.Period("2020-01"), pd.Period("2020-02")])
    assert not outcome_months_are_consecutive([pd.Period("2020-01"), pd.Period("2020-03")])
