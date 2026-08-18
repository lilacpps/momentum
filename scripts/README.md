# Scripts

予定:
- run_baseline.py
- build_report.py
- compare_parameters.py
- compare_symbols.py

## Track B structural validation

The production entry point is
`momentum.data.structural_validation.run_track_b_structural_validation`.
It reads prepared Daily files from `data/processed/<SYMBOL>_1d.csv` and only
validates the prepared OHLC; it does not read raw ticks or aggregate 1m data.
The validator writes no real output by default.

From the repository root, the CLI wrapper runs the same v2 structural
validation without executing M1A:

```text
python scripts/run_structural_validation.py
```

It uses `config/research_track_b.yaml` and `data/processed` by default,
prints symbol diagnostics plus the dataset fingerprint, and returns exit code
1 when any frozen primary symbol has `validation_status: fail`.

Example command for a later explicitly requested real-data run:

```text
python -c "from momentum.data.structural_validation import run_track_b_structural_validation; run_track_b_structural_validation()"
```
