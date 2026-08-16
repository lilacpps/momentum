# M1 — Academic Hypothesis Check

## Status
Specification-ready after split/universe freeze.

## 目的
strategy PnLとは別に、TSMOMの中心的なpredictive relationを直接検証する。

```text
past 12-month return -> next 1-month return
```

## 参照docs
- `docs/02_research_questions.md`
- `docs/03_data_and_costs.md`
- `docs/04_validation_policy.md`
- `docs/05_roadmap.md`
- `docs/06_evaluation_protocol.md`
- `docs/07_academic_validation_spec.md`

## 前提
M0完了済み。
さらにM1を見る前に、
- development
- validation
- final holdout
- symbol universe
をfreeze済みであること。

## 固定仕様

### Practical Track
```text
P[M] = month M の最後のvalid Daily Close
past_12m_return[M] = P[M] / P[M-12] - 1
next_1m_return[M]  = P[M+1] / P[M] - 1
```

### Academic Track
futures / forward / excess-returnまたはreference dataが利用可能なら、
spot resultと分離して評価する。

## Primary analyses
- sign-conditioned next-month return
- continuous predictor regression
- sign-predictor regression
- symbol-level effect size
- pooled / cross-market effect
- confidence intervals
- sample-size diagnostics

## Statistical policy
naive IID standard errorのみをprimary evidenceにしない。

default:
- symbol-level: HAC / Newey-West系
- lag default: 12 months
- pooled: two-way clustered SEが可能なら使用
- alternative: calendar-month block bootstrap
- method / lag / seedをmetadataへ保存

## 実装対象
M1はM3 multi-symbol backtest engineを必要としない。
別のresearch/statistics moduleで複数symbol seriesを読んでよい。

## 非対象
- broker execution
- transaction cost
- swap
- portfolio construction
- parameter optimization

## 成果物
- Track A / Track Bを分けたprediction tables
- effect-size report
- CI / inference metadata
- symbol-level table
- pooled summary
- sample diagnostics

## 完了条件
- return definitions are deterministic and tested
- no future leakage in formation variables
- statistical method is recorded
- Track A / Track B are not mixed
- result language respects `docs/06_evaluation_protocol.md`

## 人間が決める未決事項
M1開始前に実データに対して固定する:
- development / validation / holdout dates
- symbol universe
- Academic Trackで利用可能なdata source
