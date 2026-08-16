# Research Questions

## RQ0: Time-Series predictabilityは手元dataでも見えるか

M1で、strategy PnLではなく予測問題として直接確認する。

```text
past 12-month return
      ->
next 1-month return
```

見るもの:

- sign-conditioned future return
- continuous predictor
- effect size
- uncertainty
- symbol別
- pooled / cross-market

M0のdaily PnLだけを答えにしない。

## RQ1: Academic dataとspot/CFD analogueはどう違うか

M1を2 trackに分ける。

### Academic Track

可能ならfutures / forward / excess-returnまたはAQR referenceを使う。

### Practical Track

spot/CFD price returnを使う。

後者が有意でもMOP完全再現とは呼ばない。

## RQ2: Daily simplified baselineとmonthly comparatorはどう違うか

M2で比較する。

### M0 Daily

- 240 observed intervals
- daily refresh
- next-open execution
- target変更までhold

### M2 Monthly

- 12 completed calendar months
- monthly decision
- next-month first open execution
- 1-month holding

差を見る:

- gross return
- DD
- turnover
- holding period
- direction agreement

## RQ3: Edgeは単一symbol依存か

M3/M4で、

- symbol別
- common rule
- portfolio

を評価する。

単一symbolだけでTSMOM全体を判断しない。

## RQ4: Lookbackにplateauがあるか

粗いgridのみ使用。

例:

```text
20 / 60 / 120 / 240 daily intervals
```

isolated optimumをbaseline採用しない。

## RQ5: Volatility normalizationは何を改善するか

M5で、

- return
- Sharpe
- DD
- concentration
- contribution balance

を見る。

risk scaling改善をsignal alpha改善と混同しない。

## RQ6: Costでedgeはどこまで減るか

M6で、

- spread
- commission
- slippage
- turnover
- break-even cost

を評価する。

historical cost seriesがなくてもscenario分析を行う。

## RQ7: Swap / financingはどの程度重要か

比較候補:

- Gross price-only
- Net ex-financing
- historical swap available subset
- financing proxy（proxyと明記）
- future forward-test actual swap

historical swapなしでFull broker netを名乗らない。

## RQ8: 年次・regime依存はどの程度か

M7で、

- yearly returns
- rolling 1y / 3y
- longest underwater
- consecutive losing years
- parameter x year
- symbol x year

を見る。

## RQ9: Final holdoutでも残るか

M7で初めてfinal holdoutを開封し、
事前固定した仕様を変更せず評価する。

## RQ10: 短期化するとどこでedgeが崩れるか

M8/M9:

```text
Daily -> 4h -> 1h
```

turnover / spread / slippage / whipsaw増加を重点評価する。

## RQ11: Academic reference dataと自作系は整合するか

`references/` 配下の資料を使い、可能な範囲で

- published factor return
- aggregate characteristics
- signal direction（underlying dataが実際にあれば）
- period / summary statistics

をsanity checkする。

AQR workbookにraw underlying seriesが含まれることを事前に仮定しない。
