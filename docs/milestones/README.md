# Milestone Index

`docs/00〜07` は横断的な設計・研究ポリシー、
`docs/milestones/M0〜M9` は各工程の実行契約です。

| Milestone | File | Status |
|---|---|---|
| M0 | `M0_engine_correctness.md` | Ready |
| M1 | `M1_academic_hypothesis.md` | Ready after Track B split freeze; reference bootstrap algorithm lock required during implementation |
| M2 | `M2_academic_comparator.md` | Ready after M1 |
| M3 | `M3_multi_symbol.md` | High-level ready; TSH exact convention must be locked before challenge use |
| M4 | `M4_portfolio.md` | Needs final alignment rules |
| M5 | `M5_volatility_scaling.md` | MOP reference mode specified; practical mode needs final caps/targets |
| M6 | `M6_cost_financing.md` | Core contract ready |
| M7 | `M7_robust_validation.md` | Needs fixed experiment / TSH / go-no-go rules |
| M8 | `M8_4h.md` | Future / intentionally incomplete |
| M9 | `M9_1h.md` | Future / intentionally incomplete |

CodexへMilestoneを依頼する場合は、まず該当 `M*.md` を読み、その「参照docs」に列挙された横断文書を読むこと。

## Conflict rule

Milestone文書はscope / deliverables / testsのentrypointです。
`docs/01`, `03`, `04`, `07` のnormative contractと矛盾する場合、推測して実装せずdocumentation bugとして解消します。
