from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from momentum.backtest import run_target_backtest
from momentum.research.track_b_config import load_track_b_config
from momentum.signals.m2 import M2SignalError, generate_m2_signals


ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module")
def track_b_config():
    return load_track_b_config(ROOT / "config" / "research_track_b.yaml")


def _monthly_daily_fixture(start="2015-12", end="2024-01"):
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

    first = generated.decision_table.iloc[0]
    assert first["formation_month"] == pd.Period("2016-12")
    assert first["holding_month"] == pd.Period("2017-01")
    assert first["split"] == "development"
    assert first["signal"] == 1

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


def test_missing_pre_sample_history_makes_only_signal_flat(track_b_config):
    data = _monthly_daily_fixture()
    data = data.loc[data["timestamp"].dt.to_period("M") != pd.Period("2015-12")].copy()
    generated = generate_m2_signals(data, track_b_config)
    first = generated.decision_table.iloc[0]
    assert first["holding_month"] == pd.Period("2017-01")
    assert np.isnan(first["signal"])
    assert first["past_12m_return"] != first["past_12m_return"]
    jan = data["timestamp"].dt.to_period("M").eq(pd.Period("2017-01")).to_numpy()
    assert generated.target_position.loc[jan].eq(0).all()


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
