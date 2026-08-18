# M2 — Practical Monthly Comparator

## Status
M1A Practical Predictability is complete for current Track B freeze v3. M2 contract and implementation are
complete; full M2 result execution and comparison report are pending. M1B MOP Regression Comparator and M1C Huang
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

`formation_month = M`、`holding_month = M+1` とする。M2のsplit所属は
`holding_month`で決める。Developmentはholding month `2017-01`〜`2021-12`、
Validationは`2022-01`〜`2023-12`までであり、`2023-12`のreturnには境界価格として
`2024-01`最初のOpenを使ってよい。ただし`holding_month = 2024-01`のposition / returnは生成しない。

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

### Universe and sample comparison

M2はfreeze済みprimary universeの8 symbolをそれぞれ独立に実行し、各symbolについて
M0 DailyとM2 Monthlyを比較する。performanceを見てsymbolを1つ選ばず、M2でportfolio aggregation、
pooled strategy result、symbol selectionは行わない。M3でmulti-symbol researchとcross-symbol
diagnosticsを扱う。

M0とM2のgross return、drawdown、turnover、holding等は、同じreturn intervalだけで再計算して比較する。
Development+Validationなら、両者ともholding month `2017-01`〜`2023-12`に限定する。
warmupからのcausal stateは維持するが、window外で開始したcarry-in episodeはtrade count / average holdingへ
含めず、carry-in / carry-outをdiagnosticとして別記録する。return windowは終了境界を含まず、event windowは
終了境界Openを含む。

### Missing month handling

- pre-sampleで12か月historyが不足する場合はsignal undefined / Flatとする。
- requested analysis range内のcalendar monthが丸ごと欠損した場合はerrorとする。
- forward-fill、backward-fill、zero-fill、nearest-month substitutionは使用しない。

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
