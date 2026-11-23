"""Fit and score a loaded trial. File paths stay outside this module."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
from scipy.optimize import least_squares

from smokeroom.model import step_concentration

# A grid point this close, relatively, to the best calibration SSE is another
# plausible parameter choice. Distance is measured after scaling each fitted
# parameter by its declared bound width.
SIMILAR_SSE_FRACTION = 0.01
SIMILAR_SSE_FLOOR = 1e-4
DISTINCT_PARAMETER_DISTANCE = 0.05
# Comparison weakness only. This is not a health or safety threshold.
WEAK_RESIDUAL_UG_M3 = 10.0
WEAK_USABLE_FRACTION = 0.8


def evaluate_trial(loaded: dict) -> dict:
    """Return a schema-1 result for one loaded trial."""
    config = loaded["config"]
    declared = dict(config["parameters"])
    fit = _fit(loaded)
    parameters = dict(declared)
    parameters.update(fit["parameters"])
    timeline = _timeline(loaded, parameters)
    rows = [_result_row(row, timeline) for row in loaded["rows"]]
    metrics = _held_out_metrics(rows)
    incomplete = any(
        row["prediction_state"] in {"missing_observation", "unavailable_input"}
        for row in rows
    )
    reasons = _weak_reasons(fit, metrics, rows)
    return {
        "schema_version": "1",
        "status": "incomplete" if incomplete else "complete",
        "conclusion": "weak" if reasons else "supported",
        "weak_reasons": reasons,
        "trial_id": config["trial_id"],
        "units": {
            "concentration": "ug/m3",
            "rate": "1/h",
            "volume": "m3",
            "time": "h",
        },
        "limitations": [
            "Modeled concentration is not a room-safety rating and is not a stay-or-leave instruction.",
            "Filtration differences are conditional on the declared schedule and the one-zone mass balance.",
            "Indoor sources are not estimated. A spike that the balance cannot explain stays in the residual.",
            "Predictions use only the outdoor value at the start of each interval, so later samples do not leak backward.",
        ],
        "declared_parameters": {
            "penetration": declared["penetration"],
            "air_exchange_per_h": declared["air_exchange_per_h"],
            "deposition_per_h": declared["deposition_per_h"],
            "initial_indoor_ug_m3": config["initial_indoor_ug_m3"],
            "room_volume_m3": config["room_volume_m3"],
        },
        "fit": fit,
        "parameters_used": {
            "penetration": parameters["penetration"],
            "air_exchange_per_h": parameters["air_exchange_per_h"],
            "deposition_per_h": parameters["deposition_per_h"],
        },
        "metrics": {"held_out": metrics},
        "rows": rows,
    }


def _fit(loaded: dict) -> dict:
    config = loaded["config"]
    names = list(config["fit_parameters"])
    declared = config["parameters"]
    bounds = config["parameter_bounds"]
    targets = _predictable(_calibration_targets(loaded), loaded, declared)
    base = {
        "parameters": {name: declared[name] for name in names},
        "objective_sse": None,
        "calibration_row_numbers": [row["row"] for row in targets],
        "alternatives": [],
    }
    if len(targets) < len(names):
        return {
            **base,
            "status": "insufficient",
            "detail": (
                f"{len(targets)} eligible calibration rows remain after the "
                f"initial instant; fitting {len(names)} parameters needs at least that many"
            ),
        }
    start = np.array([declared[name] for name in names], dtype=float)
    lower = np.array([bounds[name][0] for name in names], dtype=float)
    upper = np.array([bounds[name][1] for name in names], dtype=float)
    fitted = least_squares(
        lambda vector: _residuals(loaded, names, vector, targets),
        start,
        bounds=(lower, upper),
        method="trf",
        xtol=1e-12,
        ftol=1e-12,
        gtol=1e-12,
    )
    best = np.clip(fitted.x, lower, upper)
    best_sse = float(np.sum(np.square(_residuals(loaded, names, best, targets))))
    alternatives = _alternatives(loaded, names, targets, best, best_sse, lower, upper)
    status = "unidentifiable" if alternatives else "fitted"
    return {
        "status": status,
        "parameters": {name: float(value) for name, value in zip(names, best)},
        "objective_sse": best_sse,
        "calibration_row_numbers": [row["row"] for row in targets],
        "alternatives": alternatives,
        "detail": (
            "More than one parameter choice matches the calibration rows nearly as well."
            if alternatives
            else "One parameter choice is distinguished on the calibration rows."
        ),
    }


def _predictable(rows: list[dict], loaded: dict, parameters: dict) -> list[dict]:
    timeline = _timeline(loaded, parameters)
    return [
        row
        for row in rows
        if timeline[row["utc"]]["predicted_ug_m3"] is not None
    ]


def _calibration_targets(loaded: dict) -> list[dict]:
    earliest = min(row["utc"] for row in loaded["rows"])
    return [
        row
        for row in loaded["rows"]
        if row["segment"] == "calibration"
        and row["utc"] != earliest
        and _eligible(row)
    ]


def _eligible(row: dict) -> bool:
    blocked = {"absent_sensor", "channel_disagree", "duplicate_timestamp"}
    return (
        row["indoor_ug_m3"] is not None
        and row["outdoor_ug_m3"] is not None
        and not blocked.intersection(row["flags"])
    )


def _residuals(loaded: dict, names: list[str], vector: np.ndarray, targets: list[dict]) -> np.ndarray:
    parameters = dict(loaded["config"]["parameters"])
    parameters.update(zip(names, (float(value) for value in vector)))
    timeline = _timeline(loaded, parameters)
    values = []
    for row in targets:
        predicted = timeline[row["utc"]]["predicted_ug_m3"]
        values.append(row["indoor_ug_m3"] - predicted)
    return np.asarray(values, dtype=float)


def _alternatives(
    loaded: dict,
    names: list[str],
    targets: list[dict],
    best: np.ndarray,
    best_sse: float,
    lower: np.ndarray,
    upper: np.ndarray,
) -> list[dict]:
    widths = np.maximum(upper - lower, 1e-9)
    found = []
    grid = [np.linspace(low, high, 7) for low, high in zip(lower, upper)]
    for point in np.ndindex(tuple(len(axis) for axis in grid)):
        vector = np.array([axis[index] for axis, index in zip(grid, point)], dtype=float)
        distance = float(np.linalg.norm((vector - best) / widths))
        if distance <= DISTINCT_PARAMETER_DISTANCE:
            continue
        sse = float(np.sum(np.square(_residuals(loaded, names, vector, targets))))
        if sse <= best_sse * (1.0 + SIMILAR_SSE_FRACTION) + SIMILAR_SSE_FLOOR:
            found.append(
                {
                    "parameters": {
                        name: float(value) for name, value in zip(names, vector)
                    },
                    "objective_sse": sse,
                }
            )
    found.sort(key=lambda item: (item["objective_sse"], _parameter_key(item["parameters"])))
    return found[:5]


def _parameter_key(parameters: dict) -> tuple:
    return tuple(parameters[name] for name in sorted(parameters))


def _timeline(loaded: dict, parameters: dict) -> dict[datetime, dict]:
    config = loaded["config"]
    unique: dict[datetime, dict] = {}
    for row in loaded["rows"]:
        unique.setdefault(row["utc"], row)
    times = sorted(unique)
    state: dict[datetime, dict] = {}
    concentration = config["initial_indoor_ug_m3"]
    blocked_after = False
    for index, instant in enumerate(times):
        if blocked_after:
            state[instant] = {"predicted_ug_m3": None, "prediction_state": "unavailable_input"}
            continue
        state[instant] = {"predicted_ug_m3": concentration, "prediction_state": "ok"}
        if index == len(times) - 1:
            continue
        outdoor = unique[instant]["outdoor_ug_m3"]
        if outdoor is None:
            blocked_after = True
            continue
        following = times[index + 1]
        dt_hours = (following - instant).total_seconds() / 3600.0
        concentration = step_concentration(
            concentration,
            outdoor,
            dt_hours,
            parameters["penetration"],
            parameters["air_exchange_per_h"],
            parameters["deposition_per_h"],
            _filtration(config, instant),
        )
    return state


def _filtration(config: dict, instant: datetime) -> float:
    for interval in config["filtration_schedule"]:
        if interval["start"].astimezone(timezone.utc) <= instant < interval["end"].astimezone(timezone.utc):
            return interval["filtration_per_h"]
    raise RuntimeError(f"no filtration interval contains {instant.isoformat()}")


def _result_row(row: dict, timeline: dict[datetime, dict]) -> dict:
    predicted_info = timeline[row["utc"]]
    predicted = predicted_info["predicted_ug_m3"]
    duplicate = "duplicate_timestamp" in row["flags"]
    if predicted is None:
        prediction_state = "unavailable_input"
        residual = None
    elif duplicate:
        prediction_state = "duplicate"
        residual = None if row["indoor_ug_m3"] is None else row["indoor_ug_m3"] - predicted
    elif row["indoor_ug_m3"] is None:
        prediction_state = "missing_observation"
        residual = None
    else:
        prediction_state = "ok"
        residual = row["indoor_ug_m3"] - predicted
    return {
        "row": row["row"],
        "timestamp": row["timestamp_text"],
        "segment": row["segment"],
        "indoor_ug_m3": row["indoor_ug_m3"],
        "outdoor_ug_m3": row["outdoor_ug_m3"],
        "predicted_ug_m3": predicted,
        "residual_ug_m3": residual,
        "prediction_state": prediction_state,
        "eligible": _eligible(row) and predicted is not None and not duplicate,
        "flags": list(row["flags"]),
    }


def _held_out_metrics(rows: list[dict]) -> dict:
    held_out = [row for row in rows if row["segment"] == "evaluation"]
    eligible = [row for row in held_out if row["eligible"]]
    usable = (len(eligible) / len(held_out)) if held_out else 0.0
    if not eligible:
        return {
            "n_rows": len(held_out),
            "n_eligible": 0,
            "usable_fraction": usable,
            "mae_ug_m3": None,
            "bias_ug_m3": None,
            "state": "insufficient",
        }
    residuals = [row["residual_ug_m3"] for row in eligible]
    return {
        "n_rows": len(held_out),
        "n_eligible": len(eligible),
        "usable_fraction": usable,
        "mae_ug_m3": float(sum(abs(value) for value in residuals) / len(residuals)),
        "bias_ug_m3": float(sum(residuals) / len(residuals)),
        "state": "complete",
    }


def _weak_reasons(fit: dict, metrics: dict, rows: list[dict]) -> list[str]:
    reasons = []
    if fit["status"] == "insufficient":
        reasons.append("Calibration does not identify the requested parameters.")
    if fit["status"] == "unidentifiable":
        reasons.append("Several parameter choices fit the calibration rows similarly.")
    if metrics["state"] != "complete":
        reasons.append("The held-out segment has no eligible paired observations.")
    elif metrics["usable_fraction"] < WEAK_USABLE_FRACTION:
        reasons.append(
            "Held-out usable fraction is "
            f"{metrics['usable_fraction']:.3f}, below {WEAK_USABLE_FRACTION:.3f}."
        )
    peak = max(
        (abs(row["residual_ug_m3"]) for row in rows if row["eligible"]),
        default=0.0,
    )
    if peak > WEAK_RESIDUAL_UG_M3:
        reasons.append(
            "An eligible absolute residual exceeds "
            f"{WEAK_RESIDUAL_UG_M3:.1f} ug/m3. That marks a weak model comparison, "
            "not a safety category."
        )
    return reasons
