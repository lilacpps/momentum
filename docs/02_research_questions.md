# Research Questions

## RQ0: Time-Series predictabilityは手元dataでも見えるか

M1で、strategy PnLではなく予測問題として直接確認する。

```text
past 12-month return -> next 1-month return
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

M1を少なくとも次の3 workstreamに分ける。

- M1A Practical Predictability: Track B split / universe freeze後に実行
- M1B MOP Regression Comparator: eligible reference underlying data確認後に実行
- M1C-Huang-reference / M1C-Huang-practical-analogue: methodology contract freeze後、各data gateに応じて実行

### Academic Track

futures / forward / excess-returnまたはreference seriesを使う。
既知のpublished sampleはreplication sampleとして扱い、final holdoutとは呼ばない。

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

M3/M4で、symbol別 / common rule / portfolioを評価する。

## RQ4: Lookbackにplateauがあるか

粗いgridのみ使用。

```text
20 / 60 / 120 / 240 daily intervals
```

isolated optimumをbaseline採用しない。

## RQ5: Volatility normalizationは何を改善するか

M5で、

- unscaled
- practical vol-scaled
- MOP-compatible reference-scaled

を比較し、return / Sharpe / DD / concentration / contribution balanceを見る。

risk scaling改善をsignal alpha改善と混同しない。

## RQ6: Costでedgeはどこまで減るか

M6でspread / commission / slippage / turnover / break-even costを評価する。

## RQ7: Swap / financingはどの程度重要か

比較候補:

- Gross price-only
- Net ex-financing
- historical swap available subset
- financing proxy（proxyと明記）
- future forward-test actual swap

historical swapなしでFull broker netを名乗らない。

## RQ8: 年次・regime依存はどの程度か

M7で、yearly returns / rolling 1y・3y / longest underwater / consecutive losing years / parameter x year / symbol x yearを見る。

## RQ9: Practical final holdoutでも残るか

Track BではM7で初めてfinal holdoutを開封し、事前固定した仕様を変更せず評価する。

Track Aのpublished sampleはこのholdoutとは別概念。

## RQ10: 短期化するとどこでedgeが崩れるか

M8/M9:

```text
Daily -> 4h -> 1h
```

turnover / spread / slippage / whipsaw増加を重点評価する。

## RQ11: Academic reference dataと自作系は整合するか

`references/` 配下の資料を使い、

- published factor return
- period / observation count
- aggregate characteristics
- methodology metadata

をsanity checkする。

AQR workbookにraw underlying seriesが含まれることを事前に仮定しない。

## RQ12: MOPのregression evidenceを再現できるか

M1 Reference Comparatorで、

- volatility-standardized monthly returns
- pooled panel regression
- lags `h=1...60 months`
- monthly calendar-time clustering

をMOP methodology comparatorとして実装する。

特に12-month predictor / next-month returnとの整合を報告する。

## RQ13: Huang et al.の統計的反証を再確認するとどうなるか

M1で、

- asset-by-asset regression
- pooled regression
- parametric wild bootstrap
- nonparametric pairs bootstrap
- fixed-effect sensitivity

をchallenge analysisとして扱う。

naive pooled t-statだけを結論にしない。

## RQ14: TSMのprofitはpredictabilityなしのTSHより本当に強いか

M3開始前にHuang et al.のTime-Series History (TSH) exact historical-mean contractをfreezeし、
M3〜M7で同じdefinitionを再利用する。

最低限、

- TSM return
- TSH return
- TSM - TSH
- Sharpe / alpha差
- long leg / short leg
- weighting scheme sensitivity

を見る。

TSHのhistorical-mean windowはreference paperのexact definitionを固定してから実装する。
論文仕様とcausal expanding-history analogueが異なる場合は別出力にする。
