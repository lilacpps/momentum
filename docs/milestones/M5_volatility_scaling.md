# M5 — Volatility Normalization

## Status
Specification incomplete. Must be finalized before implementation.

## 目的
directional signalを変えず、
position sizingのみ変えることでrisk scalingの効果を分離する。

## 参照docs
- `docs/00_momentum_overview.md`
- `docs/01_academic_baseline.md`
- `docs/02_research_questions.md`
- `docs/04_validation_policy.md`
- `docs/05_roadmap.md`
- `docs/06_evaluation_protocol.md`

## 比較対象
- unscaled / equal-notional
- volatility-scaled / equal-risk

## 実装前に人間が決める事項
- volatility estimator
- estimator lookback
- return frequency
- annualization convention
- target volatility / target risk
- position cap / leverage cap
- volatility floor
- missing volatility handling
- signal/vol information lag
- rebalance cadence
- portfolio-level targetかasset-level targetか
- MOP methodologyへどこまで近づけるか

## 実装対象
仕様固定後に、
- ex-ante volatility estimate
- scaled target exposure
- contribution diagnostics
- unscaled-vs-scaled comparison
を実装する。

## 非対象
- signal変更
- momentum strength filter
- optimizer
- costs（M6）

## 必須テスト
仕様確定後に追加:
- vol lag causality
- zero/near-zero vol
- cap/floor
- annualization
- target sizing
- no future data
- scaled contribution accounting

## 完了条件
- estimator/target/capが文書固定
- unscaled signal path unchanged
- scaling改善をsignal alphaと表現しない
