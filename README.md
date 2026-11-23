# SmokeRoom

Compare observed single-room PM2.5 with a one-zone filtration model on a
held-out window. The bundled trials are synthetic. A modeled concentration
is not a room-safety rating, and the tool does not say whether to stay or
leave.

## Prerequisites

Verified on Ubuntu with CPython 3.12. The same commands are the supported
path for CPython 3.11 or newer. Windows virtual environments use
`.venv\Scripts\` instead of `.venv/bin/`. No other platform is part of the
recorded check.

Pinned runtime packages, from `pyproject.toml`:

- NumPy 1.26.4
- SciPy 1.14.1

Development checks also install pytest 9.2.0 and ruff 0.8.6. No data are
downloaded at run time. There is no separate hardware, live-sensor, or
real-monitoring demo.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/ruff check src tests scripts
.venv/bin/pytest
```

## Demo

After that install, one command runs the noiseless fixture:

```bash
.venv/bin/python -m smokeroom run \
  --measurements fixtures/noiseless/measurements.csv \
  --config fixtures/noiseless/config.json \
  --output outputs/noiseless
```

Expected result: fitted penetration `0.8`, deposition `0.2` 1/h, held-out
usable fraction `1` (3 of 3), and held-out MAE and bias within `1e-6` µg/m³
of zero. The report is `outputs/noiseless/report.html`. The machine-readable
copy is `outputs/noiseless/result.json`. Reload that file with:

```bash
.venv/bin/python -m smokeroom show outputs/noiseless/result.json
```

`run` writes three files in the output directory:

- `result.json` — configuration, parameter assumptions, row residuals, and held-out MAE, bias, and usable fraction
- `summary.txt` — the same rows in a short text form
- `report.html` — alignment, a timeline with gaps and the held-out window marked, and the residual table

Standard output is the JSON result. A one-line `diagnostic:` note goes to standard error. `show` loads `result.json` and prints the text summary. `--help` lists the commands. Exit 0 means the command finished, and exit 2 means the input or saved file was rejected.

On this noiseless trial the fitted penetration and deposition stay at the
declared 0.8 and 0.2 1/h, and the predicted indoor series matches
`fixtures/oracle/noiseless.md` within 1e-6 µg/m³. Held-out MAE and bias are
about 0, and the usable fraction is 1. The noisy trial is the partial case:
it keeps a missing comparison and a large held-out residual, and the report
labels that comparison weak.

`validate` prints a JSON summary and exits 0 when the trial matches schema 1.
A rejected trial prints `category: message` on standard error and exits 2.
The negative indoor fixture is the labeled invalid example:

```bash
.venv/bin/python -m smokeroom validate \
  --measurements fixtures/invalid/negative_indoor.csv \
  --config fixtures/invalid/config.json
```

Input and output shapes are in `docs/schema.md`. The closed-form reference
for the noiseless trial is in `fixtures/oracle/noiseless.md`. Generation
notes, the seed, and file checksums are in `fixtures/MANIFEST.json`.

## Fixture terms

The CSV and JSON trials in `fixtures/` are original synthetic series released
under CC0-1.0. They are not observations from a monitoring network. The noisy
trial uses random seed `20241123` only for its Gaussian noise. Real series
are out of scope until calibration, redistribution permission, collection
dates, and station metadata are recorded.

## License and changes

The program is MIT. See `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, and
`SECURITY.md`. Version 0.1.0 is the first release candidate.

## Scope

Retrospective evaluation of one well-mixed room. Filtration comparisons
depend on the declared schedule and the mass-balance assumptions. Live
safety classification, exposure prescriptions, sensor control, and
multiroom airflow are out of scope.
