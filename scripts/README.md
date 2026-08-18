# Scripts

予定:
- run_baseline.py
- build_report.py
- compare_parameters.py
- compare_symbols.py

## Track B structural validation

The production entry point is
`momentum.data.structural_validation.run_track_b_structural_validation`.
It discovers source files from `data/raw/<SYMBOL>/*.csv`; one-year-per-file is
not assumed, so annual, monthly, and mixed CSV splits are supported.  The
validator only builds and validates canonical Daily OHLC and writes no real
output by default.

Example command for a later explicitly requested real-data run:

```text
python -c "from momentum.data.structural_validation import run_track_b_structural_validation; run_track_b_structural_validation()"
```
