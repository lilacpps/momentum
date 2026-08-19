# Momentum Research Project — Revised Reference-Validation Plan

この文書群は、Time-Series Momentum（TSMOM）を

1. softwareとして正しく実装する
2. academic literatureの中心仮説と原論文仕様を検証する
3. 反証研究（Huang et al. 2020）の主要な批判にも耐えるか確認する
4. spot FX / CFD上でstrategyとして評価する
5. portfolio / volatility scaling / costs / financingを段階的に追加する

ための研究・開発計画です。

## 重要な位置づけ

M0の `240 observed daily return intervals / daily refresh / next-open execution / unscaled` は、
Moskowitz, Ooi, Pedersen (2012; MOP) の完全再現ではありません。

M0は **Single-Symbol Unscaled Daily TSMOM Research Baseline** であり、
第一目的は **engine correctness** です。

reference validationは1つのMilestoneで完了するものではありません。

```text
M0  engine correctness
M1  predictive evidence + MOP regression comparator + Huang statistical challenge
M2  monthly 12m/1m unscaled strategy comparator
M3  multi-symbol common-rule evidence
M4  portfolio aggregation + challenge benchmark plumbing
M5  MOP-compatible volatility-scaled strategy comparator
M6  cost / financing robustness
M7  robust validation + TSM-vs-TSH + final practical holdout
```

**MOPの代表TSMOM factorに近いstrategy-level comparatorが成立するのはM5完了後**です。
M2だけをもってpaper replicationとは呼びません。

---

# Two Tracks

## Track A — Academic / Reference Validation

問い:

> 自作研究系はMOPのmethodology / published factor / reference resultsとどこまで整合するか。

主な材料:

- `references/2.Time-series-momentum_2012_Journal-of-Financial-Economics.pdf`
- `references/3.Time Series Momentum Original Paper Data.xlsx`
- `references/7.Time-series momentum_ Is it there_.pdf`
- futures / forward / excess-return dataが別途得られる場合はそれを優先

### Track Aのsample policy

MOPの1985–2009等、**既に論文結果が公開されている期間はreplication sample**です。
それを「未見final holdout」とは呼びません。

Track Aでは、

- published-sample replication
- reference-series sanity check
- method reproduction
- post-publication dataが取得できる場合のtrue out-of-sample extension

を明確に分けます。

## Track B — Practical Spot FX / CFD

問い:

> 手元のspot/CFD dataと現実的execution assumptionで利用可能なedgeか。

主な材料:

- broker / spot Daily OHLC
- causal next-open execution
- gross result
- cost scenarios
- financing dataがあればbroker-net評価

Track Bでは、M0 implementation後にgolden fixture / synthetic data / unit testsでengine correctnessを確定し、
実historical performanceを一件も見る前に、`docs/04_validation_policy.md` §1の
Track B freeze gateに従って、次の値を具体的にfreezeします。

- development
- validation
- final holdout
- symbol universe
- data source
- price type
- timezone
- daily boundary

をfreezeします。freezeした具体値は、machine-readableまたはversion-controlledなfreeze artifactとして保存します。
artifactの必須項目・保存時期・version policyは`docs/04_validation_policy.md`がauthoritativeであり、
data source / price type / timezone / daily boundaryの意味とデータ契約は
`docs/03_data_and_costs.md`がauthoritativeです。freeze前の実データ利用はschema/timestamp等のstructural validationに限り、
performance / PnL / predictive resultは見ません。freeze後に初めてhistorical gross resultを生成します。
final holdoutはM7まで原則見ません。

Track B current freeze valuesは、version-controlled artifact
`config/research_track_b.yaml`をsource of truthとします。freeze/split/warmup/version policyは
`docs/04_validation_policy.md`、data contractは`docs/03_data_and_costs.md`を参照します。

Track AとTrack Bを「論文再現」という同じラベルで混ぜません。

---

# Reference Methodology Anchors

## MOP strategy comparator

reference comparatorでは最低限、以下を再現対象として固定します。

- monthly decision
- past 12-month return sign
- 1-month holding
- futures / forward excess-return dataを利用できる場合はそれを優先
- ex-ante volatility estimateはlagged daily returnsのEWMA系（数式・初期化・欠損・availabilityは`docs/07_academic_validation_spec.md` §3.2がauthoritative）
- `w_i=(1-delta)delta^i`
- `delta/(1-delta)=60`, `delta=60/61`
- annualization = 261
- information lag: `sigma[t-1]` をtime-t returnへ適用
- per-instrument ex-ante annualized target volatility = 40%
- position magnitude = `0.40 / sigma[t-1]`
- available instrumentsをequal-weight aggregation

40% targetは実運用推奨値ではなく、**MOP reference comparatorの再現用**です。
Practical Trackのtarget volatilityは別実験として扱います。

## Huang et al. challenge

肯定的なMOP resultだけで結論を出しません。
最低限、

- asset-by-asset predictability
- pooled regression
- bootstrap-based inference
- TSM vs Time-Series History (TSH)
- long / short leg attribution

をchallenge suiteとして扱います。

TSHのhistorical-mean definitionは `references/7.Time-series momentum_ Is it there_.pdf` の式・sample conventionに合わせ、
`docs/07_academic_validation_spec.md`で`tsh_spec_version = tsh-huang-v1`としてM3開始前に固定します。
paper/referenceとTrack B practical analogueは、causalityの対立ではなく
`method_role = tsh_huang_reference` / `tsh_track_b_practical`で区別します。
TSHのprimary TSM-vs-TSH comparisonは、各symbolのM2 TSM-valid/formable holding-month mask、
同一first-Open boundary、同一daily Open-to-Open intervalに限定します。
Huang bootstrapはM1C開始前にpaperからcontractをfreezeし、その後に実装します。

### M1 workstream status

- M1A implementation: `complete`; current freeze v3 real-data execution is complete after structural validation pass
- AQR Reference Sanity: `Ready independently of eligible MOP underlying data`
- M1B MOP Regression Comparator: `Ready only after eligible reference underlying data is identified`
- M1C-Huang-reference: `Ready after Huang methodology contract freeze and eligible reference underlying data`
- M1C-Huang-practical-analogue: `Ready after Huang methodology contract freeze and Track B data`

AQR factor-only workbookはM1B/M1C-Huang-referenceのunderlyingとはみなしません。reference underlyingが
unavailableでも、M1A、M1C-Huang-practical-analogue、AQR factor sanity checkは継続します。

---

# Documentation Authority

文書の重複によるspec driftを避けるため、責務を次のように固定します。

| Topic | Authoritative document |
|---|---|
| M0 engine / daily baseline | `docs/01_academic_baseline.md` |
| data / cost / financing units | `docs/03_data_and_costs.md` |
| validation / holdout policy | `docs/04_validation_policy.md` |
| M1 / M2 academic methodology | `docs/07_academic_validation_spec.md` |
| milestone scope / deliverables / tests | corresponding `docs/milestones/M*.md` |
| overview / questions / roadmap / conclusion language | `00`, `02`, `05`, `06` |

Milestone文書はscopeを狭めてよいですが、上記normative specを上書きしてはいけません。
矛盾を見つけた場合は、実装で推測せずdocumentation bugとして解消してから進みます。

---

# Milestone体系

```text
M0  Engine Correctness — Single-Symbol Daily Baseline
M1  Academic Hypothesis + Reference Statistical Validation
M2  Practical Monthly Comparator
M3  Multi-Symbol Common Rule
M4  Portfolio Aggregation
M5  Volatility Normalization + MOP Strategy Comparator
M6  Cost and Financing Layer
M7  Robust Historical Validation + Challenge Benchmarks
M8  4h Momentum
M9  1h Momentum
```

## 最初に読む文書

1. `README.md`
2. `docs/00_momentum_overview.md`
3. `docs/01_academic_baseline.md`
4. `docs/04_validation_policy.md`
5. `docs/05_roadmap.md`
6. `docs/07_academic_validation_spec.md`
7. `docs/03_data_and_costs.md`
8. `docs/06_evaluation_protocol.md`

## M0開始可否

M0の仕様は変更していません。
**M0は現時点で実装開始可能です。**

M1A開始前にはTrack Bの具体的freeze artifactが必要です。Huang methodology/bootstrap contractは
M1C開始前にfreezeします。Huang contract未freezeを理由にM1Aを停止しません。
TSH exact historical-mean contractはM3開始前にfreezeし、M3/M4/M7で再利用します。
