# Development Roadmap

このroadmapでは、software implementation milestoneを `M*`、research checkpointを `R*` とする。

R0/R1は新しいengineを大規模に作るMilestoneではなく、次の実装段階へ進む前に研究上の意味を確認するcheckpointである。

## M0 — Single-Symbol Unscaled Daily TSMOM Baseline

### 主目的

**Engine correctness**。

TSMOMのdirectional componentを、portfolio / volatility scaling / costから分離して実装する。

M0のprofitability自体を合否条件にしない。

### 成果

- Daily OHLC data contract
- causal return-sign signal
- explicit signal / execution timing
- Long / Short / Flat state engine
- reversal handling
- normalized gross return
- trade / position ledger
- basic gross metrics
- unit / golden tests

### 非対象

- multi-symbol
- portfolio aggregation
- volatility scaling
- transaction costs
- swap
- TP / SL
- parameter optimization
- walk-forward

### 完了条件

- hand-calculated signal fixtureと完全一致
- entry / exit / reversal fixtureと完全一致
- gross PnL fixtureと完全一致
- lookahead mutation test通過
- warm-up期間でpositionを取らない
- unchanged signalで不要なtradeを生成しない
- zero signalがFlatとして機能する
- invalid input dataを仕様通り処理
- M0処理経路にcost / volatility / portfolio logicが混入していない

---

## R0 — Academic Hypothesis Check

### 目的

strategy engineのprofitabilityとは別に、TSMOMの中心的predictive relationを直接確認する。

### 基本検証

```text
past approximately 12-month return
        ->
next 1-month return
```

### 成果

- sign-conditioned future returns
- continuous predictor results
- symbol別結果
- pooled / cross-market results
- uncertainty / sample size diagnostics

### Cost

commission / spread / swapは不要。
R0はnet trading PnLではなくpredictabilityの検証だからである。

### 判定

R0が弱くても研究終了とは限らないが、M0の収益性だけを根拠に「academic TSMOMが再現した」とは言わない。

---

## R1 — Academic-Style Comparator

### 目的

M0のdaily refresh / reversal仕様と、academic literatureへ近いholding conventionを比較する。

### 初期仕様

- monthly decision frequency
- approximately 12-month past price return
- 1-month holding
- gross
- unscaled
- spot/CFD price data

### 注意

spot/CFD price dataを使うため、MOPのfutures / forward excess-return完全再現ではない。

### 成果

- M0 Daily vs R1 Monthly comparator
- turnover差
- holding差
- return / DD等の差

---

## M1 — Multi-Symbol Common Rule

M0と同じruleを複数symbolへ独立適用する。

### 成果

- symbol別backtest
- symbol別metrics
- same parameter contract

M1ではまだportfolio aggregationを行わない。

### 完了条件

- symbol固有strategy parameterなしで実行可能
- single-symbol engineを変更せず再利用可能

---

## M2 — Portfolio Aggregation

M1のsymbol別returnをportfolioへ集約する。

### 成果

- portfolio equity
- portfolio return
- drawdown
- Sharpe
- exposure summary

M2ではまずequal-notional aggregationを標準とする。

---

## M3 — Volatility Normalization

directional signalを変えず、position sizingのみ変更する。

### 成果

- unscaled / equal-notional
- volatility-scaled / equal-risk

の比較。

Academic TSMOMとのvolatility methodology差分を記録する。

vol scalingによる改善をsignal predictability改善と混同しない。

---

## M4 — Cost and Financing Layer

### 成果

- spread
- commission
- slippage
- gross / net separation
- swap / financing capability
- cost scenarios
- break-even cost
- Result Level labeling

### historical commission / spreadが不足する場合

plausible low / base / high scenariosで耐コスト性を評価する。
正確なhistorical broker replicationとは呼ばない。

### historical swapが不足する場合

`Net ex-financing` までを主要結果とし、`Full broker net` は作らない。

---

## M5 — Robust Validation

### 成果

- parameter plateau
- chronological development / validation / holdout
- year slice
- symbol slice
- cost stress
- rolling metrics
- underwater analysis
- walk-forward
- M0 vs R1 academic-style comparatorの再確認
- always-long等のbenchmark（必要に応じて）

この時点までにTrack A Academic ValidationとTrack B Practical FX/CFD Researchを分けて報告できる状態にする。

---

## M6 — 4h Momentum

Dailyと同じ研究プロトコルを短期化する。

Dailyよりcost / execution assumptionsへの依存が強くなるため、M4のcost frameworkを先に完了させる。

---

## M7 — 1h Momentum

turnover / execution cost / slippage / whipsawを重点評価する。

historical spread / execution dataが不十分な場合、結論の強さをDailyよりさらに制限する。
