# Development Roadmap

## M0 — Single-Symbol Pure Daily TSMOM

成果:
- causal signal
- basic trade engine
- gross metrics
- unit tests

完了条件:
- lookahead test通過
- 手計算fixtureとsignal一致

## M1 — Multi-Symbol Common Rule

成果:
- 同一lookbackを全symbolへ適用
- symbol別report

完了条件:
- symbol固有parameterなしで実行可能

## M2 — Portfolio Aggregation

成果:
- portfolio equity
- return / DD / Sharpe
- exposure summary

## M3 — Volatility Normalization

成果:
- equal notional vs equal risk比較
- concentration診断

## M4 — Cost Layer

成果:
- spread / commission / slippage
- gross/net分離
- swap capability（データがあれば）

## M5 — Robust Validation

成果:
- plateau
- chronological validation
- holdout
- cost stress
- year/symbol slices

## M6 — 4h Momentum

Dailyと同じ研究プロトコルで短期化。

## M7 — 1h Momentum

turnover/cost/whipsawに重点。
