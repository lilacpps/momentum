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
price type
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

- `freeze_version` fieldはinteger conventionです。current valueは`3`で、旧`v1`/`v2` artifactは
  `config/archive/research_track_b_v1.yaml`/`config/archive/research_track_b_v2.yaml`に保持します。
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

M2では同じcalendar monthをposition/PnLの用語で`holding_month`と呼び、split assignmentも
`holding_month`で行います。すなわちM2の`formation_month = M`、`holding_month = M+1`であり、
M1Aのoutcome-month assignmentと境界は同じです。current v3 artifactの機械可読なbasis名はM1Aとの
互換性のため維持し、M2のnormative名称だけを`holding_month`として固定します。

`warmup_data_start`の`2015-09`はDevelopment開始ではありません。これはDevelopment開始時点から
past-12-month return等のcausal predictorを作成し、必要なstateを初期化するためのpre-sample historyです。
warmup observationsはDevelopment / Validation / Final Holdoutの評価sampleに含めず、predictor formation
とstate initializationだけに利用します。最初のDevelopment outcome `2017-01`はformation month
`2016-12`のpast-12m price `2015-12`を必要とするため、`2015-09`開始でもDevelopment sampleは失われません。
future informationは利用せず、split assignmentは常にoutcome monthで決定します。実データの取得対象は
`2015-09`から`2026-06`までです。

### Track B universe policy

`config/research_track_b.yaml`のprimary universeと`secondary_cross_robustness` universeは、current freeze version時点で
事前指定された役割です。performance結果を見てprimaryからsymbolを除外したり、secondaryから好調symbolだけを
追加したり、両universeを入れ替えたりしません。

ただしhistorical predictive/performance resultを見る前のstructural validationで、coverage不足、timestamp
corruption、duplicate / missing dataの重大問題、source consistency failure、prepared Bid OHLCとして不成立、
その他客観的なdata-quality failureが判明した場合は、既存versionをin-place変更せず、理由を記録した新しい
freeze versionで変更します。

Final HoldoutはM7までpredictive/performance resultを閲覧しません。

### M1A implementation and real-data execution gates

M1A implementation readinessは、valid current Track B freeze artifactが存在し、frozenであることです。
synthetic fixture / unit test等を使ったM1A code implementationは、real-data structural validationの
完了を待たずに開始できます。

M1A real-data execution readinessは、current freeze versionに対応するTrack B structural validationが
下記のoverall gateを満たして完了していることです。これを満たすまで、Track B real historical dataから
predictive regression、effect-size table、pooled result、Development / Validation resultを生成・閲覧しません。
Final Holdoutは従来どおりM7まで開きません。

Track B structural validationのoverall gateは、primaryとsecondaryを分けて判定します。

- **Primary gate**: frozen primary 8 symbolsがすべて`pass`または`pass_with_warning`であること。
  primaryに1 symbolでも`fail`があれば、current freeze versionではM1A primaryのreal-data executionを開始しません。
- **Secondary robustness gate**: robustness analysisに含めるfrozen secondary symbolが`pass`または`pass_with_warning`であること。
  secondaryの`fail`はM1A primaryおよびM2をblockしませんが、そのsymbolのsecondary robustness analysisは実行しません。

`fail`を理由にuniverseを変更する場合は、既存freeze versionをin-place変更せず、新しいfreeze versionを作成して
再validationします。各analysis output / metadataには、使用したinteger `freeze_version`を必ず記録します。

Current status: freeze v3のprimary 8 symbolおよびsecondary 4 symbolはすべて
`pass`であり、同一のprepared Daily datasetに対するM1A real historical executionは完了しています。
実行結果はFinal Holdoutを含まず、`freeze_version`、`structural_spec_version`、
`dataset_fingerprint`、`dataset_fingerprint_algorithm`をmetadataへ保存しています。

## Track B v2 structural validation contract (current)

Track B v2は、既に生成済みのprepared Exness Bid OHLCをresearch input authorityとする。
prepared OHLCは1m〜1wまで存在し得るが、M1Aのauthorityはprepared 1dであり、1mからDailyを再生成しない。
この変更はpredictive/performance resultを見る前のengineering/data-pipeline simplificationであり、
period、split、symbol universe、M1A methodology、HAC/cluster inference、Development/Validation/Final
Holdout期間は変更しない。

### v2 input and loader

実データloaderの既定パスは`data/processed/{SYMBOL}_1d.csv`。canonical minimum schemaは
`timestamp, open, high, low, close`である。symbol列が無い場合はfile pathの`{SYMBOL}`から付与してよい。
現行prepared exportの`datetime`はloader側で`timestamp`へ名前だけ正規化でき、`volume`等の追加列は無視する。
timezone-naiveなCSV timestampはloader境界でUTC labelとして許可するが、canonical in-memory timestampは
timezone-aware UTCへ統一する。
bar labelの値・意味は変更せず、NY17 nominal-close timestampへの変換は要求しない。

### v2 fail-fast checks

The validation order is: parse timestamps, filter to the requested UTC month
range, then validate duplicate timestamps, ordering, and OHLC values. Thus
parsed rows outside the frozen range are not part of structural validation
authority or the fingerprint. A timestamp that cannot be parsed cannot be
range-filtered and remains a failure.

各symbolについて、次だけを確認する。

- required columns
- timestamp parse
- timestamp ascending
- duplicate timestampなし
- OHLC numeric / finite / positive
- `nonfinite_or_invalid_ohlc_rows`は異常cell数ではなく、異常を含むunique row数
- `high >= open, close`、`low <= open, close`、`high >= low`
- requested range filtering (`2015-09`〜`2026-06`、current artifact値)
- requested UTC calendar monthがすべて少なくとも1本のDaily barを持つこと

malformed、unsorted、duplicate、invalid OHLCはrepairせずfail/errorとする。raw tick adapter、per-tick
Python loop、SQLite fallback、source_file_order/source_row_number、repeated/exact tick duplicate処理、
tick-level Bid validation、NY17 tick aggregation、suspicious tick-gap reconstruction、Fingerprint/M1A
binding専用の別dataset生成はv2から削除する。

検証済みprepared Daily datasetを同じオブジェクトとして

```text
validate -> compute_track_b_daily_fingerprint -> StructuralValidationSummary -> M1A
```

へ渡す。fingerprint algorithm `track-b-daily-sha256-v1`は維持し、structural spec identifierは
`track-b-structural-v2`へ更新する。fingerprintに入るのはrequested range内の
`symbol,timestamp,open,high,low,close`だけである。

calendar monthはprepared Daily timestampのUTC calendar monthから決め、
`P[M] = calendar month Mの最後のvalid prepared Daily Close`を維持する。
NY17境界付近の数時間/約1分の違いはv2 Practical Trackのnon-material implementation conventionとする。

### v2 diagnostics and gate

symbol-level diagnosticsは上記checkのfailure reason、source file、requested range、valid row count、
available/missing calendar months、validation statusを記録する。statusは`pass`または`fail`とし、
malformed inputを`pass_with_warning`へ昇格させない。current v2 freezeに対応するprimary全symbolが
passするまで、M1A real historical executionを開始しない。secondary failureは従来どおりprimaryを
blockしない。

Current freeze v3では、上記の明示的な実行が完了しています。Final Holdoutのpredictive / performance
結果は引き続きM7まで開きません。

## Historical v1 note

旧v1のraw-tick structural-validation contractは、下記の
`Track B Structural Validation v1 Implementation Convention`に履歴として保持する。
current v2のloader、validator、fingerprint入力、M1A authorityとして参照してはならない。

## M1 — Academic Hypothesis + Statistical Challenge

M1はworkstream別にstatusを持つ。

- M1A implementation: `complete`; M1A real-data execution: `complete` for current freeze v3 after structural validation pass
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

---

# Track B Structural Validation v1 Implementation Convention

This section is retained only for historical v1 provenance. It is superseded by the current v2 structural
contract and v3 freeze artifact above and
must not be used by the current loader or M1A path. `docs/03_data_and_costs.md` remains authoritative for
current data semantics, and `docs/07_academic_validation_spec.md` remains authoritative for M1A methodology.

Structural validation inspects raw data structure and produces canonical Daily OHLC plus a `StructuralValidationSummary`. It does not generate returns, predictors, regressions, effect sizes, PnL, Sharpe, or strategy results. Raw structure in the Final Holdout may be inspected for coverage and integrity, but Final Holdout performance information remains sealed until M7.

## Frozen identifiers and requested range

The historical v1 structural validator used these identifiers:

```text
structural_spec_version = track-b-structural-v1
dataset_fingerprint_algorithm = track-b-daily-sha256-v1
```

The historical v1 requested range was `2015-01` through `2026-06`, inclusive. The integer `freeze_version` is read from the current Track B artifact. A freeze artifact is never modified in place; an objectively justified change creates a new integer version with its reason and affected fields recorded.

## Canonical raw tick adapter input

Vendor CSV headers are not frozen. A source-specific adapter must emit this canonical representation before validation:

```text
symbol
timestamp
bid
source_file_order
source_row_number
```

`symbol` is a frozen Track B symbol. `timestamp` must be parseable as timezone-aware UTC on the real-data path; timezone-naive timestamps are not implicitly localized. `bid` must be numeric, finite, and strictly positive. A timestamp parse failure or missing timestamp is an invalid record and is counted in diagnostics.

`source_file_order` is a deterministic integer assigned from a stable sort of normalized relative file paths in the source manifest. `source_row_number` is the original zero-based row position within its source file. Together they reproduce raw source order deterministically.

## Canonical ordering and duplicate handling

Valid ticks are processed with a stable sort by:

```text
symbol ascending
timestamp UTC ascending
source_file_order ascending
source_row_number ascending
```

Raw input need not already be sorted. Whether out-of-order records were present is recorded as a diagnostic. Repeated timestamps within a symbol are not an automatic failure. Ticks with the same timestamp but different Bid values are retained and processed in source order.

An exact duplicate is a row whose canonical `symbol`, `timestamp`, and `bid` fields are identical. The validator must record `exact_duplicate_row_count`, retain the first row in canonical stable order, and remove later exact duplicates. Same-timestamp rows with different prices are not removed.

## Invalid record policy

The validator may exclude rows with an unparseable or missing timestamp, a nonnumeric/NaN/infinite Bid, or a Bid less than or equal to zero. It must record at least `timestamp_parse_errors` and `nonfinite_or_invalid_bid_rows`. No arbitrary invalid-row threshold is used. Failure is determined by whether the remaining data can produce deterministic Daily OHLC, usable Bid series, and required monthly coverage.

## NY 17:00 session and Daily OHLC

The aggregation authority is raw timestamp in UTC, boundary timezone `America/New_York`, boundary local time `17:00`, and Bid price. The IANA timezone database is the DST authority; fixed UTC offset tables are not.

Session D is the half-open-on-the-left interval `(previous NY 17:00, current NY 17:00]`. A tick exactly on the previous boundary belongs to the previous session; a tick exactly on the current boundary belongs to the current session. The generated Daily timestamp is the current session's NY 17:00 close boundary converted to a timezone-aware UTC timestamp. It is not a bar-open timestamp.

For each non-empty session, the validator constructs:

```text
open  = first valid Bid in canonical order
high  = maximum valid Bid
low   = minimum valid Bid
close = last valid Bid in canonical order
```

Each generated bar must satisfy `open > 0`, `high > 0`, `low > 0`, `close > 0`, `high >= open`, `high >= close`, `low <= open`, `low <= close`, and `high >= low`. Empty sessions are not synthesized and no fill is applied.

## Calendar month and coverage

Calendar month is determined from the Daily close timestamp converted to the `America/New_York` local date. The existing M1A rule applies: `P[M]` is the last valid Daily Close in calendar month M. Forward-fill, backward-fill, zero-fill, and nearest-month substitution are prohibited.

For the requested range, every calendar month must have at least one valid Daily Close. A completely missing requested month is a `fail`, because it affects exact-calendar-month predictors and HAC calendar continuity. A single missing session, short tick gap, holiday, or weekend closure is not an automatic failure.

## Large-gap diagnostic

Using the canonical valid tick sequence and expected NY daily-close boundaries, a suspicious gap is two or more consecutive expected daily-close boundaries crossed without a valid tick. The normal weekly closure from Friday 17:00 to Sunday 17:00 is excluded conceptually. `suspicious_gap_count > 0` is a warning, not an automatic failure. Failure occurs only through a separate criterion such as missing monthly coverage, inability to construct a trusted series, or clear source corruption.

## Status decision table

`pass` requires complete requested monthly coverage, deterministic timestamp interpretation and ordering, a valid Bid series, deterministic Daily aggregation, no source-corruption indication, and no structural warnings.

`pass_with_warning` means the research series remains complete, deterministic, and usable, but minor anomalies were recorded. Examples include out-of-order input, removed invalid rows, removed exact duplicates, harmless repeated timestamps, or suspicious gaps. Such a symbol remains in its frozen universe role.

`fail` means a required month is absent, UTC interpretation or deterministic ordering is impossible, no usable Bid series exists, Daily OHLC invariants fail, source corruption is major, requested coverage is materially insufficient, or the M1A/M2 research series cannot be trusted.

The v1 contract does not add arbitrary thresholds such as tick completeness percentages, missing-rate limits, minimum ticks per day, invalid-row counts, or cross-source price-difference limits.

## Validator output contract

The canonical Daily output is the long-form dataset with exactly:

```text
symbol
timestamp
open
high
low
close
```

Its timestamp is timezone-aware UTC and represents the nominal NY 17:00 close. The exact canonical Daily dataset inspected by structural validation must be the dataset passed to `compute_track_b_daily_fingerprint()` and then to M1A. The validator must not generate a separate dataset for either consumer.

Symbol-level diagnostics must be able to report:

```text
symbol
freeze_version
structural_spec_version
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
available_calendar_months
missing_calendar_months
validation_status
warnings
failure_reasons
```

`warnings` and `failure_reasons` are machine-readable lists. The run-level `StructuralValidationSummary` retains:

```text
freeze_version
structural_spec_version
dataset_fingerprint
dataset_fingerprint_algorithm
status_by_symbol
```

The fixed fingerprint algorithm canonicalizes timestamps as signed int64 nanoseconds since the Unix epoch in UTC. It fingerprints the exact canonical Daily dataset used by validation and M1A.

## Primary, secondary, and Final Holdout gates

All frozen primary symbols must be `pass` or `pass_with_warning` before current-freeze M1A primary real-data execution begins. Secondary symbols are gated individually for their own robustness analysis; a secondary failure does not block primary M1A or M2. Removing a failed symbol requires a new freeze version before any performance result is viewed; the existing artifact is not edited in place.

Structural validation may inspect Final Holdout raw coverage and integrity. It must not generate or expose Final Holdout returns, predictors, regressions, effect sizes, PnL, Sharpe, or strategy results.
