# Grokbot progress

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
