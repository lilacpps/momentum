from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from momentum.backtest import run_target_backtest
from momentum.data.track_b import TrackBDailyValidationError, compute_track_b_daily_fingerprint
from momentum.metrics.gross import gross_metrics
from momentum.research import run_m2_track_b
from momentum.research.track_b_config import (
    SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
    SUPPORTED_STRUCTURAL_SPEC_VERSION,
    StructuralValidationSummary,
    load_track_b_config,
)
from momentum.signals.m2 import M2SignalError, generate_m2_signals


ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module")
def track_b_config():
    return load_track_b_config(ROOT / "config" / "research_track_b.yaml")


def _monthly_daily_fixture(start="2015-09", end="2024-01"):
    rows = []
    periods = pd.period_range(start, end, freq="M")
    for index, month in enumerate(periods):
        for day in (1, 2):
            timestamp = month.start_time + pd.Timedelta(days=day - 1)
            close = 100.0 + index
            rows.append({
                "symbol": "XAUUSD",
                "timestamp": timestamp,
                "open": close + day / 100.0,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
            })
    return pd.DataFrame(rows)


def test_m2_uses_month_end_close_and_first_open_of_holding_month(track_b_config):
    data = _monthly_daily_fixture()
    generated = generate_m2_signals(data, track_b_config)

    first = generated.decision_table.loc[
        generated.decision_table["holding_month"] == pd.Period("2017-01")
    ].iloc[0]
    assert first["formation_month"] == pd.Period("2016-12")
    assert first["holding_month"] == pd.Period("2017-01")
    assert first["split"] == "development"
    assert first["signal"] == 1
    assert first["entry_timestamp"] == pd.Timestamp("2017-01-01")


def test_m2_uses_first_available_open_after_calendar_gap(track_b_config):
    data = _monthly_daily_fixture()
    dec = data["timestamp"].dt.to_period("M") == pd.Period("2016-12")
    jan = data["timestamp"].dt.to_period("M") == pd.Period("2017-01")
    data.loc[dec, "timestamp"] = [pd.Timestamp("2016-12-30"), pd.Timestamp("2016-12-31")]
    data.loc[jan, "timestamp"] = [pd.Timestamp("2017-01-03"), pd.Timestamp("2017-01-04")]
    generated = generate_m2_signals(data.sort_values("timestamp").reset_index(drop=True), track_b_config)
    first = generated.decision_table.loc[
        generated.decision_table["holding_month"] == pd.Period("2017-01")
    ].iloc[0]
    assert first["entry_timestamp"] == pd.Timestamp("2017-01-03")
    assert first["entry_timestamp"] != pd.Timestamp("2016-12-31")

    jan = data["timestamp"].dt.to_period("M") == pd.Period("2017-01")
    assert generated.target_position.loc[jan].tolist() == [1, 1]
    assert generated.rebalance.loc[jan].tolist() == [True, False]


def test_m2_does_not_generate_boundary_month_position(track_b_config):
    data = _monthly_daily_fixture()
    generated = generate_m2_signals(data, track_b_config)
    boundary = data["timestamp"].dt.to_period("M") == pd.Period("2024-01")
    assert (generated.target_position.loc[boundary] == 0).all()
    assert pd.Period("2024-01") not in set(generated.decision_table["holding_month"])


def test_missing_requested_month_is_an_error_without_fill(track_b_config):
    data = _monthly_daily_fixture()
    data = data.loc[data["timestamp"].dt.to_period("M") != pd.Period("2020-06")].copy()
    with pytest.raises(M2SignalError, match="2020-06"):
        generate_m2_signals(data, track_b_config)


def test_missing_terminal_boundary_month_is_an_error(track_b_config):
    data = _monthly_daily_fixture()
    data = data.loc[data["timestamp"].dt.to_period("M") != pd.Period("2024-01")].copy()
    with pytest.raises(M2SignalError, match="2024-01"):
        generate_m2_signals(data, track_b_config)


def test_v3_config_has_no_m2_specific_field(tmp_path, track_b_config):
    artifact = dict(track_b_config.raw)
    artifact["split_assignment"] = dict(artifact["split_assignment"])
    artifact["split_assignment"].pop("m2_basis", None)
    path = tmp_path / "track_b.yaml"
    path.write_text(yaml.safe_dump(artifact, sort_keys=False), encoding="utf-8")
    loaded = load_track_b_config(path)
    assert "m2_basis" not in loaded.raw["split_assignment"]


def test_missing_pre_sample_history_makes_only_signal_flat(track_b_config):
    data = _monthly_daily_fixture()
    data = data.loc[data["timestamp"].dt.to_period("M") != pd.Period("2015-12")].copy()
    generated = generate_m2_signals(data, track_b_config)
    first = generated.decision_table.loc[
        generated.decision_table["holding_month"] == pd.Period("2017-01")
    ].iloc[0]
    assert first["holding_month"] == pd.Period("2017-01")
    assert np.isnan(first["signal"])
    assert first["past_12m_return"] != first["past_12m_return"]
    jan = data["timestamp"].dt.to_period("M").eq(pd.Period("2017-01")).to_numpy()
    assert generated.target_position.loc[jan].eq(0).all()


def test_zero_signal_is_flat(track_b_config):
    data = _monthly_daily_fixture()
    past = data["timestamp"].dt.to_period("M") == pd.Period("2015-12")
    formation = data["timestamp"].dt.to_period("M") == pd.Period("2016-12")
    data.loc[past | formation, "close"] = 777.0
    data.loc[past | formation, "open"] = 777.1
    data.loc[past | formation, "high"] = 778.0
    data.loc[past | formation, "low"] = 776.0
    generated = generate_m2_signals(data, track_b_config)
    row = generated.decision_table.loc[
        generated.decision_table["holding_month"] == pd.Period("2017-01")
    ].iloc[0]
    assert row["signal"] == 0
    jan = data["timestamp"].dt.to_period("M").eq(pd.Period("2017-01")).to_numpy()
    assert generated.target_position.loc[jan].eq(0).all()


def test_future_mutation_does_not_change_prior_m2_signals(track_b_config):
    data = _monthly_daily_fixture()
    mutated = data.copy()
    cutoff = pd.Timestamp("2020-01-01")
    mutated.loc[mutated["timestamp"] >= cutoff, "close"] *= 3.0
    before = generate_m2_signals(data, track_b_config)
    after = generate_m2_signals(mutated, track_b_config)
    prior = data["timestamp"] < cutoff
    pd.testing.assert_series_equal(
        before.target_position.loc[prior].reset_index(drop=True),
        after.target_position.loc[prior].reset_index(drop=True),
    )
    pd.testing.assert_series_equal(
        before.signal.loc[prior].reset_index(drop=True),
        after.signal.loc[prior].reset_index(drop=True),
    )


def test_shared_metrics_use_initial_equity_as_drawdown_peak():
    bars = pd.DataFrame({
        "timestamp": pd.date_range("2020-01-01", periods=2, freq="D"),
        "strategy_return": [-0.10, 0.05],
        "executed_position": [1, 1],
        "reversal_from_episode_id": [None, None],
    })
    metrics = gross_metrics(pd.DataFrame(), bars)
    assert metrics["max_drawdown"] == pytest.approx(-0.10)


def test_sample_window_events_exclude_carry_in_and_future_activity():
    data = pd.DataFrame({
        "timestamp": pd.date_range("2020-01-01", periods=6, freq="D"),
        "open": [100.0, 101.0, 102.0, 101.0, 100.0, 99.0],
        "high": [101.0, 102.0, 103.0, 102.0, 101.0, 100.0],
        "low": [99.0, 100.0, 101.0, 100.0, 99.0, 98.0],
        "close": [100.0, 101.0, 102.0, 101.0, 100.0, 99.0],
    })
    result = run_target_backtest(data, pd.Series([1, 1, -1, -1, 0, 0]))
    metrics = gross_metrics(
        result.ledger,
        result.bars,
        sample_start=pd.Timestamp("2020-01-02"),
        sample_end=pd.Timestamp("2020-01-06"),
    )
    assert metrics["turnover"] == 3.0  # reverse 2 + exit 1; warmup entry excluded
    assert metrics["trade_count"] == 1  # only the short episode starts in-window
    assert metrics["average_holding"] == 2.0
    assert metrics["reversal_count"] == 1
    assert metrics["reversal_frequency"] == pytest.approx(1 / 2)
    assert metrics["carry_in_episode_count"] == 1
    assert metrics["carry_in_position"] == 1
    assert metrics["carry_out_episode_count"] == 0


def _track_b_fixture(config, end="2024-06"):
    rows = []
    periods = pd.period_range("2015-09", end, freq="M")
    for symbol_index, symbol in enumerate(config.primary_symbols):
        for index, month in enumerate(periods):
            close = 100.0 + symbol_index + index
            rows.append({
                "symbol": symbol,
                "timestamp": month.start_time.tz_localize("UTC"),
                "open": close,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
            })
    return pd.DataFrame(rows)


def _summary(config, data):
    statuses = {
        **{symbol: "pass" for symbol in config.primary_symbols},
        **{symbol: "fail" for symbol in config.secondary_symbols},
    }
    return StructuralValidationSummary(
        freeze_version=config.freeze_version,
        structural_spec_version=SUPPORTED_STRUCTURAL_SPEC_VERSION,
        dataset_fingerprint=compute_track_b_daily_fingerprint(data),
        dataset_fingerprint_algorithm=SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
        status_by_symbol=statuses,
    )


def test_production_runner_truncates_at_validation_boundary_and_rejects_holdout(track_b_config):
    data = _track_b_fixture(track_b_config)
    summary = _summary(track_b_config, data)
    result = run_m2_track_b(
        data,
        track_b_config,
        summary,
        symbol=track_b_config.primary_symbols[1],
    )
    assert result.metadata["final_holdout_included"] is False
    assert result.bars["timestamp"].max() == pd.Timestamp("2024-01-01", tz="UTC")
    assert result.bars["timestamp"].max() < pd.Timestamp("2024-02-01", tz="UTC")
    assert result.metrics["return_count"] > 0
    with pytest.raises(TypeError):
        run_m2_track_b(data, track_b_config, summary, symbol=track_b_config.primary_symbols[1], include_holdout=True)


def test_production_runner_binds_fingerprint(track_b_config):
    data = _track_b_fixture(track_b_config)
    summary = _summary(track_b_config, data)
    mutated = data.copy()
    mutated.loc[0, "close"] += 0.01
    with pytest.raises(TrackBDailyValidationError, match="fingerprint"):
        run_m2_track_b(mutated, track_b_config, summary, symbol=track_b_config.primary_symbols[0])


def test_shared_daily_accounting_reports_m2_metrics():
    data = pd.DataFrame({
        "timestamp": pd.date_range("2020-01-01", periods=3, freq="D"),
        "open": [100.0, 110.0, 105.0],
        "high": [101.0, 111.0, 106.0],
        "low": [99.0, 109.0, 104.0],
        "close": [100.0, 110.0, 105.0],
    })
    result = run_target_backtest(data, pd.Series([1, 1, 0]), pd.Series([1.0, np.nan, 0.0]))
    assert result.metrics["gross_return"] == pytest.approx(0.05)
    assert result.metrics["max_drawdown"] == pytest.approx(-5.0 / 110.0)
    assert result.metrics["turnover"] == 2.0
    assert result.metrics["trade_count"] == 1
    assert result.metrics["average_holding"] == 2.0
    assert result.metrics["reversal_count"] == 0
