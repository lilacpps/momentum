# M0 — Engine Correctness

## Status
Ready for implementation.

## 目的
Single-symbol Daily TSMOM baselineを、lookaheadやaccounting ambiguityなしに正しく実装する。
M0の合否はprofitabilityではなく **engine correctness** で判定する。

## 参照docs
- `docs/00_momentum_overview.md`
- `docs/01_academic_baseline.md`
- `docs/03_data_and_costs.md`
- `docs/04_validation_policy.md`
- `docs/05_roadmap.md`
- `docs/06_evaluation_protocol.md`
- `config/baseline.example.yaml`

## 固定仕様
- single symbol
- Daily OHLC
- lookback = 240 return intervals
- required Close observations = 241
- signal = `Close[t-1] / Close[t-241] - 1`
- `>0 Long / <0 Short / =0 Flat`
- insufficient history = undefined signal, target Flat
- decision after `Close[t-1]`
- execution at `Open[t]`
- same signal = hold
- reversal = close and reverse at same `Open[t]`
- normalized exposure = `-1 / 0 / +1`
- periodic return = `Open[t+1] / Open[t] - 1`
- strategy return = executed position × asset return
- synthetic terminal liquidation = none
- costs = none
- volatility scaling = none
- portfolio = none

## 実装対象
- input validation
- signal generation
- target-position generation
- execution/state transition
- return accounting
- trade/position ledger
- basic gross metrics
- deterministic output
- test fixtures

## 非対象
- multi-symbol orchestration
- portfolio aggregation
- volatility normalization
- spread / commission / slippage / swap
- TP / SL
- parameter optimization
- walk-forward
- profitability gating
- MOP regression reproduction
- Huang bootstrap analysis

## 成果物
- reusable single-symbol engine
- hand-calculated golden fixture
- unit tests
- gross result table
- trade ledger
- metadata showing this is not MOP replication

## 必須テスト
- positive / negative / zero signal
- 240 intervals require 241 Close observations
- warm-up boundary
- off-by-one
- `t-1 Close -> t Open`
- overnight-gap fixture
- Flat→Long / Flat→Short
- Long→Long / Short→Short
- Long→Flat / Short→Flat
- Long→Short / Short→Long
- no unnecessary trade on unchanged target
- lookahead mutation
- duplicate timestamp
- unsorted timestamp
- NaN open / close
- insufficient observations
- final open position left open
- deterministic rerun

## 完了条件
- all M0 tests pass
- hand-calculated signal / execution / PnL match
- future mutation does not alter past outputs
- no cost / vol / portfolio logic in M0 execution path
- terminal handling follows documented policy

## 次工程へ進む前の必須作業
Track BについてM1 historical resultを見る前に以下をfreezeする。

- development period
- validation period
- final holdout period
- symbol universe
- data source / timezone / daily boundary

Track Aのpublished replication sampleは上記holdoutと分離する。

## 人間が決める未決事項
M0についてはなし。実装開始可能。
