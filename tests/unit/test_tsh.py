from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from momentum.research.track_b_config import load_track_b_config
from momentum.signals.tsh import TSHSignalError, generate_tsh_signals


ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module")
def track_b_config():
    return load_track_b_config(ROOT / "config" / "research_track_b.yaml")


def _daily_monthly(closes: list[float], start: str = "2015-09") -> pd.DataFrame:
    periods = pd.period_range(start, periods=len(closes), freq="M")
    rows = []
    for index, (month, close) in enumerate(zip(periods, closes)):
        first = month.start_time.tz_localize("UTC")
        second = (month.start_time + pd.Timedelta(days=1)).tz_localize("UTC")
        rows.extend([
            {
                "symbol": "XAUUSD",
                "timestamp": first,
                "open": 1000.0 + index,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close - 0.5,
            },
            {
                "symbol": "XAUUSD",
                "timestamp": second,
                "open": 2000.0 + index,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
            },
        ])
    return pd.DataFrame(rows)


def test_tsh_uses_month_end_close_and_arithmetic_expanding_mean(track_b_config):
    data = _daily_monthly(
        [100.0, 110.0, 99.0, 108.9, 108.9, 119.79, 119.79],
        start="2016-09",
    )
    generated = generate_tsh_signals(
        data,
        track_b_config,
        analysis_start="2017-01",
        analysis_end="2017-02",
    )

    row = generated.decision_table.loc[
        generated.decision_table["formation_month"] == pd.Period("2017-01")
    ].iloc[0]
    assert row["month_end_close"] == pytest.approx(108.9)
    assert row["monthly_return"] == pytest.approx(0.0)
    assert row["historical_mean"] == pytest.approx(0.025)
    assert row["tsh_signal"] == 1.0
    assert row["holding_month"] == pd.Period("2017-02")
    assert row["entry_timestamp"] == pd.Timestamp("2017-02-01", tz="UTC")


def test_zero_historical_mean_is_long(track_b_config):
    data = _daily_monthly([100.0, 110.0, 99.0, 99.0, 99.0, 99.0], start="2016-10")
    generated = generate_tsh_signals(
        data,
        track_b_config,
        analysis_start="2016-12",
        analysis_end="2017-01",
    )
    row = generated.decision_table.loc[
        generated.decision_table["formation_month"] == pd.Period("2016-12")
    ].iloc[0]
    assert row["historical_mean"] == pytest.approx(0.0)
    assert row["tsh_signal"] == 1.0
    jan = data["timestamp"].dt.to_period("M").eq(pd.Period("2017-01"))
    assert generated.target_position.loc[jan].eq(1).all()


def test_requested_calendar_month_missing_is_fail_fast(track_b_config):
    periods = pd.period_range("2015-09", "2020-08", freq="M")
    data = _daily_monthly([100.0 + index for index in range(len(periods))])
    data = data.loc[data["timestamp"].dt.to_period("M") != pd.Period("2020-06")]
    with pytest.raises(TSHSignalError, match="2020-06"):
        generate_tsh_signals(
            data,
            track_b_config,
            analysis_start="2020-01",
            analysis_end="2020-07",
        )


def test_open_pnl_does_not_change_historical_mean(track_b_config):
    data = _daily_monthly(
        [100.0, 110.0, 99.0, 108.9, 108.9, 119.79, 119.79],
        start="2016-09",
    )
    mutated = data.copy()
    mutated["open"] = np.linspace(10.0, 10000.0, len(mutated))
    first = generate_tsh_signals(data, track_b_config, analysis_start="2017-01", analysis_end="2017-02")
    second = generate_tsh_signals(mutated, track_b_config, analysis_start="2017-01", analysis_end="2017-02")
    pd.testing.assert_series_equal(
        first.monthly_history["historical_mean"],
        second.monthly_history["historical_mean"],
        check_names=False,
    )
    pd.testing.assert_series_equal(first.signal, second.signal)


def test_future_close_mutation_does_not_change_prior_signal(track_b_config):
    data = _daily_monthly(
        [100.0, 110.0, 99.0, 108.9, 108.9, 119.79, 119.79],
        start="2016-09",
    )
    mutated = data.copy()
    mutated.loc[mutated["timestamp"] >= pd.Timestamp("2017-02-01", tz="UTC"), "close"] *= 3.0
    first = generate_tsh_signals(data, track_b_config, analysis_start="2017-01", analysis_end="2017-02")
    second = generate_tsh_signals(mutated, track_b_config, analysis_start="2017-01", analysis_end="2017-02")
    cutoff = data["timestamp"] < pd.Timestamp("2017-02-01", tz="UTC")
    pd.testing.assert_series_equal(
        first.target_position.loc[cutoff].reset_index(drop=True),
        second.target_position.loc[cutoff].reset_index(drop=True),
    )
