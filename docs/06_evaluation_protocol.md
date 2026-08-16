# Evaluation Protocol — What Can We Conclude at Each Stage?

## 1. この文書の目的

Time-Series Momentum研究では、単純なbacktestがプラスだっただけで

> TSMOMが再現した

と結論すると、academic literature・strategy implementation・risk scaling・broker costを混同しやすい。

本プロジェクトでは、各段階で「何が分かり、何はまだ分からないか」を明示する。

---

# 2. Evidence Ladder

## E0 — Engine Correctness

対象: M0

確認すること:

- causal signal
- correct lookback
- correct execution timing
- correct reversal
- correct return accounting

言ってよいこと:

> M0仕様を実装したengineが仕様通り動く。

まだ言えないこと:

> TSMOMにはedgeがある。

---

## E1 — Predictive Evidence

対象: R0

確認すること:

```text
past ~12m return -> next 1m return
```

言ってよいこと:

> 手元data上で、academic TSMOMの中心的な方向予測関係が見える / 見えない。

commission等はこの結論に不要。

まだ言えないこと:

> 現実のbrokerでnet profitableである。

---

## E2 — Strategy Construction Evidence

対象: R1 / M1

確認すること:

- daily simplified strategy
- academic-style monthly comparator
- multiple symbols
- turnover / holding differences

言ってよいこと:

> このsignalを特定のposition ruleへ変換したgross strategyの性質。

まだ言えないこと:

> portfolioとして優れている。
> real costs後にも残る。

---

## E3 — Portfolio Evidence

対象: M2 / M3

確認すること:

- diversification
- equal-notional
- volatility-scaled
- concentration

言ってよいこと:

> cross-market diversificationとrisk scalingを含むportfolio特性。

注意:

volatility scalingの改善をsignal alphaそのものの改善としない。

---

## E4 — Cost Robustness Evidence

対象: M4

確認すること:

- plausible commission
- spread
- slippage
- turnover
- break-even cost

historical cost seriesがなくても実施可能。

言ってよいこと:

> strategy edgeが想定cost rangeに対してrobust / fragileである。

historical seriesが不足する場合、まだ言えないこと:

> 過去の特定brokerで実際にこのNet PnLだった。

---

## E5 — Broker-Net Evidence

対象: historical execution / financing dataが十分な場合のみ

確認すること:

- historical spread / fee schedule
- realistic slippage
- historical swap / financing
- contract specification

言ってよいこと:

> 特定broker条件を近似したhistorical net simulation。

それでもtick-level約定等がなければ「完全再現」とは限らない。

---

# 3. Commissionデータがなくても研究する意味

ある。

commission履歴がなくても、研究上は少なくとも以下を分離できる。

### Predictability

R0ではcost自体が不要。

### Gross strategy behavior

M0〜M3では、signalとposition constructionの性質をcostから分離して見る。

### Cost robustness

M4では

```text
0
low
base
high
```

等のscenarioを置く。

さらにbreak-even costを計算し、未知の実コストに対してedgeが十分大きいかを判断する。

したがって、commission履歴がないことは

> 研究が無意味

を意味しない。

意味するのは

> exact historical broker net PnLという強い主張はできない

ということである。

---

# 4. Swapデータがない場合

Daily / long-horizon FX/CFDではcommissionより重大になり得る。

swapは保有期間中累積し、direction / symbol / date / broker条件に依存する。

historical swapがない場合は、結果を次のように分ける。

```text
Level 1: Gross price-only
Level 2: Net ex-financing
Level 3: Full broker net
```

Level 3を無理に作らない。

current swapをhistorical全期間へ適用することは原則避ける。

将来のforward testではactual swapを保存し、Level 3評価能力を高める。

---

# 5. Academic TrackとPractical Track

## Track A — Academic Validation

問い:

> academic TSMOMのsignal / evidenceと自作研究系は整合するか？

利用:

- original paper
- AQR Original Paper Data
- academic-style monthly comparator
- futures / forward dataが得られれば優先

## Track B — Practical FX/CFD

問い:

> 手元のspot/CFD dataと現実的executionで利用可能なedgeか？

利用:

- broker OHLC
- next-open execution
- commission/spread scenarios
- swap dataがあれば追加

この2つが一致する必要はない。

例えばTrack Aでacademic evidenceが確認できても、Track Bではswap/costで消える可能性がある。
逆にTrack Bの特定symbolだけで利益が出ても、それだけでacademic evidenceの再現とはしない。

---

# 6. 推奨Decision Gates

## Gate 0 — M0完了

進む条件:

- golden tests通過
- causality通過
- execution / accounting確定

profitabilityは条件にしない。

## Gate 1 — R0/R1確認

確認する:

- academic hypothesisとの方向整合
- M0 vs academic-style comparator差

結果が弱くても即終了ではないが、今後の目的を

- academic replication
- practical trend strategy exploration

のどちらに置くか再確認する。

## Gate 2 — M1/M2

確認する:

- symbol横断性
- portfolio diversification

単一symbol optimumに依存する場合はbaseline採用しない。

## Gate 3 — M3

確認する:

- unscaledで何が残るか
- scalingで何が改善するか

## Gate 4 — M4

確認する:

- break-even cost
- realistic scenarioでedgeが残るか
- financing不足による結論制約

## Gate 5 — M5

確認する:

- holdout
- plateau
- year / symbol robustness
- walk-forward

ここまで通って初めて、4h / 1hや追加filterの研究へ進む。
