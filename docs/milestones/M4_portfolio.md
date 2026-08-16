# M4 — Portfolio Aggregation

## Status
Partially specified. Final weighting/alignment rules must be frozen before implementation.

## 目的
M3のsymbol-level returnsをportfolioへ集約し、cross-market diversificationを評価する。
TSM / TSH challengeのportfolio-level比較ができるaggregation layerを作る。

## 参照docs
- `docs/02_research_questions.md`
- `docs/04_validation_policy.md`
- `docs/05_roadmap.md`
- `docs/06_evaluation_protocol.md`
- `docs/07_academic_validation_spec.md`

## 初期方針
baselineは **equal-notional**。
portfolio constructionとsignal generationを分離する。

## 実装対象
- return alignment
- equal-notional aggregation
- portfolio equity / return
- DD / Sharpe
- exposure summary
- contribution summary
- TSM / TSH portfolio series aggregation

## 2種類のuniverse alignment

### Practical comparison
推奨defaultはcommon valid start以降。

### MOP reference comparator preparation
M5では「その月にavailableなinstrumentsをequal weight」するreference modeが必要。
M4のcommon-valid-start practical modeと混ぜない。

## 非対象
- volatility scaling
- performance-based symbol weighting
- dynamic optimizer
- transaction costs

## 実装前に固定すべき事項
- equal-notionalの厳密な数式
- symbolごとのdata start差の扱い
- practical common valid start
- missing symbol-dayの扱い
- portfolio rebalance cadence
- unavailable symbolを0 weightにするかexperiment exclusionにするか
- FX common-currency exposureは診断のみか制約するか
- TSH series convention

## 推奨default
- experiment universe事前固定
- common valid startをPractical主要比較期間
- ex-post performanceでsymbol除外しない
- missing dataをperformance都合でforward-fillしない
- initial portfolioはsimple equal-notional

## 必須テスト
- weights sum / exposure contract
- missing data behavior
- contribution sums to portfolio return
- aligned dates only
- deterministic universe handling
- TSM and TSH aggregation use identical universe/weight contract within each comparison

## 完了条件
上記未決事項が文書化され、equal-notional portfolioがreproducibleであること。
