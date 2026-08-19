# Evaluation Protocol — What Can We Conclude at Each Milestone?

## 1. 目的

backtestがプラスだっただけで、

> TSMOMが再現した

とは結論しません。

---

## E0 — Engine Correctness

対象: M0

言ってよい:

> 定義したM0 engineがcausalかつ仕様通り動く。

まだ言えない:

> TSMOMにedgeがある。

---

## E1 — Predictive / Statistical Evidence

対象: M1

確認:

- past 12m -> next 1m
- MOP pooled regression comparator
- asset-by-asset evidence
- bootstrap challenge

言ってよい:

> Track A / Track Bそれぞれでdirectional predictabilityの証拠が見える / 見えない。

> MOPのregression methodologyでどの程度reference resultを再現できるか。

> Huang型bootstrap challengeを通すとstatistical evidenceがどの程度残るか。

まだ言えない:

> brokerでnet profitable。

---

## E2 — Monthly Strategy Construction Evidence

対象: M2 / M3

確認:

- daily simplified
- monthly academic-style unscaled
- multiple symbols
- turnover / holding

言ってよい:

> signalを特定のposition ruleへ変換したgross strategyの性質。

まだ言えない:

> MOP representative factorを完全再現した。

> realistic costs後にも残る。

---

## E3 — Portfolio Evidence

対象: M4

確認:

- diversification
- equal-notional
- concentration

言ってよい:

> unscaled portfolio constructionのgross特性。

まだ言えない:

> MOP volatility-scaled factorと同等。

---

## E4 — MOP Strategy Comparator / Risk Evidence

対象: M5

確認:

- unscaled vs volatility-scaled
- MOP-compatible ex-ante volatility estimator
- 40% per-instrument reference target
- available-instrument equal aggregation
- published factor sanity comparison

言ってよい:

> MOP代表TSMOM factorに近いmethodology comparatorを構築し、reference resultとの整合性を評価した。

ただしunderlying dataがMOPと異なる場合は「exact replication」とは呼ばない。

vol scaling改善をsignal alphaと混同しない。

---

## E5 — Cost Robustness

対象: M6

historical cost seriesがなくてもplausible scenarios / turnover / break-even costで評価可能。

言ってよい:

> 想定cost rangeに対してedgeがrobust / fragile。

まだ言えない:

> 特定brokerで過去にこのNet PnLだった。

---

## E6 — Robust / Challenge / Holdout Evidence

対象: M7

確認:

- parameter / year / symbol robustness
- TSM vs TSH
- long / short attribution
- Track B final holdout

言ってよい:

> TSMのprofitabilityがpredictabilityなしのchallenge benchmarkをどの程度上回るか。

> 事前固定したPractical strategyが未見期間でもどの程度維持されたか。

Track Aのpublished replication sampleはfinal holdoutとは別に報告する。

---

## E7 — Broker-Net Evidence

十分なhistorical execution / financing dataがある場合のみ。

必要:

- spread
- fee schedule
- realistic slippage
- swap / financing
- contract specification

言ってよい:

> 特定broker条件を近似したhistorical net simulation。

---

# Swapデータがない場合

```text
Level 1 Gross price-only
Level 2 Net ex-financing
Level 3 Full broker net
```

Level 3を無理に作りません。
current swapの過去一律適用は原則避けます。

---

# Decision Gates

## Gate M0
- golden tests
- causality
- accounting
- engine correctness確定後の`docs/04_validation_policy.md`に従ったTrack B concrete freeze artifact
- freeze前はstructural validationのみ、freeze後に初めてhistorical gross performance

## Gate M1
- M1A implementation: `docs/04_validation_policy.md`のvalid current Track B freeze artifact後
- M1A real-data execution: current freeze v3ではPrimary structural-validation overall gate通過後に完了
- AQR Reference Sanity: eligible MOP underlying dataとは独立
- M1B MOP comparator: eligible reference underlying data identified
- M1C-Huang-reference: Huang contract freeze + eligible reference underlying data
- M1C-Huang-practical-analogue: Huang contract freeze + Track B data

M1Aは実装・current freeze v3のreal-data executionともにcompleteです。したがってM2はunblock済みです。
M1B/M1CのpendingはM2をblockしません。M1/M2のnormative
methodology、M1Aのcalendar-month/zero/missing/inference、M1B equation、Huang procedureは
`docs/07_academic_validation_spec.md`を参照します。
- Academic / Practical tracks separated
- uncertainty

## Gate M2
- monthly 12-calendar-month formation / next-month first-Open execution verified
- warmupからcausal state continuity verified
- M0/M2 common evaluation window verified
- Final Holdout sealed
- frozen primary 8 symbols independently executed
- signal agreement / turnover / trade count / holding / gross return / max DD / reversal frequency reported
- differences attributable to documented daily-vs-monthly rules

## Gate M3/M4
- symbol横断性
- diversification
- M3開始前に`tsh_spec_version = tsh-huang-v1`のTSH exact historical-mean contractをfreeze済み
- primary TSM-vs-TSH comparisonはM2 TSM-valid/formable holding-month maskで整列済み
- signal-formationのClose-to-Close monthly returnとexecuted Open-to-Open PnLを分離済み

## Gate M5
- unscaledで何が残るか
- scalingで何が改善するか
- MOP-compatible reference resultとの整合

## Gate M6
- break-even cost
- realistic cost scenarios
- financing limitation

## Gate M7
- plateau
- validation
- TSM vs TSH
- final practical holdout
- year / symbol robustness

ここまで通ってからM8/M9へ進む。
