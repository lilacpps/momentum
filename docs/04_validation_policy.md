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
-> Track B development / validation / final holdout / symbol universe freeze
-> 実historical dataで初めてgross performanceを生成
-> M1
```

**split freeze前にPractical Trackのstrategy performance / predictive resultを見てはいけません。**
schema、timestamp、ordering、missingness等のstructural validationは可能ですが、performance / PnL /
predictive metricは不可とします。

```text
development
validation
final holdout
symbol universe
```

を固定します。

Track Aのpublished replication sampleは既知のreference sampleなので、このfinal holdoutには含めません。

## M1 — Academic Hypothesis + Statistical Challenge

M1はworkstream別にstatusを持つ。

- M1A Practical Predictability: `Ready after Track B split / universe freeze`
- M1B MOP Regression Comparator: `Ready only after eligible reference underlying data is identified`
- M1C Huang Statistical Challenge: `Ready after Huang methodology contract freeze`

M1Bのunderlyingが無い場合もM1AとAQR factor sanity checkは継続し、M1Bだけを data unavailable / pending とする。

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

## M2 — Academic-Style Monthly Comparator

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
