# Grokbot progress

## Phase and status

P03 — Build the working core — **PASS**

## Files changed

- `src/smokeroom/analysis.py`
- `src/smokeroom/validate.py`
- `src/smokeroom/cli.py`
- `tests/test_run.py`
- `docs/schema.md`
- `README.md`
- `docs/grokbot-progress.md`

## Commands and results

- `.venv/bin/pytest`: 10 passed.
- `.venv/bin/python -m smokeroom run --measurements fixtures/noiseless/measurements.csv --config fixtures/noiseless/config.json --output outputs/noiseless` exited 0. Fit status `fitted`. Penetration 0.8 and deposition 0.2 1/h. Held-out MAE `2.90582e-13` µg/m³, bias `1.83409e-13` µg/m³, usable fraction 1 (3 of 3). Conclusion `supported`.
- The same command on `fixtures/noisy` exited 0. Row 3 is `missing_observation`. Row 7 evaluation residual is `29.9399` µg/m³. Held-out MAE `15.011`, bias `15.011`, usable fraction `0.666667` (2 of 3). Conclusion `weak`. Fitted parameters do not change when only that held-out indoor value is replaced.
- The negative fixture exits 2 with `negative_concentration` and writes no result file.

## Artifact paths

- `outputs/noiseless/result.json`
- `outputs/noiseless/summary.txt`
- `outputs/noisy/result.json`
- `outputs/noisy/summary.txt`

`outputs/` is gitignored. `pytest` rebuilds the same assertions in a temporary directory.

## Open issues

- The user-facing HTML report and save/load inspection path are P04.
- Noisy calibration uses two eligible rows for two parameters, so those two calibration residuals are driven to about 0. That is expected for this fixture, and the held-out spike is not used.

## Next phase

P04 — Ship the user workflow and reports.

## Phase and status

P02 — Create the repository and data contracts — **PASS**

## Files changed

- `pyproject.toml`
- `.gitignore`
- `README.md`
- `src/smokeroom/`
- `tests/test_validate.py`
- `scripts/generate_fixtures.py`
- `fixtures/`
- `docs/schema.md`
- `docs/grokbot-progress.md`

## Commands and results

- `python3 scripts/generate_fixtures.py` wrote the noiseless, noisy, invalid, and oracle files. Noiseless indoor value at 01:00 is `25.616722965469` µg/m³.
- `python3 -m venv .venv` required the `python3.12-venv` package, which was installed from Ubuntu archives. `.venv/bin/pip install -e ".[dev]"` installed NumPy 1.26.4, SciPy 1.14.1, and pytest 8.3.4.
- `.venv/bin/python -m smokeroom validate --measurements fixtures/noiseless/measurements.csv --config fixtures/noiseless/config.json` exited 0. Summary status `accepted`, 7 rows, no flags.
- The same command on `fixtures/invalid/negative_indoor.csv` exited 2. Standard error: `negative_concentration: row 2 indoor_pm25_ug_m3 is -1.5 ug/m3; concentrations must be >= 0`.
- The noisy trial exited 0 with flags `absent_sensor`, `timezone_offset`, `channel_disagree`, and `duplicate_timestamp`.
- `.venv/bin/pytest`: 6 passed before the P03 tests were added.

## Artifact paths

- `fixtures/noiseless/measurements.csv`
- `fixtures/noiseless/config.json`
- `fixtures/noisy/measurements.csv`
- `fixtures/noisy/config.json`
- `fixtures/invalid/negative_indoor.csv`
- `fixtures/invalid/config.json`
- `fixtures/oracle/noiseless.md`
- `fixtures/oracle/noiseless_steps.json`
- `fixtures/MANIFEST.json`

## Open issues

- None from P02. The solver was only a single tested step until P03.

## Next phase

P03 — Build the working core.

## Phase and status

P01 — Research overlap and confirm the MVP — **PASS**

## Files changed

- `docs/overlap.md`
- `docs/project-contract.md`
- `docs/grokbot-progress.md`

## Commands and results

- GitHub repository search `wildfire indoor PM2.5 mass balance validation paired sensor held out calibration`: `total_count` 0.
- GitHub repository search `indoor wildfire smoke filtration PM2.5 residual sensor uncertainty`: `total_count` 0.
- `git clone --depth 1 https://github.com/AnwarDebes/SmokeShield.git /tmp/SmokeShield` succeeded. HEAD `53b61644e504b6a7d2be28155f0abc34ddcee5bb`.
- PyPI JSON for `smokeshield`, `contam`, `indoor-pm25`, and `pm25-mass-balance`: HTTP 404.
- Shared-fixture probe (`PYTHONPATH=/tmp/SmokeShield`, Python 3.12.3, NumPy 1.26.4): decay max absolute error `1.1102230246251565e-16`; steady state `16.3265306122449` on both the library and the independent quotient.
- Source token scan of SmokeShield `*.py`: no `csv`, `held_out`, `timezone`, `quality_flag`, `mae`, `bias`, or `residual`.
- Downloaded `https://www.nist.gov/document/contam-x-3403-linux-64bittargz`. SHA-256 `3612798dff9a4f1ea4f0279c4c7b526b244b88875dea425fafd868f3570df4fa` matches the NIST page. `contamx3 -v` printed `3.4.0.3 64 bit`.
- Downloaded tutorial zip `https://www.nist.gov/document/introtocontam-part1-6zip`. `contamx3 demo1-filt.prj` failed with `Could not open file demo-3day.ctm` until that file was linked from `Weather/`, then exit code 0 and `demo1-filt.sim` was written. PM2.5 in `demo-3day.ctm` is a mass ratio (first value `1.268E-08`), not a µg/m³ sensor CSV.
- BERG repository and AirCalibrate were inspected through GitHub metadata and README text only.

## Artifact paths

- `docs/overlap.md`
- `docs/project-contract.md`
- Probe clones and NIST binaries stayed in `/tmp` and are not part of this repository.

## Open issues

- A CONTAM `.prj` with the exact shared rates was not authored. ContamW is Windows-only. This does not block the MVP: the tutorial run already shows different inputs, units, and outputs.
- BERG README terms conflict with the GitHub MIT metadata. Those scripts are not a dependency.

## Next phase

P02 — Create the repository and data contracts.
