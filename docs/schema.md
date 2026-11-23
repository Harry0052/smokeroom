# Schema 1

SmokeRoom reads a measurements CSV and a trial JSON file. Both are
version `1`. Concentrations are PM2.5 in µg/m³ (`ug/m3` in the files).
Rates are h⁻¹. Volume is m³. This schema does not represent a room-safety
rating.

## Measurements

Header, in order:

```text
timestamp,indoor_pm25_ug_m3,outdoor_pm25_ug_m3,indoor_quality,outdoor_quality
```

- `timestamp`: ISO-8601 with an explicit offset. `Z` is accepted as UTC.
  A missing offset is `timezone_naive` and rejects the file. A non-zero
  offset is accepted and flagged `timezone_offset` after the instant is
  converted to UTC.
- Concentrations: finite numbers from the trial's minimum through its
  maximum, which cannot exceed 0 to 10000 µg/m³. A negative value rejects
  the file as `negative_concentration`. A blank cell is allowed only when
  that side's quality is `missing`.
- Quality tokens: `ok`, `missing`, `channel_disagree`.

Row flags, which do not by themselves reject a file:

| Flag | Meaning |
| --- | --- |
| `absent_sensor` | Indoor or outdoor value is missing |
| `channel_disagree` | The declared sensor channels disagree |
| `timezone_offset` | The timestamp offset is not UTC |
| `duplicate_timestamp` | The same UTC instant already appeared |

## Trial JSON

Required fields:

| Field | Constraint |
| --- | --- |
| `schema_version` | `"1"` |
| `trial_id` | Non-empty string |
| `timezone` | `"UTC"` |
| `room_volume_m3` | Greater than 0 and at most 10000 |
| `initial_indoor_ug_m3` | 0 to 10000 |
| `parameters.penetration` | 0 to 1 |
| `parameters.air_exchange_per_h` | 0 to 20 |
| `parameters.deposition_per_h` | 0 to 20 |
| `parameter_bounds` | Inclusive bounds for those three parameters and `filtration_per_h` |
| `fit_parameters` | Non-empty subset of the three physical parameters. Filtration is declared, not fitted |
| `filtration_schedule` | Contiguous half-open intervals covering the first timestamp through the last |
| `calibration_end` | Aware timestamp that leaves both segments non-empty. Rows earlier than this instant are calibration |
| `limits.max_rows` | Integer from 2 through 10000 |
| `limits.max_bytes` | Integer from 1 through 2000000 |
| `limits.min_concentration_ug_m3` / `max_concentration_ug_m3` | Inside 0 to 10000 |

## Error categories

`schema_version`, `missing_column`, `unexpected_column`, `bad_timestamp`,
`timezone_naive`, `negative_concentration`, `concentration_out_of_bounds`,
`non_numeric`, `unknown_quality_flag`, `inconsistent_quality`,
`oversized_input`, `invalid_parameter`, `schedule_gap`, `schedule_overlap`.

The `validate` command prints `category: message` on standard error and
exits 2. An accepted trial prints a JSON summary on standard output and
exits 0.

## Run result

`smokeroom run` writes `result.json` and `summary.txt`. Both use the rows
from this schema. A row is eligible for fitting and for held-out MAE, bias,
and usable fraction when both concentrations are present, the prediction
was produced, and the flags do not include `absent_sensor`,
`channel_disagree`, or `duplicate_timestamp`. A `timezone_offset` row stays
eligible after conversion to UTC.

`prediction_state` is `ok`, `missing_observation` (prediction exists, indoor
value does not), `unavailable_input` (an earlier outdoor value was missing,
so the state cannot advance), or `duplicate`.

The fit uses only eligible calibration rows after the first instant.
`fit.status` is `fitted`, `unidentifiable`, or `insufficient`. Held-out
metrics report MAE, bias (observed minus predicted), and usable fraction
together. `conclusion` is `weak` when coverage is below 0.8, a parameter
set is not identified, or an eligible absolute residual exceeds 10 µg/m³.
That 10 µg/m³ figure is a comparison weakness mark, not a safety category.
