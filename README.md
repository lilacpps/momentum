# Momentum Research Project — Revised Plan

この文書群は、Time-Series Momentum（TSMOM）を

1. softwareとして正しく実装する
2. academic literatureに近い仮説を検証する
3. spot FX / CFD上でstrategyとして評価する
4. portfolio / volatility scaling / costs / financingを段階的に追加する

ための研究・開発計画です。

## 重要な位置づけ

M0の `240 observed daily bars / daily refresh / next-open execution / unscaled` は、
Moskowitz, Ooi, Pedersen (2012; MOP) の完全再現ではありません。

M0は **Single-Symbol Unscaled Daily TSMOM Research Baseline** であり、
第一目的は **engine correctness** です。

academic TSMOMとの整合性はM1/M2で別途確認します。

## Milestone体系

research checkpointを別の `R*` 系列にはせず、全工程を `M*` に統一します。

```text
M0  Engine Correctness — Single-Symbol Daily Baseline
M1  Academic Hypothesis Check
M2  Academic-Style Monthly Comparator
M3  Multi-Symbol Common Rule
M4  Portfolio Aggregation
M5  Volatility Normalization
M6  Cost and Financing Layer
M7  Robust Historical Validation
M8  4h Momentum
M9  1h Momentum
```

M1/M2は実装量が小さくても、研究上の重要なdecision gateなのでMilestoneとして扱います。

## Two Tracks

### Track A — Academic Validation

問い:

> 自作研究系はacademic TSMOMのsignal / evidence / reference resultsと整合するか。

主な材料:

- `references/` の原論文
- AQR Original Paper Data
- monthly / 12-month formation / 1-month holding comparator
- futures / forward / excess-return dataが得られる場合はそれを優先

### Track B — Practical Spot FX / CFD

問い:

> 手元のspot/CFD dataと現実的execution assumptionで利用可能なedgeか。

主な材料:

- broker / spot Daily OHLC
- causal next-open execution
- gross result
- cost scenarios
- financing dataがあればbroker-net評価

Track AとTrack Bを「論文再現」という同じラベルで混ぜません。

## Holdoutの重要ルール

M0のengine correctnessを確定した後、**M1でhistorical performanceを見る前に**

- development
- validation
- final holdout

の期間と対象symbol universeを固定します。

final holdoutは原則M7まで見ません。

## 最初に読む文書

1. `docs/00_momentum_overview.md`
2. `docs/01_academic_baseline.md`
3. `docs/04_validation_policy.md`
4. `docs/05_roadmap.md`
5. `docs/07_academic_validation_spec.md`
6. `docs/03_data_and_costs.md`
7. `docs/06_evaluation_protocol.md`

## この版で前回レビューから追加で固定した事項

- `lookback=240` は240個のreturn intervalを意味し、241個のClose observationが必要
- dataset末尾ではsynthetic liquidationを行わず、未決済tradeはopenのまま残す
- final holdoutをM1より前にロック
- M1のmonthly return定義を固定
- M1ではIID前提のnaive t-valueだけで判定しない
- M1をAcademic / Practicalの2系統に分離
- M2のmonth-end decision / next-month first open executionを固定
- M1はM3のmulti-symbol backtest engineを要求しない
- M2のためにM0を万能schedulerへ過剰一般化しない

## Milestone別実行契約

`docs/00〜07` は横断的な設計・研究ポリシーです。

各工程の実装・研究をCodexへ渡しやすくするため、
`docs/milestones/` に `M0〜M9` の実行契約を置きます。

各Milestone文書には、

- 目的
- 参照docs
- 固定仕様
- 実装対象
- 非対象
- 成果物
- 必須テスト
- 完了条件
- 人間が決める未決事項

を記載します。

M5/M8/M9など後段でまだ決めるべき内容があるMilestoneは、
無理に仕様を確定せず `Specification incomplete` と明記しています。

