# M7 — Robust Historical Validation

## Status
Framework defined. Exact split dates and validation rules must already be frozen before M1.

## 目的
事前固定したstrategyがparameter / symbol / year / regime / holdoutに対してrobustか確認する。

## 参照docs
- `docs/02_research_questions.md`
- `docs/04_validation_policy.md`
- `docs/05_roadmap.md`
- `docs/06_evaluation_protocol.md`

## 前提
M1開始前に、
- development
- validation
- final holdout
- symbol universe
がfreeze済みであること。

## 実装対象
- parameter plateau
- validation period
- year slices
- symbol slices
- rolling metrics
- underwater analysis
- cost stress
- walk-forward
- benchmarks
- final holdout one-shot evaluation

## Final holdout policy
M7まで原則見ない。

final holdoutを開いた後に、
- lookback
- symbol universe
- filter
- execution rule
- convenient cost assumption
を変更して同じholdoutを再利用しない。

## 実装前に固定すべき事項
- exact split dates
- walk-forward window definitions
- parameter grid
- benchmark set
- plateau judgment rule
- minimum sample criteria
- final report metrics
- go/no-go decision rule

## 推奨benchmark
- always-long
- zero-position / cash
- M0 daily unscaled
- M2 monthly comparator
- M4 equal-notional
- M5 vol-scaled

## 完了条件
- final holdout evaluated once
- all metrics reproducible
- parameter plateau documented
- negative evidence also retained
- Track A / Track B separately reported
