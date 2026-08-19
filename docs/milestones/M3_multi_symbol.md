# M3 — Multi-Symbol Common Rule

## Status
High-level contract defined. Implementation may proceed after M0-M2.

## 目的
M0と同じdaily ruleを複数symbolへ独立適用し、single-symbol dependencyを確認する。
TSH challengeで必要になるsymbol-level monthly historiesも再利用可能にする。

## 参照docs
- `docs/02_research_questions.md`
- `docs/04_validation_policy.md`
- `docs/05_roadmap.md`
- `docs/06_evaluation_protocol.md`
- `docs/07_academic_validation_spec.md`

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
- monthly history export usable by TSH comparator

## TSH preparation
M3開始前に、`docs/07_academic_validation_spec.md`のTSH exact historical-mean contractを
`tsh_spec_version = tsh-huang-v1`としてfreezeする。M3/M4/M7で同一contractを再利用する。

TSH historical meanは各symbolの最初のvalid monthly returnからformation month `M`までの
month-end Close-to-Close returnを使う。

```text
P[M] = month M の最後の valid Daily Close
r_monthly[M] = P[M] / P[M-1] - 1
historical_mean[M] = arithmetic expanding mean through M inclusive
historical_mean >= 0 -> Long
historical_mean <  0 -> Short
```

executed Open-to-Open strategy PnLはhistorical meanへ入力しない。strategy returnは
M2と共有する次のaccountingで計算する。

```text
entry = first available Open of M+1
exit  = first available Open of M+2
accounting_engine = shared_daily_open_to_open_v1
```

paper/referenceとTrack B practical analogueはcausalityの対立ではなく、次の
machine-readable method roleで分離する。

- `tsh_huang_reference`
- `tsh_track_b_practical`

primary TSM-vs-TSH comparison maskは日付範囲ではなく、各symbolの**M2 TSM-valid/formable
holding months**とする。TSMとTSHは同一holding month、同一first-Open execution boundary、
同一daily Open-to-Open return intervalで比較し、TSHだけ早い期間をprimary comparisonへ
追加しない。早期TSH signalはwarmup diagnosticに限定する。

## 非対象
- portfolio weighting
- vol scaling
- cost layer
- symbol selection based on performance

## 成果物
- symbol x metrics table
- symbol x year diagnostic
- same-config reproducibility report
- TSM/TSH-compatible monthly history table

## 必須テスト
- multiple symbols reuse same engine
- no symbol-specific parameter override
- one symbol failure does not corrupt others
- timestamp/data validation per symbol
- deterministic aggregation of reports
- no future data in TSH signal history
- TSM-vs-TSH uses the M2 TSM-valid holding-month mask
- historical mean and executed strategy PnL use separate return definitions

## 完了条件
- all symbols run under common rule
- no hidden per-symbol tuning
- outputs separable by symbol
- no portfolio return yet

## 人間が決める未決事項
M1前にfreezeしたsymbol universeを使う。
追加symbolを入れる場合は新しいexperimentとして扱う。
TSH exact conventionはM3開始前にreferenceから固定する。
TSH output metadataには`freeze_version`、`structural_spec_version`、`dataset_fingerprint`、
`dataset_fingerprint_algorithm`、`tsh_spec_version`、`method_role`、
`accounting_engine`、`final_holdout_included`を記録し、M1A/M2と同一dataset identityを要求する。
