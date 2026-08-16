# Academic TSMOM Baseline Specification

## 目的

最初からMOPの完全なportfolio strategyを複製せず、

- directional signal
- causal execution
- position state
- normalized gross return

を分離した最小engineをM0として実装します。

M0名称:

> **Single-Symbol Unscaled Daily TSMOM Research Baseline**

第一目的は **engine correctness** です。

---

# M0 Specification

## Frequency

- input: Daily OHLC
- signal evaluation: every observed daily bar
- target position update: every observed daily bar

## Lookback

```text
lookback_intervals = 240
```

これはcalendar daysではなく、observed daily price-return interval数です。

### 必要observation数

`L=240` のsignalは、

```text
Close[t-1] / Close[t-241] - 1
```

なので、`t-1` までに241個のvalid Close observationsが必要です。

## Signal timing

対象execution barを `t` とすると、

```text
past_return(t)
  = Close[t-1] / Close[t-1-L] - 1
```

のみを使用します。

```text
past_return > 0 -> signal +1
past_return < 0 -> signal -1
past_return = 0 -> signal  0
```

`Close[t]` やfuture dataをsignalへ使用してはなりません。

## Warm-up

必要な `L+1` Close observationsがない期間:

```text
signal = undefined
target_position = Flat
```

部分lookbackを使いません。

## Execution timing

```text
Close[t-1]まで確定
       ↓
signal / target決定
       ↓
Open[t] でposition変更
```

同じbarのCloseを見て同じCloseで約定させません。

## Position state

```text
Long  = +1
Flat  =  0
Short = -1
```

### Same state

```text
Long  -> Long
Short -> Short
Flat  -> Flat
```

新規tradeを生成しません。

### Entry

```text
Flat -> Long
Flat -> Short
```

`Open[t]` でentry。

### Exit

```text
Long  -> Flat
Short -> Flat
```

`Open[t]` でexit。

### Reversal

```text
Long  -> Short
Short -> Long
```

`Open[t]` で旧positionを閉じ、同じexecution priceで逆positionへ移行します。

ledger上は2 eventでも1 transitionでもよいですが、economic PnLは一致させます。

## Zero signal

```text
signal = 0 -> target Flat
```

zero signal時のholdは採用しません。

## Stop / Take Profit

M0では全てなし。

- stop loss: none
- take profit: none
- trailing stop: none
- time stop: none

## Position size

normalized exposure:

```text
Long  +1
Flat   0
Short -1
```

M0では、

- lot size
- leverage
- margin
- account-currency conversion
- volatility scaling

を扱いません。

## Return accounting

positionを `Open[t]` で変更するため、periodic research returnは原則open-to-next-openです。

```text
asset_return[t]
  = Open[t+1] / Open[t] - 1

strategy_return[t]
  = executed_position[t] * asset_return[t]
```

これにより `Close[t-1] -> Open[t]` のmoveを、
まだ存在しなかったpositionへ誤帰属しません。

## Dataset terminal policy

M0ではdataset末尾に**synthetic liquidationを作りません**。

- `Open[t+1]` がない最終barにはperiodic returnを作らない
- dataset末尾でopenのtradeはopen tradeとしてledgerに残す
- closed-trade statisticsから未決済tradeを除外する
- 架空のterminal execution priceを作らない

必要なら未決済状態を別metadataで報告します。

## 最低限保持する出力

- timestamp
- signal
- target_position
- executed_position
- execution event
- entry / exit price
- open-to-next-open asset return
- gross strategy return
- cumulative gross return
- trade ledger
- open-position status

---

# Academic literatureとの差分

| 項目 | MOP代表仕様 | M0 | 理由 |
|---|---|---|---|
| signal | past excess-return sign | past price-return sign | spot/CFD directional effectを分離 |
| formation | 約12か月 | 240 observed intervals | daily engineering baseline |
| decision | monthly | daily | daily baselineを先に実装 |
| holding | 1 month等 | target変更まで | rolling daily rule |
| sizing | inverse-vol scaling | ±1 | signal/risk分離 |
| instruments | futures / forwards | spot FX / CFD | 手元data |
| carry | returnに関係 | 未考慮 | M6以降 |
| transaction costs | 別途 | 未考慮 | M6 |
| portfolio | multi-market | single symbol | M3/M4 |

M0をpaper replicationとは呼びません。

---

# Volatility-Normalized Comparator

volatility normalizationは **M5** で追加します。

directional signalを変えずposition magnitudeのみ変更し、

- signal edge
- risk scaling

を分離して評価します。

---

# Parameter Policy

M0のengine fixtureでは240を標準にします。

historical researchでは粗い意味的gridのみを使います。

例:

```text
20 / 60 / 120 / 240
```

避ける:

```text
37, 38, 39, ... 83
```

ただしparameter performanceを見る前にholdout policyを固定します。
