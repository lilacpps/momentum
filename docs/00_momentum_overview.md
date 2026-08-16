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

- `t` = positionを更新する対象daily bar
- `t-1` = signal計算時に利用可能な直近確定bar
- `L` = calendar daysではなくreturn interval数
- M0標準 = `L = 240`

### Off-by-one契約

`L = 240` は240個のprice-return intervalを意味します。

```text
Close[t-1] / Close[t-241] - 1
```

を計算し、signal生成には241個のClose observationが必要です。

```text
past_return > 0 -> Long
past_return < 0 -> Short
past_return = 0 -> Flat
```

history不足時は `signal = undefined` とし、target positionはFlatにします。

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

MOPの代表的TSMOM factorは概ね、

- monthly decision
- past 12-month return sign
- 1-month holding
- ex-ante volatility scaling
- per-instrument 40% annualized target volatility
- available instrumentsのequal-weight aggregation

を含みます。

M0は、その完全再現ではありません。

| 項目 | MOP代表的構成 | M0 |
|---|---|---|
| signal source | futures / forward excess return | spot / CFD price return |
| formation | 12 months | 240 observed daily intervals |
| decision cadence | monthly | daily |
| holding | 1 month | target変更まで |
| sizing | ex-ante volatility scaling | unscaled ±1 |
| portfolio | multi-market equal aggregation | single symbol |
| carry / financing | excess-return definitionに関係 | 未考慮 |
| cost | strategy評価で別途 | M0では未考慮 |

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

## 6. Reference validationへの段階

```text
M0: engine correctness

M1: predictive relationを直接検証
    + MOP regression comparator
    + Huang statistical challenge

M2: monthly / 12m formation / 1m holding
    のunscaled strategy comparator

M3/M4: multi-symbol / portfolio

M5: MOP-compatible volatility scaling
    + 40% per-instrument reference sizing
    + available-instrument equal aggregation

M6: cost / financing

M7: robustness / TSM-vs-TSH / practical final holdout
```

**M2だけではMOP代表TSMOM factorのstrategy-level reproductionには不足**します。
M5でvolatility scalingまで入って初めてreference strategy comparatorが成立します。

## 7. MOP肯定結果だけで判断しない

`references/7.Time-series momentum_ Is it there_.pdf` の批判をchallenge suiteへ入れます。

最低限、

- asset-by-asset predictability
- pooled regression inference
- wild / pairs bootstrap
- TSM vs TSH
- long / short leg attribution

を確認します。

strategyが利益を出しても、predictabilityが原因とは限らない点を明示します。

## 8. 単一symbolだけで判断しない

TSMOMは単一市場で常に強いedgeが出ることを前提にしません。

- M0の単一symbolが負
- ある1 symbolだけが非常に強い

のどちらもTSMOM全体の結論にはしません。

M3/M4でcommon ruleとportfolioを評価します。

## 9. Volatility scaling

volatility scalingはacademic TSMOMで重要ですが、
signal predictabilityとrisk engineeringを混同しないためM0には入れません。

M5で、

- unscaled / equal-notional
- practical volatility-scaled
- MOP-compatible reference-scaled

を分離して比較します。

MOP-compatible comparatorでは、

- `docs/07_academic_validation_spec.md` §3.2のauthoritative EWMA formula
- weights `w_i=(1-delta)delta^i`
- `delta/(1-delta)=60`, `delta=60/61`
- annualization 261
- `sigma[t-1]` を使用
- asset target annualized vol 40%

をreference contractとします。初期化、minimum history、missing、zero/near-zero、cap/floorは
`docs/07_academic_validation_spec.md` §3.2の区分に従います。

vol scalingでSharpeが上がっても、それをsignal predictabilityが強くなったとは表現しません。

## 10. 最初に追加しないもの

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

## 11. 成功条件の考え方

最終的な良い兆候は、

- MOP方法論・reference seriesとの整合性を説明できる
- Huang challengeで弱点も可視化される
- 粗いparameter範囲で結果が壊れない
- 複数市場で同方向の証拠がある
- portfolioで分散効果がある
- realistic cost scenarioでも完全には消えない
- year / regimeで極端に一点依存しない
- Practical Trackのfinal holdoutで大崩れしない

ことです。

ただしこれらはM0の完了条件ではなく、後続Milestoneで評価します。
