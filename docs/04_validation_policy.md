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

Track Bのcurrent machine-readable freeze artifactは`config/research_track_b.yaml`です。
このartifactがTrack Bの具体値のsource of truthであり、本文書はfreeze timing、split assignment、
warmup、version policyを定義します。

### Track B freeze artifact contract

Track Bのhistorical predictive/performance analysisを開始する前に、freezeされた具体値を
machine-readableまたはversion-controlled artifactとして保存します。artifactは少なくとも次を持ちます。

```text
development_period
validation_period
final_holdout_period
warmup_data_start
split_assignment
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
artifactは既に存在し、concrete valuesは`config/research_track_b.yaml`がsource of truthです。

### Track B freeze artifact version policy

- `freeze_version` fieldはinteger conventionです。current valueは`1`で、次versionは`2`のように整数で増分します。
- freeze artifactは分析開始後にin-place変更しません。`freeze_version: 1`の値を後から上書きすることは禁止します。
- freeze項目を変更する場合は、旧artifactを保持したまま、理由付きの新version（例: `freeze_version: 2`）を作成します。
- 新versionには少なくとも`freeze_date`、`freeze_version`、変更理由、変更対象、旧versionとの関係を記録します。
- 既に開始したanalysisの結果へ新versionを遡及適用せず、各analysisが使用したfreeze versionをmetadataへ記録します。
- version変更がanalysis sampleや解釈に影響する場合は、旧version結果を破棄・上書きせず、変更理由と再分析範囲を別途記録します。

### Track B split and warmup semantics

`split_assignment.basis`は`next_1m_return_outcome_month`です。M1A observationのsplit所属は
predictor formation monthではなく、next-month returnのoutcome monthで決めます。例えばformation
monthが`2023-12`、next-1m outcome monthが`2024-01`なら、そのobservationはFinal Holdoutに所属します。
split境界をまたぐfuture returnを直前splitへ混入させません。

`warmup_data_start`の`2015-01`はDevelopment開始ではありません。これはDevelopment開始時点から
past-12-month return等のcausal predictorを作成し、必要なstateを初期化するためのpre-sample historyです。
warmup observationsはDevelopment / Validation / Final Holdoutの評価sampleに含めず、predictor formation
とstate initializationだけに利用します。future informationは利用せず、split assignmentは常にoutcome
monthで決定します。実データの取得対象は`2015-01`から`2026-06`までです。

### Track B universe policy

`config/research_track_b.yaml`のprimary universeと`secondary_cross_robustness` universeは、current freeze version時点で
事前指定された役割です。performance結果を見てprimaryからsymbolを除外したり、secondaryから好調symbolだけを
追加したり、両universeを入れ替えたりしません。

ただしhistorical predictive/performance resultを見る前のstructural validationで、coverage不足、timestamp
corruption、duplicate / missing dataの重大問題、source consistency failure、Bid tick dataとして不成立、
その他客観的なdata-quality failureが判明した場合は、既存versionをin-place変更せず、理由を記録した新しい
freeze versionで変更します。

Final HoldoutはM7までpredictive/performance resultを閲覧しません。

### M1A implementation and real-data execution gates

M1A implementation readinessは、valid current Track B freeze artifactが存在し、frozenであることです。
synthetic fixture / unit test等を使ったM1A code implementationは、real-data structural validationの
完了を待たずに開始できます。

M1A real-data execution readinessは、current freeze versionに対応するTrack B structural validationが
`pass`または`pass_with_warning`で完了していることです。これを満たすまで、Track B real historical dataから
predictive regression、effect-size table、pooled result、Development / Validation resultを生成・閲覧しません。
Final Holdoutは従来どおりM7まで開きません。

各analysis output / metadataには、使用したinteger `freeze_version`を必ず記録します。

## Track B structural validation contract

Track B structural validationは、些細なtick欠損を理由にsymbolを落とすためではなく、M1A/M2に必要な
Daily / monthly research seriesを安全かつ決定論的に構築できない重大なdata problemを検出するために行います。
Exness MT5 tick dataについて、arbitraryなtick completeness thresholdは設けません。

### PASS criteria

各frozen symbolについて、少なくとも次を確認します。

#### A. Coverage

- 取得対象`2015-01`–`2026-06`について、開始月・終了月を含む必要なcalendar-month seriesを構築できる。
- `2015-01-01 00:00`等の厳密な開始timestamp一致は要求しない。
- 休日・週末等の通常のmarket closureは欠損扱いしない。

#### B. Timestamp validity

- timestampがparse可能で、raw timestamp timezoneをUTCとして一意に解釈できる。
- non-finite / malformed timestampは存在しない、または明確に除外・記録できる。
- chronological processingを決定論的に行える。
- raw fileが完全にsort済みであることは要求せず、canonical sortを許可する。ただしout-of-orderはdiagnosticへ記録する。

#### C. Bid validity

- OHLC生成に使うBidがnumeric、finite、positiveである。
- 少数の明らかなmalformed recordは機械的に除外してよいが、除外件数をdiagnosticへ記録する。
- 少数のmalformed recordだけを理由にsymbol failureとはしない。

#### D. Duplicate / repeated timestamps

- repeated timestampをautomatic failureとはしない。
- 同一timestampの複数tickは、source orderまたは明示したstable ordering ruleにより決定論的に処理できれば許可する。
- 完全に同一のduplicate rowの扱いと件数を記録し、duplicateを理由に都合よくprice seriesを書き換えない。

#### E. Daily aggregation determinism

以下のcontractで、同じinputから常に同じDaily OHLCを生成できる。

```text
raw timestamps: UTC
boundary timezone: America/New_York
boundary local time: 17:00
price: Bid
```

DST切替はIANA timezone databaseの`America/New_York`で判定し、expected UTC offsetをロジックのauthorityとしない。

#### F. Monthly availability

- 必要なcalendar monthについて`P[M] = last valid Daily Close of calendar month M`を構築できる。
- 必要calendar monthが丸ごと欠け、past_12m / next_1m observationの構築に重大な影響がある場合はfailure候補とする。
- 数tick、数時間、単一Daily bar程度の欠損だけを理由にsymbolを自動除外しない。

#### G. Large-gap diagnostics

- market openが期待される期間の不自然な長時間 / 複数営業日のgapはflagする。
- large gap detectedだけではautomatic failureとしない。
- Daily OHLCを信頼して構築できない、calendar-month seriesを構築できない、source corruptionを強く示す、または
  M1A sample definitionに重大な影響がある場合にfailureとする。

### 明示的に採用しないthreshold

primary structural validationでは、次のarbitrary thresholdを要求しません。

- tick completeness `>= 99.9%`
- missing tick rate `<= 0.1%`
- 1日あたり最低N ticks
- 他sourceとの価格差 `<= X bps`

必要な場合は、将来のdata-quality sensitivityとして別methodで定義します。

### Result classification

各symbolのvalidation statusは次の3状態を許可します。

- `pass`: 重大なstructural issueなし。
- `pass_with_warning`: minor out-of-order、少数malformed rows、short unexplained gap、harmless duplicate rows等はあるが、
  Daily/monthly research seriesに重大な影響がない。primary/secondary universeに残す。
- `fail`: M1A/M2用research seriesを信頼して構築できない重大問題。required coverage不足、timestamp corruption、
  Bid series不成立、Daily aggregation不能、大規模calendar-month欠落、明確なsource corruption等を含む。

### Symbol exclusion rule

`fail`となったsymbolのみfreeze universe変更の候補とします。`pass_with_warning`だけを理由に除外しません。
除外候補の判定はpredictive result、PnL、Sharpe、symbol-level performanceを見る前に行います。
変更する場合は既存freeze versionをin-place変更せず、integer `freeze_version: 2`等の新versionを作成し、
`previous_freeze_version`、`change_reason`、`changed_fields`、`affected_symbols`を記録します。
performanceが悪いことを理由としたsymbol除外は禁止します。

### Structural validation output contract

validation実装時は、少なくとも次をsymbolごとにreport可能にします。

```text
symbol
freeze_version
requested_start
requested_end
first_valid_tick
last_valid_tick
timestamp_parse_errors
nonfinite_or_invalid_bid_rows
out_of_order_detected
repeated_timestamp_count
exact_duplicate_row_count
suspicious_gap_count
daily_bar_count
missing_calendar_months
validation_status
warnings
failure_reasons
```

このsectionはdocumentation contractのみを定義し、今回validation codeは実装しません。

## M1 — Academic Hypothesis + Statistical Challenge

M1はworkstream別にstatusを持つ。

- M1A implementation: `Ready after valid current Track B freeze artifact`; M1A real-data execution: `Ready after structural validation pass or pass_with_warning`
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
