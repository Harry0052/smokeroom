# Project contract

Status: accepted for implementation after the P01 proceed decision in `docs/overlap.md` (2026-11-23).

## User task

An indoor-air researcher or facilities analyst compares observed single-room PM2.5 with a simple filtration model.

They supply an hourly table of timezone-aware timestamps, indoor PM2.5, outdoor PM2.5, and sensor quality fields, plus a JSON description of room volume, a declared filtration schedule, and the calibration/evaluation boundary. SmokeRoom aligns the rows, flags timezone offsets, duplicate samples, absent observations, disagreements, and negative concentrations, solves a well-mixed mass balance, fits a small parameter set only on the calibration segment when that fit is identifiable, and writes a report for the held-out segment.

The report shows alignment and coverage, observed and predicted timelines, residuals, and held-out MAE, bias, and usable fraction together. When residuals or coverage make the comparison weak, the report says so. Filtration differences are conditional on the declared rates and the one-zone assumptions. The tool does not classify a room as safe, recommend staying or leaving, control sensors, or model multiroom airflow.

The shipped demo uses only the bundled synthetic trials.

## Minimum dependencies

- Python 3.11 or newer
- NumPy
- SciPy
- pytest, for the test run

The HTML report and CSV/JSON adapters use the Python standard library. No paid service, account, or network fetch is required after install. Optional plotting libraries are out of scope.

## Model contract

For a piecewise-constant step of length `Δt` hours, with nonnegative unit-checked inputs:

```text
L = a + k_dep + k_filt
C_ss = (P * a * C_out) / L    when L > 0
C_next = C_ss + (C - C_ss) * exp(-L * Δt)
```

`C` and `C_out` are PM2.5 in µg/m³. `P` is dimensionless. `a`, `k_dep`, and `k_filt` are per hour. `k_filt` may change on the declared schedule. The outdoor value used on an interval is the aligned value at the start of that interval, so a later sample cannot affect an earlier prediction. Indoor sources are not estimated. An unexplained indoor spike remains a residual.

Parameter search, when run, uses only rows inside the calibration segment. Candidates whose calibration loss is nearly as good as the best candidate are reported as not uniquely identified. Held-out rows are scored and never used to update parameters.

## Measurable acceptance case

On the noiseless synthetic trial with known infiltration and a higher removal rate during the scheduled filter period, predictions from the public entry point match an independent closed-form reference within a relative tolerance of `1e-6` (and an absolute tolerance of `1e-6` µg/m³).

On the second synthetic trial, which contains gaps, sensor disagreement, and an unexplained indoor spike, the report marks missing comparison points, shows the residual at the spike, and does not change fitted parameters when only held-out measurements change. The same eligible rows appear in the residual summary and the downloadable result. Held-out MAE, bias, and usable fraction are reported together.

Negative measured concentrations are rejected with an actionable error or an explicit row flag and are excluded from fitting and scores.

## Provenance

Fixtures are original and synthetic. Generation seed, equations, and checksums live in the fixture manifest. Real monitoring series are out of scope until calibration, redistribution permission, collection dates, and station metadata are recorded.

## Out of scope

Live safety classification, personal exposure prescriptions, stay-or-leave thresholds, remote sensor control, and multiroom airflow.
