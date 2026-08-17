from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from momentum.data.track_b import TrackBDailyValidationError, build_monthly_observations, validate_track_b_daily
from momentum.research.inference import moving_block_bootstrap, outcome_months_are_consecutive
from momentum.research.m1a import run_m1a
from momentum.research.track_b_config import TrackBConfigError, load_track_b_config, validate_m1a_real_data_gate


ROOT = Path(__file__).parents[2]


def _session_close(month: pd.Period) -> pd.Timestamp:
    local = month.start_time.tz_localize("America/New_York").replace(hour=17)
    return local.tz_convert("UTC")


def _daily_fixture(start: str = "2015-01", end: str = "2024-01", symbols=("XAUUSD", "EURUSD")) -> pd.DataFrame:
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


@pytest.fixture(scope="module")
def track_b_config():
    return load_track_b_config(ROOT / "config" / "research_track_b.yaml")


def test_config_loader_validates_current_frozen_artifact(track_b_config):
    assert track_b_config.status == "frozen"
    assert track_b_config.freeze_version == 1
    assert track_b_config.split_assignment_basis == "next_1m_return_outcome_month"
    assert track_b_config.boundary_timezone == "America/New_York"
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
    validated = validate_track_b_daily(data)
    assert validated["timestamp"].dt.tz is not None
    pd.testing.assert_frame_equal(data, original)

    duplicate = pd.concat([data, data.iloc[[0]]], ignore_index=True)
    with pytest.raises(TrackBDailyValidationError, match="duplicate"):
        validate_track_b_daily(duplicate)


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
    extra["timestamp"] = extra["timestamp"] + pd.Timedelta(hours=1)
    extra["close"] = 999.0
    extra["open"] = 998.9
    extra["high"] = 999.2
    extra["low"] = 998.8
    data = pd.concat([data, extra], ignore_index=True).sort_values(["symbol", "timestamp"]).reset_index(drop=True)

    built = build_monthly_observations(data, track_b_config)
    row = built.observations.loc[
        (built.observations["symbol"] == "XAUUSD")
        & (built.observations["formation_month"] == pd.Period("2020-06"))
    ].iloc[0]
    assert row["past_12m_return"] == pytest.approx(999.0 / prior - 1.0)
    assert row["next_1m_return"] == pytest.approx(next_close / 999.0 - 1.0)


def test_calendar_month_uses_new_york_local_date_not_utc_bar_open(track_b_config):
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
    built = build_monthly_observations(data, track_b_config)
    row = built.observations.loc[
        (built.observations["formation_month"] == pd.Period("2020-05"))
        & (built.observations["outcome_month"] == pd.Period("2020-06"))
    ]
    assert len(row) == 1
    assert row.iloc[0]["next_1m_return"] == pytest.approx(777.0 / may_close - 1.0)


def test_missing_calendar_month_is_excluded_without_fill(track_b_config):
    data = _daily_fixture()
    missing = _session_close(pd.Period("2019-06"))
    data = data.loc[~((data["symbol"] == "XAUUSD") & (data["timestamp"] == missing))].copy()
    built = build_monthly_observations(data, track_b_config)
    assert len(built.observations.loc[
        (built.observations["symbol"] == "XAUUSD")
        & (built.observations["formation_month"] == pd.Period("2019-06"))
    ]) == 0
    assert "2019-06" in built.diagnostics["missing_calendar_months"]["XAUUSD"]
    assert built.diagnostics["excluded_observation_count"] > 0


def test_outcome_month_split_and_final_holdout_is_not_returned_by_analysis(track_b_config):
    data = _daily_fixture()
    built = build_monthly_observations(data, track_b_config)
    final_row = built.observations.loc[
        (built.observations["symbol"] == "XAUUSD")
        & (built.observations["formation_month"] == pd.Period("2023-12"))
    ].iloc[0]
    assert final_row["outcome_month"] == pd.Period("2024-01")
    assert final_row["split"] == "final_holdout"
    result = run_m1a(data, track_b_config, include_sensitivity=False)
    assert "final_holdout" not in set(result.observations["split"])
    assert (result.observations["outcome_month"] < pd.Period("2024-01")).all()


def test_warmup_is_history_but_first_development_outcome_is_assigned_by_outcome_month(track_b_config):
    built = build_monthly_observations(_daily_fixture(), track_b_config)
    first_development = built.observations.loc[
        (built.observations["symbol"] == "XAUUSD")
        & (built.observations["outcome_month"] == pd.Period("2017-01"))
    ].iloc[0]
    assert first_development["formation_month"] == pd.Period("2016-12")
    assert first_development["split"] == "development"
    warmup = built.observations.loc[
        (built.observations["symbol"] == "XAUUSD")
        & (built.observations["outcome_month"] == pd.Period("2016-12"))
    ].iloc[0]
    assert warmup["split"] == "warmup"


def test_m1a_results_have_primary_metadata_and_zero_semantics(track_b_config):
    data = _daily_fixture()
    result = run_m1a(data, track_b_config, include_sensitivity=False)
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

    result = run_m1a(data, track_b_config, include_sensitivity=False)
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
    result = run_m1a(_varying_daily_fixture(), track_b_config, include_sensitivity=True)
    sensitivity = result.regression_results.loc[result.regression_results["result_role"] == "sensitivity"]
    assert {"two_way_clustered", "moving_block_bootstrap"}.issubset(set(sensitivity["covariance_method"]))
    bootstrap = sensitivity.loc[sensitivity["covariance_method"] == "moving_block_bootstrap"].iloc[0]
    assert bootstrap["bootstrap_replications"] == 5000
    assert bootstrap["bootstrap_seed"] == 20260817
    assert bootstrap["block_length_months"] == 12


def test_symbol_hac_is_unavailable_for_calendar_gap(track_b_config):
    data = _daily_fixture()
    missing = _session_close(pd.Period("2020-06"))
    data = data.loc[~((data["symbol"] == "XAUUSD") & (data["timestamp"] == missing))].copy()
    result = run_m1a(data, track_b_config, include_sensitivity=False)
    rows = result.regression_results.loc[
        (result.regression_results["symbol"] == "XAUUSD")
        & (result.regression_results["analysis_name"] == "continuous_regression")
        & (result.regression_results["sample_period"].str.startswith("2017-01"))
    ]
    assert len(rows) == 1
    assert rows.iloc[0]["inference_status"] == "unavailable"
    assert rows.iloc[0]["inference_unavailable_reason"] == "non_consecutive_calendar_months"


def test_bootstrap_uses_calendar_slots_and_is_deterministic(track_b_config):
    observations = build_monthly_observations(_daily_fixture(), track_b_config).observations
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


def test_future_month_mutation_does_not_change_prior_observations(track_b_config):
    data = _daily_fixture()
    mutated = data.copy()
    cutoff = _session_close(pd.Period("2021-01"))
    mutated.loc[mutated["timestamp"] > cutoff, "close"] *= 5.0
    before = run_m1a(data, track_b_config, include_sensitivity=False).observations
    after = run_m1a(mutated, track_b_config, include_sensitivity=False).observations
    before = before.loc[before["outcome_month"] < pd.Period("2021-01")].reset_index(drop=True)
    after = after.loc[after["outcome_month"] < pd.Period("2021-01")].reset_index(drop=True)
    pd.testing.assert_frame_equal(before, after)


def test_consecutive_month_helper_does_not_compress_gaps():
    assert outcome_months_are_consecutive([pd.Period("2020-01"), pd.Period("2020-02")])
    assert not outcome_months_are_consecutive([pd.Period("2020-01"), pd.Period("2020-03")])
