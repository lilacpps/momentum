# Research Questions

## RQ0: Pure directional TSMOM signalは手元データでも存在するか

まず、strategy PnLだけでなく、academic literatureに近い予測問題として直接確認する。

Research checkpoint R0では主に、

```text
past approximately 12-month return
        ->
next 1-month return
```

の関係を見る。

確認候補:

- `E[next_1m_return | past_12m_return > 0]`
- `E[next_1m_return | past_12m_return < 0]`
- continuous past-return predictor
- sign predictor
- symbol別
- pooled / market横断

M0のdaily strategy PnLだけをRQ0の答えとしない。

## RQ1: Edgeは単一symbol依存か

- symbol別
- market横断
- portfolio

single-symbolで弱い、または負であることだけでTSMOM全体を棄却しない。
逆に、単一symbolだけで非常に強い結果も十分な証拠とはみなさない。

## RQ2: Lookbackにplateauがあるか

- 20 / 60 / 120 / 240 barsなどの粗いgrid
- isolated optimumを採用しない
- parameterを細かく探索して最高値を選ばない

## RQ3: Volatility normalizationは何を改善するか

- gross return
- Sharpe
- DD
- concentration
- contribution balance

signal alphaとrisk engineeringを分離する。

## RQ4: Costでedgeはどこまで減るか

- spread
- commission
- slippage
- turnover
- break-even cost

historical cost seriesが存在しない場合も、cost scenarioとbreak-even analysisで耐コスト性を評価する。

## RQ5: Swap / financingはどの程度重要か

正確なhistorical swapがない場合は、推測値を「実績Net PnL」として混ぜない。

比較候補:

- gross price-only
- net ex-financing
- historical swap available subset
- policy-rate differential proxy（research proxyでありbroker PnL再現ではない）
- future forward-testで記録したactual broker swap

positive-swap-only filter等はbaseline cost treatmentではなく別strategyとして扱う。

## RQ6: 年次の凸凹はどの程度か

- yearly returns
- rolling 1y / 3y
- longest underwater
- consecutive losing years

## RQ7: 短期化するとどこでedgeが崩れるか

Daily -> 4h -> 1h

cost / turnover / whipsawの増加を測る。

## RQ8: Simplified Daily BaselineとAcademic-style TSMOMはどの程度異なるか

比較する:

### Simplified Daily

- Daily
- 240 observed bars
- daily signal refresh
- reverse when target changes
- initially unscaled

### Academic-style comparator

- monthly decision frequency
- approximately 12-month past return
- next 1-month holding
- initially unscaled
- spot/CFD price-return implementationであることを明示

その後、volatility scalingを追加した比較も行う。

目的は、「TSMOM」というラベルの下で実装差を混同しないことである。

## RQ9: Price momentumとexcess-return / carryを含むmomentumはどの程度異なるか

spot FX / CFDのprice-return signalと、futures / forwardsを使ったacademic return definitionには差がある。

可能なデータが確保できた段階で、

- price-only
- carry / financingを含むreturn
- academic excess-returnに近いreturn

を分けて評価する。

## RQ10: Academic reference dataと自作実装は整合するか

`references/` 配下の原論文・AQR Original Paper Data等を用い、可能な範囲で

- signal direction
- return seriesの方向性
- aggregate characteristics

をsanity checkする。

これはbroker spot/CFD PnLの再現とは別trackとする。
