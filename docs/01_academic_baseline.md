# Academic TSMOM Baseline Specification

## 目的

本プロジェクトでは、最初からMoskowitz, Ooi, Pedersen (2012) の完全なportfolio strategyを複製しません。

まず、

- directional momentum signal
- position state transition
- causal execution
- gross return

だけを分離した最小baselineをM0として実装します。

M0は **Single-Symbol Unscaled Daily TSMOM Research Baseline** と位置づけます。

M0の第一目的はhistorical profitabilityの証明ではなく、**signal / execution / position state / return accountingを正しく実装すること（engine correctness）**です。M0のbacktestがプラスかマイナスかだけで、academic TSMOMの存在を判断しません。

M0完了後は `docs/04_validation_policy.md` および `docs/06_evaluation_protocol.md` に従い、R0 Academic Hypothesis CheckとR1 Academic-Style Comparatorを実施します。

原論文との差分は意図的なものを含め、必ず本書に記録します。

## Baseline A — M0: Unscaled Daily Directional TSMOM

### Frequency

- input timeframe: Daily
- signal evaluation frequency: every observed daily bar
- target position update frequency: every observed daily bar

### Lookback

標準値:

```text
lookback_bars = 240
```

`lookback_bars` はcalendar daysではなく、有効なobserved daily barsの数を意味します。

将来のresearch gridとして、

```text
20 / 60 / 120 / 240 bars
```

などを使用できますが、M0のengine実装確認では240を標準とします。

### Signal timing

対象barを `t` としたとき、signal計算に使用できるデータは `t-1` までに確定したものだけとします。

```text
past_return(t) = Close[t-1] / Close[t-1-lookback_bars] - 1
```

signal:

```text
past_return > 0 -> +1
past_return < 0 -> -1
past_return = 0 -> 0
```

`Close[t]` やそれ以降の値をsignal生成へ使用してはなりません。

### Execution timing

`t-1` のbarが確定した後にtarget positionを決定し、position変更は `Open[t]` で行います。

```text
data through Close[t-1]
        ↓
calculate signal
        ↓
target_position[t]
        ↓
execute at Open[t]
```

M0では、同一barのcloseを見て同じcloseで約定したものとしてはなりません。

### Position state

target positionは以下の3状態とします。

```text
+1 = Long
 0 = Flat
-1 = Short
```

#### Unchanged signal

```text
Long  -> Long
Short -> Short
Flat  -> Flat
```

の場合、新規tradeを生成せず既存stateを維持します。

#### Entry

```text
Flat -> Long
Flat -> Short
```

の場合、`Open[t]` で新規positionへ移行します。

#### Exit

```text
Long  -> Flat
Short -> Flat
```

の場合、`Open[t]` でpositionを閉じます。

#### Reversal

```text
Long  -> Short
Short -> Long
```

の場合、`Open[t]` で旧positionを終了し、同一execution priceで反対方向のpositionへ移行したものとして扱います。

実装上、「close + new entry」の2イベントとして記録しても、単一のposition transitionとして記録してもよいですが、PnL結果が同一でなければなりません。

### Zero signal

M0では

```text
signal = 0 -> target Flat
```

とします。

zero signal時に既存positionを維持する仕様は採用しません。

### Warm-up

signal生成に必要なlookback historyが揃うまでは

```text
target position = Flat
```

とします。

不足期間を部分的なlookbackで計算してはなりません。

### Stop / Take Profit

M0では使用しません。

- stop loss: none
- take profit: none
- trailing stop: none
- time stop: none

position変更理由はtarget signalの変更のみとします。

### Position size

M0ではvolatility scalingを使用しません。

positionはnormalized exposureとして、

```text
Long  = +1
Flat  = 0
Short = -1
```

を基本単位とします。

lot size、leverage、margin、account currency conversionはM0の対象外とします。

### Return accounting

M0ではbroker account PnLではなく、strategy research用のnormalized gross returnを計算します。

positionを `Open[t]` で変更するため、daily strategy returnは原則として **open-to-next-open** で定義します。

```text
asset_return[t] = Open[t+1] / Open[t] - 1
strategy_return[t] = position_after_execution[t] * asset_return[t]
```

これにより、`Close[t-1]` を見てから `Open[t]` で初めて取れるpositionに、`Close[t-1] -> Open[t]` のovernight moveを誤って帰属させません。

`Open[t+1]` が存在しない最終barはperiodic return計算から除外します。dataset末尾のopen positionを強制決済したものとしてtrade PnLへ加える場合は、terminal mark-to-marketとして明示し、通常のdaily returnと混同しません。

少なくとも、

- target position
- executed position
- entry / exit
- open-to-open asset return
- gross strategy return
- cumulative gross return

を再現可能な形式で保持します。

spread、commission、slippage、swapは含めません。

## Academic literatureとの差分

| 項目 | Moskowitz, Ooi, Pedersen (2012)代表仕様 | M0 | 理由 |
|---|---|---|---|
| signal | past excess-return sign | past price-return sign | spot/CFD dataでdirectional effectを分離 |
| lookback | 約12か月 | 240 observed daily bars | 実装をbar-basedに明確化 |
| signal frequency | monthlyが代表 | daily | daily baselineを先に評価 |
| holding | 1 month等 | target変更まで | daily rolling signalとして単純化 |
| position size | inverse-volatility scaling | ±1 normalized | signalとrisk scalingを分離 |
| instruments | futures / forwards | spot FX / CFD | 手元dataへ適用 |
| excess return | 使用 | 使用しない | carryを含めないM0 |
| financing/carry | instrument returnに関係 | 未考慮 | M4以降 |
| transaction costs | strategy評価上考慮可能 | 未考慮 | M4 |
| portfolio | multi-market | single symbol | M1/M2で追加 |

この表の差分を理由なく変更してはなりません。

M0結果は「academic paper replication」ではなく、**academic TSMOM-inspired directional baseline** として扱います。

## Baseline B — Volatility-Normalized Comparator

Baseline BはM0には含めず、M3で実装します。

directional signalはBaseline Aと同一とし、position magnitudeのみex-ante volatilityに応じて変更します。

目的は、

- directional signalのedge
- volatility normalizationの効果

を分離することです。

M3ではAcademic TSMOMとの比較のため、原論文のvolatility scaling methodologyとの差分も明示します。

## Research parameter policy

パラメータは「最高値探索」ではなく粗い意味的gridを使用します。

例:

```text
20 / 60 / 120 / 240 bars
```

避ける:

```text
37, 38, 39, ..., 83 bars
```
