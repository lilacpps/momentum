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

## FXの日足境界

broker/server timezoneでDaily barが変わるため、複数データソースを混ぜる場合は境界を固定する。

## Transaction costs

GrossとNetを必ず分離する。

Netで考慮候補:
- spread
- commission
- slippage
- swap / financing

## Swap

長期FX/CFDでは重要だが、現在swapを過去全期間へ適用してはいけない。

過去swapがない場合:
1. V0ではswap未考慮と明示。
2. その結果を「実運用Net return」と呼ばない。
3. 別途forward testでbroker実swapを記録する。
4. 政策金利差proxyを使う場合は、strategy research用proxyと明示する。

## Cost stress

最終段階では最低でも:
- base
- 1.5x cost
- 2.0x cost

を検討する。
