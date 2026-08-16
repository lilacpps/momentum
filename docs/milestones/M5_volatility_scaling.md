# M5 — Volatility Normalization + MOP Strategy Comparator

## Status
MOP-compatible reference mode is specified.
Practical volatility target / caps / floors must be finalized before practical-mode implementation.

## 目的
directional signalを変えずposition sizingのみ変えることでrisk scalingの効果を分離する。
同時にMOP representative TSMOM factorに近いstrategy comparatorを構築する。

## 参照docs
- `docs/00_momentum_overview.md`
- `docs/01_academic_baseline.md`
- `docs/02_research_questions.md`
- `docs/04_validation_policy.md`
- `docs/05_roadmap.md`
- `docs/06_evaluation_protocol.md`
- `docs/07_academic_validation_spec.md`

## Comparison modes

1. unscaled / equal-notional
2. practical volatility-scaled / equal-risk
3. MOP-compatible reference-scaled

---

# MOP-Compatible Reference Mode — Fixed Contract

## Direction / holding
- monthly
- past 12-month return sign
- 1-month holding
- Academic Trackではfutures / forward excess returnを使える場合は優先

## Ex-ante volatility
- lagged daily returnsのEWMA variance
- annualization scalar = 261
- exponential-weight center-of-mass = 60 days
- future data禁止
- time-t return / sizingには `sigma[t-1]` を使用

## Position magnitude

```text
abs(position[s,t]) = 0.40 / sigma[s,t-1]
```

signはTSM signalから与える。

40%はreference comparator用であり、practical targetではありません。

## Portfolio aggregation
各月のavailable instrumentsのstrategy returnをequal weightで集約する。

```text
portfolio_return[t] = mean(available instrument strategy returns at t)
```

exact missing / availability definitionは実装前に固定し、common-valid-start practical modeと分離する。

## Reference restrictions
MOP comparatorにcap / floor / leverage limitを追加するとmethodologyが変わるため、
それらを付けたseriesは別名で出す。

---

# Practical Mode — 実装前に決める事項

- volatility estimator（referenceと同じでも別でもよい）
- estimator lookback
- return frequency
- annualization convention
- target volatility / target risk
- position cap / leverage cap
- volatility floor
- missing volatility handling
- signal/vol information lag
- rebalance cadence
- portfolio-level targetかasset-level targetか

---

# AQR / Reference Comparison

AQR factor seriesが利用可能なら、

- period
- monthly dates
- mean / vol / Sharpe
- cumulative path
- correlation

をM5 reference reportへ出す。

underlying instrument data / roll / excess-return definitionが同一でない場合、exact numeric equalityは要求しない。
差分原因をmetadataへ記録する。

---

# 実装対象
- ex-ante volatility estimate
- scaled target exposure
- available-universe MOP aggregation
- contribution diagnostics
- unscaled-vs-scaled comparison
- practical-vs-reference comparison
- AQR sanity comparison

## 非対象
- signal変更
- momentum strength filter
- optimizer
- costs（M6）

## 必須テスト
- vol lag causality
- EWMA center-of-mass contract
- annualization 261 in reference mode
- zero/near-zero vol behavior
- reference mode contains no undocumented cap/floor
- `0.40 / sigma[t-1]` sizing
- available-instrument equal aggregation
- no future data
- scaled contribution accounting
- unscaled signal path unchanged

## 完了条件
- MOP reference estimator / target / lag / aggregation fixed and tested
- practical estimator/target/cap documented before practical result is viewed
- unscaled signal path unchanged
- scaling改善をsignal alphaと表現しない
- exact replication vs methodology comparator labeling is honest
