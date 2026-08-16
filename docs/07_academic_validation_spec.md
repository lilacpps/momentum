# M1 / M2 / M5 / Challenge Academic Validation Specification

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
判定を先に完了します。実historical performanceを一件も生成する前に、以下をfreezeします。

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

| Workstream | 内容 | Status |
|---|---|---|
| M1A Practical Predictability | past 12m spot/CFD return -> next 1m return | Ready after Track B split / universe freeze |
| M1B MOP Regression Comparator | eligible futures / forward / excess-return underlying series | Ready only after eligible reference underlying data is identified |
| M1C Huang Statistical Challenge | exact bootstrap contractをfreeze後に実装 | Ready after Huang methodology contract freeze |

AQR workbookがfactor returnだけの場合、それだけでlag-by-lag instrument regression用のunderlying
seriesがあるとはみなしません。underlyingが確保できない場合もM1AとAQR factor sanity checkは進め、
M1Bだけを `data unavailable / pending` と報告します。

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

12か月returnには13個のmonth-end price observationsが必要です。

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

report:

- effect size
- CI
- sample size
- symbol-level
- pooled / panel summary

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

## 3.3 Pooled regression family

月次returnについて、instrumentとdateをstackしたpooled regressionを作り、
MOPと同様にlag horizonを

```text
h = 1, 2, ..., 60 months
```

で評価します。

回帰のdependent / predictor双方のvolatility standardization、lag direction、return intervalは
reference paperのequationをgolden testへ転記して固定します。

primary output:

- beta by lag h
- clustered t-stat by lag h
- sample count by h
- positive-continuation region / reversal region

calendar-time dependenceを考慮し、MOP comparatorではmonthly-level clusteringを実装します。

## 3.4 Focused 12m -> 1m comparator

Huang challengeとの接続用に、

```text
past 12-month return -> next 1-month return
```

のpooled specificationも別表で出します。

MOP lag-by-lag regression familyと、この12m cumulative predictor regressionを同一視しません。

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
- empirical null distribution
- 5% / 1% critical values
- bootstrap p-value
- iterations
- random seed
- resampling unit

### Huang methodology contract — freeze before implementation

`M1 challenge module`開始前に `references/7.Time-series momentum_ Is it there_.pdf` を確認し、
以下をfreezeします。論文で明示される部分と、このprojectが不足部分を埋めるconventionを区別します。

**Paper-explicit**

- null: pooled regressionのtime-series momentum slope `beta = 0`
- regression: volatility-standardized next return on lagged volatility-standardized return,
  with an intercept; the focused case is past 12-month -> next 1-month
- residual: full-sample fitted regression residual
- parametric wild bootstrap: fitted model plus residual multiplied by an independent
  Rademacher draw `v in {-1,+1}`, each probability 1/2; the predictor is held fixed
- nonparametric pairs bootstrap: observed `(standardized dependent, standardized predictor)`
  pairsを、同時に、replacementありでT pairs resample
- both methods preserve the observed cross-sectional rows; the paper does not introduce a
  time-series block or cross-sectional cluster resample in these two contracts
- test statistic: pooled regression slope t-statistic
- one-sided research question: positive TSM (`beta > 0`); reported two-sided diagnosticsは補助表
- 1,000 simulated samples / method

**Implementation convention (paper text aloneで一意でない事項)**

- seedはreplication metadataへ記録する固定整数とし、分析開始前に決める。
- empirical one-sided p-valueは `mean(t* >= t_obs)`、two-sidedは
  `mean(abs(t*) >= abs(t_obs))` とし、critical valueはbootstrap statisticの対応する
  95th/99th percentileとする。
- missing rowはそのregressionのcomplete-caseとして除外し、各bootstrap replicateで再度
  欠損を補間しない。sample size Tはfreeze後のcomplete-case数とする。
- cross-sectional / time dependenceの追加cluster/block処理はHuang primary bootstrapへ
  勝手に追加しない。感度分析として出す場合は別method名にする。

このcontractを文書化してfreezeした後にだけ実装を開始し、fixtureでnull、residual、Rademacher、
pairs resampling、statistic、p-valueを検証します。

plain asymptotic t-valueだけをprimary conclusionにしません。

---

# 5. General Inference Policy

Practical symbol-level analysisではmonthly serial dependenceを考慮したHAC/Newey-West系CIを使用し、lag defaultは12 monthsとします。

pooled / cross-marketではcalendar-time dependenceとsymbol dependenceを無視しません。

補助分析として、

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

をreference reportへ出します。

自作MOP comparatorと同一data definitionを使えていない場合、
correlationが低いことだけでimplementation failureと判定しません。

data-definition差、instrument universe差、roll / excess-return差を先に説明します。

---

# 7. M2 — Academic-Style Monthly Comparator

## 7.1 Formation date

calendar month `M` の最後のvalid Daily Closeが確定した後にsignalを決めます。

```text
signal[M] = sign(month_end_close[M] / month_end_close[M-12] - 1)
```

これは12 completed calendar monthsのformationです。
M0の240 observed daily intervalsとは別仕様です。

## 7.2 Execution

Month Mのsignalは、**Month M+1 の最初のavailable Daily Open** でexecutionします。

```text
last valid Close of M
        ↓
signal
        ↓
first available Open of M+1
```

同じmonth-end Closeで約定しません。

## 7.3 Holding

positionは次のmonthly rebalanceまで保持。

```text
entry: first available Open of M+1
exit/rebalance: first available Open of M+2
```

monthly first-open-to-next-month-first-openで測定します。

## 7.4 State

```text
positive -> Long
negative -> Short
zero     -> Flat
```

M2初期版はunscaled。

## 7.5 Missing month

formationに必要なmonth-end priceが欠ける場合、黙って補間しません。
calendar monthそのものに観測がない異常datasetはerrorまたはexplicit exclusion。

## 7.6 Comparison with M0

最低限比較:

- signal direction agreement
- gross return
- drawdown
- turnover
- trade count
- average holding
- reversal frequency

M2の目的は「どちらが最適か」ではなく、daily refresh / 240-barというimplementation choiceの影響を分離することです。

**M2はunscaledなのでMOP representative factorのcomplete strategy reproductionとは呼びません。**

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
