# Validation Policy

## 原則

以下を混同しません。

1. engineが正しい
2. predictive relationがある
3. gross strategyとして性質が良い
4. portfolioとして有用
5. cost後にも残る
6. broker historical netを近似再現できる

---

# 1. Validation Sequence

## M0 — Engineering Validation

profitabilityではなくcorrectnessを判定。

必須:

- golden fixture
- off-by-one
- lookahead mutation
- execution timing
- state transition
- return accounting
- terminal policy
- deterministic output
- invalid data handling

M0がnegativeでもcorrectなら完了。

## ★ M0完了直後: Split Lock

**M1でhistorical performance / predictabilityを見る前に**、

```text
development
validation
final holdout
```

の期間とsymbol universeを固定します。

この順序は必須です。

## M1 — Academic Hypothesis Check

原則development setで研究します。

見るもの:

```text
past 12m return -> next 1m return
```

commission / spread / swapは不要。

### Statistical uncertainty

IID前提のnaive t-valueだけで結論しません。

最低限:

- effect size
- confidence interval
- sample size
- symbol別結果
- pooled結果
- serial dependenceを考慮したuncertainty

を報告します。

default inferenceは `docs/07_academic_validation_spec.md` に固定します。

## M2 — Academic-Style Comparator

monthly decision / 12 calendar-month formation / 1-month holdingを実装し、
M0 daily ruleとの差を比較します。

## M3 — Multi-Symbol

common ruleを複数symbolへ適用。

単一市場依存を確認。

## M4 — Portfolio

diversificationとequal-notional aggregationを評価。

## M5 — Risk Scaling

unscaledとvolatility-scaledを分離。

## M6 — Cost Robustness

scenario / turnover / break-even cost。

historical cost replicationとcost robustnessを区別。

## M7 — Robust Historical Validation

ここで、

- validation
- parameter plateau
- year / symbol slices
- rolling results
- walk-forward
- cost stress

を行い、**最後にfinal holdoutを一度だけ評価**します。

final holdoutを見て仕様変更した場合、それはfinal holdoutではなくなります。

---

# 2. Holdout Usage Policy

## Development

M1〜M6の設計・debug・explorationに使用可能。

## Validation

事前に固定したmajor designの確認に使用。

validation結果を見て頻繁にruleを変更し続けない。

## Final Holdout

M7まで原則見ない。

final holdoutを開いた後は、

- lookback
- symbol universe
- filter
- execution
- cost assumptionの都合のよい変更

を行って同じholdoutを再評価しません。

---

# 3. Causality Mutation

時点 `T` より後のOHLCを変更しても、

```text
signal[t]
target_position[t]
executed_position[t]
```

for `t <= T`

が変化してはなりません。

---

# 4. 禁止事項

- M1前にfinal holdoutを覗く
- holdoutを見てparameter変更
- symbolごとのlookback optimumをbaseline採用
- isolated optimumを採用
- filterを結果を見ながら追加し続ける
- M0利益だけをTSMOM evidenceとする
- spot analogueをMOP完全再現と呼ぶ
- vol scaling改善をsignal alphaと呼ぶ
- incomplete cost modelをFull broker netと呼ぶ

---

# 5. 推奨成果物

- M0 golden fixture report
- M1 prediction tables / regressions
- M2 M0-vs-monthly comparator
- parameter x symbol
- parameter x year
- portfolio equity
- rolling return / Sharpe
- underwater
- turnover / holding period
- cost sensitivity
- break-even cost
- Result Level metadata
- final holdout report
