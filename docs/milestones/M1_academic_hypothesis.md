# M1 — Academic Hypothesis + Reference Statistical Validation

## Status
Workstream別。M1A implementationは `Ready after valid current Track B freeze artifact`、M1A real-data executionは
`Ready after current freeze version structural validation pass or pass_with_warning`、AQR Reference Sanityは
`Ready independently of eligible MOP underlying data`、M1Bは `Ready only after eligible reference underlying data is identified`、
M1C-Huang-referenceは `Ready after Huang methodology contract freeze and eligible reference underlying data`、
M1C-Huang-practical-analogueは `Ready after Huang methodology contract freeze and Track B data`。
statusは`not_ready`、`ready`、`in_progress`、`complete`、`data_unavailable_pending`をworkstream単位で
保持し、M1全体を単一booleanで扱わない。

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
Track BについてM1結果を見る前に、`config/research_track_b.yaml`としてconcrete freeze artifactを
保存済みとする。artifactの時期・version policyは`docs/04`、data source / price type / timezone /
daily boundaryの意味は`docs/03`、M1 methodologyは`docs/07`をauthoritative sourceとする。
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

`M-12`は厳密に12 calendar months前であり、observed rowの12行前ではない。required calendar monthが
欠ける場合は補間せずobservationをunavailableとし、missing/excluded countを記録する。zero returnは
sign `0`とし、sign-conditioned groupから除外するがsign regressionのrowには保持する。

Primary:
- sign-conditioned next-month return
- continuous predictor regression
- sign-predictor regression
- symbol-level effect size
- pooled / cross-market effect
- symbol-level primary: HAC / Newey-West, lag 12 months
- pooled primary: calendar-month clustered SE
- sensitivity: symbol × calendar-month two-way cluster and calendar-month block bootstrap

## Workstream B — M1B MOP Regression Comparator

- excess-return dataを使える場合は優先
- ex-ante vol standardization
- annualization 261
- EWMA center-of-mass 60 days
- `sigma[t-1]` information lag
- pooled monthly regression
- lag `h=1...60`
- monthly calendar-time clustering
- canonical equation and causal `sigma[t-1]` predictor indexing are defined in `docs/07`
- 0.40 target-volatility sizing is excluded from M1B regression and belongs to M5
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

`T_i`、asset内path resampling、Huang reference fixed-effectのdemeaned equation、97.5th-percentile
critical valueは`docs/07`に従う。`Huang_reference_inference`と
`project_positive_tsm_one_sided`は別methodとして報告する。

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
- return unit conversion
- annualization factor
- Sharpe calculation convention
- missing-value handling

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

- M1A complete: Practical predictability tables, diagnostics, and inference are complete after the current freeze version's structural validation is `pass` or `pass_with_warning` and real-data execution is complete.
- M1B complete: eligible reference underlying data is available and the MOP comparator is executed; otherwise `data unavailable / pending`.
- M1C-Huang-reference complete: Huang contract is frozen and eligible reference underlying data is available; otherwise `data unavailable / pending`.
- M1C-Huang-practical-analogue complete: the same frozen challenge contract is executed on Track B data and labeled as an analogue, not a Huang replication.
- AQR Reference Sanity complete: workbook inventory and factor-series sanity diagnostics are complete; it does not require eligible MOP underlying data.

M1全体がcompleteでなくても、M1AがcompleteならM2をunblockする。M1B/M1Cの未完了はPractical Trackを停止しない。

## Pre-implementation checklist

### M1A

- [ ] Track B development / validation / final holdout periods frozen in artifact
- [ ] Track B symbol universe frozen in artifact
- [ ] Track B data source / price type frozen in artifact
- [ ] Track B timezone / daily boundary frozen in artifact
- [ ] Calendar-month, missing-month, and zero-return semantics accepted from `docs/07`
- [ ] Symbol HAC(12) and pooled calendar-month primary inference frozen

### M1B

- [ ] Eligible reference underlying identified
- [ ] Canonical MOP regression equation frozen in `docs/07`
- [ ] Volatility standardization and causal `sigma[t-1]` contract frozen
- [ ] 0.40 strategy sizing excluded from the regression contract

### M1C

- [ ] Huang paper methodology rechecked
- [ ] Resampling unit and asset identity/path rule frozen
- [ ] FE procedure and demeaned reference equation frozen
- [ ] Huang reference inference and 97.5th-percentile critical value frozen
- [ ] Project one-sided diagnostic separated from Huang reference inference
- [ ] Bootstrap iterations frozen
- [ ] Bootstrap seed and seed policy frozen

### AQR Reference Sanity

- [ ] Workbook sheets, frequency, period, unit, and missingness inventoried
- [ ] Annualization factor and Sharpe convention recorded

## Human decisions still required

M1A開始前:
- a valid current Track B freeze artifact is present and frozen

M1C開始前:
- Huang bootstrap contract freeze（null / regression / residual / Rademacher / pairs / T_i convention /
  statistic / 97.5th-percentile critical value / missing / fixed-effect equation）
- paper-explicit bootstrap replications = 1,000
- implementation seed value and seed policy

M1B開始前:
- Academic Trackで利用可能なeligible reference underlying data source
