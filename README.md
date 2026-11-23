# SmokeRoom

Compare observed single-room PM2.5 with a one-zone filtration model on a
held-out window. The bundled trials are synthetic. A modeled concentration
is not a room-safety rating, and the tool does not say whether to stay or
leave.

## Prerequisites

- Python 3.11 or newer
- The pinned packages in `pyproject.toml`: NumPy 1.26.4 and SciPy 1.14.1
- pytest 8.3.4 for the test run

No data are downloaded at run time.

## Install and check a fixture

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m smokeroom validate \
  --measurements fixtures/noiseless/measurements.csv \
  --config fixtures/noiseless/config.json
.venv/bin/pytest
```

Compare the bundled noiseless trial, then open the report:

```bash
.venv/bin/python -m smokeroom run \
  --measurements fixtures/noiseless/measurements.csv \
  --config fixtures/noiseless/config.json \
  --output outputs/noiseless
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

## Scope

Retrospective evaluation of one well-mixed room. Filtration comparisons
depend on the declared schedule and the mass-balance assumptions. Live
safety classification, exposure prescriptions, sensor control, and
multiroom airflow are out of scope.
