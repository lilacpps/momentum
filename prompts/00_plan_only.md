# Plan-only prompt

このリポジトリにTime-Series Momentum研究基盤を実装したいです。
まだコードは変更しないでください。

最初に以下を読んでください。

- README.md
- docs/00_momentum_overview.md
- docs/01_academic_baseline.md
- docs/02_research_questions.md
- docs/03_data_and_costs.md
- docs/04_validation_policy.md
- docs/05_roadmap.md
- references/README.md

その上で、既存コードがある場合はデータローダ、バックテスト、metrics、portfolio、cost、validation基盤を調査し、M0〜M2の具体的な実装計画を作成してください。

重要:
- Pure TSMOM baselineを先に作る。
- RSI/ADX/MA等の追加filterを入れない。
- symbol別最適化をしない。
- lookaheadを最優先で防ぐ。
- academic literatureとの差分を明示する。
- 不明点を勝手に埋めず unresolved として列挙する。
- まだ実装しない。
