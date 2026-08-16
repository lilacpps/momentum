# Development Roadmap

全工程を `M0...M9` に統一します。

研究checkpointもproject progression上のMilestoneとして扱います。

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

- profitabilityを合否条件にすること
- multi-symbol
- portfolio
- vol scaling
- costs
- optimization

### 完了条件

- 241 Close requirementを含むoff-by-one test
- hand-calculated signal一致
- execution一致
- PnL一致
- lookahead mutation通過
- warm-up正しい
- unchanged signalで余計なtradeなし
- zero signal Flat
- terminal open positionをsynthetic liquidationしない
- invalid input処理
- deterministic

### Gate

M0完了直後、M1開始前にhistorical splitとsymbol universeをfreezeする。

---

## M1 — Academic Hypothesis Check

### 目的

strategy engineとは別に、

```text
past 12-month return -> next 1-month return
```

のpredictabilityを直接確認。

### Track A

academic / excess-return / reference data。

### Track B

spot/CFD price-return analogue。

### 成果

- sign-conditioned future returns
- continuous predictor
- effect size / CI
- symbol別
- pooled
- robust uncertainty
- sample diagnostics

M1はM3のmulti-symbol backtest engineを要求しない。
別の軽量research moduleで複数seriesを読んでよい。

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

M2のためにM0を万能schedulerへ過剰一般化しない。
signal/target generationとexecution/accountingの境界を再利用する。

---

## M3 — Multi-Symbol Common Rule

M0と同じdaily ruleを複数symbolへ独立適用。

- symbol別metrics
- common parameter
- symbol-specific tuningなし

可能ならM2 comparatorも同じuniverseで出す。

---

## M4 — Portfolio Aggregation

初期baselineはequal-notional。

原則:

- experiment universeを事前固定
- common valid start以降で比較
- ex-post symbol selectionなし

成果:

- portfolio equity
- return
- DD
- Sharpe
- exposure
- contribution

---

## M5 — Volatility Normalization

directional signalを変えずsizingのみ変更。

比較:

- equal-notional
- equal-risk / volatility-scaled

vol estimator / target riskはM5開始前に仕様化する。

---

## M6 — Cost and Financing Layer

成果:

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

## M7 — Robust Historical Validation

成果:

- plateau
- development / validation
- year / symbol slice
- rolling metrics
- underwater
- walk-forward
- cost stress
- benchmark
- final holdout one-shot evaluation

ここまででTrack A / Track Bを分けて報告可能にする。

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
