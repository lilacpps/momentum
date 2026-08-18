# Data and Cost Policy

# 1. M0 Data Contract

Track B current freezeの具体的data contractは`config/research_track_b.yaml`を参照します。

M0入力:

```text
timestamp
open
high
low
close
```

single-symbol Daily OHLCを基本とします。

## Timestamp

data sourceごとに、timestampがbar openかcloseか / timezone / daily session boundary / source / price type をmetadataへ記録します。

`data_source`、`price_type`、`timezone`、`daily_bar_boundary`（daily session boundary）の意味、許容値、
検証方法は本章のdata contractをauthoritative sourceとします。これらはTrack B freeze artifactにも
記録しますが、freezeの時期・artifact versioning・gateは`docs/04_validation_policy.md`が定義します。

## Track B v2 prepared Daily contract

Track B v2 uses already prepared Exness Bid OHLC as the research input
authority. Prepared frequencies from 1m through 1w may exist, but M1A uses
only the prepared 1d file directly. Momentum does not regenerate Daily bars
from 1m data.

The production loader expects one file per symbol at:

```text
data/processed/{SYMBOL}_1d.csv
```

The canonical minimum schema is:

```text
timestamp,open,high,low,close
```

`symbol` may be omitted and is attached from `{SYMBOL}` in the file path.
The current prepared export uses `datetime` instead of `timestamp`; the
loader treats that name as a source-column alias and passes the canonical
`timestamp` column downstream. Timezone-naive CSV labels are accepted and
interpreted as UTC by the loader. The canonical in-memory `timestamp` is
always timezone-aware UTC. Optional columns such as `volume` are ignored. No
timestamp or OHLC repair is performed.

`timestamp` is the prepared bar label, interpreted as a UTC calendar
timestamp. It is not converted to a nominal NY17 close. Calendar month is
`timestamp`'s UTC calendar month. Small differences of a few hours or about a
minute around the NY17 boundary are accepted as a non-material v2 Practical
Track implementation convention.

## Ordering

timestamp ascendingを必須とします。
unsorted inputは自動sortせず、failします。

## Duplicate

duplicate timestampは黙って処理せず、M0では原則error。

## Missing values

OHLCをforward-fillしてsignalやexecutionを成立させません。
特にcloseのforward-fillは禁止。
欠損barを除外する場合、その処理をpreprocessing metadataへ残します。

## Lookback semantics

`lookback_intervals=N` はN本のreturn intervalを意味します。
必要Close observationsは `N+1`。

例えば240なら、

```text
Close[t-1] / Close[t-241] - 1
```

です。

## Daily boundary

FX/CFDではbroker/server timezoneによりDaily barが異なるため、同一experiment内ではboundaryを固定します。
複数sourceを無条件に混ぜません。

Track B v2ではprepared bar labelをauthorityとし、Daily boundaryの再計算は行いません。

```text
data_source: exness_prepared_bid_ohlc
price_type: bid
timezone: UTC
daily_bar_boundary: prepared daily bar label
calendar_month_timezone: UTC
ny17_conversion_required: false
```

OHLCは既に生成済みのExness Bid OHLCをそのまま使用します。raw tickの再validation、per-tick loop、
NY17 aggregation、gap reconstructionはTrack B v2の責務ではありません。

## Price type

最低限、

```text
bid / ask / mid / broker_chart
```

のどれかを記録します。

M0のbroker-chart OHLCはgross research priceであり、Net execution priceとはみなしません。

---

# 2. Monthly Research Data Contract — M1/M2

daily dataからmonth-end seriesを作る場合、

```text
month_end_price[M] = calendar month M の最後のvalid daily Close
```

とします。

M1 Practical Track:

```text
past_12m_return[M] = month_end_price[M] / month_end_price[M-12] - 1
next_1m_return[M]  = month_end_price[M+1] / month_end_price[M] - 1
```

これは統計的predictability用であり、tradable next-open PnLとは別です。

Track B frozen contractの取得対象は`2015-09`から`2026-06`です。`2015-09`から`2016-12`はwarmup / pre-development
historyであり、Development outcome sampleは`2017-01`から開始します。最初のDevelopment outcome `2017-01`の
formation monthは`2016-12`で、必要なpast-12m priceは`2015-12`です。そのため`2015-09`開始でもDevelopment
sampleは失われません。split所属はformation monthではなく
`next_1m_return` outcome monthで決定します。詳細なfreeze policyは`docs/04_validation_policy.md`、
具体値は`config/research_track_b.yaml`を参照します。

calendar monthにvalid Closeが存在しない場合は補間せず、必要なM1 observationをunavailableとします。
forward-fill、backward-fill、zero-fill、nearest-month substitutionは禁止です。観測の欠損・除外数は
diagnostics metadataへ記録し、calendar monthとobserved rowを同一視しません。詳細なM1 methodologyは
`docs/07_academic_validation_spec.md`がauthoritativeです。

M2のexecutionは `docs/07_academic_validation_spec.md` に従います。

M2では`formation_month = M`、`holding_month = M+1`とし、split assignmentはholding month基準です。
Evaluationの最終holding monthの次月first Openは終了境界価格として許可しますが、その次月を新しい
holding position / returnのsampleには含めません。

---

# 3. Academic / Reference Data Contract

Track Aのpublished-sample replicationでは、spot/CFD OHLC contractを無理に流用しません。

reference datasetごとに、

- excess return / price return
- monthly / daily
- unit（decimal / percent）
- sample period
- instrument count
- missing-value convention
- volatility normalization済みか

をmetadataへ記録します。

AQR Original Paper Dataがfactor returnのみを含む場合、それをraw instrument seriesとして扱いません。

---

# 4. Price ReturnとAcademic Excess Return

spot/CFD price returnは、futures / forward excess returnと同一ではありません。

差には、currency carry / futures roll yield / financing / broker swap が含まれ得ます。

Track A / Track Bを分離して報告します。

---

# 5. Transaction Cost Policy

目的を2つに分けます。

1. historical broker PnLを再現する
2. strategy edgeが現実的costに耐えるか調べる

historical cost series不足でも2は可能です。

## Result Levels

### Level 1 — Gross price-only

- spreadなし
- commissionなし
- slippageなし
- financingなし

M0〜M5の基本。

### Level 2 — Net ex-financing

```text
Gross
- spread
- commission
- slippage
```

### Level 3 — Full broker net

```text
Gross
- spread
- commission
- slippage
- swap / financing
```

historical条件が十分に再現可能な場合だけこの名称を使います。

---

# 6. M6 Cost Unit Contract

```text
turnover[t] = abs(position[t] - position[t-1])
```

例:

```text
Flat -> Long   = 1
Long -> Flat   = 1
Long -> Short  = 2
```

cost parameterは原則、**one-way basis points per unit normalized notional turnover** へ正規化します。

```text
cost_return[t] = turnover[t] * all_in_one_way_cost_bps / 10000
```

round-trip quoteしかない場合はone-wayへ変換してmetadataへ残します。

---

# 7. Commission / Spread / Slippage

historical scheduleがなくてもscenario分析できます。

spread / slippage履歴がない場合は、0 / low / base / 1.5x / 2.0x等でrobustnessを確認し、historical execution replicationとは呼びません。

---

# 8. Break-even Cost

M6で必須診断とし、gross edgeがゼロになるall-in one-way cost levelを求めます。

---

# 9. Swap / Financing

historical swapがない場合:

1. current swapを過去全期間へ一律適用しない
2. Level 2をFull broker netと呼ばない
3. proxyはresearch proxyと明示
4. historical subsetがあれば別評価
5. future forward testでactual swapを記録

Daily/long-horizon FX/CFDでは重要になる可能性があるため、欠落を明示します。

**swap情報がない現段階ではM0〜M5をGross price-onlyで進めてよい**ものとします。

---

# 10. Milestone Boundary

- M0〜M5: Level 1 Grossを基本
- M6: cost / financing capabilityとscenario
- M7: robustness / holdout上でもcost sensitivityを確認
- M8/M9: M6 cost framework完了後に短期化
