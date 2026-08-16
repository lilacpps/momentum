# M2 — Practical Monthly Comparator

## Status
Ready after M1A Practical Predictability. M1B MOP Regression Comparator and M1C Huang
Reference Challenge may remain pending without blocking this Practical Track milestone.

## 目的
M0のdaily refresh / reversal仕様と、academic literatureに近いmonthly formation / holding仕様との差を分離する。

## 参照docs
- `docs/01_academic_baseline.md`
- `docs/02_research_questions.md`
- `docs/04_validation_policy.md`
- `docs/05_roadmap.md`
- `docs/06_evaluation_protocol.md`
- `docs/07_academic_validation_spec.md`

## 固定仕様

### Formation
```text
signal[M] = sign(month_end_close[M] / month_end_close[M-12] - 1)
```

### Execution
Month Mのsignalを `Month M+1 の最初のavailable Daily Open` で実行。

### Holding
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

## 重要な位置づけ
M2はmonthly 12m/1m constructionのcomparatorですが、volatility scaling / futures excess return / multi-market factor aggregationがないため、MOP representative factorのcomplete replicationとは呼びません。

## Architecture guidance
M2のためにM0を万能schedulerへ一般化しない。

```text
signal / target generation
        ↓
execution / accounting
```

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
- monthly timing deterministic
- daily vs monthly difference attributable to documented rules
- no accidental use of 240 daily bars in M2 formation
- M2 remains unscaled/gross
