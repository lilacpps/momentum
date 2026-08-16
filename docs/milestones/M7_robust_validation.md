# M7 — Robust Historical Validation + Challenge Benchmarks

## Status
Framework defined. Exact Track B split dates and validation rules must already be frozen before any
historical Track B performance is generated. Huang bootstrap contract is frozen before M1C implementation,
and TSH exact reference convention is frozen before M3; neither is deferred to M7.

## 目的
事前固定したstrategyがparameter / symbol / year / regime / challenge benchmark / practical holdoutに対してrobustか確認する。

## 参照docs
- `docs/02_research_questions.md`
- `docs/04_validation_policy.md`
- `docs/05_roadmap.md`
- `docs/06_evaluation_protocol.md`
- `docs/07_academic_validation_spec.md`

## 前提
Track BについてM1開始前に、development / validation / final holdout / symbol universe /
data source / timezone / daily boundaryがfreeze済み。
Track A published sampleはreplication sampleとして分離。

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
- TSM vs TSH
- long / short leg attribution
- weighting-scheme sensitivity
- Track B final holdout one-shot evaluation

## TSM vs TSH Challenge

最低限:

- TSM mean / vol / Sharpe
- TSH mean / vol / Sharpe
- TSM - TSH mean
- uncertainty of difference
- long legs
- short legs
- equal-weight comparison
- volatility-weight comparison where appropriate

reference TSHとcausal TSHが異なる場合は別series。

TSMがprofitableでもTSHを明確に上回らない場合、profitをpredictabilityの証拠とは結論しない。

## Track B Final holdout policy
M7まで原則見ない。

final holdoutを開いた後に、
- lookback
- symbol universe
- filter
- execution rule
- convenient cost assumption
を変更して同じholdoutを再利用しない。

## Track A policy
MOP published sample等はknown replication sampleとして報告する。
post-publication Academic OOSがある場合は別ラベルで一度だけ評価する。

## M7開始時に既にfreeze済みであるべき事項
- exact Track B split dates
- Track B data source
- Track B timezone
- Track B daily boundary
- symbol universe
- TSH exact historical-mean convention

## M7開始前に新たに固定する事項
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
- M5 practical vol-scaled
- M5 MOP-compatible reference-scaled
- TSH reference comparator
- TSH causal analogue（必要な場合）

## 完了条件
- Track B final holdout evaluated once
- all metrics reproducible
- parameter plateau documented
- TSM-vs-TSH conclusion documented
- long/short attribution documented
- negative evidence retained
- Track A / Track B separately reported
