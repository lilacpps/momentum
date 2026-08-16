# M3 — Multi-Symbol Common Rule

## Status
High-level contract defined. Implementation may proceed after M0-M2.

## 目的
M0と同じdaily ruleを複数symbolへ独立適用し、
single-symbol dependencyを確認する。

## 参照docs
- `docs/02_research_questions.md`
- `docs/04_validation_policy.md`
- `docs/05_roadmap.md`
- `docs/06_evaluation_protocol.md`

## 固定方針
- common rule
- common lookback contract
- symbol-specific parameter tuning禁止
- M0 single-symbol engineを変更せず再利用
- M3ではportfolio aggregationしない

## 実装対象
- multi-symbol orchestration
- symbol-level result collection
- symbol-level metrics
- common metadata
- failure/isolation handling per symbol

## 非対象
- portfolio weighting
- vol scaling
- cost layer
- symbol selection based on performance

## 成果物
- symbol x metrics table
- symbol x year diagnostic
- same-config reproducibility report

## 必須テスト
- multiple symbols reuse same engine
- no symbol-specific parameter override
- one symbol failure does not corrupt others
- timestamp/data validation per symbol
- deterministic aggregation of reports

## 完了条件
- all symbols run under common rule
- no hidden per-symbol tuning
- outputs are separable by symbol
- no portfolio return yet

## 人間が決める未決事項
M1前にfreezeしたsymbol universeを使う。
追加symbolを入れる場合は新しいexperimentとして扱う。
