# Momentum Research Project Scaffold

このプロジェクトは、Time-Series Momentum（TSMOM）を「まず単純な学術ベースラインとして再現し、その後に実運用上の拡張を検証する」ための研究・開発用ひな型です。

## 方針

1. 最初に Pure TSMOM を再現する。
2. 利益最大化のための細かいパラメータ探索はしない。
3. 単一ペアの最高成績ではなく、複数市場に共通する弱い edge を重視する。
4. Gross / Net、signal edge / risk scaling、single-market / portfolio を分離して評価する。
5. Daily → 4h → 1h の順に短期化する。

最初に読む文書:
- `docs/00_momentum_overview.md`
- `docs/01_academic_baseline.md`
- `docs/02_research_questions.md`
- `docs/05_roadmap.md`
- `references/README.md`

## 推奨初期スコープ

最初の実装は M0〜M2 まで。

- M0: Daily Pure TSMOM, single symbol
- M1: common rule を複数symbolへ適用
- M2: portfolio集計

volatility targeting、swap、4h/1h は、その後に段階的に追加する。
