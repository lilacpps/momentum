# Time-Series Momentum（TSMOM）とは何か

## 1. このプロジェクトでいう Momentum

「Momentum」には複数の意味があります。本プロジェクトでは、まず **Time-Series Momentum（TSMOM）** を対象にします。

TSMOMの中心的な仮説は非常に単純です。

> ある市場について、過去一定期間のリターンが正なら、その後もしばらく正方向へ動きやすく、過去リターンが負なら、その後もしばらく負方向へ動きやすい。

重要なのは、**他の銘柄との相対比較ではなく、その市場自身の過去リターンを見る**ことです。

### 本プロジェクトのM0におけるsignal

M0では、TSMOMのdirectional componentだけを最小構成で検証するため、単純なprice-return signalを用います。

```text
past_return_L(t) = Close[t-1] / Close[t-1-L] - 1
```

ここで、

- `t` はpositionを更新する対象bar
- `t-1` はsignal計算時点で利用可能な直近確定bar
- `L` はcalendar daysではなく **observed daily barsの本数**
- M0の標準値は `L = 240`

とします。

したがって、`240 bars` を厳密な意味で「12か月」とは呼びません。実際のcalendar期間は休日やデータ欠損によって異なり得ます。

```text
past_return > 0 -> target Long
past_return < 0 -> target Short
past_return = 0 -> target Flat
```

M0ではsignalの強さはposition sizeへ反映せず、方向だけを `-1 / 0 / +1` として使用します。

## 2. Cross-Sectional Momentumとの違い

### Time-Series Momentum

```text
EURUSD自身が過去に上昇していた -> EURUSD Long
EURUSD自身が過去に下落していた -> EURUSD Short
```

### Cross-Sectional Momentum

```text
複数資産を比較
上位のwinnerをLong
下位のloserをShort
```

この2つは似ていますが、研究上は別の戦略です。

## 3. 代表的な研究

Moskowitz, Ooi, Pedersen (2012) は、株価指数、通貨、商品、国債の58の流動性の高い先物・forwardを用い、各市場の過去リターンと将来リターンの関係を調べました。

主なポイント:

- 過去1〜12か月のreturn persistenceを検証。
- 特に過去12か月のexcess returnを代表的signalとして使用。
- 58市場にまたがって現象を確認。
- 単一市場の大きなedgeより、複数市場に共通する弱いedgeと分散を重視。
- Time-Series MomentumとCross-Sectional Momentumを明確に区別。

したがって、TSMOMは「EURUSDだけで高PFを狙うEA」というより、

```text
小さなtrend edge
× 多数市場
× 長期間
× risk control
```

という発想に近い戦略です。

## 4. Academic TSMOMとの関係

Moskowitz, Ooi, Pedersen (2012) の代表的なTime-Series Momentum strategyは、本プロジェクトのM0と完全に同一ではありません。

| 項目 | Academic literatureの代表仕様 | M0 |
|---|---|---|
| signal source | futures / forwardのexcess return | spot / CFD price return |
| lookback | 約12か月 | 240 observed daily bars |
| signal更新 | monthlyが代表的 | daily |
| holding | 1か月等を明示 | target signal変更まで |
| sizing | volatility scalingあり | unscaled |
| portfolio | multi-market | single symbol |
| costs / carry | instrument returnの定義に依存 | M0では未考慮 |

したがってM0の結果を「Moskowitz–Ooi–Pedersen (2012) の完全再現」とは呼びません。

M0の目的は、TSMOMのdirectional signalそのものが手元のprice dataでどのように振る舞うかを、他の要素から分離して確認することです。

## 5. なぜ trend が続く可能性があるのか

研究では複数の説明が議論されています。

- 新情報への反応が一度に完了せず、価格へ徐々に織り込まれる。
- 投資家のunderreaction / delayed reaction。
- herding。
- institutional flow / capital-market frictions。
- 中央銀行・企業・投資家の大規模なポジション調整が時間をかけて行われる。

重要なのは、これらは「確定した唯一の原因」ではなく、trend persistenceを説明する候補です。

## 6. なぜ単一ペアだけでは弱く見えやすいのか

Momentumは、すべての市場で常にtrendが出る戦略ではありません。

```text
EURUSD: range
Gold: strong trend
USDJPY: weak trend
Oil: strong trend
```

のように、市場ごとに機会の時期が違います。

そのため、研究上のTSMOMは複数市場をまとめたportfolioで評価されることが多いです。

## 7. Momentumの典型的な弱点

- Rangeでwhipsawが増える。
- 長い停滞期・drawdownがあり得る。
- 短期化するほどspread/slippageの影響が大きくなる。
- FX/CFDで長期保有する場合はswapの影響が重要。
- signalのedgeとvolatility scalingの効果を混同しやすい。
- lookbackを市場ごとに細かく最適化するとoverfitしやすい。

## 8. Momentum strength と regime

MomentumはLong / Shortの二値signalだけでなく、trendの強さを表す連続的なscoreとして扱うこともできます。

例えば、単純な過去リターンだけでなく、volatilityで正規化した値を補助的に記録できます。

```text
normalized_momentum = past_return_N / realized_volatility
```

これにより、marketや時期をまたいでMomentumの強弱を比較しやすくなります。

ただし、最初のPure TSMOM baselineでは、このscoreを追加filterとして使わず、まず基本signalそのものの成績を確認します。

## 9. 最初にやってはいけないこと

最初から次を追加しません。

- RSI
- ADX
- MACD
- MA alignment
- session filter
- fine-tuned stop / take profit
- symbol別の最適lookback
- 利益を見ながらの閾値追加

まずは「Pure Momentumが自分のデータでも再現するか」を確認します。

## 10. このプロジェクトにおける成功条件

最初の目標は高PFではありません。

良い兆候は例えば次です。

- 粗い複数lookbackで同方向の結果が出る。
- 特定symbolだけでなく複数symbolにedgeが見える。
- costを入れても完全には消えない。
- year別に凸凹があっても、長期間・portfolioで残る。
- parameterを少し変えても壊れない。
- holdout / walk-forwardで極端に崩れない。

これを満たして初めて、4h / 1hへの短期化や追加的な研究へ進みます。

## 10. M0の役割と研究上の証拠

M0の目的は、最初から「TSMOMが儲かる」と示すことではありません。

M0では、

- signalの時点整合
- lookback
- execution timing
- position transition
- return accounting

を固定し、engine correctnessを確認します。

その後、academic TSMOMとの整合は別のresearch checkpointで確認します。

```text
M0: engine correctness
R0: past ~12m return -> next 1m return のpredictability
R1: monthly / ~12m lookback / 1m hold comparator
M1+: multi-symbol / portfolio / risk / costs
```

したがって、M0単一symbolの損益だけでTSMOM全体の有無を判断しません。

詳細は `docs/04_validation_policy.md` と `docs/06_evaluation_protocol.md` を参照します。
