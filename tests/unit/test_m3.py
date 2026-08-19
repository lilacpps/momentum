from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from momentum.backtest import run_m0_backtest
from momentum.data.track_b import compute_track_b_daily_fingerprint
from momentum.research import m3
from momentum.research.track_b_config import (
    SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
    SUPPORTED_STRUCTURAL_SPEC_VERSION,
    StructuralValidationSummary,
    load_track_b_config,
)
from momentum.signals.m2 import M2SignalResult


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


def _summary(config, daily):
    return StructuralValidationSummary(
        freeze_version=config.freeze_version,
        structural_spec_version=SUPPORTED_STRUCTURAL_SPEC_VERSION,
        dataset_fingerprint=compute_track_b_daily_fingerprint(daily),
        dataset_fingerprint_algorithm=SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
        status_by_symbol={
            symbol: "pass"
            for symbol in config.primary_symbols + config.secondary_symbols
        },
    )


def test_m3_passes_full_dataset_to_m2_and_canonical_frame_to_m0_tsh(track_b_config, monkeypatch):
    daily = _daily_fixture(track_b_config)
    summary = _summary(track_b_config, daily)
    original = m3.run_m2_track_b
    captured = {}

    def wrapped(full_daily, *args, **kwargs):
        captured["frame"] = full_daily
        return original(full_daily, *args, **kwargs)

    monkeypatch.setattr(m3, "run_m2_track_b", wrapped)
    result = m3.run_m3_symbol(
        daily,
        track_b_config,
        summary,
        symbol=track_b_config.primary_symbols[0],
        universe_role="primary",
    )

    assert captured["frame"] is daily
    assert set(captured["frame"]["symbol"]) == set(
        track_b_config.primary_symbols + track_b_config.secondary_symbols
    )
    expected = result.m0.bars["timestamp"]
    assert result.tsh.bars["timestamp"].equals(expected)
    assert result.m2 is not None
    assert result.m2.bars["timestamp"].equals(expected)
    assert pd.isna(result.tsh.bars.iloc[-1]["strategy_return"])
    assert result.comparison["holding_month_count"] > 0
    valid_months = tuple(
        result.m2_generated.decision_table["holding_month"].dropna().tolist()
    )
    masked = m3._masked_metrics(result.m2, valid_months[:1], result.window)
    assert masked["return_count"] < result.m2_metrics["return_count"]
    expected_entry = result.m2_generated.decision_table["entry_timestamp"]
    actual_entry = result.m2.bars.loc[result.m2.bars["signal"].notna(), "timestamp"]
    pd.testing.assert_series_equal(
        pd.to_datetime(expected_entry, utc=True).reset_index(drop=True),
        pd.to_datetime(actual_entry, utc=True).reset_index(drop=True),
        check_names=False,
    )

    standalone = run_m0_backtest(m3._execution_frame(daily, track_b_config, result.window))
    pd.testing.assert_frame_equal(
        standalone.bars,
        result.m0.bars,
        check_dtype=False,
    )


def test_secondary_runs_m0_and_tsh_only(track_b_config):
    daily = _daily_fixture(track_b_config)
    result = m3.run_m3_symbol(
        daily,
        track_b_config,
        _summary(track_b_config, daily),
        symbol=track_b_config.secondary_symbols[0],
        universe_role="secondary_cross_robustness",
    )
    assert result.m2 is None
    assert result.comparison is None
    assert result.m0.metadata.get("method_role") is None
    assert result.tsh.metadata["method_role"] == "tsh_track_b_practical"


def test_m3_method_identities_are_not_relabelled(track_b_config):
    daily = _daily_fixture(track_b_config)
    result = m3.run_m3_symbol(
        daily,
        track_b_config,
        _summary(track_b_config, daily),
        symbol=track_b_config.primary_symbols[0],
        universe_role="primary",
    )
    assert result.m0.metadata.get("tsh_spec_version") is None
    assert result.m0.metadata.get("method_role") is None
    assert result.m2 is not None
    assert result.m2.metadata["spec_version"] == "m2-practical-v1"
    assert result.m2.metadata.get("method_role") is None
    assert result.tsh.metadata["tsh_spec_version"] == "tsh-huang-v1"
    assert result.tsh.metadata["method_role"] == "tsh_track_b_practical"


def test_m2_mask_distinguishes_nan_zero_and_signed_signals(track_b_config):
    table = pd.DataFrame({
        "holding_month": pd.period_range("2017-01", periods=4, freq="M"),
        "signal": [float("nan"), 0.0, 1.0, -1.0],
    })
    generated = M2SignalResult(
        signal=pd.Series(dtype="float64"),
        target_position=pd.Series(dtype="int8"),
        rebalance=pd.Series(dtype="bool"),
        decision_table=table,
    )
    months = m3._valid_holding_months(generated, track_b_config)
    assert months == (pd.Period("2017-02"), pd.Period("2017-03"), pd.Period("2017-04"))
