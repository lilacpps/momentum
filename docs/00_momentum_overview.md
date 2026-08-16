# Time-Series Momentum（TSMOM）とは何か

## 1. このプロジェクトでいうMomentum

本プロジェクトではまず **Time-Series Momentum（TSMOM）** を対象にします。

中心的な仮説は、

> ある市場について、過去一定期間のリターンの方向が、その後のリターン方向と正の関係を持つ可能性がある

というものです。

Cross-Sectional Momentumのように複数銘柄を順位付けするのではなく、
各市場自身の過去returnを使います。

## 2. M0で使用する簡略signal

M0ではdirectional componentだけを分離するため、次のprice-return signを使います。

```text
past_return_L(t) = Close[t-1] / Close[t-1-L] - 1
```

ここで、

- `t` = positionを更新する対象daily bar
- `t-1` = signal計算時に利用可能な直近確定bar
- `L` = calendar daysではなく **return interval数**
- M0標準 = `L = 240`

です。

### Off-by-one契約

`L = 240` は240個のprice-return intervalを意味します。

したがって、

```text
Close[t-1] / Close[t-241] - 1
```

を計算し、signal生成には **241個のClose observation** が必要です。

rolling windowを240 observationsとして1本短く実装してはなりません。

signal mapping:

```text
past_return > 0 -> Long
past_return < 0 -> Short
past_return = 0 -> Flat
```

history不足時は `signal = undefined` とし、target positionはFlatにします。
history不足を `signal = 0` と混同しません。

## 3. Cross-Sectional Momentumとの違い

### Time-Series Momentum

```text
EURUSD自身の過去return > 0 -> EURUSD Long
EURUSD自身の過去return < 0 -> EURUSD Short
```

### Cross-Sectional Momentum

```text
複数市場を比較
winnerをLong
loserをShort
```

本プロジェクトのbaselineは前者です。

## 4. Academic TSMOMとの関係

Moskowitz, Ooi, Pedersen (2012) は株価指数、通貨、商品、債券の
futures / forwardsを横断してTime-Series Momentumを研究しています。

本プロジェクトのM0は、その代表strategyの完全再現ではありません。

| 項目 | Academic literatureの代表的構成 | M0 |
|---|---|---|
| signal source | futures / forward excess return | spot / CFD price return |
| formation | 約12か月 | 240 observed daily return intervals |
| decision cadence | monthlyが代表 | daily |
| holding | 1 month等 | target変更まで |
| sizing | volatility scalingあり | unscaled ±1 |
| portfolio | multi-market | single symbol |
| carry / financing | return definitionに関係 | 未考慮 |
| cost | strategy評価で別途考慮 | M0では未考慮 |

したがってM0を、

- MOP replication
- original-paper replication
- academic TSMOM完全再現

とは呼びません。

M0は **academic TSMOM-inspired directional engineering baseline** です。

## 5. M0の役割

M0の第一目的は利益の証明ではありません。

確認するのは、

- signal timing
- lookback
- off-by-one
- next-open execution
- position state transition
- return accounting
- lookahead safety

です。

M0がnegative returnでも、engineが仕様通りならM0は完了できます。

## 6. M1/M2でacademicな問いへ近づける

```text
M0: engine correctness

M1: past 12-month return
        ->
    next 1-month return
    のpredictability

M2: monthly decision
    12 calendar-month formation
    1-month holding
    のacademic-style comparator

M3+: multi-symbol / portfolio / risk / costs
```

M1/M2でもspot/CFD price dataを使う場合は、
futures / forward excess-return strategyの完全再現とは呼びません。

## 7. なぜ単一symbolだけで判断しないか

TSMOMは単一市場で常に強いedgeが出ることを前提にしません。

そのため、

- M0の単一symbolが負
- ある1 symbolだけが非常に強い

のどちらもTSMOM全体の結論にはしません。

M3/M4で共通ruleとportfolioを評価します。

## 8. Volatility scaling

volatility scalingはacademic TSMOMで重要ですが、
signal predictabilityとrisk engineeringを混同しないためM0には入れません。

M5で、

- unscaled
- volatility-scaled

を比較します。

vol scalingでSharpeが上がっても、
それをsignal predictabilityが強くなったとは表現しません。

## 9. 最初に追加しないもの

M0では以下を追加しません。

- RSI
- ADX
- MACD
- MA alignment
- session filter
- TP / SL
- trailing stop
- symbol別lookback最適化
- performanceを見ながら追加する閾値

## 10. 成功条件の考え方

最終的な良い兆候は、

- 粗いparameter範囲で結果が壊れない
- 複数市場で同方向の証拠がある
- portfolioで分散効果がある
- realistic cost scenarioでも完全には消えない
- year / regimeで極端に一点依存しない
- final holdoutで大崩れしない

ことです。

ただしこれらはM0の完了条件ではなく、後続Milestoneで評価します。
