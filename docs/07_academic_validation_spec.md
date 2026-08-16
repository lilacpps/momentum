# M1 / M2 Academic Validation Specification

この文書はM1とM2開始前に固定するresearch contractです。

---

# 1. Split Freeze

M0完了後、M1開始前に以下を固定します。

- development period
- validation period
- final holdout period
- symbol universe
- data source / timezone / daily boundary

final holdoutはM7まで原則見ません。

---

# 2. M1 — Academic Hypothesis Check

## 2.1 Practical Track monthly series

Daily dataから、

```text
P[M] = month M の最後のvalid Daily Close
```

を作ります。

```text
past_12m_return[M]
  = P[M] / P[M-12] - 1

next_1m_return[M]
  = P[M+1] / P[M] - 1
```

12か月returnには13個のmonth-end price observationsが必要です。

このfuture returnは統計的predictability用であり、
tradable next-open PnLではありません。

## 2.2 Academic Track

futures / forward / excess-returnまたはreference dataが利用可能なら、
そのdata definitionを優先します。

spot price-return resultと同じ列へ無条件に混ぜません。

AQR Original Paper Dataについては、
workbookにraw underlying seriesがあると事前に仮定しません。

まず、

- published factor return
- period
- aggregate characteristics

のsanity checkを行い、
underlying seriesが確認できた場合のみsignal-level reproductionへ進みます。

## 2.3 Primary analyses

### Sign-conditioned

```text
mean(next_1m_return | past_12m_return > 0)
mean(next_1m_return | past_12m_return < 0)
difference
```

### Continuous

```text
next_1m_return
  = alpha + beta * past_12m_return + error
```

### Sign predictor

```text
next_1m_return
  = alpha + beta * sign(past_12m_return) + error
```

report:

- effect size
- CI
- sample size
- symbol-level
- pooled / panel summary

## 2.4 Inference policy

IID前提のplain OLS standard errorだけで有意性を判定しません。

default:

### Symbol-level

monthly serial dependenceを考慮したHAC/Newey-West系CIを使用。
lagは最低12 monthsをdefaultとし、実装metadataへ記録します。

### Pooled / cross-market

calendar-time dependenceとsymbol dependenceを無視しません。

推奨default:

- two-way clustered SE（symbol × calendar month）が実装可能なら使用
- 代替としてcalendar-month block bootstrapでcross-sectionをまとめてresample

少なくともnaive IID resultだけをprimary evidenceにしません。

method / lag / random seedは出力metadataに残します。

---

# 3. M2 — Academic-Style Monthly Comparator

## 3.1 Formation date

calendar month `M` の最後のvalid Daily Closeが確定した後にsignalを決めます。

```text
signal[M]
  = sign(
      month_end_close[M]
      / month_end_close[M-12]
      - 1
    )
```

これは12 completed calendar monthsのformationです。

M0の240 observed daily intervalsとは別仕様です。

## 3.2 Execution

Month Mのsignalは、
**Month M+1 の最初のavailable Daily Open** でexecutionします。

```text
last valid Close of M
        ↓
signal
        ↓
first available Open of M+1
```

同じmonth-end Closeで約定しません。

## 3.3 Holding

positionは次のmonthly rebalanceまで保持。

```text
entry:
first available Open of M+1

exit/rebalance:
first available Open of M+2
```

したがってgross strategy returnは、
monthly first-open-to-next-month-first-openで測定します。

## 3.4 State

```text
positive -> Long
negative -> Short
zero     -> Flat
```

M2初期版はunscaled。

## 3.5 Missing month

formationに必要なmonth-end priceが欠ける場合、
黙って補間しません。

calendar monthそのものに観測がない異常datasetはerrorまたはexplicit exclusion。

## 3.6 Comparison with M0

最低限比較:

- signal direction agreement
- gross return
- drawdown
- turnover
- trade count
- average holding
- reversal frequency

M2の目的は「どちらが最適か」ではなく、
daily refresh / 240-barというimplementation choiceの影響を分離することです。

---

# 4. Architecture Guidance

M1はbacktest engineとは別のresearch/statistics moduleでよいです。
M3のmulti-symbol engine完成を待つ必要はありません。

M2のためにM0を万能schedulerへ一般化しません。

推奨境界:

```text
signal / target-position generation
            ↓
execution / accounting
```

M0とM2で前段だけ差し替え、
execution/accountingの再利用可能部分だけ共有します。
