# Validation Policy

## 原則

Momentumは単純だからこそ、複雑な最適化で「良くしすぎない」。

また、以下を混同しない。

1. software / engineが正しいか
2. predictive relationが存在するか
3. strategyとして収益性があるか
4. portfolioとして有用か
5. realistic cost後にも残るか
6. broker PnLを正確に再現できるか

各段階は別の証拠を必要とする。

# Validation Architecture

## Stage E0 — Engineering Validation (M0)

目的はコードの正しさであり、profitabilityの判定ではない。

使用してよいもの:

- synthetic fixture
- hand-calculated fixture
- small development sample

必須:

- lookahead mutation
- off-by-one tests
- execution timing
- state transitions
- PnL accounting
- deterministic output
- invalid data handling

**M0がnegative returnでもM0失敗とはしない。**
M0の完了条件はengine correctnessで判定する。

## Stage R0 — Academic Hypothesis Check

M0直後に、trading engineの結果とは別に、academic literatureの中心的な予測問題を直接確認する。

基本形:

```text
past approximately 12-month return
        ->
next 1-month return
```

確認候補:

- sign-conditioned future return
- continuous predictor regression
- symbol-by-symbol results
- pooled / cross-market results
- confidence intervals / statistical uncertainty

R0ではcommission / spread / swapは不要である。
ここで調べるのはexecution後のnet profitabilityではなく、return predictabilityだからである。

## Stage R1 — Academic-Style Strategy Comparator

M0 daily strategyと別に、academic literatureへ近いdecision cadenceを持つcomparatorを用意する。

初期仕様:

```text
monthly decision
approximately 12-month past price return
1-month holding
gross
unscaled
```

spot/CFD price dataを使う限り、MOPのfutures / forward excess-return完全再現とは呼ばない。

R1の目的は、M0の結果が

- TSMOM signalによるものか
- daily refresh / reversalというimplementation choiceによるものか

を分離することである。

## Stage R2 — Multi-Symbol / Portfolio

M1/M2で同一ruleを複数symbolへ適用し、単一市場依存を確認する。

single-symbolの結果のみでTSMOM全体を評価しない。

## Stage R3 — Risk Scaling

M3でvolatility normalizationを追加し、

- unscaled signal result
- scaled portfolio result

を分離する。

vol scalingでSharpeが改善した場合、それをsignal predictabilityの改善と表現しない。

## Stage R4 — Cost Robustness

M4で、historical broker costが完全でなくても

- plausible scenarios
- cost stress
- turnover
- break-even cost

を評価する。

historical cost再現とcost robustnessを区別する。

## Stage R5 — Robust Historical Validation

M5で

- chronological development / validation / holdout
- parameter plateau
- symbol slices
- year slices
- rolling results
- underwater
- walk-forward

を評価する。

# Academic Track と Practical Track

## Track A — Academic Validation

目的:

> 自作研究系がacademic TSMOMの考え方・reference resultsと整合するか

利用候補:

- `references/2.Time-series-momentum_2012_Journal-of-Financial-Economics.pdf`
- `references/3.Time Series Momentum Original Paper Data.xlsx`
- その他 `references/` 配下資料

可能な範囲でacademic-style signal / comparator / reference seriesとのsanity checkを行う。

## Track B — Practical Spot FX / CFD Research

目的:

> 手元のspot/CFD dataと現実的なexecution assumptionでedgeが利用可能か

ここでは

- broker daily bars
- next-open execution
- cost scenarios
- actual swapがあればfinancing

を使う。

Track AとTrack Bの結果を同じ「論文再現」というラベルで混ぜない。

# Holdout Policy

## Research development

複数lookbackや複数symbolのperformance比較を開始する前に、historical dataを少なくとも

```text
development
validation
final holdout
```

へchronologicalに分離する。

## Final holdout

final holdoutの期間または決定ruleは、本格的なparameter比較を始める前に固定する。

final holdoutを見た後に

- lookback
- filter
- execution rule
- symbol selection

を変更した場合、そのdatasetはfinal holdoutではなくなる。

# Causality Validation

ある時点 `T` より後のprice dataを意図的に変更しても、

```text
signal[t]
target_position[t]
```

for `t <= T`

が変化してはならない。

future data変更によって過去signalが変化した場合、lookaheadまたは非因果的なdata transformationが存在する。

# 禁止事項

- holdoutを見てparameter変更
- symbolごとのlookback最適化をbaseline採用
- 一点だけ良いparameterを採用
- filterを結果を見ながら追加し続ける
- M0の利益だけをTSMOM存在証拠とみなす
- volatility scaling改善をsignal alphaと混同する
- incomplete cost modelをFull broker netと呼ぶ

# 推奨成果物

- R0 prediction tables / regressions
- M0 vs R1 comparator
- parameter x symbol matrix
- parameter x year matrix
- portfolio equity
- rolling Sharpe / return
- underwater curve
- turnover / holding period
- cost sensitivity
- break-even cost
- Result Level metadata
