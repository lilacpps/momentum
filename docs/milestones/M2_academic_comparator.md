# M2 — Academic-Style Monthly Comparator

## Status
Specification-ready after M1.

## 目的
M0のdaily refresh / reversal仕様と、
academic literatureに近いmonthly formation / holding仕様との差を分離する。

## 参照docs
- `docs/01_academic_baseline.md`
- `docs/02_research_questions.md`
- `docs/04_validation_policy.md`
- `docs/05_roadmap.md`
- `docs/06_evaluation_protocol.md`
- `docs/07_academic_validation_spec.md`

## 固定仕様

### Formation
calendar month `M` の最後のvalid Daily Close確定後にsignalを生成。

```text
signal[M] = sign(month_end_close[M] / month_end_close[M-12] - 1)
```

12 completed calendar monthsを使う。

### Execution
Month Mのsignalを、
`Month M+1 の最初のavailable Daily Open`
で実行する。

### Holding
次のmonthly rebalanceまで保持。

```text
entry = first Open of M+1
exit  = first Open of M+2
```

### Initial version
- gross
- unscaled
- spot/CFD price data
- Long / Short / Flat
- no costs

## Architecture guidance
M2のためにM0を万能schedulerへ一般化しない。

推奨境界:
```text
signal / target generation
        ↓
execution / accounting
```

M0とM2で前段を差し替え、
再利用可能なaccounting部分だけ共有する。

## 実装対象
- month-end formation
- monthly target series
- next-month-first-open execution
- monthly holding/rebalance
- M0 comparator report

## 非対象
- volatility scaling
- portfolio optimization
- cost layer
- symbol-specific tuning

## 成果物
- M0 Daily vs M2 Monthly
- signal-direction agreement
- turnover comparison
- trade count
- average holding
- gross return
- DD
- reversal frequency

## 必須テスト
- 12 calendar-month formation boundary
- month with weekends/holidays
- first available open of next month
- no same-close execution
- zero signal
- missing month handling
- terminal month handling
- no lookahead

## 完了条件
- monthly timing is deterministic
- daily vs monthly difference is attributable to documented rules
- no accidental use of 240 daily bars in M2 formation
- M2 remains unscaled/gross

## 人間が決める未決事項
なし。M1でfreezeしたuniverse/splitsを使用。
