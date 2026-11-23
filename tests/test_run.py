"""Core success and failure cases for the public run command."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from smokeroom.analysis import evaluate_trial
from smokeroom.validate import load_trial

ROOT = Path(__file__).resolve().parents[1]
NOISELESS = ROOT / "fixtures" / "noiseless"
NOISY = ROOT / "fixtures" / "noisy"
INVALID = ROOT / "fixtures" / "invalid"


def test_noiseless_run_matches_oracle(tmp_path: Path) -> None:
    result = _run(NOISELESS, tmp_path / "noiseless")
    oracle = json.loads(
        (ROOT / "fixtures" / "oracle" / "noiseless_steps.json").read_text(
            encoding="utf-8"
        )
    )
    assert result["status"] == "complete"
    assert result["conclusion"] == "supported"
    assert result["fit"]["status"] == "fitted"
    assert result["parameters_used"]["penetration"] == pytest.approx(0.8, abs=1e-6)
    assert result["parameters_used"]["deposition_per_h"] == pytest.approx(0.2, abs=1e-6)
    assert result["parameters_used"]["air_exchange_per_h"] == pytest.approx(
        0.5, abs=1e-12
    )
    indoors = [float(step["indoor_ug_m3"]) for step in oracle["steps"]]
    predicted = [row["predicted_ug_m3"] for row in result["rows"]]
    assert predicted == pytest.approx(indoors, abs=1e-6, rel=1e-6)
    metrics = result["metrics"]["held_out"]
    assert metrics["n_eligible"] == metrics["n_rows"] == 3
    assert metrics["usable_fraction"] == pytest.approx(1.0)
    assert metrics["mae_ug_m3"] == pytest.approx(0.0, abs=1e-6)
    assert metrics["bias_ug_m3"] == pytest.approx(0.0, abs=1e-6)
    summary = (tmp_path / "noiseless" / "summary.txt").read_text(encoding="utf-8")
    assert "eligible=True" in summary
    assert str(tmp_path / "noiseless" / "result.json") in summary


def test_noisy_run_marks_gap_and_spike_without_using_holdout(tmp_path: Path) -> None:
    original = _run(NOISY, tmp_path / "noisy")
    by_row = {row["row"]: row for row in original["rows"]}
    assert by_row[3]["prediction_state"] == "missing_observation"
    assert by_row[3]["residual_ug_m3"] is None
    assert by_row[3]["eligible"] is False
    assert by_row[7]["segment"] == "evaluation"
    assert by_row[7]["residual_ug_m3"] > 20.0
    assert all(
        row["segment"] == "calibration"
        for row in original["rows"]
        if row["row"] in original["fit"]["calibration_row_numbers"]
    )
    metrics = original["metrics"]["held_out"]
    assert metrics["n_rows"] == 3
    assert metrics["n_eligible"] == 2
    assert {
        metrics["mae_ug_m3"],
        metrics["bias_ug_m3"],
        metrics["usable_fraction"],
    } <= set(metrics.values())
    assert original["conclusion"] == "weak"

    changed = tmp_path / "changed"
    _copy_trial(NOISY, changed)
    _replace_indoor(changed / "measurements.csv", row_number=7, indoor="90.0")
    rerun = evaluate_trial(
        load_trial(changed / "measurements.csv", changed / "config.json")
    )
    assert rerun["fit"]["parameters"] == original["fit"]["parameters"]
    assert rerun["rows"][6]["residual_ug_m3"] != pytest.approx(
        original["rows"][6]["residual_ug_m3"]
    )


def test_run_rejects_negative_fixture(tmp_path: Path) -> None:
    completed = _cli(
        INVALID / "negative_indoor.csv",
        INVALID / "config.json",
        tmp_path / "invalid",
    )
    assert completed.returncode == 2
    assert completed.stderr.startswith("negative_concentration:")
    assert not (tmp_path / "invalid" / "result.json").exists()


def test_missing_outdoor_stops_later_predictions(tmp_path: Path) -> None:
    trial = tmp_path / "trial"
    _copy_trial(NOISELESS, trial)
    rows = list(csv.DictReader((trial / "measurements.csv").open(encoding="utf-8")))
    rows[2]["outdoor_pm25_ug_m3"] = ""
    rows[2]["outdoor_quality"] = "missing"
    _write_rows(trial / "measurements.csv", rows)
    result = evaluate_trial(
        load_trial(trial / "measurements.csv", trial / "config.json")
    )
    states = [row["prediction_state"] for row in result["rows"]]
    assert states[2] == "ok"
    assert states[3] == "unavailable_input"
    assert result["status"] == "incomplete"


def _run(directory: Path, output: Path) -> dict:
    completed = _cli(
        directory / "measurements.csv",
        directory / "config.json",
        output,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads((output / "result.json").read_text(encoding="utf-8"))


def _copy_trial(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "measurements.csv").write_text(
        (source / "measurements.csv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (destination / "config.json").write_text(
        (source / "config.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )


def _replace_indoor(path: Path, row_number: int, indoor: str) -> None:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    rows[row_number - 1]["indoor_pm25_ug_m3"] = indoor
    _write_rows(path, rows)


def _write_rows(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _cli(
    measurements: Path, config: Path, output: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "smokeroom",
            "run",
            "--measurements",
            str(measurements),
            "--config",
            str(config),
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
