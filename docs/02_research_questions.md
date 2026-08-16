# Research Questions

## RQ0: Pure TSMOMは手元データでも存在するか

- Daily
- common rule
- no discretionary filter

## RQ1: Edgeは単一symbol依存か

- symbol別
- market横断
- portfolio

## RQ2: Lookbackにplateauがあるか

- 20 / 60 / 120 / 240日などの粗いgrid
- isolated optimumを採用しない

## RQ3: Volatility normalizationは何を改善するか

- gross return
- Sharpe
- DD
- concentration

signal alphaとrisk engineeringを分離する。

## RQ4: Costでedgeはどこまで減るか

- spread
- commission
- slippage
- turnover

## RQ5: Swapはどの程度重要か

正確なhistorical swapがない場合は、推測値を本番結果へ混ぜない。

比較候補:
- swap ignored baseline
- historical swap available subset
- policy-rate differential proxy（研究用補助。broker PnL再現ではない）
- positive-swap-only filter（別strategyとして評価）

## RQ6: 年次の凸凹はどの程度か

- yearly returns
- rolling 1y / 3y
- longest underwater
- consecutive losing years

## RQ7: 短期化するとどこでedgeが崩れるか

Daily -> 4h -> 1h

cost / turnover / whipsawの増加を測る。
