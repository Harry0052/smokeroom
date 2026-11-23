"""Parse and check a schema-1 trial without solving the mass balance."""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from smokeroom.errors import ContractError
from smokeroom.schema import (
    FIT_PARAMETER_NAMES,
    HARD_MAX_BYTES,
    HARD_MAX_CONCENTRATION_UG_M3,
    HARD_MAX_RATE_PER_H,
    HARD_MAX_ROWS,
    HARD_MAX_VOLUME_M3,
    MEASUREMENT_COLUMNS,
    QUALITY_FLAGS,
    SCHEMA_VERSION,
)


def load_trial(measurements_path: Path, config_path: Path) -> dict:
    """Load a schema-1 trial or raise ``ContractError``."""
    config = _load_config(config_path)
    limits = config["limits"]
    text = _read_limited(measurements_path, limits["max_bytes"], "measurements")
    rows = _parse_rows(text, limits)
    _check_schedule_covers_rows(config, rows)
    flagged = _annotate(config, rows)
    calibration = [row for row in flagged if row["segment"] == "calibration"]
    evaluation = [row for row in flagged if row["segment"] == "evaluation"]
    if not calibration or not evaluation:
        raise ContractError(
            "invalid_parameter",
            "calibration_end must leave at least one row in the calibration "
            "segment and one row in the evaluation segment",
        )
    return {
        "config": config,
        "rows": flagged,
        "measurements_path": str(measurements_path),
        "config_path": str(config_path),
    }


def validate_trial(measurements_path: Path, config_path: Path) -> dict:
    """Accept a trial or raise ``ContractError`` with a stable category."""
    loaded = load_trial(measurements_path, config_path)
    rows = loaded["rows"]
    calibration = [row for row in rows if row["segment"] == "calibration"]
    evaluation = [row for row in rows if row["segment"] == "evaluation"]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "accepted",
        "trial_id": loaded["config"]["trial_id"],
        "units": {
            "concentration": "ug/m3",
            "rate": "1/h",
            "volume": "m3",
            "time": "h",
        },
        "n_rows": len(rows),
        "n_calibration_rows": len(calibration),
        "n_evaluation_rows": len(evaluation),
        "row_flags": [
            {
                "row": row["row"],
                "timestamp": row["timestamp_text"],
                "flags": row["flags"],
            }
            for row in rows
            if row["flags"]
        ],
    }


def _load_config(path: Path) -> dict:
    raw = _read_limited(path, HARD_MAX_BYTES, "config")
    try:
        config = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractError(
            "schema_version",
            f"config is not JSON ({exc.msg} at line {exc.lineno})",
        ) from exc
    if not isinstance(config, dict):
        raise ContractError("schema_version", "config must be a JSON object")
    if config.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(
            "schema_version",
            f"schema_version must be {SCHEMA_VERSION!r}; "
            f"got {config.get('schema_version')!r}",
        )
    trial_id = config.get("trial_id")
    if not isinstance(trial_id, str) or not trial_id.strip():
        raise ContractError("invalid_parameter", "trial_id must be a non-empty string")
    if config.get("timezone") != "UTC":
        raise ContractError(
            "invalid_parameter",
            "timezone must be 'UTC'; timestamps may carry other offsets "
            "and are flagged rather than shifted silently",
        )
    volume = _bounded_number(
        config.get("room_volume_m3"),
        "room_volume_m3",
        "m3",
        minimum=0.0,
        maximum=HARD_MAX_VOLUME_M3,
        inclusive_min=False,
    )
    initial = _bounded_number(
        config.get("initial_indoor_ug_m3"),
        "initial_indoor_ug_m3",
        "ug/m3",
        minimum=0.0,
        maximum=HARD_MAX_CONCENTRATION_UG_M3,
    )
    parameters = _parameters(config.get("parameters"))
    bounds = _bounds(config.get("parameter_bounds"))
    _parameters_inside_bounds(parameters, bounds)
    fit_parameters = config.get("fit_parameters")
    if not isinstance(fit_parameters, list) or not fit_parameters:
        raise ContractError(
            "invalid_parameter",
            "fit_parameters must be a non-empty list of parameter names",
        )
    unknown = [name for name in fit_parameters if name not in FIT_PARAMETER_NAMES]
    if unknown:
        raise ContractError(
            "invalid_parameter",
            "fit_parameters may only name "
            f"{', '.join(FIT_PARAMETER_NAMES)}; got {unknown!r}",
        )
    schedule = _schedule(config.get("filtration_schedule"), bounds)
    calibration_end = _parse_timestamp(config.get("calibration_end"), "calibration_end")
    limits = _limits(config.get("limits"))
    return {
        "trial_id": trial_id,
        "room_volume_m3": volume,
        "initial_indoor_ug_m3": initial,
        "parameters": parameters,
        "parameter_bounds": bounds,
        "fit_parameters": list(fit_parameters),
        "filtration_schedule": schedule,
        "calibration_end": calibration_end,
        "limits": limits,
    }


def _parameters(value: object) -> dict:
    if not isinstance(value, dict):
        raise ContractError("invalid_parameter", "parameters must be an object")
    expected = ("penetration", "air_exchange_per_h", "deposition_per_h")
    missing = [key for key in expected if key not in value]
    if missing:
        raise ContractError(
            "invalid_parameter",
            f"parameters is missing {missing}",
        )
    return {
        "penetration": _bounded_number(
            value["penetration"], "penetration", "1", 0.0, 1.0
        ),
        "air_exchange_per_h": _bounded_number(
            value["air_exchange_per_h"],
            "air_exchange_per_h",
            "1/h",
            0.0,
            HARD_MAX_RATE_PER_H,
        ),
        "deposition_per_h": _bounded_number(
            value["deposition_per_h"],
            "deposition_per_h",
            "1/h",
            0.0,
            HARD_MAX_RATE_PER_H,
        ),
    }


def _bounds(value: object) -> dict:
    if not isinstance(value, dict):
        raise ContractError("invalid_parameter", "parameter_bounds must be an object")
    required = (*FIT_PARAMETER_NAMES, "filtration_per_h")
    parsed = {}
    for name in required:
        pair = value.get(name)
        if not isinstance(pair, list) or len(pair) != 2:
            raise ContractError(
                "invalid_parameter",
                f"parameter_bounds.{name} must be [minimum, maximum]",
            )
        low = _finite(pair[0], f"parameter_bounds.{name}[0]")
        high = _finite(pair[1], f"parameter_bounds.{name}[1]")
        if low > high:
            raise ContractError(
                "invalid_parameter",
                f"parameter_bounds.{name} minimum {low} exceeds maximum {high}",
            )
        parsed[name] = (low, high)
    if parsed["penetration"][0] < 0.0 or parsed["penetration"][1] > 1.0:
        raise ContractError(
            "invalid_parameter",
            "penetration bounds must stay inside 0 to 1 inclusive",
        )
    return parsed


def _parameters_inside_bounds(parameters: dict, bounds: dict) -> None:
    for name, value in parameters.items():
        low, high = bounds[name]
        if value < low or value > high:
            raise ContractError(
                "invalid_parameter",
                f"parameters.{name} is {value}, outside declared bounds [{low}, {high}]",
            )


def _schedule(value: object, bounds: dict) -> list[dict]:
    if not isinstance(value, list) or not value:
        raise ContractError(
            "schedule_gap",
            "filtration_schedule must contain at least one interval",
        )
    intervals = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ContractError(
                "invalid_parameter",
                f"filtration_schedule[{index}] must be an object",
            )
        start = _parse_timestamp(
            item.get("start"), f"filtration_schedule[{index}].start"
        )
        end = _parse_timestamp(item.get("end"), f"filtration_schedule[{index}].end")
        if end <= start:
            raise ContractError(
                "schedule_overlap",
                f"filtration_schedule[{index}] end must be after start",
            )
        rate = _bounded_number(
            item.get("filtration_per_h"),
            f"filtration_schedule[{index}].filtration_per_h",
            "1/h",
            0.0,
            HARD_MAX_RATE_PER_H,
        )
        low, high = bounds["filtration_per_h"]
        if rate < low or rate > high:
            raise ContractError(
                "invalid_parameter",
                f"filtration_schedule[{index}].filtration_per_h is {rate} 1/h, "
                f"outside declared bounds [{low}, {high}]",
            )
        intervals.append({"start": start, "end": end, "filtration_per_h": rate})
    intervals.sort(key=lambda item: item["start"])
    for previous, current in zip(intervals, intervals[1:]):
        if current["start"] < previous["end"]:
            raise ContractError(
                "schedule_overlap",
                "filtration intervals overlap at " f"{_iso(current['start'])}",
            )
        if current["start"] > previous["end"]:
            raise ContractError(
                "schedule_gap",
                "filtration schedule has a gap between "
                f"{_iso(previous['end'])} and {_iso(current['start'])}",
            )
    return intervals


def _limits(value: object) -> dict:
    if not isinstance(value, dict):
        raise ContractError("invalid_parameter", "limits must be an object")
    max_rows = value.get("max_rows")
    max_bytes = value.get("max_bytes")
    if not isinstance(max_rows, int) or isinstance(max_rows, bool) or max_rows < 2:
        raise ContractError(
            "invalid_parameter",
            "limits.max_rows must be an integer >= 2",
        )
    if max_rows > HARD_MAX_ROWS:
        raise ContractError(
            "oversized_input",
            f"limits.max_rows {max_rows} exceeds the hard cap of {HARD_MAX_ROWS}",
        )
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 1:
        raise ContractError(
            "invalid_parameter",
            "limits.max_bytes must be a positive integer",
        )
    if max_bytes > HARD_MAX_BYTES:
        raise ContractError(
            "oversized_input",
            f"limits.max_bytes {max_bytes} exceeds the hard cap of {HARD_MAX_BYTES}",
        )
    minimum = _finite(
        value.get("min_concentration_ug_m3"),
        "limits.min_concentration_ug_m3",
    )
    maximum = _finite(
        value.get("max_concentration_ug_m3"),
        "limits.max_concentration_ug_m3",
    )
    if minimum < 0.0 or maximum > HARD_MAX_CONCENTRATION_UG_M3 or minimum > maximum:
        raise ContractError(
            "invalid_parameter",
            "concentration limits must satisfy 0 <= minimum <= maximum "
            f"<= {HARD_MAX_CONCENTRATION_UG_M3} ug/m3",
        )
    return {
        "max_rows": max_rows,
        "max_bytes": max_bytes,
        "min_concentration_ug_m3": minimum,
        "max_concentration_ug_m3": maximum,
    }


def _parse_rows(text: str, limits: dict) -> list[dict]:
    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None:
        raise ContractError("missing_column", "measurements CSV has no header")
    fields = list(reader.fieldnames)
    if fields != list(MEASUREMENT_COLUMNS):
        missing = [name for name in MEASUREMENT_COLUMNS if name not in fields]
        unexpected = [name for name in fields if name not in MEASUREMENT_COLUMNS]
        if missing:
            raise ContractError(
                "missing_column",
                "measurements CSV is missing "
                + ", ".join(missing)
                + "; expected "
                + ", ".join(MEASUREMENT_COLUMNS),
            )
        raise ContractError(
            "unexpected_column",
            "measurements CSV has unexpected columns "
            + ", ".join(unexpected)
            + "; expected "
            + ", ".join(MEASUREMENT_COLUMNS),
        )
    rows = []
    for row_number, raw in enumerate(reader, start=1):
        if row_number > limits["max_rows"]:
            raise ContractError(
                "oversized_input",
                f"measurements exceed limits.max_rows ({limits['max_rows']})",
            )
        timestamp = _parse_timestamp(raw["timestamp"], f"row {row_number} timestamp")
        indoor, indoor_flags = _concentration(
            raw["indoor_pm25_ug_m3"],
            raw["indoor_quality"],
            row_number,
            "indoor",
            limits,
        )
        outdoor, outdoor_flags = _concentration(
            raw["outdoor_pm25_ug_m3"],
            raw["outdoor_quality"],
            row_number,
            "outdoor",
            limits,
        )
        rows.append(
            {
                "row": row_number,
                "timestamp": timestamp,
                "indoor_ug_m3": indoor,
                "outdoor_ug_m3": outdoor,
                "flags": indoor_flags + outdoor_flags,
            }
        )
    if len(rows) < 2:
        raise ContractError(
            "invalid_parameter",
            "measurements must contain at least two rows so a step can be checked",
        )
    return rows


def _concentration(
    text: str,
    quality: str,
    row_number: int,
    side: str,
    limits: dict,
) -> tuple[float | None, list[str]]:
    label = f"row {row_number} {side}"
    if quality not in QUALITY_FLAGS:
        raise ContractError(
            "unknown_quality_flag",
            f"{label}_quality must be one of {', '.join(QUALITY_FLAGS)}; got {quality!r}",
        )
    blank = text.strip() == ""
    if quality == "missing" and not blank:
        raise ContractError(
            "inconsistent_quality",
            f"{label}_quality is missing but {side}_pm25_ug_m3 is {text!r}",
        )
    if quality != "missing" and blank:
        raise ContractError(
            "inconsistent_quality",
            f"{label}_pm25_ug_m3 is blank but {side}_quality is {quality!r}; "
            "use quality 'missing' for an absent observation",
        )
    flags = ["absent_sensor"] if quality == "missing" else []
    if quality == "channel_disagree":
        flags.append("channel_disagree")
    if blank:
        return None, flags
    try:
        value = float(text)
    except ValueError as exc:
        raise ContractError(
            "non_numeric",
            f"{label}_pm25_ug_m3 is not a number ({text!r})",
        ) from exc
    if not math.isfinite(value):
        raise ContractError(
            "non_numeric",
            f"{label}_pm25_ug_m3 must be finite; got {text!r}",
        )
    if value < 0.0:
        raise ContractError(
            "negative_concentration",
            f"{label}_pm25_ug_m3 is {value} ug/m3; concentrations must be >= 0",
        )
    maximum = limits["max_concentration_ug_m3"]
    minimum = limits["min_concentration_ug_m3"]
    if value < minimum or value > maximum:
        raise ContractError(
            "concentration_out_of_bounds",
            f"{label}_pm25_ug_m3 is {value} ug/m3, outside "
            f"[{minimum}, {maximum}] ug/m3",
        )
    return value, flags


def _check_schedule_covers_rows(config: dict, rows: list[dict]) -> None:
    schedule = config["filtration_schedule"]
    first = schedule[0]["start"]
    last = schedule[-1]["end"]
    stamps = [row["timestamp"] for row in rows]
    if min(stamps) != first or max(stamps) != last:
        raise ContractError(
            "schedule_gap",
            "filtration_schedule must start at the earliest timestamp "
            f"({_iso(min(stamps))}) and end at the latest timestamp "
            f"({_iso(max(stamps))})",
        )
    for row in rows:
        stamp = row["timestamp"]
        if stamp == last:
            continue
        if not any(item["start"] <= stamp < item["end"] for item in schedule):
            raise ContractError(
                "schedule_gap",
                f"row {row['row']} timestamp {_iso(stamp)} is outside the filtration schedule",
            )


def _annotate(config: dict, rows: list[dict]) -> list[dict]:
    seen: dict[datetime, int] = {}
    annotated = []
    for row in rows:
        flags = list(row["flags"])
        stamp = row["timestamp"]
        if stamp.utcoffset() != timedelta(0):
            flags.append("timezone_offset")
        utc = stamp.astimezone(timezone.utc)
        if utc in seen:
            flags.append("duplicate_timestamp")
        else:
            seen[utc] = row["row"]
        segment = (
            "calibration"
            if utc < config["calibration_end"].astimezone(timezone.utc)
            else "evaluation"
        )
        annotated.append(
            {
                "row": row["row"],
                "timestamp": stamp,
                "timestamp_text": _iso(stamp),
                "utc": utc,
                "segment": segment,
                "indoor_ug_m3": row["indoor_ug_m3"],
                "outdoor_ug_m3": row["outdoor_ug_m3"],
                "flags": flags,
            }
        )
    return annotated


def _read_limited(path: Path, max_bytes: int, label: str) -> str:
    if not path.is_file():
        raise ContractError("invalid_parameter", f"{label} file does not exist: {path}")
    size = path.stat().st_size
    if size > max_bytes:
        raise ContractError(
            "oversized_input",
            f"{label} file is {size} bytes, above the limit of {max_bytes} bytes",
        )
    return path.read_text(encoding="utf-8")


def _parse_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ContractError("bad_timestamp", f"{label} must be an ISO-8601 string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ContractError(
            "bad_timestamp",
            f"{label} is not an ISO-8601 timestamp ({value!r})",
        ) from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ContractError(
            "timezone_naive",
            f"{label} has no timezone offset; use an explicit offset such as +00:00",
        )
    return stamp


def _bounded_number(
    value: object,
    name: str,
    unit: str,
    minimum: float,
    maximum: float,
    inclusive_min: bool = True,
) -> float:
    number = _finite(value, name)
    too_low = number < minimum or (not inclusive_min and number <= minimum)
    if too_low or number > maximum:
        raise ContractError(
            "invalid_parameter",
            f"{name} must be within {minimum} to {maximum} {unit}; got {number}",
        )
    return number


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError("non_numeric", f"{name} must be a number; got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ContractError("non_numeric", f"{name} must be finite; got {value!r}")
    return number


def _iso(stamp: datetime) -> str:
    return stamp.isoformat()
