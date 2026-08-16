# Data and Cost Policy

## Data

最低限必要:

- timestamp
- OHLC
- symbol

可能なら:

- bid/ask
- spread
- tick volume / volume

## M0 Data Contract

M0ではsingle-symbol Daily OHLCを入力とする。

最低限必要なcolumn:

```text
timestamp
open
high
low
close
```

### Timestamp

timestampが

- bar open time
- bar close time

のどちらを表すかをdata sourceごとにmetadataへ記録する。

strategy内部では、各barがchronological orderで一意に並べられることを必須とする。

### Ordering

入力dataは `timestamp ascending` でなければならない。

実装が自動sortする場合でも、元dataがunsortedだった事実を検出可能にする。

### Duplicate

同一timestampの重複barを黙って採用してはならない。
M0では原則errorとする。

### Missing values

signalやexecutionに必要なOHLCがNaNのbarをforward-fillしてはならない。
特にcloseをforward-fillしてlookbackを成立させてはならない。

欠損barの扱いはdata preprocessing段階で明示する。

### Lookback semantics

`lookback_bars = N` は、**valid observed barsをN本遡る**ことを意味する。
calendar timedeltaとしてN日を遡ることを意味しない。

## FXの日足境界

broker/server timezoneでDaily barが変わるため、複数データソースを混ぜる場合は境界を固定する。

同一experiment内ではdaily boundaryを固定する。

可能ならmetadataへ以下を記録する。

```text
source
timezone
daily_session_boundary
price_type
```

## Price type

使用価格が

- bid
- ask
- mid
- broker chart OHLC

のどれかを記録する。

M0ではgross research baselineであるため、broker chart OHLCを使用可能とするが、Net execution priceとはみなさない。

## Price ReturnとAcademic Excess Return

M0はspot/CFD price seriesのprice changeをsignalへ利用する。

これはfutures / forwardを用いるacademic literatureのexcess-return seriesと同一ではない。

特に、

- currency carry
- futures roll yield
- financing
- broker swap

等の扱いが異なる。

したがってM0からacademic futures / forward strategyのreturnを直接再現したとは解釈しない。

# Transaction Cost Policy

## 目的

コスト研究では、次の2つを分離する。

1. **historical broker PnLを正確に再現できるか**
2. **strategy edgeが現実的なcostに耐えられるか**

historical commission / spread / swap seriesが不足していても、2は検証可能である。

## Result Levels

結果のラベルを次の3段階に分ける。

### Level 1 — Gross price-only

```text
Gross price-only
```

- spreadなし
- commissionなし
- slippageなし
- swap / financingなし

M0〜M3の基本結果。

### Level 2 — Net ex-financing

```text
Gross
- spread
- commission
- slippage
```

swap / financingを含めない。

historical swapがない環境では、このレベルまではscenario analysisとして評価可能である。

### Level 3 — Full broker net

```text
Gross
- spread
- commission
- slippage
- swap / financing
```

historical条件が十分に再現できる場合のみこの名称を使用する。

historical swapがない場合、Level 2をLevel 3と呼んではならない。

## Commission

commissionの完全なhistorical time seriesがなくても、fee scheduleを

- per lot
- per notional
- bps

等へ正規化できる場合はscenarioとしてモデル可能である。

正確な過去scheduleが不明な場合は、単一の推測値を真値とせず、例えば

```text
commission = 0
commission = low
commission = base
commission = high
```

のようなscenarioを用いる。

## Spread / Slippage

bid/ask履歴やtick-level execution dataがない場合も、

```text
0 cost
low cost
base cost
1.5x base
2.0x base
```

等の感度分析を行う。

この結果は「historical execution replication」ではなく「cost robustness」と呼ぶ。

## Break-even Cost

M4では、可能な限り **break-even cost** を計算する。

目的は、実コストを一点推定するよりも、

> strategyがどの程度のall-in transaction costまで耐えられるか

を示すことである。

turnoverの定義と単位を明示した上で、strategy gross edgeがゼロになるcost水準を求める。

break-even costが現実的costより十分に高いか低いかを、M4以降の主要診断とする。

## Swap / Financing

長期FX/CFDではswap / financingの影響が大きくなり得る。

historical swapがない場合:

1. 現在のswapを過去全期間へ一律適用しない。
2. swapなし結果を「Full broker net」と呼ばない。
3. policy-rate differential等を使う場合はresearch proxyと明示する。
4. historical swapが得られるsubsetでは別途検証する。
5. 今後のforward testではactual broker swapを記録する。

## Milestone Boundary

### M0〜M3

- Level 1 Gross price-onlyを基本とする。
- transaction costをstrategy logicへ混ぜない。

### M4

- spread
- commission
- slippage
- swap / financing capability
- scenario analysis
- break-even cost

を追加する。

コストデータが不完全でもM4は実施できる。
ただし結論の強さをResult Levelに応じて制限する。
