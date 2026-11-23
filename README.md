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

Compare a trial and write `result.json` plus `summary.txt`:

```bash
.venv/bin/python -m smokeroom run \
  --measurements fixtures/noiseless/measurements.csv \
  --config fixtures/noiseless/config.json \
  --output outputs/noiseless
```

On this noiseless trial the fitted penetration and deposition stay at the
declared 0.8 and 0.2 1/h, and the predicted indoor series matches
`fixtures/oracle/noiseless.md` within 1e-6 µg/m³. Held-out MAE and bias are
about 0, and the usable fraction is 1.

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
