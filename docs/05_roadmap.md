# Development Roadmap

全工程を `M0...M9` に統一します。
research checkpointもproject progression上のMilestoneとして扱います。

---

## M0 — Single-Symbol Unscaled Daily TSMOM / Engine Correctness

### 目的
causal daily engineを正しく実装する。

### 成果
- Daily OHLC contract
- 240-return-interval signal
- next-open execution
- Long / Short / Flat
- reversal
- open-to-next-open gross return
- ledger
- golden/unit tests

### 非対象
profitability gating / multi-symbol / portfolio / vol scaling / costs / optimization。

### Gate
M0完了直後、Track BのM1結果を見る前にhistorical splitとsymbol universeをfreezeする。
Track Aのpublished replication sampleは別管理。

---

## M1 — Academic Hypothesis + Reference Statistical Validation

### 目的
strategy engineとは別にpredictabilityを直接確認し、MOPのregression methodologyとHuang et al.の反証も検証する。

### Track A

- MOP published/reference sample
- excess-return dataが使える場合は優先
- AQR factor data sanity check
- MOP regression comparator
- Huang challenge

### Track B

- spot/CFD monthly price-return analogue
- past 12m -> next 1m

### MOP comparator

- monthly standardized returns
- pooled regression
- lags `h=1...60`
- calendar-month clustering

### Huang challenge

- asset-by-asset
- pooled
- fixed-effect sensitivity
- wild bootstrap
- pairs bootstrap

### 成果

- sign-conditioned future returns
- continuous predictor
- effect size / CI
- symbol別 / pooled
- MOP regression comparison
- bootstrap inference report
- sample diagnostics

M1はM3 multi-symbol backtest engineを要求しません。

---

## M2 — Academic-Style Monthly Comparator

### 初期仕様

- month-end signal decision
- 12 completed calendar months formation
- next calendar month first available Daily Openでexecution
- 次月first available Openまでhold
- gross
- unscaled
- spot/CFD price data

### 成果

- M0 Daily vs M2 Monthly
- turnover
- holding period
- return / DD
- signal agreement

M2はMOP representative factorの完全再現ではありません。

---

## M3 — Multi-Symbol Common Rule

M0と同じdaily ruleを複数symbolへ独立適用。

- symbol別metrics
- common parameter
- symbol-specific tuningなし
- TSH comparatorに必要なsymbol-level monthly historyを供給可能にする

---

## M4 — Portfolio Aggregation

初期baselineはequal-notional。

原則:

- experiment universeを事前固定
- practical主要比較はcommon valid start
- ex-post symbol selectionなし
- MOP available-universe aggregationとは別mode

成果:

- portfolio equity
- return / DD / Sharpe
- exposure / contribution
- TSM vs TSH portfolio comparator plumbing

---

## M5 — Volatility Normalization + MOP Strategy Comparator

### Comparison modes

1. unscaled / equal-notional
2. practical equal-risk / volatility-scaled
3. MOP-compatible reference-scaled

### MOP-compatible fixed reference contract

- EWMA lagged daily variance
- annualization = 261
- center-of-mass = 60 days
- `sigma[t-1]` information lag
- per-instrument target annualized volatility = 40%
- `position magnitude = 0.40 / sigma[t-1]`
- available instrumentsをequal weight
- 12-month sign / 1-month holding comparatorと接続

Practical cap / floor / target riskはMOP reference modeとは別experiment。

### 成果

- unscaled vs scaled
- practical vs MOP-compatible
- contribution diagnostics
- AQR published factorとのseries-level sanity comparison（可能な範囲）

---

## M6 — Cost and Financing Layer

- spread
- commission
- slippage
- turnover
- break-even cost
- scenario analysis
- gross / net separation
- financing capability
- Result Level

historical swap不足時はFull broker netを作らない。

---

## M7 — Robust Historical Validation + Challenge Benchmarks

成果:

- plateau
- development / validation
- year / symbol slice
- rolling metrics
- underwater
- walk-forward
- cost stress
- benchmark
- TSM vs TSH
- long / short leg attribution
- weighting-scheme sensitivity
- Track B final holdout one-shot evaluation

Track A published replication sampleとTrack B final holdoutを分離して報告する。

---

## M8 — 4h Momentum

Dailyと同じ研究protocolを短期化。
M6 cost framework完了後に開始。

---

## M9 — 1h Momentum

重点:

- turnover
- spread
- slippage
- whipsaw
- execution sensitivity

historical execution data不足時はDailyより結論を弱くする。
