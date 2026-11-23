# Overlap review

Access date: 2026-11-23.

Decision: **proceed** with a separate SmokeRoom repository.

SmokeRoom's acceptance case is a retrospective one-zone comparison: match an analytic synthetic mass balance within a declared tolerance, and on a noisy paired-sensor fixture report held-out mean absolute error (MAE), bias, and usable fraction together. Quality flags must make timezone offsets, duplicate samples, and absent observations traceable. Changing only held-out measurements must not change fitted calibration parameters.

No inspected tool already does that case. Contributing the missing workflow to an existing project would also pull in product behavior this MVP excludes (safety categories, stay-or-leave guidance, intervention ranking, or multizone airflow authoring).

## Shared comparison fixture

The same numeric case was used wherever a tool could accept it.

| Quantity | Value |
| --- | --- |
| Room volume | 50 m³ (unused by the steady equation when rates are already per hour) |
| Air exchange `a` | 0.50 h⁻¹ |
| Penetration `P` | 0.80 |
| Deposition `k_dep` | 0.25 h⁻¹ |
| Filtration | MERV-style efficiency 0.85, recirculation 4.0 h⁻¹, duty 0.50 |
| Total removal `L` | 0.50 + 0.25 + 0.85 × 4.0 × 0.50 = 2.45 h⁻¹ |
| Decay case | Outdoor PM2.5 = 0, initial indoor = 80 µg/m³, hourly steps 0 through 4 h |
| Steady case | Outdoor PM2.5 = 100 µg/m³ constant, indoor source = 0 |
| Analytic decay | `C(t) = 80 exp(-2.45 t)` µg/m³ |
| Analytic steady state | `C_ss = (0.50 × 0.80 × 100) / 2.45 = 16.3265306122449` µg/m³ |
| Acceptance metric | Absolute error ≤ 1e-6 µg/m³ on the analytic series, plus held-out MAE, bias, and usable fraction on a noisy paired series |

Independent NumPy evaluation of the closed form was the reference. No network data was fetched at comparison time.

## Capability matrix

| Capability | SmokeShield 0.1.0 | NIST CONTAM 3.4 | BERG source/sink scripts | SmokeRoom MVP |
| --- | --- | --- | --- | --- |
| One-zone PM2.5 mass balance | Yes, steady and piecewise exponential | Yes, as one zone inside a multizone project | Decay and source strength, not a paired outdoor inflow model | Required |
| Outdoor penetration × exchange × outdoor concentration | Yes | Yes, via airflow paths and a species file | Not the published workflow | Required |
| Removal by exchange, deposition, and filtration | Yes | Yes, filter elements exist | Deposition-style decay | Required |
| Import a paired indoor/outdoor sensor CSV | No | No. Species files are mass ratio, not µg/m³ CSV | Indoor time series plus plug load, not this contract | Required |
| Time alignment, duplicate, gap, and timezone flags | No | Schedules and weather files, no sensor-quality flags | Peak and background detection | Required |
| Reject negative measurements | Not exposed | Not a sensor contract | Not checked here | Required |
| Fit only on a calibration segment | No | No | Characterization is not a held-out parameter fit | Required |
| Held-out MAE, bias, and usable fraction together | No | No | Evaluation metrics are not this trio | Required |
| States when evidence is weak | Publishes ratio bands, not residual coverage | Simulation log only | Not this report | Required |
| Safety category or stay/leave guidance | Yes (AQI and mortality risk) | Exposure output can be used that way | No | Excluded |
| Runs from an ordinary Linux checkout without a GUI | Yes | Engine yes, project authoring no | Scripts yes, license conflict | Required |

## Probe outcomes

### SmokeShield

- Primary URL: https://github.com/AnwarDebes/SmokeShield
- Commit inspected: `53b61644e504b6a7d2be28155f0abc34ddcee5bb` (2026-11-05, default branch `main`)
- Release: v0.1.0 at `2557df2`
- License: CC0-1.0 (`LICENSE` in the repository). Not published on PyPI (HTTP 404 for `smokeshield` on 2026-11-23).
- Dataset terms: no bundled monitoring dataset. Validation cites published indoor/outdoor ratios. Scenario series are described as calibrated to public monitors. Not reused here.
- Evidence: **observed run** of the library on the shared fixture, plus source inspection.

Observed on Python 3.12.3 and NumPy 1.26.4, with `PYTHONPATH=/tmp/SmokeShield` (clone discarded after the probe; not vendored):

- Decay series matched `80 exp(-2.45 t)` at hours 0, 1, 2, 3, 4. Maximum absolute error `1.11e-16` µg/m³.
- Steady state from `indoor_steady_state` was `16.3265306122449` µg/m³, identical to the separate quotient.
- A 48-hour transient from 0 µg/m³ reached that same steady value.
- Repository Python sources contain none of `csv`, `held_out`, `timezone`, `quality_flag`, `mae`, `bias`, or `residual`.

Matching features: well-mixed balance, penetration, deposition, HVAC filtration, analytic piecewise step, and steady state. Missing features: paired-sensor import, quality flags, calibration/holdout split, and the acceptance metrics. The library also emits AQI and relative-mortality categories, which this MVP will not copy.

### NIST CONTAM

- Primary URL: https://www.nist.gov/publications/contam-user-guide-and-program-documentation-version-34
- Software page: https://www.nist.gov/services-resources/software/contam
- Download page accessed 2026-11-23: https://www.nist.gov/el/beed/nist-multizone-modeling/software/contam/download-contam
- Version: package 3.4.0.8 (released 2026-01-08). Linux engine file `contam-x-3.4.0.3-Linux-64bit.tar.gz`, SHA-256 `3612798dff9a4f1ea4f0279c4c7b526b244b88875dea425fafd868f3570df4fa` (matches the published hash). `contamx3 -v` printed `3.4.0.3 64 bit`.
- License: public domain (US government work, 17 USC 105), redistributable with a derivative-work notice. CVODE portions have their own notice. Not a PyPI package (HTTP 404 for `contam`).
- Dataset terms: tutorial contaminant file ships with the public tutorial zip `IntroToCONTAM-part1-6.zip`. It is a demonstration species file, not a sensor dataset. Not redistributed in SmokeRoom.
- Evidence: **observed run** of ContamX, plus the user guide. The shared analytic fixture was **not** loaded.

Observed:

- `contamx3 --help` documents a CONTAM `.prj` input. There is no CSV or sensor-flag interface.
- `demo1-filt.prj` from the public tutorial failed until `demo-3day.ctm` was linked beside the project, then completed with exit code 0 and wrote `demo1-filt.sim`.
- That project is a multizone demonstration (crawl space and first floor, four species). PM2.5 is species 4 with diameter `2.5e-6` m. The contaminant file stores PM2.5 near `1e-8`, which is a mass ratio, not µg/m³. Example first outdoor value `1.268e-08` is about 15 µg/m³ if multiplied by the project density 1.2041 kg/m³ and converted to µg.
- ContamW, which authors `.prj` files, is Windows-only. An equivalent single-room project with the shared rates was not constructed in this session.

Matching features: mass balance, filtration elements, deposition, and transient simulation. Missing features: the paired CSV contract, explicit sensor-quality flags, calibration versus held-out segments, and the MAE/bias/usable-fraction report. Units and project structure differ from the acceptance fixture, so CONTAM does not already cover the case.

### Closest additional discovery result

GitHub repository search for `wildfire indoor PM2.5 mass balance validation paired sensor held out calibration` and for `indoor wildfire smoke filtration PM2.5 residual sensor uncertainty` returned `total_count: 0` on 2026-11-23. PyPI names `indoor-pm25` and `pm25-mass-balance` returned HTTP 404.

The closest public code found from those queries is the Built Environment Research Group repository:

- Primary URL: https://github.com/berg-lab/Characterization-of-Pollutant-Sources-and-Sinks
- Commit: `7ca3e3c0c5084730ba4da44882a07d4c124d2fd8` (2025-07-26)
- GitHub license metadata: MIT
- README use terms: personal or academic use only, and redistribution or modification requires prior written permission
- Dataset: a sample of PurpleAir and plug-load data is in the repository. Terms for redistribution are not stated separately from the README restriction.
- Evidence: **documentation only**. The code was not executed. The README/license conflict and the household sample make a local run a poor comparison, and the tool identifies peaks, background periods, and indoor source strength rather than scoring a declared filtration schedule on held-out paired sensors.

A second nearby project, https://github.com/xiangchen-stat/AirCalibrate (pushed 2021-09-06, no GitHub license, R, PurpleAir-versus-EPA calibration), reports held-out sensor error but does not implement a room filtration mass balance. It was not run. The repository is very large and its monitoring data are outside this synthetic-fixture scope.

Literature checked as context, not as runnable tools: Liang et al. indoor mass balance during wildfire episodes (PMC8026580) and the AAQR 2021 paired PurpleAir filtration note. Those papers support the equation form. Their measurements are not bundled.

## Remaining uncertainties

- CONTAM can represent a single well-mixed zone, but this session did not author a `.prj` with the shared rates. The unit conversion from mass ratio to µg/m³ was checked only on the tutorial file's first outdoor sample and the project density.
- BERG GitHub metadata and the README disagree on redistribution. Treat the stricter README as the operative restriction until the authors state otherwise.
- SmokeShield's MERV efficiency table is an approximation. The probe used the code's MERV 13 value 0.85 so both sides shared `L = 2.45`. SmokeRoom will take filtration rate as an explicit input instead of copying that table.
- No public package already pins this acceptance metric. That absence is a search result from 2026-11-23, not a proof that no private tool exists.

## Decision

**Proceed.** Build SmokeRoom as a small Python, NumPy, and SciPy library with a local HTML report. Bundle original synthetic trials only. Keep the mass-balance step independently testable. Do not integrate SmokeShield, CONTAM, or the BERG scripts into the runtime. Do not add safety ratings, exposure prescriptions, or multizone airflow.

The fixture provenance path is viable: equations are standard and re-derived in this repository, traces are generated locally from a fixed seed, and the runtime does not download monitors or third-party binaries.
