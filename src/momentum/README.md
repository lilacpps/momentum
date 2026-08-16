# Source package layout

- `data/` : market data normalization, calendars, resampling
- `signals/` : pure TSMOM signal only
- `portfolio/` : position sizing, aggregation, exposure
- `costs/` : spread/commission/slippage/swap models
- `backtest/` : causal execution and accounting
- `metrics/` : PF, CAGR, Sharpe, DD, rolling/yearly metrics

Signal generation and risk/portfolio logic must remain separable.
