# Validation Policy

## 原則

以下を混同しません。

1. engineが正しい
2. predictive relationがある
3. MOPのmethodology / published resultを再現できる
4. gross strategyとして性質が良い
5. portfolioとして有用
6. cost後にも残る
7. broker historical netを近似再現できる

---

# 1. Validation Sequence

## M0 — Engineering Validation

profitabilityではなくcorrectnessを判定。

必須:

- golden fixture
- off-by-one
- lookahead mutation
- execution timing
- state transition
- return accounting
- terminal policy
- deterministic output
- invalid data handling

M0がnegativeでもcorrectなら完了。

## ★ M0 correctness後、実historical performance前: Track B Split Lock

順序は固定します。

```text
M0 implementation
-> golden fixture / synthetic data / unit tests
-> engine correctness確定
-> Track B concrete freeze artifactを作成し、development / validation / final holdout /
   symbol universe / data source / price type / timezone / daily boundaryをfreeze
-> 実historical dataで初めてgross performanceを生成
-> M1
```

**split freeze前にPractical Trackのstrategy performance / predictive resultを見てはいけません。**
schema、timestamp、ordering、missingness等のstructural validationは可能ですが、performance / PnL /
predictive metricは不可とします。

```text
development period
validation period
final holdout period
symbol universe
data source
timezone
daily boundary
```

を固定します。

Track Aのpublished replication sampleは既知のreference sampleなので、このfinal holdoutには含めません。

Track B v1のmachine-readable freeze artifactは`config/research_track_b.yaml`です。
このartifactがTrack Bの具体値のsource of truthであり、本文書はfreeze timing、split assignment、
warmup、version policyを定義します。

### Track B freeze artifact contract

Track Bのhistorical predictive/performance analysisを開始する前に、freezeされた具体値を
machine-readableまたはversion-controlled artifactとして保存します。artifactは少なくとも次を持ちます。

```text
development_period
validation_period
final_holdout_period
symbol_universe
data_source
price_type
timezone
daily_bar_boundary
freeze_date
freeze_version
notes
```

このsectionは、Track Bのfreeze時期、required gate、artifact保存、version policyについてauthoritativeです。
`data_source` / `price_type` / `timezone` / `daily_bar_boundary`の意味とデータ検証契約は
`docs/03_data_and_costs.md`、M1のmethodologyは`docs/07_academic_validation_spec.md`を参照します。
今回、未決の具体値を推測せず、artifactの実体や値は追加しません。将来は
`config/research_track_b.yaml`等のversion-controlled artifactを利用できます。

### Track B freeze artifact version policy

- freeze artifactは分析開始後にin-place変更しません。`freeze_version = v1`の値を後から上書きすることは禁止します。
- freeze項目を変更する場合は、旧artifactを保持したまま、理由付きの新version（例: `v2`）を作成します。
- 新versionには少なくとも`freeze_date`、`freeze_version`、変更理由、変更対象、旧versionとの関係を記録します。
- 既に開始したanalysisの結果へ新versionを遡及適用せず、各analysisが使用したfreeze versionをmetadataへ記録します。
- version変更がanalysis sampleや解釈に影響する場合は、旧version結果を破棄・上書きせず、変更理由と再分析範囲を別途記録します。

### Track B v1 split and warmup semantics

`split_assignment.basis`は`next_1m_return_outcome_month`です。M1A observationのsplit所属は
predictor formation monthではなく、next-month returnのoutcome monthで決めます。例えばformation
monthが`2023-12`、next-1m outcome monthが`2024-01`なら、そのobservationはFinal Holdoutに所属します。
split境界をまたぐfuture returnを直前splitへ混入させません。

`warmup_data_start`の`2015-01`はDevelopment開始ではありません。これはDevelopment開始時点から
past-12-month return等のcausal predictorを作成し、必要なstateを初期化するためのpre-sample historyです。
warmup observationsはDevelopment / Validation / Final Holdoutの評価sampleに含めず、predictor formation
とstate initializationだけに利用します。future informationは利用せず、split assignmentは常にoutcome
monthで決定します。実データの取得対象は`2015-01`から`2026-06`までです。

### Track B v1 universe policy

`config/research_track_b.yaml`のprimary universeと`secondary_cross_robustness` universeは、freeze v1時点で
事前指定された役割です。performance結果を見てprimaryからsymbolを除外したり、secondaryから好調symbolだけを
追加したり、両universeを入れ替えたりしません。

ただしhistorical predictive/performance resultを見る前のstructural validationで、coverage不足、timestamp
corruption、duplicate / missing dataの重大問題、source consistency failure、Bid tick dataとして不成立、
その他客観的なdata-quality failureが判明した場合は、既存versionをin-place変更せず、理由を記録した新しい
freeze versionで変更します。

Final HoldoutはM7までpredictive/performance resultを閲覧しません。

## M1 — Academic Hypothesis + Statistical Challenge

M1はworkstream別にstatusを持つ。

- M1A Practical Predictability: `Ready after Track B concrete freeze artifact`
- AQR Reference Sanity: `Ready independently of eligible MOP underlying data`
- M1B MOP Regression Comparator: `Ready only after eligible reference underlying data is identified`
- M1C-Huang-reference: `Ready after Huang methodology contract freeze and eligible reference underlying data`
- M1C-Huang-practical-analogue: `Ready after Huang methodology contract freeze and Track B data`

M1Bのunderlyingが無い場合もM1AとAQR factor sanity checkは継続し、M1Bだけを data unavailable /
pending とする。M1C-Huang-referenceもeligible reference underlyingがなければpendingとし、
M1C-Huang-practical-analogueはTrack B dataで独立して進める。ただしpractical analogueをHuang replicationとは呼ばない。

### Practical primary

```text
past 12m return -> next 1m return
```

### Reference comparator

MOP methodologyに合わせ、volatility-standardized monthly returnのpooled regressionをlag `h=1...60` で再現する。

### Huang challenge

最低限、

- asset-by-asset regression
- pooled result
- fixed-effect sensitivity
- parametric wild bootstrap
- nonparametric pairs bootstrap

を実施する。

naive IID / conventional pooled t-valueだけをprimary evidenceにしません。

## M2 — Practical Monthly Comparator

M1Aの完了後に開始可能。M1B/M1Cが未完でもM2をblockせず、Practical Trackを停止しない。

monthly decision / 12 calendar-month formation / 1-month holdingを実装し、M0 daily ruleとの差を比較します。

M2はunscaledなので、MOP representative factorのcomplete strategy comparatorではありません。

## M3 — Multi-Symbol

common ruleを複数symbolへ適用。
単一市場依存を確認。

M3開始前にTSH exact historical-mean contractを`docs/07_academic_validation_spec.md`でfreezeし、
M3/M4/M7で同一definitionを再利用します。

## M4 — Portfolio

diversificationとequal-notional aggregationを評価。
TSM / TSHのportfolio-level comparisonを可能にします。

## M5 — Risk Scaling + MOP Strategy Comparator

unscaledとvolatility-scaledを分離。
さらにMOP-compatible reference modeとして、

- EWMA ex-ante vol
- annualization 261
- center-of-mass 60 days
- one-period information lag
- 40% asset target vol
- available-instrument equal aggregation

を再現します。

ここで初めて「MOP代表TSMOM factorに近いstrategy comparator」と表現できます。

## M6 — Cost Robustness

scenario / turnover / break-even cost。
historical cost replicationとcost robustnessを区別。

## M7 — Robust Historical Validation

- validation
- parameter plateau
- year / symbol slices
- rolling results
- walk-forward
- cost stress
- TSM vs TSH challenge

を行い、Track Bについて**最後にfinal holdoutを一度だけ評価**します。

---

# 2. Holdout Usage Policy

## Track A — Published replication sample

MOP等の既知の結果を再現する期間は、

- replication sample
- method-validation sample

であり、final holdoutとは呼びません。

post-publication / genuinely unseen academic dataが入手できた場合のみ、別のAcademic OOSとして扱います。

## Track B Development

M1〜M6の設計・debug・explorationに使用可能。

## Track B Validation

事前に固定したmajor designの確認に使用。
validation結果を見て頻繁にruleを変更し続けない。

## Track B Final Holdout

M7まで原則見ない。

final holdoutを開いた後は、lookback / symbol universe / filter / execution / cost assumptionを都合よく変更して同じholdoutを再評価しません。

---

# 3. Reference Result Integrity

AQR等のreference seriesを使う場合、比較前に以下を固定します。

- expected period
- expected frequency
- observation count
- unit conversion
- missing-value treatment
- comparison metric

同じseriesを直接読み込むsanity checkではdate/count/unitのexact consistencyを求めます。
自作reproductionとの比較は、data definitionが同一でない限り「一致/不一致」を単一thresholdだけで断定せず、correlation / mean / vol / Sharpe / cumulative path差を報告します。

---

# 4. Causality Mutation

時点 `T` より後のOHLCを変更しても、

```text
signal[t]
target_position[t]
executed_position[t]
```

for `t <= T` が変化してはなりません。

---

# 5. 禁止事項

- Track BでM1前にfinal holdoutを覗く
- holdoutを見てparameter変更
- published replication sampleを未見holdoutと呼ぶ
- symbolごとのlookback optimumをbaseline採用
- isolated optimumを採用
- filterを結果を見ながら追加し続ける
- M0利益だけをTSMOM evidenceとする
- spot analogueをMOP完全再現と呼ぶ
- M2 unscaled comparatorだけをMOP factor reproductionと呼ぶ
- vol scaling改善をsignal alphaと呼ぶ
- pooled t-valueだけでHuang challengeを無視する
- incomplete cost modelをFull broker netと呼ぶ

---

# 6. 推奨成果物

- M0 golden fixture report
- M1 prediction tables / MOP regression comparator
- M1 bootstrap challenge report
- M2 M0-vs-monthly comparator
- parameter x symbol / year
- MOP-compatible M5 factor comparator
- AQR reference sanity report
- TSM vs TSH report
- long / short leg attribution
- portfolio equity
- rolling return / Sharpe
- underwater
- turnover / holding period
- cost sensitivity / break-even cost
- Result Level metadata
- Track B final holdout report
