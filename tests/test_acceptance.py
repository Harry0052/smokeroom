"""Playbook acceptance checks on the synthetic fixtures."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from smokeroom.analysis import evaluate_trial
from smokeroom.errors import ContractError
from smokeroom.model import step_concentration
from smokeroom.report import render_report
from smokeroom.validate import load_trial, validate_trial

ROOT = Path(__file__).resolve().parents[1]
NOISELESS = ROOT / "fixtures" / "noiseless"
NOISY = ROOT / "fixtures" / "noisy"


def test_zero_outdoor_decay_matches_independent_exponential() -> None:
    got = step_concentration(40.0, 0.0, 1.0, 0.8, 0.5, 0.2, 1.0)
    expected = 40.0 * math.exp(-(0.5 + 0.2 + 1.0))
    assert got == pytest.approx(expected, abs=1e-9, rel=1e-9)


def test_constant_outdoor_approaches_independent_steady_state() -> None:
    penetration = 0.8
    exchange = 0.5
    deposition = 0.2
    filtration = 1.5
    outdoor = 100.0
    removal = exchange + deposition + filtration
    steady = (penetration * exchange * outdoor) / removal
    concentration = 0.0
    for _ in range(80):
        concentration = step_concentration(
            concentration,
            outdoor,
            1.0,
            penetration,
            exchange,
            deposition,
            filtration,
        )
    assert concentration == pytest.approx(steady, abs=1e-6, rel=1e-6)


def test_quality_flags_are_traceable_on_the_noisy_trial() -> None:
    summary = validate_trial(NOISY / "measurements.csv", NOISY / "config.json")
    found = {flag for item in summary["row_flags"] for flag in item["flags"]}
    assert {"absent_sensor", "timezone_offset", "duplicate_timestamp"} <= found


def test_later_outdoor_value_does_not_change_earlier_predictions() -> None:
    outdoors = [20.0, 20.0, 20.0, 20.0]
    original = _declared_series(outdoors)
    changed = _declared_series([20.0, 20.0, 80.0, 20.0])
    assert changed[:3] == pytest.approx(original[:3], abs=1e-12)
    assert changed[3] != pytest.approx(original[3], abs=1e-4)


def test_held_out_metrics_use_only_the_eligible_rows() -> None:
    result = evaluate_trial(
        load_trial(NOISY / "measurements.csv", NOISY / "config.json")
    )
    eligible = [
        row
        for row in result["rows"]
        if row["segment"] == "evaluation" and row["eligible"]
    ]
    residuals = [row["residual_ug_m3"] for row in eligible]
    metrics = result["metrics"]["held_out"]
    assert metrics["n_eligible"] == len(eligible)
    assert metrics["n_rows"] == sum(
        row["segment"] == "evaluation" for row in result["rows"]
    )
    assert metrics["mae_ug_m3"] == pytest.approx(
        sum(abs(value) for value in residuals) / len(residuals)
    )
    assert metrics["bias_ug_m3"] == pytest.approx(sum(residuals) / len(residuals))
    report = render_report(result | {"inputs": {}, "configuration": {}})
    for row in eligible:
        assert f"{row['residual_ug_m3']:.4f}" in report
    assert "not a room-safety rating" in report
    assert f"{metrics['n_eligible']} of {metrics['n_rows']}" in report


def test_fixture_manifest_checksums_match() -> None:
    manifest = json.loads(
        (ROOT / "fixtures" / "MANIFEST.json").read_text(encoding="utf-8")
    )
    for item in manifest["files"]:
        digest = hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest()
        assert digest == item["sha256"]


def test_report_escapes_untrusted_trial_text() -> None:
    result = evaluate_trial(
        load_trial(NOISELESS / "measurements.csv", NOISELESS / "config.json")
    )
    result["trial_id"] = "<script>alert(1)</script>"
    result["inputs"] = {}
    result["configuration"] = {}
    report = render_report(result)
    assert "<script>" not in report
    assert "&lt;script&gt;" in report


def test_two_thousand_rows_finish_within_budget(tmp_path: Path) -> None:
    trial = tmp_path / "long"
    trial.mkdir()
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    count = 2000
    rows = []
    for hour in range(count):
        rows.append(
            {
                "timestamp": (start + timedelta(hours=hour)).isoformat(),
                "indoor_pm25_ug_m3": "10.0",
                "outdoor_pm25_ug_m3": "20.0",
                "indoor_quality": "ok",
                "outdoor_quality": "ok",
            }
        )
    _write_rows(trial / "measurements.csv", rows)
    config = json.loads((NOISELESS / "config.json").read_text(encoding="utf-8"))
    config["filtration_schedule"] = [
        {
            "start": rows[0]["timestamp"],
            "end": rows[-1]["timestamp"],
            "filtration_per_h": 0.3,
        }
    ]
    config["calibration_end"] = rows[count // 2]["timestamp"]
    (trial / "config.json").write_text(json.dumps(config), encoding="utf-8")
    started = time.perf_counter()
    result = evaluate_trial(
        load_trial(trial / "measurements.csv", trial / "config.json")
    )
    elapsed = time.perf_counter() - started
    assert elapsed < 5.0
    assert result["metrics"]["held_out"]["n_rows"] == count // 2


def test_concentration_above_the_declared_maximum_is_rejected(tmp_path: Path) -> None:
    trial = tmp_path / "high"
    trial.mkdir()
    (trial / "measurements.csv").write_text(
        "timestamp,indoor_pm25_ug_m3,outdoor_pm25_ug_m3,indoor_quality,outdoor_quality\n"
        "2024-01-01T00:00:00+00:00,10,20,ok,ok\n"
        "2024-01-01T01:00:00+00:00,1001,20,ok,ok\n",
        encoding="utf-8",
    )
    config = json.loads(
        (ROOT / "fixtures" / "invalid" / "config.json").read_text(encoding="utf-8")
    )
    (trial / "config.json").write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ContractError) as caught:
        validate_trial(trial / "measurements.csv", trial / "config.json")
    assert caught.value.category == "concentration_out_of_bounds"


def _declared_series(outdoors: list[float]) -> list[float]:
    concentration = 40.0
    series = [concentration]
    for hour, outdoor in enumerate(outdoors[:-1]):
        filtration = 0.0 if hour < 3 else 1.5
        concentration = step_concentration(
            concentration, outdoor, 1.0, 0.8, 0.5, 0.2, filtration
        )
        series.append(concentration)
    return series


def _write_rows(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
