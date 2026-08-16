# M1 — Academic Hypothesis + Reference Statistical Validation

## Status
Workstream別。M1Aは `Ready after Track B split / universe freeze`、M1Bは `Ready only after eligible reference underlying data is identified`、M1C-Huang-referenceは `Ready after Huang methodology contract freeze and eligible reference underlying data`、M1C-Huang-practical-analogueは `Ready after Huang methodology contract freeze and Track B data`。

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
Track BについてM1結果を見る前にdevelopment / validation / final holdout / symbol universe /
data source / timezone / daily boundaryをfreeze済み。
Track A published sampleはreplication sampleとして別管理。
M1AはAcademic underlying dataなしでも実行可能。AQR factor-only workbookはM1Bのunderlyingとはみなさない。
M1B data unavailable / pendingでもM1AとAQR sanity checkは停止しない。M1C-Huang-referenceも
reference underlyingがなければpendingとし、M1C-Huang-practical-analogueはTrack B dataで独立して進める。

## Workstream A — M1A Practical Predictability

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

## Workstream B — M1B MOP Regression Comparator

- excess-return dataを使える場合は優先
- ex-ante vol standardization
- annualization 261
- EWMA center-of-mass 60 days
- `sigma[t-1]` information lag
- pooled monthly regression
- lag `h=1...60`
- monthly calendar-time clustering
- focused 12m cumulative -> next1m comparatorも別表

## Workstream C — M1C Huang Challenge

`M1C-Huang-reference` はeligible reference underlying dataが必要。
`M1C-Huang-practical-analogue` はTrack B dataで実行できるが、Huang replicationとは呼ばない。

- asset-by-asset regression
- pooled regression
- fixed-effect sensitivity
- scaled / unscaled sensitivity
- parametric wild bootstrap
- nonparametric pairs bootstrap

challenge module開始前に、`docs/07_academic_validation_spec.md`のHuang methodology contractをfreezeし、
その後に実装してfixture testを作る。

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

### Workstream completion and unblock rule

- M1A complete: Practical predictability tables, diagnostics, and inference are complete after the Track B freeze.
- M1B complete: eligible reference underlying data is available and the MOP comparator is executed; otherwise `data unavailable / pending`.
- M1C-Huang-reference complete: Huang contract is frozen and eligible reference underlying data is available; otherwise `data unavailable / pending`.
- M1C-Huang-practical-analogue complete: the same frozen challenge contract is executed on Track B data and labeled as an analogue, not a Huang replication.

M1全体がcompleteでなくても、M1AがcompleteならM2をunblockする。M1B/M1Cの未完了はPractical Trackを停止しない。

## 人間が決める未決事項
M1開始前:
- Track B split dates
- Track B validation / final holdout periods
- Track B symbol universe
- Track B data source / timezone / daily boundary
- Academic Trackで利用可能なdata source

M1C開始前:
- Huang bootstrap contract freeze（null / regression / residual / Rademacher / pairs / T / statistic / p-value / missing）
- paper-explicit bootstrap replications = 1,000
- implementation seed value and seed policy
