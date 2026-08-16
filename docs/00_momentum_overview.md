# Time-Series Momentum（TSMOM）とは何か

## 1. このプロジェクトでいう Momentum

「Momentum」には複数の意味があります。本プロジェクトでは、まず **Time-Series Momentum（TSMOM）** を対象にします。

TSMOMの中心的な仮説は非常に単純です。

> ある市場について、過去一定期間のリターンが正なら、その後もしばらく正方向へ動きやすく、過去リターンが負なら、その後もしばらく負方向へ動きやすい。

最小のシグナルは概念的には次の形です。

```
past_return_N = Price[t-1] / Price[t-1-N] - 1

past_return_N > 0  -> Long
past_return_N < 0  -> Short
```

重要なのは、**他の銘柄との相対比較ではなく、その市場自身の過去リターンを見る**ことです。

## 2. Cross-Sectional Momentumとの違い

### Time-Series Momentum

```
EURUSD自身が過去に上昇していた -> EURUSD Long
EURUSD自身が過去に下落していた -> EURUSD Short
```

### Cross-Sectional Momentum

```
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

```
小さなtrend edge
× 多数市場
× 長期間
× risk control
```

という発想に近い戦略です。

## 4. なぜ trend が続く可能性があるのか

研究では複数の説明が議論されています。

- 新情報への反応が一度に完了せず、価格へ徐々に織り込まれる。
- 投資家のunderreaction / delayed reaction。
- herding。
- institutional flow / capital-market frictions。
- 中央銀行・企業・投資家の大規模なポジション調整が時間をかけて行われる。

重要なのは、これらは「確定した唯一の原因」ではなく、trend persistenceを説明する候補です。

## 5. なぜ単一ペアだけでは弱く見えやすいのか

Momentumは、すべての市場で常にtrendが出る戦略ではありません。

```
EURUSD: range
Gold: strong trend
USDJPY: weak trend
Oil: strong trend
```

のように、市場ごとに機会の時期が違います。

そのため、研究上のTSMOMは複数市場をまとめたportfolioで評価されることが多いです。

## 6. Momentumの典型的な弱点

- Rangeでwhipsawが増える。
- 長い停滞期・drawdownがあり得る。
- 短期化するほどspread/slippageの影響が大きくなる。
- FX/CFDで長期保有する場合はswapの影響が重要。
- signalのedgeとvolatility scalingの効果を混同しやすい。
- lookbackを市場ごとに細かく最適化するとoverfitしやすい。

## 7. Momentum strength と regime

MomentumはLong / Shortの二値signalだけでなく、trendの強さを表す連続的なscoreとして扱うこともできます。

例えば、単純な過去リターンだけでなく、volatilityで正規化した値を補助的に記録できます。

```
normalized_momentum = past_return_N / realized_volatility
```

これにより、marketや時期をまたいでMomentumの強弱を比較しやすくなります。

ただし、最初のPure TSMOM baselineでは、このscoreを追加filterとして使わず、まず基本signalそのものの成績を確認します。

## 8. 最初にやってはいけないこと

最初から次を追加しないこと。

- RSI
- ADX
- MACD
- MA alignment
- session filter
- fine-tuned stop / take profit
- symbol別の最適lookback
- 利益を見ながらの閾値追加

まずは「Pure Momentumが自分のデータでも再現するか」を確認します。

## 9. このプロジェクトにおける成功条件

最初の目標は高PFではありません。

良い兆候は例えば次です。

- 粗い複数lookbackで同方向の結果が出る。
- 特定symbolだけでなく複数symbolにedgeが見える。
- costを入れても完全には消えない。
- year別に凸凹があっても、長期間・portfolioで残る。
- parameterを少し変えても壊れない。
- holdout / walk-forwardで極端に崩れない。

これを満たして初めて、4h / 1hへの短期化や追加的な研究へ進みます。
