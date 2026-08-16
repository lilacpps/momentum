# M1 / M2 Academic Validation Specification

この文書はM1とM2開始前に固定するresearch contractです。

---

# 1. Track / Split Contract

## 1.1 Track A — Academic / Reference

MOP等のpublished sampleは結果が既知なので、**replication sample**として扱います。

- published sampleをfinal holdoutと呼ばない
- reference methodology reproductionに使用可能
- AQR published factor seriesはsanity checkに使用
- post-publication dataが得られればAcademic OOSを別途定義可能

## 1.2 Track B — Practical Spot/CFD

M0完了後、M1のhistorical resultを見る前に以下をfreezeします。

- development period
- validation period
- final holdout period
- symbol universe
- data source / timezone / daily boundary

final holdoutはM7まで原則見ません。

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

MOP-compatible modeではex-ante volatilityを、

- lagged daily returnのexponentially weighted variance
- annualization scalar = 261
- exponential-weight center-of-mass = 60 days
- time-t returnに `sigma[t-1]` を適用

で計算します。

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

実装前に `references/7.Time-series momentum_ Is it there_.pdf` のbootstrap algorithmを読み、
residual construction / null imposition / resampling unitをtestable specへ固定します。

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

ただし「historical sample」のwindow / start conventionはpaperのexact specificationを実装前に固定します。

もしreference paperのreproduction conventionがfull-sample information等を含み、causal trading analogueと異なる場合は、

```text
TSH_reference_replication
TSH_causal_expanding
```

を別seriesとして出力します。

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
