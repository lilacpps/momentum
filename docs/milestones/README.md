# Milestone Index

`docs/00〜07` は横断的な設計・研究ポリシー、
`docs/milestones/M0〜M9` は各工程の実行契約です。

| Milestone | File | Status |
|---|---|---|
| M0 | `M0_engine_correctness.md` | Ready |
| M1 | `M1_academic_hypothesis.md` | M1A complete for current freeze v3; AQR sanity independent; M1B after eligible underlying; M1C-reference after reference underlying + contract; M1C-practical after Track B data + contract |
| M2 | `M2_academic_comparator.md` | Complete for freeze v3; M1B/M1C may remain pending |
| M3 | `M3_multi_symbol.md` | TSH contract `tsh-huang-v1` frozen; ready for implementation without portfolio aggregation |
| M4 | `M4_portfolio.md` | Needs final alignment rules |
| M5 | `M5_volatility_scaling.md` | MOP reference EWMA contract in `docs/07`; practical mode remains separate |
| M6 | `M6_cost_financing.md` | Core contract ready |
| M7 | `M7_robust_validation.md` | Needs fixed experiment / go-no-go rules; reuses frozen TSH contract and M2 comparison mask |
| M8 | `M8_4h.md` | Future / intentionally incomplete |
| M9 | `M9_1h.md` | Future / intentionally incomplete |

CodexへMilestoneを依頼する場合は、まず該当 `M*.md` を読み、その「参照docs」に列挙された横断文書を読むこと。

## Conflict rule

Milestone文書はscope / deliverables / testsのentrypointです。
`docs/01`, `03`, `04`, `07` のnormative contractと矛盾する場合、推測して実装せずdocumentation bugとして解消します。
