# M1 / M2 / M5 / Challenge Academic Validation Specification

## M1A v2 implementation safety convention

The normative Track B structural-validation implementation contract is maintained in `docs/04_validation_policy.md`; this document defines the M1A methodology and its interface to that contract.

The implementation identifier is `spec_version = m1a-practical-v1`. The only
production execution entry point is `run_m1a_track_b`. Synthetic fixtures may
use private test-support builders, but they are not production package exports.
The Track B builder performs the structural-status and matching `freeze_version`
gate itself, filters eligible symbols before monthly construction and diagnostics,
and constructs real-data observations only through the Validation outcome month.
Final Holdout observations are not constructed or returned by the real-data path.

Each observation carries `universe_role`. Normative primary analyses use only
the frozen primary universe. Eligible secondary symbols are reported only as
symbol-level robustness results with `result_role = robustness` and
`universe_role = secondary_cross_robustness`; no combined secondary pooled
primary is implied by this contract.
Diagnostics retain aggregate counts for backward compatibility and additionally
report `diagnostics_by_universe_role` with observation, positive, negative, and
zero counts for primary and secondary robustness samples.

Structural validation is bound to the executed prepared Daily dataset by
`dataset_fingerprint_algorithm = track-b-daily-sha256-v1`. The fingerprint
covers only `symbol`, `timestamp`, `open`, `high`, `low`, and `close`; rows are
canonicalized by symbol and UTC timestamp ordering before deterministic SHA-256
serialization. `run_m1a_track_b` rejects any fingerprint, algorithm, or
freeze-version mismatch before producing an M1A result.
Its structural-validation input is a `StructuralValidationSummary` containing
`freeze_version`, `structural_spec_version`, `dataset_fingerprint`,
`dataset_fingerprint_algorithm`, and `status_by_symbol`.
The frozen structural specification identifier is
`structural_spec_version = track-b-structural-v2`; other structural spec
versions are rejected. Timestamp serialization is a signed int64 count of
nanoseconds since the Unix epoch after UTC canonicalization, independent of the
input datetime dtype resolution.

For real Track B v2 input, `timestamp` is the prepared Daily bar label. A
timezone-naive timestamp in the prepared CSV is accepted by the production
loader and interpreted as a UTC label; the canonical in-memory `timestamp` is
always timezone-aware UTC. It need not represent the nominal
`America/New_York` 17:00 session close, and no NY17 conversion is performed.
Calendar month identity is derived from the canonical prepared timestamp's UTC
calendar month.
The v2 structural validator performs only minimal fail-fast checks and passes
the same validated prepared Daily dataset to fingerprinting and M1A.

The current Track B freeze v3 requests prepared Daily data from `2015-09`
through `2026-06`. `2015-09` through `2016-12` is warmup history. The first
Development outcome is `2017-01`, whose formation month is `2016-12` and whose
past-12m price begins at `2015-12`; therefore the v3 availability change does
not remove any Development sample.

Statsmodels robust results are the inference authority for one-way HAC and
calendar-month cluster confidence intervals: `conf_int()` and `t_test()` are
used directly with the frozen covariance options. For pooled cluster results,
metadata records `outcome_month_cluster_count`, the expected degrees of freedom
(`cluster_count - 1`), `statsmodels_df_resid_inference`, and whether those values
match. OLS `df_resid` is never used as a fallback for clustered inference.
If `statsmodels_df_resid_inference` exists and does not equal the expected
cluster-count-minus-one value, the result is `inference_status = unavailable`
with `inference_unavailable_reason = cluster_df_mismatch`.

Rank-deficient designs, including constant predictors and one-sided
sign-conditioned samples, have `inference_status = unavailable` and
`inference_unavailable_reason = rank_deficient_design`. Symbol HAC(12) is also
unavailable, without row compression, when outcome months are not a consecutive
calendar-month sequence.

For two-way cluster sensitivity, the statsmodels API metadata contains only
`use_correction = True` because that is the supported `cov_cluster_2groups`
option. The project-side convention separately records `df_correction = True`,
`use_t = True`, cluster counts, and
`degrees_of_freedom = min(symbol_cluster_count, outcome_month_cluster_count) - 1`.

この文書はM1/M2/M5およびHuang/TSH challengeのnormative research contractです。
ここにない実装詳細は、原典の仕様として扱わず、実装前に別途
`implementation convention` として記録します。

---

# 1. Track / Split Contract

## 1.1 Track A — Academic / Reference

MOP等のpublished sampleは結果が既知なので、**replication sample**として扱います。

- published sampleをfinal holdoutと呼ばない
- reference methodology reproductionに使用可能
- AQR published factor seriesはsanity checkに使用
- post-publication dataが得られればAcademic OOSを別途定義可能

## 1.2 Track B — Practical Spot/CFD

M0 implementation、golden fixture / synthetic data / unit tests、engine correctness
判定を先に完了します。M1Aは、`docs/04_validation_policy.md`に定義された有効なTrack B
concrete freeze artifactが存在する場合にだけReadyとします。freezeの時期、artifact保存、version policyは
`docs/04_validation_policy.md`、data source / price type / timezone / daily boundaryの意味は
`docs/03_data_and_costs.md`を参照します。

- development period
- validation period
- final holdout period
- symbol universe
- data source / timezone / daily boundary

split/universe freeze前に許される実データ利用は、schema、timestamp、ordering、missingness等の
structural validationだけです。strategy performance、predictive result、PnL、Sharpe等は生成・閲覧しません。
freeze後に初めてhistorical gross resultを生成します。

final holdoutはM7まで原則見ません。

## 1.3 M1 workstream status

M1は一つのReady gateではなく、次のworkstreamごとに判定します。
許容statusは少なくとも`not_ready`、`ready`、`in_progress`、`complete`、
`data_unavailable_pending`です。例えば`M1A complete / M1B data_unavailable_pending /
M1C pending`を正式な状態として扱い、M1全体を単一booleanに集約しません。

| Workstream | 内容 | Status |
|---|---|---|
| M1A Practical Predictability | past 12m spot/CFD return -> next 1m return | Complete for current freeze v3 after structural validation and real-data execution |
| AQR Reference Sanity | workbook inventory and factor-series sanity | Ready independently of eligible MOP underlying data |
| M1B MOP Regression Comparator | eligible futures / forward / excess-return underlying series | Ready only after eligible reference underlying data is identified |
| M1C-Huang-reference | Huang methodology contract + eligible MOP-like reference underlying series | Ready after methodology freeze and eligible reference underlying data |
| M1C-Huang-practical-analogue | same frozen methodology on Track B data | Ready after methodology freeze and Track B data |

AQR workbookがfactor returnだけの場合、それだけでlag-by-lag instrument regression用のunderlying
seriesがあるとはみなしません。underlyingが確保できない場合もM1AとAQR factor sanity checkは進め、
M1Bだけを `data unavailable / pending` と報告します。M1C-Huang-referenceもeligible reference
underlyingがない場合は `data unavailable / pending` とし、M1C-Huang-practical-analogueはTrack B
dataで独立して進めます。後者をHuang replicationとは呼びません。

---

# 2. M1 — Practical Predictability Track

## 2.1 Monthly series

Daily dataから、

```text
P[M] = month M の最後のvalid Daily Close
```

を作ります。

```text
past_12m_return[M] = P[M] / P[M-12] - 1
next_1m_return[M]  = P[M+1] / P[M] - 1
```

`M-12`は観測month列の12行前ではなく、厳密に12 calendar months前のmonth `M-12`です。
例えば`2020-06`のpredictorは`2019-06`を使います。calendar monthそのものにvalid Closeが
存在しない場合は補間しません。forward-fill、backward-fill、zero-fill、nearest-month substitutionを
禁止し、`P[M-12]`、`P[M]`、`P[M+1]`のいずれかが欠けるobservationはunavailableとします。
必要なanalysis rowを作らず、missing/excluded countをdiagnostics metadataへ記録します。
12か月returnには、必要なcalendar month identityを持つ13個のmonth-end price observationsが必要です。

このfuture returnは統計的predictability用であり、tradable next-open PnLではありません。

## 2.2 Primary analyses

### Sign-conditioned

```text
mean(next_1m_return | past_12m_return > 0)
mean(next_1m_return | past_12m_return < 0)
difference
```

### Continuous

```text
next_1m_return = alpha + beta * past_12m_return + error
```

### Sign predictor

```text
next_1m_return = alpha + beta * sign(past_12m_return) + error
```

zero-return semanticsは次の通り固定します。

```text
past_12m_return > 0  -> sign = +1
past_12m_return < 0  -> sign = -1
past_12m_return == 0 -> sign = 0
```

sign-conditioned analysisでは`past_12m_return == 0`をpositive/negative groupのどちらにも
含めません。一方、sign-predictor regressionでは`sign(0)=0`としてrowを保持します。zero observation
countはdiagnostic metadataへ記録します。

report:

- effect size
- CI
- sample size
- symbol-level
- pooled / panel summary

### M1A inference roles

symbol-levelのcontinuous regressionとsign regressionは、HAC / Newey-West、lag `12 months`を
primary inferenceとします。最低限、`alpha`、`beta`、`standard_error`、`t_stat`、confidence interval、
`nobs`、`covariance_method`、`hac_lag`を出力します。

M1A pooled regressionのprimary inferenceはcalendar-month clustered standard errorsです。cluster unitは
calendar monthであり、同一monthの複数symbolを独立観測として扱いません。two-way clustered SE
（symbol × calendar month）とcalendar-month block bootstrapはsensitivityとして別出力し、primary resultへ
混ぜません。出力には`result_role`（`primary` / `sensitivity`等）を持たせます。

stats libraryを使う場合も自作実装の場合も、`regression_method`、`covariance_method`、`hac_lag`、
`cluster_variable`、`small_sample_correction`、`confidence_level`をmethod metadataへ記録します。
statsmodels等を使う場合はlibrary名、version、covariance optionsも記録します。

M1出力は、少なくとも`track`、`workstream`、`analysis_name`、`symbol`、`sample_period`、`return_type`、
`predictor_definition`、`dependent_definition`、`inference_method`、`covariance_method`、
`lag_or_cluster`、`nobs`、`data_source`、`timezone`、`daily_boundary`、`spec_version`の意味を保持します。

### M1A implementation convention — `m1a-practical-v1` on Track B v2

以下はpaper-explicitな仕様ではなく、M1A v1の再現可能なproject implementation conventionです。

#### Daily timestamp and calendar identity

M1AのDaily input timestampはprepared OHLCのbar labelをauthorityとし、UTC calendar timestampとして扱います。
calendar monthはそのtimestampのUTC calendar monthから決定し、NY17 nominal-close timestampへの変換は要求しません。
prepared CSV内のtimezone-naive labelはproduction loaderでUTCとして解釈し、canonical in-memory timestampはtimezone-aware UTCへ統一します。

The production loader accepts timezone-aware timestamps and timezone-naive CSV
labels. Naive labels are normalized to timezone-aware UTC at the loader
boundary; downstream M1A receives only canonical timezone-aware UTC timestamps.
The prepared timestamp need not be the nominal
`America/New_York` 17:00 session close, and calendar month identity uses UTC.
#### Covariance options

statsmodelsのlibrary defaultに依存せず、次のoptionsを明示的に渡します。confidence levelは`0.95`です。

Symbol-level HAC / Newey-West primary:

```text
cov_type = HAC
kernel = bartlett
maxlags = 12
use_correction = True
use_t = True
confidence_level = 0.95
```

通常のHACがconsecutive / equally-spaced observationsを前提とするため、outcome monthのcalendar gapをrow圧縮してHAC(12)へ渡しません。
symbol sampleにgapがある場合、point estimateを保持できてもprimary HAC inferenceはunavailableとし、
`inference_unavailable_reason = non_consecutive_calendar_months`をmetadataへ記録します。

Pooled calendar-month clustered primary:

```text
cov_type = cluster
groups = outcome_month
use_correction = True
df_correction = True
use_t = True
confidence_level = 0.95
```

cluster variableはformation monthではなく`outcome_month`です。同一outcome monthの全symbol observationを同一clusterとして扱います。

Two-way clustered sensitivity:

```text
groups = symbol × outcome_month
use_correction = True
df_correction = True
use_t = True
confidence_level = 0.95
result_role = sensitivity
```

実際に使用したstatsmodels API、library version、covariance kwargsをresult metadataへ記録します。

#### Sign-conditioned effect confidence intervals

sign-conditioned effectのCIは、zero predictor observationsを除いたsample上で、次のpositive-indicator regressionから算出します。

```text
next_1m_return = alpha + beta * I(past_12m_return > 0) + error
```

negative meanは`alpha`、positive meanは`alpha + beta`、differenceは`beta`です。
symbol-levelではHAC(12)、pooledではoutcome-month clustered SEを使います。
これは`sign(past_12m_return)`のzero rowを保持するsign-predictor regressionとは別analysisです。

#### M1A moving block bootstrap sensitivity

M1A pooled continuous regressionおよびpooled sign-predictor regressionのsensitivityとして、moving block bootstrapを使います。
これはpaper-explicitなM1A primary methodologyではありません。

```text
bootstrap_method = moving_block
bootstrap_unit = calendar_month
sequence_axis = ordered outcome_month
block_length_months = 12 calendar-month slots
bootstrap_replications = 5000
bootstrap_seed = 20260817
rng = numpy.Generator(PCG64)
confidence_level = 0.95
interval_method = percentile
result_role = sensitivity
```

block lengthは12 observed monthsではなく12 calendar-month slotsです。calendar gapを圧縮せず、block内部のcalendar順序を保持します。
同一outcome monthの全symbol rowを一単位としてreplacementありでresampleし、sampleと同じcalendar-month slot数まで連結してtruncateします。
missing symbol/monthは補間せず、そのslotにrowがない状態を保ちます。DevelopmentとValidationを跨いでresampleせず、Final HoldoutはM7まで対象外です。

point estimateはoriginal OLS coefficientとし、bootstrap meanへ置き換えません。bootstrap standard errorはsuccessful coefficientのsample SD、
95% CIは`[2.5%, 97.5%]` percentile intervalです。failed / singular drawは黙って破棄せず、`successful_draws`と`failed_draws`をmetadataへ記録します。

---

# 3. M1 — MOP Regression Comparator

MOPのstrategy returnだけでなく、predictability regressionもreference comparatorとして実装します。

## 3.1 Data preference

優先順位:

1. MOPに近いfutures / forward excess-return data
2. academic reference dataでmethodology reproduction可能なseries
3. spot/CFD monthly analogue（明示的にanalogueとラベル）

## 3.2 Volatility standardization

### Authoritative MOP-compatible EWMA contract

日次decimal returnを `r_{s,d}`、対象instrumentを`s`とします。原典で明示された重みは

```text
w_i = (1 - delta) * delta^i,   i = 0, 1, 2, ...
delta / (1 - delta) = 60
delta = 60 / 61
sum_i w_i = 1
```

時点`t−1`までで利用可能なlagged daily returnsに対して、

```text
m[s,t-1]      = sum_{i=0..infinity} w_i * r[s,t-2-i]
v[s,t-1]      = 261 * sum_{i=0..infinity} w_i * (r[s,t-2-i] - m[s,t-1])^2
sigma[s,t-1]  = sqrt(v[s,t-1])
position[s,t] = signal[s,t] * 0.40 / sigma[s,t-1]
```

をこのprojectのindex contractとします。したがってtime-`t` returnは必ず `sigma[s,t-1]`
でscaleし、time-`t`以後のreturnはvolatility estimateへ入りません。`261`はvarianceを年率化
するscalarです。論文はこのEWMA、中心、261、lagged estimateの使用を明示しています。

### Boundary and numerical contract

以下は原典に完全には明示されないため、`implementation convention` です。

- infinite-history EWMAをtruncateせず、recursive stateとして実装する。
- 初期化はinstrument最初のvalid return `r_0`で `m_0=r_0`, `q_0=r_0^2` とする。
  以後 `m_k=delta*m_{k-1}+(1-delta)*r_k`、`q_k=delta*q_{k-1}+(1-delta)*r_k^2`、
  `variance=261*max(q_k-m_k^2, 0)` とする。
- reference availabilityは、最初のsigmaを出すまで少なくとも60個の連続したvalid daily
  returnsがあることを要求する。欠損returnは除外・forward-fill・zero-fillせず、連続履歴を
  途切れさせ、必要な履歴が再び揃うまでinstrumentをunavailableとする。
- `variance <= 0` はinfinite positionを作らずunavailableとする。near-zero判定は
  `variance <= max(1e-24, 1e-12 * max(q_k, 1))` とし、このtoleranceは数値安全のための
  conventionである。
- NaN、missing、non-finite returnはvalid observationではない。timestamp gap自体は欠損returnと
  同一視せず、data contractに従ってdaily boundaryの妥当性を別途検証する。

MOP-compatible reference modeにはcap、floor、leverage limitを原則追加しません。安全のため
  cap/floor付きseriesを作る場合は `MOP_reference` と別名（例 `practical_capped`）にし、
  reference comparatorの結果へ混ぜません。

future informationはvol estimateに入れません。

上記の`position`はM5 strategy comparatorのsizing contractです。M1B regressionではpositionを作らず、
volatility-standardized return `r/sigma`を回帰します。M1B regressionには`0.40` target-volatility
multiplierを使用しません。40% sizingはM5 strategy comparatorに限定します。

## 3.3 Pooled regression family

月次returnについて、instrumentとdateをstackしたpooled regressionを作り、
MOPと同様にlag horizonを

```text
h = 1, 2, ..., 60 months
```

で評価します。

### Canonical M1B equation

M1Bのnormative equationはgolden testではなく、このsectionで固定します。instrument `s`のmonthly
returnを`r[s,t]`、time-`t` returnに利用するex-ante annualized volatilityを`sigma[s,t-1]`とし、
`standardized_return[s,t] = r[s,t] / sigma[s,t-1]`と定義します。

```text
standardized_return[s,t]
    = alpha_h
    + beta_h * standardized_return[s,t-h]
    + error[s,t]

h = 1, 2, ..., 60 months
```

従ってpredictorは`r[s,t-h] / sigma[s,t-h-1]`であり、future informationを使いません。
dependent / predictorのreturn interval、lag direction、volatility indexingはこのcanonical formに
従います。MOP paper-explicitな内容とprojectのimplementation conventionは別々に記録します。
golden testはこのspecificationを検証するために使い、仕様自体をgolden testから導出しません。

primary output:

- beta by lag h
- clustered t-stat by lag h
- sample count by h
- positive-continuation region / reversal region

calendar-time dependenceを考慮し、MOP comparatorではmonthly-level clusteringを実装します。
M1Bのregression outputに40% strategy sizingを混ぜず、strategy-level sizingはM5へ限定します。

## 3.4 Focused 12m -> 1m comparator

MOPのlag-by-lag regressionでは、single-month lagged returnとpast-h-month cumulative returnを別の
predictor familyとして扱います。forecast originを`t`、dependent returnを次月`t+1`とし、
volatility standardizationはpaperのTable 8 Panel A/Bのindexingに合わせます。

### Panel A — single-month lagged return

単一の月次returnをlagさせるfamilyは、

```text
y[s,t+1] = r[s,t+1] / sigma[s,t]
x_A[s,t,h] = r[s,t-h+1] / sigma[s,t-h]

y[s,t+1] = alpha_h + beta_A,h * x_A[s,t,h] + error[s,t+1]
```

これはTable 8 Panel Aの「return lagged h months」に対応します。`x_A`はhか月累積returnではなく、
単一monthのreturnです。

### Panel B — past-h-month cumulative return

過去hか月の累積returnをpredictorにするfamilyは、

```text
r[s,t-h,t] = product_{j=t-h+1..t} (1 + r[s,j]) - 1
y[s,t+1] = r[s,t+1] / sigma[s,t]
x_B[s,t,h] = r[s,t-h,t] / sigma[s,t-1]

y[s,t+1] = alpha_h + beta_B,h * x_B[s,t,h] + error[s,t+1]
```

とします。`r[s,t-h,t]`は`t-h+1`から`t`までのh個のmonthly returnを累積したreturnであり、
単一monthの`r[s,t-h+1]`とは別定義です。これはTable 8 Panel Bの「past h-month returns」に
対応します。

Huang challengeのfocused 12m → 1m specificationはPanel Bの`h=12`、すなわちpast-12-month
cumulative returnを使います。

```text
past_12m_return[s,t] = r[s,t-12,t]
next_1m_return[s,t]  = r[s,t+1]

standardized_next_1m[s,t] = r[s,t+1] / sigma[s,t]
standardized_past_12m[s,t] = r[s,t-12,t] / sigma[s,t-1]
```

のpooled specificationを使います。focused caseではsingle-month lagged returnをpast-12-month
cumulative returnの代替として使用しません。

MOP Panel A single-month lag family、MOP Panel B cumulative-return family、focused Huang 12m→1m
challengeを同一視しません。原論文Table 8のPanel A/Bはそれぞれ上記のpredictor定義に対応し、
Panel Bのh=12がfocused challengeです。

---

# 4. M1 — Huang et al. Statistical Challenge

肯定的なpooled resultだけで結論を出さないため、challenge suiteをprimary deliverableに含めます。

## 4.1 Asset-by-asset regression

各instrumentについて、

```text
next_1m_return = alpha_s + beta_s * past_12m_return + error
```

を評価し、

- beta
- CI / t-stat
- OOS可能ならOOS predictive metric
- positive/negative evidence count

を報告します。

## 4.2 Pooled regression diagnostics

- pooled without fixed effects
- instrument fixed-effect sensitivity
- volatility-scaled / unscaled sensitivity

を比較します。

## 4.3 Bootstrap inference

最低限、

1. parametric wild bootstrap
2. nonparametric pairs bootstrap

を実装対象とします。

report:

- observed t-stat
- bootstrap sampling distribution / bootstrap t-statistic distribution
- Huang reference 5% critical value: 97.5th percentile of simulated t-statistics
- 1% critical value, if reported, with its explicitly documented percentile convention
- bootstrap p-value, when using a separately labeled project convention
- iterations
- random seed and seed policy
- resampling unit

### Huang methodology contract — freeze before implementation

`M1 challenge module`開始前に `references/7.Time-series momentum_ Is it there_.pdf` を確認し、
以下をfreezeします。論文で明示される部分と、このprojectが不足部分を埋めるconventionを区別します。

**Paper-explicit**

- null: pooled regressionのtime-series momentum slope `beta = 0` [Huang §4.1, Eq. (3), journal p.780]
- regression: volatility-standardized next return on lagged volatility-standardized return,
  with an intercept; the focused case is past 12-month -> next 1-month [Huang §4.1, Eq. (3), journal p.780]
- residual: full-sample fitted regression residual [Huang §4.3, Eq. (8), journal p.783]
- parametric wild bootstrap: fitted model plus residual multiplied by an independent
  Rademacher draw `v in {-1,+1}`, each probability 1/2; the predictor is held fixed
  [Huang §4.3, Eqs. (8)–(10), journal p.783]
- nonparametric pairs bootstrap: observed `(standardized dependent, standardized predictor)`
  pairsを、同時に、replacementありでT pairs resampleする。各assetのidentityを保ち、assetごとに
  T observationsのpathを生成してからstackしたpooled regressionを行う [Huang §4.3, Eq. (11),
  journal p.784; Table 5]
- test statistic: pooled regression slope t-statistic
- 5% significanceのcritical valueはsimulated t-statisticsの97.5th percentile
  [Huang §4.3, journal pp.783–784]
- 1,000 simulated samples / method [Huang §4.3, journal pp.783–784]

MOP EWMA anchor: [MOP §2.4, journal PDF pp.233–234, volatility equation and lag statement]
です。原典PDF版によってequation numberingが異なるため、MOPについてはsectionと印刷ページを
primary anchorとし、数式自体をこの文書へ転記します。

**Implementation convention (paper text aloneで一意でない事項)**

- `bootstrap_seed`、`bootstrap_iterations`、`seed_policy`はM1C開始前にfreezeし、replication metadataへ
  記録する。paper-explicit reference modeは`bootstrap_iterations = 1000`とし、10000等の追加反復は
  別sensitivityとして扱う。seed値そのものは今回決めない。
- `T_i = asset iのfreeze後complete-case observation count`とする。unbalanced practical dataでは、
  asset i内のT_i observationsをreplacementありでresampleし、asset identity/pathを保持したまま
  stackしてpooled regressionを行う。このT_iルールはproject implementation conventionであり、
  Huang paperが共通Tを前提に記述したreference procedureそのものとは区別する。
- missing rowはそのregressionのcomplete-caseとして除外し、各bootstrap replicateで欠損を補間しない。
- `project_positive_tsm_one_sided`では、project conventionとして`mean(t* >= t_obs)`等のp-valueを
  使用できるが、Huang reference critical valueとは別method・別result roleで出力する。
- primary Huang bootstrapではtime-series blockやcross-sectional cluster resampleを追加しない。
  追加する場合は別method名の感度分析とする。

### Huang reference fixed-effect procedure

`Huang_reference_fixed_effect`はinstrument dummyを単にOLSへ加えるgeneric panel regressionではなく、
Huang §4.4 Eq. (12)のasset内demeaningをreference procedureとします。Eq. (12)のfocused challenge
では、dependent variableとpredictorをTable 8 Panel Bの定義に従って、
`y[s,t+1] = r[s,t+1] / sigma[s,t]`、
`x_B[s,t,h] = r[s,t-h,t] / sigma[s,t-1]`（focused caseは`h=12`）とします。

Panel Bに対応するdemeaned reference equationは、

```text
(y[s,t+1] - mean_s(y))
    = beta_FE,B,h * (x_B[s,t,h] - mean_s(x_B))
    + error[s,t+1]
```

です。ここで`mean_s(.)`はasset sのfreeze-period sample meanです。
Panel Aのsingle-month lagged-return fixed-effect sensitivityを出す場合は、同じEq. (12)の形で
`x_B`を`x_A[s,t,h] = r[s,t-h+1] / sigma[s,t-h]`へ置き換え、
`beta_FE,A,h`として別method/result labelで報告します。Panel AとPanel Bのfixed-effect resultを
同じfocused coefficientとして混ぜません。Huang reference procedureでは、
このdemeaned dataに対してwild bootstrapを行い、pairs bootstrapではdemeaning後の`(x, y)` pairsを
asset identity/pathごとにreplacementありでresampleします。各assetのpathを生成してからstackする点を
保持します。instrument dummyを使うgeneric panel fixed-effect sensitivityは
`generic_panel_fixed_effect_sensitivity`という別method名で扱い、reference procedureと同一視しません。

### Separate inference labels

`Huang_reference_inference`は、原論文のbootstrap t-statistic distributionと、5% critical valueである
97.5th percentileを再現します。これはnull hypothesis `beta = 0`とbootstrap sample generation
mechanism（full-sample fitted model plus residual/Rademacher等）を混同しません。

`project_positive_tsm_one_sided`はproject独自のpositive TSM (`beta > 0`) diagnosticです。project側で
95th percentile等を使う場合もimplementation conventionとして明示し、`Huang replication`とは呼びません。
両methodはresult labelとmetadataで区別します。

このcontractを文書化してfreezeした後にだけ実装を開始し、fixtureでnull、residual、Rademacher、
pairs resampling、statistic、p-valueを検証します。

plain asymptotic t-valueだけをprimary conclusionにしません。

---

# 5. General Inference Policy

Practical symbol-level analysisではmonthly serial dependenceを考慮したHAC/Newey-West系CIを使用し、lag defaultは12 monthsとします。
M1A symbol-level continuous/sign regressionではこれをprimary inferenceとします。

M1A pooled regressionのprimary inferenceはcalendar-month clustered standard errorsです。cluster unitは
calendar monthです。

M1A pooledの補助分析として、

- two-way clustered SE（symbol × calendar month）
- calendar-month block bootstrap

を使えます。

ただしMOP comparator / Huang challengeは、それぞれreference methodologyを優先します。

method / lag / seedは出力metadataに残します。

---

# 6. AQR Original Paper Data Sanity Contract

workbookにraw underlying seriesがあると事前に仮定しません。

最初に、

- sheet names / field definitions
- period
- frequency
- observation count
- return unit
- missing values

をinventoryします。

factor return seriesが確認できた場合、最低限:

- date alignment
- observation count
- mean
- volatility
- Sharpe
- cumulative-return path

に加えて、次をmetadataへ記録します。

- return unit conversion
- frequency-specific annualization factor
- Sharpe calculation convention
- missing-value handling

annualization factorはreference workbookをinventoryしてfrequencyを確定した後に選び、実装者の
暗黙選択にしません。monthly factor returnならmonthly frequencyに適合するannualization conventionを
明記し、daily等の別frequencyとは混同しません。

をreference reportへ出します。

自作MOP comparatorと同一data definitionを使えていない場合、
correlationが低いことだけでimplementation failureと判定しません。

data-definition差、instrument universe差、roll / excess-return差を先に説明します。

---

# 7. M2 — Practical Monthly Comparator

## 7.1 Formation date

calendar month `M` の最後のvalid Daily Closeが確定した後にsignalを決めます。

```text
signal[M] = sign(month_end_close[M] / month_end_close[M-12] - 1)
formation_month = M
holding_month = M+1
```

これは12 completed calendar monthsのformationです。M0の240 observed daily intervalsとは別仕様です。

## 7.2 Execution and split assignment

Month Mのsignalは、**holding month M+1の最初のavailable Daily Open**でexecutionします。
M2のsplit assignmentは`holding_month`です。既存のM1Aでいう`next_1m_return`のoutcome monthと
同じcalendar monthですが、M2ではposition/PnLの所属を明示するため`holding_month`という名前を使います。

```text
last valid Close of formation_month M
        ↓
signal[M]
        ↓
first available Open of holding_month M+1
```

同じmonth-end Closeで約定しません。

For the current Track B freeze, M2 may generate only these holding months before M7:

```text
Development : 2017-01 ... 2021-12
Validation  : 2022-01 ... 2023-12
Final Holdout: 2024-01 ... 2026-06 (sealed until M7)
```

The first Open of `2024-01` may be used only as the exit boundary for the
`2023-12` Validation holding interval. No `holding_month = 2024-01`
position or return may be generated before M7.

## 7.3 Holding

positionは次のmonthly rebalanceまで保持します。

```text
entry: first available Open of holding_month M+1
exit/rebalance: first available Open of holding_month M+2
```

M2は月次PnLを別engineで計算しません。M0と共有するdaily Open-to-Open accountingへtarget positionを渡し、
holding month内のdaily strategy returnsをcompoundします。これにより、月内daily returnのcompoundは
`first Open of M+1`から`first Open of M+2`までのmonthly gross returnと一致し、M0とdaily drawdownを比較できます。

M2 target stateは`warmup_data_start`からcausalに構築し、Development開始時にFlatへresetしません。
M2の最初のformable holding monthは`warmup_data_start + 13 calendar months`です。pre-sample historyが
不足するholding monthはsignal undefined / Flatとし、stateを人工的に補完しません。

## 7.4 State and universe

```text
positive -> Long
negative -> Short
zero     -> Flat
```

M2初期版はunscaled、gross、spot/CFD price-onlyです。freeze済みprimary universeの8 symbolをそれぞれ
独立に実行します。M2ではperformanceを見たsymbol selection、portfolio aggregation、pooled strategy
resultを行いません。M3でmulti-symbol research、cross-symbol diagnostics、TSH plumbingを扱います。

## 7.5 Missing month

- pre-sampleで12か月historyが不足する場合はsignal undefined / Flatとします。
- requested analysis range内のcalendar monthが丸ごと欠損した場合はerrorとします。
- forward-fill、backward-fill、zero-fill、nearest-month substitutionは禁止します。

holiday/weekendによる個別Daily barの不在はcalendar month欠損ではありません。first available Openを使います。

## 7.6 Common interval and comparison with M0

M0とM2は必ず同じreturn intervalに揃えて比較します。M2 Development+Validationを評価する場合、
M0側もholding month `2017-01`〜`2023-12`のdaily Open-to-Open intervalsだけから再計算します。
M0/M2をそれぞれの全計算可能期間で比較してはいけません。

rebalanceごとのsignal-direction agreementは、M2がtargetを変更する各holding-month first Openで、
M0が同じOpenで実行しているtargetと比較します。agreementは一致したrebalance数をcomparable
rebalance数で割ったものとし、同じmonthly signalを全daily barへ複製して比較しません。

**M2はunscaledなのでMOP representative factorのcomplete strategy reproductionとは呼びません。**

## 7.7 M2 implementation convention and result metadata

M2 production entry pointは、current Track B freeze artifact、matching
`StructuralValidationSummary`、およびそのsummaryと同一のprepared Daily datasetを要求します。
M1Aと同じfingerprint gateを使い、別dataset、別freeze version、別structural spec version、別fingerprint
algorithmでは実行しません。各symbolはfrozen primary universeから事前に選択し、resultをpooledにしません。

公開production entry point `run_m2_track_b(..., symbol=...)`はDevelopment+Validation専用です。
`include_holdout`のようなholdout escape hatchは持ちません。fingerprint検証後のbacktest inputは、
warmup開始からValidation終了翌月のfirst Openまでにtruncateし、current freezeでは`2024-01`のfirst
Openより後のbar、asset return、Final Holdout resultを生成・返却しません。M7用のFinal Holdout entry pointは
この契約とは別に設計します。

最低限、result metadataは次を持ちます。

```text
spec_version = m2-practical-v1
freeze_version
structural_spec_version
dataset_fingerprint
dataset_fingerprint_algorithm
symbol
split
sample_period
data_source
price_type
timezone
daily_boundary
result_level = gross_price_only
academic_mop_replication = false
final_holdout_included = false
sample_start_timestamp
sample_end_timestamp
accounting_engine = shared_daily_open_to_open_v1
sample_start_by_symbol
sample_end_by_symbol
```

The production comparison runner derives one canonical execution window per
symbol from the validation canonical Daily dataset. It passes the same
`sample_start`, `sample_end`, and truncated execution frame to M0 and M2.
Before saving an artifact it hard-checks the boundary timestamps, first and
last evaluation return timestamps, return count, and the complete evaluation
return interval. The terminal boundary row remains in both bars files, has
`asset_return = NaN` and `strategy_return = NaN`, and no later bar or return is
allowed.

Gate M2 #7 is an implementation invariant, not a performance judgment. It
passes only when M0 and M2 use the same frozen input identity, symbol, market
contract, canonical window, and shared daily Open-to-Open accounting, while
their documented daily and monthly construction rules are the only difference.
The runner does not infer this gate from which strategy performs better.
The production gate also validates the required metric contract separately for
every primary symbol, and requires non-null finite
`signal_direction_agreement` in `[0, 1]`.

## 7.8 Metric definitions

`gross_return`はreturn window `[sample_start, sample_end)` 内のdaily strategy returnsをcompoundしたものです。
`max_drawdown`は同じdaily Open-to-Open equity curveから計算し、初期equity `1.0`をpeakへ含めた
`equity / prior_peak - 1`の最小値として負の値で報告します。

`turnover[t] = abs(new_position[t] - old_position[t])`とし、Flat→Longは1、Long→Shortは2です。
event windowは`[sample_start, sample_end]`とし、終了境界Openでのexit/reversalを含めます。
`trade_count`はevent window内に新規開始したnon-flat episode数です。window外で開始したcarry-in episodeは
trade countへ含めません。`average_holding`はevent window内にentryし、終了境界までにcloseしたepisodeの
holding daily-return interval数の平均とし、calendar days平均はdiagnosticとして併記します。
`reversal_count`はevent window内のLong→ShortまたはShort→Longの回数、`reversal_frequency`は
同じwindow内の`reversal_count / position-change event count`です。分母が0の場合はundefinedとします。
carry-in / carry-out episode countとpositionはdiagnosticとして別記録します。

成果物にはsignal-direction agreement、turnover、trade count、average holding、gross return、
max drawdown、reversal frequencyを含めます。

## 7.9 Terminal boundary

`evaluation_period_end = 2026-06`をM2で完全評価するには`2026-07`の最初のOpenが必要です。
したがってM7でFinal Holdoutの最後のholding monthを評価する場合は、評価期間外の終了境界データを
`execution_boundary_data through first Open of 2026-07`として明示的に許可し、freeze metadataへ記録します。
その境界データだけでは`holding_month = 2026-07`のposition / returnを生成しません。

---

# 8. TSH Challenge Contract — M3〜M7

Huang et al.のTime-Series History comparatorを実装します。

原則:

> historical sample meanがpositiveならLong、negativeならShort

## 8.1 Freeze gate

M3開始前にpaperを再確認し、TSH exact historical-mean contractをfreezeします。M3/M4/M7は
同じcontractを再利用し、milestoneごとに再定義しません。

**Paper-explicit core:** TSHはassetのhistorical sample meanがnon-negativeならLong、negative
ならShortとし、TSMのpast-12-month signalと比較します。原典はこのeconomic definitionを示します。

**Implementation convention frozen before M3 (paper specificationとは別名義):**

- `TSH_reference_replication` のsample startは、freezeしたreference datasetで各instrumentに
  利用可能な最初のvalid monthly returnとする。`TSH_causal_expanding`も同じstartを使う。
- historical meanはexpanding mean、時点`t`のsignalは`t-1`までのreturnだけで計算する。
- signalはmonth-endに決定し、次月first available executionから次のrebalanceまで保持する。
- historical mean `> 0` はLong、`< 0` はShort、`= 0` はFlatとする。
- volatility scalingはMOP reference comparatorでは§3.2の`0.40/sigma[t-1]`、TSH単体の
  unscaled comparatorではequal-notionalとし、両方を別seriesで出す。
- rebalance cadenceはmonthly、available universeはその時点でsignal・return・volatilityが
  全てvalidなinstrument、long/short legはposition signで分解する。

この値はpaper本文が一意に指定した仕様ではなく、このprojectの再現可能な
`implementation convention` です。paperのfull-sample/non-causal conventionを別途採用する場合は、
必ず`TSH_reference_replication`に限定し、causal seriesと混ぜません。

もしreference paperのreproduction conventionがfull-sample information等を含み、causal trading analogueと異なる場合は、

```text
TSH_reference_replication
TSH_causal_expanding
```

を別seriesとして出力します。

causal trading strategyとして実行できる定義とpaperのreplication定義が異なる場合、必ず

```text
TSH_reference_replication
TSH_causal_expanding
```

を別seriesにします。

最低比較:

- TSM vs TSH return
- TSM - TSH
- Sharpe / alpha difference
- long leg
- short leg
- equal-weight / volatility-weight sensitivity

TSM strategyがprofitableでもTSHを有意に上回れない場合、
「profitabilityがTSM predictabilityの証拠」とは表現しません。

---

# 9. Architecture Guidance

M1はbacktest engineとは別のresearch/statistics moduleでよいです。
M3のmulti-symbol engine完成を待つ必要はありません。

M2のためにM0を万能schedulerへ一般化しません。

推奨境界:

```text
signal / target-position generation
            ↓
execution / accounting
```

M0とM2で前段だけ差し替え、execution/accountingの再利用可能部分だけ共有します。

MOP regression / Huang bootstrapはstrategy engineへ押し込まず、research moduleとして分離します。
