# Momentum Documentation Revision — M0 + Research Validation Protocol

このZIPは、M0実装前レビューと、その後の「baselineからどのように妥当性を検証するか」のレビューを統合した文書修正版です。

## この版で固定する考え方

1. M0はMoskowitz, Ooi, Pedersen (2012; 以下MOP) の完全再現ではない。
2. M0は `Single-Symbol Unscaled Daily TSMOM Research Baseline` とし、主目的を **engine correctness** とする。
3. M0のsignalは `Close[t-1] / Close[t-1-L] - 1`、`L=240 observed daily bars` を標準とする。
4. signalは `t-1` 確定後に計算し、position変更は `Open[t]` で行う。
5. zero signal = Flat、same signal = Hold、reversal = next openで反転。
6. M0はnormalized gross returnのみ。volatility scaling / portfolio / costs / swapは混入させない。
7. M0の成績だけで「academic TSMOMを再現した」と結論しない。
8. M0後に **R0 Academic Hypothesis Check** を行い、`past ~12m return -> next 1m return` の予測関係を直接確認する。
9. 続いて **R1 Academic-Style Comparator** を作り、monthly / ~12m lookback / 1m holdingをspot/CFD price data上で比較する。
10. Academic validationとPractical FX/CFD validationを別trackとして扱う。
11. historical commission/spread seriesがなくても、cost scenarioとbreak-even costで「edgeの耐コスト性」は評価できる。
12. historical swapがない場合は、完全なbroker net PnLを再現したとは呼ばない。
13. 結果は `Gross price-only` / `Net ex-financing` / `Full broker net` の3レベルを区別する。
14. volatility scalingはsignal edgeとrisk engineeringを分離するためM3で追加する。

## 推奨順序

```text
M0  Engine correctness
 |
 +-- R0 Academic hypothesis check
 |     past ~12m return -> next 1m return
 |
 +-- R1 Academic-style comparator
 |     monthly / ~12m lookback / 1m hold / initially unscaled
 |
M1  Multi-symbol common rule
M2  Portfolio aggregation
M3  Volatility normalization
M4  Cost and financing layer
M5  Robust validation
M6  4h
M7  1h
```

R0/R1はsoftware milestoneとは別の **research checkpoint** とする。実装番号を増やすためのMilestoneではなく、「次へ進む前に何を確認するか」を表す。

## 収録ファイル

- `docs/00_momentum_overview.md`
- `docs/01_academic_baseline.md`
- `docs/02_research_questions.md`
- `docs/03_data_and_costs.md`
- `docs/04_validation_policy.md`
- `docs/05_roadmap.md`
- `docs/06_evaluation_protocol.md` — 今回追加
- `config/baseline.example.yaml`

## 注意

- このZIPは提案版であり、GitHubへはまだ反映していない。
- M0は「利益が出たか」で合否判定しない。signal / execution / state transition / accountingの正しさで完了判定する。
- R0/R1/M1以降で初めて、historical performanceを研究上の証拠として段階的に評価する。
