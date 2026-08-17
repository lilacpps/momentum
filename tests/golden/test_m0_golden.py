import numpy as np
import pandas as pd

from momentum.backtest.engine import run_m0_backtest


def test_first_valid_signal_is_t241_and_requires_242_rows(synthetic_ohlc):
    result = run_m0_backtest(synthetic_ohlc.iloc[:242])
    bars = result.bars
    assert bars.loc[240, "signal"] != bars.loc[240, "signal"]
    assert bars.loc[241, "signal"] == 1.0  # Close[240] / Close[0] - 1
    assert bars.loc[241, "target_position"] == 1
    assert bars.loc[241, "executed_position"] == 1
    assert bars.loc[241, "entry_price"] == synthetic_ohlc.loc[241, "open"]


def test_hand_calculated_state_transitions_and_episodes(synthetic_ohlc):
    result = run_m0_backtest(synthetic_ohlc)
    bars, ledger = result.bars, result.ledger
    expected = {241: 1, 242: -1, 243: 0, 244: 1, 245: 1, 246: 0,
                247: -1, 248: 1, 249: 0, 250: -1, 251: -1}
    for index, position in expected.items():
        assert bars.loc[index, "target_position"] == position
        assert bars.loc[index, "executed_position"] == position
    assert bars.loc[243, "signal"] == 0.0
    assert bars.loc[241, "execution_event"] == "enter_long"
    assert bars.loc[242, "execution_event"] == "reverse_long_to_short"
    assert bars.loc[245, "execution_event"] == "hold"
    assert bars.loc[248, "execution_event"] == "reverse_short_to_long"
    assert bars.loc[246, "execution_event"] == "exit_long"
    assert len(ledger) == 6
    assert ledger["status"].tolist() == ["closed", "closed", "closed", "closed", "closed", "open"]
    assert ledger.loc[1, "reversal_from_episode_id"] == 0


def test_result_is_deterministic(synthetic_ohlc):
    first = run_m0_backtest(synthetic_ohlc)
    second = run_m0_backtest(synthetic_ohlc)
    assert first.bars.equals(second.bars)
    assert first.ledger.equals(second.ledger)
    assert first.metrics == second.metrics


def test_entry_position_owns_only_open_to_next_open_and_terminal_is_not_liquidated(synthetic_ohlc):
    result = run_m0_backtest(synthetic_ohlc)
    bars = result.bars
    # Entry at t=241 uses Open[241]; its return is Open[242]/Open[241]-1.
    assert bars.loc[241, "asset_return"] == synthetic_ohlc.loc[242, "open"] / synthetic_ohlc.loc[241, "open"] - 1
    assert bars.loc[241, "strategy_return"] == bars.loc[241, "asset_return"]
    assert np.isnan(bars.loc[251, "asset_return"])
    assert np.isnan(bars.loc[251, "strategy_return"])
    assert bars.loc[251, "cumulative_gross_return"] == bars.loc[250, "cumulative_gross_return"]
    assert result.ledger.iloc[-1]["status"] == "open"
    assert pd.isna(result.ledger.iloc[-1]["exit_timestamp"])


def test_overnight_gap_is_not_attributed_to_new_position(synthetic_ohlc):
    result = run_m0_backtest(synthetic_ohlc.iloc[:243])
    bars = result.bars
    # Deliberately huge Close[240] -> Open[241] gap; no return column uses it.
    assert bars.loc[241, "strategy_return"] == synthetic_ohlc.loc[242, "open"] / synthetic_ohlc.loc[241, "open"] - 1


def test_metadata_and_metrics_are_gross_only(synthetic_ohlc):
    result = run_m0_backtest(synthetic_ohlc, {
        "symbol": "SYNTH",
        "academic_mop_replication": True,
        "result_level": "full_broker_net",
    })
    assert result.metadata["baseline_type"] == "simplified_daily_tsmom"
    assert result.metadata["academic_mop_replication"] is False
    assert result.metadata["result_level"] == "gross_price_only"
    assert result.metadata["symbol"] == "SYNTH"
    assert result.metrics["trade_count"] == len(result.ledger)


def test_future_mutation_does_not_change_causal_past(synthetic_ohlc):
    cutoff = 245
    mutated = synthetic_ohlc.copy()
    mutated.loc[cutoff + 1:, "close"] += 10000
    mutated.loc[cutoff + 1:, "open"] *= 3
    before = run_m0_backtest(synthetic_ohlc).bars
    after = run_m0_backtest(mutated).bars
    for column in ["signal", "target_position", "executed_position"]:
        assert before.loc[:cutoff, column].equals(after.loc[:cutoff, column])
    for column in ["asset_return", "strategy_return"]:
        assert before.loc[:cutoff - 1, column].equals(after.loc[:cutoff - 1, column])
    assert before.loc[cutoff, "strategy_return"] != after.loc[cutoff, "strategy_return"]
