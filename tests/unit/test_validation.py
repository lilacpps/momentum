import numpy as np
import pandas as pd
import pytest

from momentum.data.validation import OHLCValidationError
from momentum.backtest.engine import run_m0_backtest


def test_short_valid_dataset_is_processed_as_warmup():
    data = pd.DataFrame({
        "timestamp": pd.date_range("2020-01-01", periods=2),
        "open": [1.0, 2.0], "high": [1.0, 2.0],
        "low": [1.0, 2.0], "close": [1.0, 2.0],
    })
    result = run_m0_backtest(data)
    assert result.bars["signal"].isna().all()
    assert (result.bars["target_position"] == 0).all()
    assert (result.bars["executed_position"] == 0).all()


def test_valid_ohlc_with_non_default_index_is_processed_by_position():
    data = pd.DataFrame({
        "timestamp": pd.date_range("2020-01-01", periods=2),
        "open": [1.0, 2.0], "high": [1.0, 2.0],
        "low": [1.0, 2.0], "close": [1.0, 2.0],
    }, index=[1000, 1001])
    result = run_m0_backtest(data)
    assert result.bars["timestamp"].tolist() == data["timestamp"].tolist()
    assert result.bars.index.tolist() == [0, 1]


@pytest.mark.parametrize("column", ["open", "close"])
def test_nan_ohlc_is_rejected(column):
    data = pd.DataFrame({
        "timestamp": pd.date_range("2020-01-01", periods=2),
        "open": [1.0, 2.0], "high": [1.0, 2.0],
        "low": [1.0, 2.0], "close": [1.0, 2.0],
    })
    data.loc[0, column] = np.nan
    with pytest.raises(OHLCValidationError):
        run_m0_backtest(data)


def test_duplicate_and_unsorted_timestamps_are_rejected():
    base = pd.DataFrame({
        "timestamp": pd.date_range("2020-01-01", periods=2),
        "open": [1.0, 2.0], "high": [1.0, 2.0],
        "low": [1.0, 2.0], "close": [1.0, 2.0],
    })
    duplicate = base.copy()
    duplicate.loc[1, "timestamp"] = duplicate.loc[0, "timestamp"]
    with pytest.raises(OHLCValidationError):
        run_m0_backtest(duplicate)
    unsorted = base.iloc[::-1].reset_index(drop=True)
    with pytest.raises(OHLCValidationError):
        run_m0_backtest(unsorted)
