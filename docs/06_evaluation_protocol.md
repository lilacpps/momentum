# Evaluation Protocol — What Can We Conclude at Each Milestone?

## 1. 目的

backtestがプラスだっただけで、

> TSMOMが再現した

とは結論しません。

各Milestoneで何を言えるかを固定します。

---

## E0 — Engine Correctness

対象: M0

言ってよい:

> 定義したM0 engineがcausalかつ仕様通り動く。

まだ言えない:

> TSMOMにedgeがある。

---

## E1 — Predictive Evidence

対象: M1

確認:

```text
past 12m return -> next 1m return
```

言ってよい:

> Track A / Track Bそれぞれでdirectional predictabilityの証拠が見える / 見えない。

Track Bのspot resultだけでpaper replicationとは言わない。

commissionは不要。

まだ言えない:

> brokerでnet profitable。

---

## E2 — Strategy Construction Evidence

対象: M2 / M3

確認:

- daily simplified
- monthly academic-style
- multiple symbols
- turnover / holding

言ってよい:

> signalを特定のposition ruleへ変換したgross strategyの性質。

まだ言えない:

> realistic costs後にも残る。

---

## E3 — Portfolio / Risk Evidence

対象: M4 / M5

確認:

- diversification
- equal-notional
- volatility scaling
- concentration

言ってよい:

> portfolio constructionとrisk scalingを含むgross特性。

vol scaling改善をsignal alphaと混同しない。

---

## E4 — Cost Robustness

対象: M6

historical cost seriesがなくても、

- plausible scenarios
- turnover
- break-even cost

で評価可能。

言ってよい:

> 想定cost rangeに対してedgeがrobust / fragile。

まだ言えない:

> 特定brokerで過去にこのNet PnLだった。

---

## E5 — Robust / Holdout Evidence

対象: M7

final holdoutを一度だけ評価。

言ってよい:

> 事前固定したstrategyが未見期間でもどの程度維持されたか。

holdoutを見てruleを変えたら、その後は新しいholdoutが必要。

---

## E6 — Broker-Net Evidence

十分なhistorical execution / financing dataがある場合のみ。

必要:

- spread
- fee schedule
- realistic slippage
- swap / financing
- contract specification

言ってよい:

> 特定broker条件を近似したhistorical net simulation。

tick-level約定がなければ完全再現とは限らない。

---

# Commissionデータがなくても研究する意味

あります。

- M1: cost不要
- M0〜M5: signal / strategy / portfolioのgross構造を研究
- M6: scenario + break-even cost
- actual historical broker netだけ主張しない

という分離ができます。

---

# Swapデータがない場合

結果を、

```text
Level 1 Gross price-only
Level 2 Net ex-financing
Level 3 Full broker net
```

に分けます。

Level 3を無理に作りません。

current swapの過去一律適用は原則避けます。

---

# Decision Gates

## Gate M0

必要:

- golden tests
- causality
- accounting

次へ進む前にsplit/universe freeze。

## Gate M1

確認:

- Academic Track
- Practical Track
- uncertainty

弱くても即終了ではないが、
academic replicationとpractical trend explorationの目的を混同しない。

## Gate M2

確認:

- daily vs monthly implementation差

## Gate M3/M4

確認:

- symbol横断性
- diversification

## Gate M5

確認:

- unscaledで何が残るか
- scalingで何が改善するか

## Gate M6

確認:

- break-even cost
- realistic cost scenarios
- financing limitation

## Gate M7

確認:

- plateau
- validation
- final holdout
- year / symbol robustness

ここまで通ってからM8/M9へ進む。
