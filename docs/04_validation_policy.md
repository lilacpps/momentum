# Validation Policy

## 原則

Momentumは単純だからこそ、複雑な最適化で「良くしすぎない」。

## 必須観点

- chronological split
- final holdout
- symbol横断性
- parameter plateau
- year別安定性
- cost stress
- walk-forward（後段）

## 禁止事項

- holdoutを見てparameter変更
- symbolごとのlookback最適化をbaseline採用
- 一点だけ良いparameterを採用
- filterを結果を見ながら追加し続ける

## 推奨成果物

- parameter x symbol matrix
- parameter x year matrix
- portfolio equity
- rolling Sharpe / return
- underwater curve
- turnover / holding period
