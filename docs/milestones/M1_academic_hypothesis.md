# M1 — Academic Hypothesis + Reference Statistical Validation

## Status
Ready after Track B split/universe freeze.
Reference bootstrap algorithm details must be locked from `references/7.Time-series momentum_ Is it there_.pdf` while implementing the challenge module.

## 目的
strategy PnLとは別にTSMOMのpredictive relationを直接検証し、MOPのregression evidenceとHuang et al.の反証を同じresearch stageで確認する。

## 参照docs
- `docs/02_research_questions.md`
- `docs/03_data_and_costs.md`
- `docs/04_validation_policy.md`
- `docs/05_roadmap.md`
- `docs/06_evaluation_protocol.md`
- `docs/07_academic_validation_spec.md`

## 前提
M0完了済み。
Track BについてM1結果を見る前にdevelopment / validation / final holdout / symbol universeをfreeze済み。
Track A published sampleはreplication sampleとして別管理。

## Workstream A — Practical Track

```text
P[M] = month M の最後のvalid Daily Close
past_12m_return[M] = P[M] / P[M-12] - 1
next_1m_return[M]  = P[M+1] / P[M] - 1
```

Primary:
- sign-conditioned next-month return
- continuous predictor regression
- sign-predictor regression
- symbol-level effect size
- pooled / cross-market effect
- HAC / clustered uncertainty

## Workstream B — MOP Regression Comparator

- excess-return dataを使える場合は優先
- ex-ante vol standardization
- annualization 261
- EWMA center-of-mass 60 days
- `sigma[t-1]` information lag
- pooled monthly regression
- lag `h=1...60`
- monthly calendar-time clustering
- focused 12m cumulative -> next1m comparatorも別表

## Workstream C — Huang Challenge

- asset-by-asset regression
- pooled regression
- fixed-effect sensitivity
- scaled / unscaled sensitivity
- parametric wild bootstrap
- nonparametric pairs bootstrap

bootstrap algorithmのresidual / null / resampling unitは`references/7.Time-series momentum_ Is it there_.pdf` から固定し、fixture testを作る。

## Workstream D — AQR Reference Sanity

workbookをinventoryし、factor seriesが確認できる場合:

- period
- frequency
- observation count
- unit
- mean / vol / Sharpe
- cumulative path

をreportする。
raw underlying seriesを仮定しない。

## 非対象
- broker execution
- transaction cost
- swap
- portfolio construction
- parameter optimization
- TSH portfolio comparison（M3-M7）

## 成果物
- Track A / Track B separated prediction tables
- MOP lag-regression table / figure
- effect-size report
- bootstrap critical-value / p-value report
- symbol-level table
- pooled summary
- AQR sanity report
- sample diagnostics
- inference metadata

## 完了条件
- return definitions deterministic and tested
- no future leakage in formation / vol variables
- MOP comparator and Practical analogue clearly labeled
- bootstrap algorithm and seed recorded
- pooled t-stat alone is not final evidence
- Track A / Track B are not mixed
- result language respects `docs/06_evaluation_protocol.md`

## 人間が決める未決事項
M1開始前:
- Track B split dates
- Track B symbol universe
- Academic Trackで利用可能なdata source

implementation中・resultsを見る前:
- Huang bootstrap exact algorithm details from reference paper
- number of bootstrap replications（compute budgetと精度のtrade-offを事前固定）
