# M4 — Portfolio Aggregation

## Status
Partially specified. Final weighting/alignment rules must be frozen before implementation.

## 目的
M3のsymbol-level returnsをportfolioへ集約し、
cross-market diversificationを評価する。

## 参照docs
- `docs/02_research_questions.md`
- `docs/04_validation_policy.md`
- `docs/05_roadmap.md`
- `docs/06_evaluation_protocol.md`

## 初期方針
baselineは **equal-notional**。
portfolio constructionとsignal generationを分離する。

## 実装対象
- return alignment
- equal-notional aggregation
- portfolio equity
- portfolio return
- DD
- Sharpe
- exposure summary
- contribution summary

## 非対象
- volatility scaling
- performance-based symbol weighting
- dynamic optimizer
- transaction costs

## 実装前に固定すべき事項
- equal-notionalの厳密な数式
- symbolごとのdata start差の扱い
- common valid startを使うか
- missing symbol-dayの扱い
- portfolio rebalance cadence
- unavailable symbolを0 weightにするかexperiment exclusionにするか
- FX common-currency exposureは診断のみか制約するか

## 推奨default
- experiment universeは事前固定
- common valid start以降を主要比較期間とする
- ex-post performanceでsymbolを除外しない
- missing dataをperformance都合でforward-fillしない
- initial portfolioはsimple equal-notional

## 必須テスト
- weights sum / exposure contract
- missing data behavior
- contribution sums to portfolio return
- aligned dates only
- deterministic universe handling

## 完了条件
上記未決事項が文書化され、
equal-notional portfolioがreproducibleであること。
