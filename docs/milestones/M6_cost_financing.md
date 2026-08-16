# M6 — Cost and Financing Layer

## Status
Core cost contract defined; scenario values must be fixed before a specific experiment.

## 目的
gross edgeがtransaction cost / financingにどの程度耐えるかを評価する。
historical broker replicationとcost robustnessを分離する。

## 参照docs
- `docs/03_data_and_costs.md`
- `docs/04_validation_policy.md`
- `docs/05_roadmap.md`
- `docs/06_evaluation_protocol.md`

## 固定contract

```text
turnover[t] = abs(position[t] - position[t-1])
```

examples:
```text
Flat -> Long  = 1
Long -> Flat  = 1
Long -> Short = 2
```

cost unit:
> one-way basis points per unit normalized notional turnover

```text
cost_return[t] = turnover[t] * all_in_one_way_cost_bps / 10000
```

## Result Levels
- Level 1: Gross price-only
- Level 2: Net ex-financing
- Level 3: Full broker net

historical financing不足時にLevel 3を作らない。

## 実装対象
- spread scenario
- commission scenario
- slippage scenario
- total turnover
- net ex-financing
- break-even cost
- financing capability
- Result Level metadata

## 人間が決める事項
experimentごとに:
- low/base/high commission
- spread scenario
- slippage scenario
- one-way/round-trip conversion
- available historical swap source
- financing proxyを使うか
- actual broker assumptions

## 必須テスト
- Flat→Long cost = 1 unit
- Long→Short cost = 2 units
- cost sign always reduces PnL
- zero cost reproduces gross exactly
- break-even calculation
- result-level labeling
- financing absent => no Full broker net

## 完了条件
- cost unit unambiguous
- scenario metadata complete
- break-even cost reported
- no false claim of exact historical broker PnL
