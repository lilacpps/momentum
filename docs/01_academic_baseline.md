# Academic TSMOM Baseline Specification

## 目的

論文を完全複製することそのものではなく、まず「学術的TSMOMの核心を壊さない最小実装」を作る。

## Baseline A: Pure directional signal

### Frequency
- Daily

### Signal
- N営業日前から直近確定日までのreturn sign
- 最初の候補: N = 20, 60, 120, 240
- ただし代表研究の中心は12か月程度のlookbackであるため、240日前後を必ず含める。

### Lookahead safety
- t日のシグナル計算に使用できるのは t-1 までに確定したデータのみ。
- entry価格は次の実行可能な価格を使用する。

### Position
- signal > 0: Long
- signal < 0: Short
- signal = 0: Flatまたは既存position維持の扱いを仕様化する。

### Exit
- signal反転時にreverse。
- V0ではTP/SLを追加しない。

### Costs
- GrossとNetを別々に計算。
- V0で正確なswap履歴がない場合は `swap_not_modeled=true` を明示。

## Baseline B: Volatility-normalized

Baseline Aと同一signalを用い、position sizeのみ変える。

概念:

```
position_size ∝ target_risk / estimated_volatility
```

これにより、

- signal自体のedge
- risk normalizationによるportfolio改善

を分離して比較する。

## Portfolio

V1ではまず簡潔にする。

- 全symbol共通lookback。
- symbol別最適化禁止。
- equal notional と equal risk の両方を比較可能にする。
- FX pairの共通USD exposure調整はV1では診断表示に留めてもよい。

## Research parameter policy

パラメータは「最高値探索」ではなく粗い意味的grid。

例:

```
20 / 60 / 120 / 240 days
```

避ける:

```
37, 38, 39, ..., 83 days
```

## 研究論文との差分を必ず記録する

実装時に次の表を埋める。

| 項目 | Original literature | 本実装 | 差分理由 |
|---|---|---|---|
| signal | | | |
| lookback | | | |
| holding/rebalance | | | |
| volatility estimate | | | |
| target volatility | | | |
| instruments | | | |
| excess return | | | |
| financing/carry | | | |
| transaction costs | | | |

この差分表なしに「論文再現」と呼ばない。
