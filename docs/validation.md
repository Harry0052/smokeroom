# Validation

Recorded 2026-11-23 on Linux 6.12.113+ x86_64, glibc 2.39, CPython 3.12.3.
The checks use the bundled synthetic fixtures only. There is no external
measurement campaign in this release.

## Acceptance metric

On the noiseless synthetic trial, predictions match the closed form in
`fixtures/oracle/noiseless.md` within an absolute tolerance of `1e-6` µg/m³
and a relative tolerance of `1e-6`. Held-out MAE, bias, and usable fraction
are reported together. On that trial the observed held-out MAE was
`2.90582e-13` µg/m³, bias `1.83409e-13` µg/m³, and the usable fraction was
1 (3 of 3).

On the noisy synthetic trial the same three numbers are reported together:
MAE `15.011` µg/m³, bias `15.011` µg/m³ (observed minus predicted), usable
fraction `0.666667` (2 of 3). The comparison is marked weak because coverage
is below 0.8 and an eligible residual exceeds 10 µg/m³. That 10 µg/m³ mark
is a model-comparison rule, not a safety category.

## Commands

```bash
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/python -m compileall -q src tests scripts
.venv/bin/pytest
.venv/bin/python -m smokeroom run \
  --measurements fixtures/noiseless/measurements.csv \
  --config fixtures/noiseless/config.json \
  --output outputs/noiseless
```

Observed on this host after the pytest pin moved to 9.2.0:

- ruff 0.8.6 check: all checks passed. Format check passed after formatting.
- `compileall`: success.
- pytest: 23 passed.
- Fresh noiseless demo: 0.189 seconds wall clock, standard error
  `diagnostic: conclusion=supported status=complete held_out_usable_fraction=1.0000`.
- Bundled `fixtures/` size: 8861 bytes.

`pip-audit` 2.9.0 with `--skip-editable` reported no known vulnerabilities
after the pytest upgrade. The editable SmokeRoom package is not on PyPI and
was skipped.

## Domain safeguard

Modeled PM2.5 is not a room-safety rating and not a stay-or-leave
instruction. The HTML status line and `result.json` limitations say so.
Timestamps without an offset are rejected. Non-UTC offsets, duplicate
instants, and absent sensors remain as row flags. A later outdoor value does
not change earlier step predictions. The report shows the held-out eligible
count next to MAE and bias. Negative concentrations are rejected before a
result file is written.

## Trust boundary

The program reads the measurements file and the config file and writes
`result.json`, `summary.txt`, and `report.html` under `--output`. It does
not spawn a child process and does not contact a network service at run
time. Row and byte caps reject oversized input. Report text from the trial
is escaped; a trial id of `<script>alert(1)</script>` is stored as text.
Fixtures are original synthetic series. Checksums are in
`fixtures/MANIFEST.json` and are checked by the test suite.

## Dependencies and licenses

| Package | Version | License used with this project |
| --- | --- | --- |
| NumPy | 1.26.4 | BSD-3-Clause |
| SciPy | 1.14.1 | BSD-3-Clause. The wheel also links LGPL-2.1 `libquadmath`; this repository does not vendor that library |
| pytest | 9.2.0 | MIT |
| ruff | 0.8.6 | MIT |

SmokeRoom itself is MIT. These terms allow the documented install. pytest
8.3.4 was replaced because `pip-audit` reported PYSEC-2026-1845
(CVE-2025-71176), fixed in pytest 9.0.3. The pin is 9.2.0.

## Performance budget

The supported demo is the noiseless hourly fixture, 7 rows and about 9 KB of
fixtures. Budget: the demo command finishes in under 3 seconds, and a
2,000-row hourly series finishes the load-and-evaluate step in under 5
seconds. The 2,000-row bound is a regression test. The observed demo time
was 0.189 seconds, and an earlier 2,000-row measurement on this host was
0.202 seconds.

## Residual limitations

The noisy calibration window has two eligible rows for two fitted
parameters, so those calibration residuals can be driven near zero. The
held-out spike is not used in the fit. No real monitor series is included,
so the numbers above are synthetic checks, not a field validation. A second
parameter vector is reported only when a coarse grid point matches the
calibration loss about as well as the optimum.
