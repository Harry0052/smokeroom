"""Public validation entry point and the independent numeric oracle."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from smokeroom.errors import ContractError
from smokeroom.model import step_concentration
from smokeroom.validate import validate_trial

ROOT = Path(__file__).resolve().parents[1]
NOISELESS = ROOT / "fixtures" / "noiseless"
NOISY = ROOT / "fixtures" / "noisy"
INVALID = ROOT / "fixtures" / "invalid"


def test_cli_accepts_noiseless_fixture() -> None:
    completed = _cli(NOISELESS / "measurements.csv", NOISELESS / "config.json")
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["status"] == "accepted"
    assert summary["trial_id"] == "noiseless"
    assert summary["n_rows"] == 7
    assert summary["row_flags"] == []
    assert summary["units"]["concentration"] == "ug/m3"


def test_cli_accepts_noisy_fixture_with_traceable_flags() -> None:
    completed = _cli(NOISY / "measurements.csv", NOISY / "config.json")
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    flags = {
        item["timestamp"]: item["flags"]
        for item in summary["row_flags"]
    }
    assert any("absent_sensor" in value for value in flags.values())
    assert any("timezone_offset" in value for value in flags.values())
    assert any("channel_disagree" in value for value in flags.values())
    assert any("duplicate_timestamp" in value for value in flags.values())


def test_cli_rejects_negative_concentration() -> None:
    completed = _cli(INVALID / "negative_indoor.csv", INVALID / "config.json")
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr.startswith(
        "negative_concentration: row 2 indoor_pm25_ug_m3 is -1.5 ug/m3"
    )


def test_naive_timestamp_is_rejected(tmp_path: Path) -> None:
    measurements = tmp_path / "measurements.csv"
    config = tmp_path / "config.json"
    measurements.write_text(
        "timestamp,indoor_pm25_ug_m3,outdoor_pm25_ug_m3,indoor_quality,outdoor_quality\n"
        "2024-01-01T00:00:00,10,20,ok,ok\n"
        "2024-01-01T01:00:00,10,20,ok,ok\n",
        encoding="utf-8",
    )
    config.write_text((INVALID / "config.json").read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ContractError) as caught:
        validate_trial(measurements, config)
    assert caught.value.category == "timezone_naive"


def test_row_cap_rejects_oversized_input(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config = json.loads((NOISELESS / "config.json").read_text(encoding="utf-8"))
    config["limits"]["max_rows"] = 2
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ContractError) as caught:
        validate_trial(NOISELESS / "measurements.csv", config_path)
    assert caught.value.category == "oversized_input"


def test_noiseless_csv_matches_independent_closed_form() -> None:
    oracle = json.loads(
        (ROOT / "fixtures" / "oracle" / "noiseless_steps.json").read_text(encoding="utf-8")
    )
    indoors = [float(step["indoor_ug_m3"]) for step in oracle["steps"]]
    concentration = 40.0
    outdoor = 20.0
    for hour in range(6):
        filtration = 0.0 if hour < 3 else 1.5
        concentration = _independent_step(concentration, outdoor, filtration)
        assert concentration == pytest.approx(indoors[hour + 1], abs=5e-10)
        assert step_concentration(
            indoors[hour],
            outdoor,
            1.0,
            0.8,
            0.5,
            0.2,
            filtration,
        ) == pytest.approx(indoors[hour + 1], abs=5e-10)
    narrative = (ROOT / "fixtures" / "oracle" / "noiseless.md").read_text(encoding="utf-8")
    assert "25.616722965469" in narrative


def _independent_step(concentration: float, outdoor: float, filtration: float) -> float:
    removal = 0.5 + 0.2 + filtration
    steady = (0.8 * 0.5 * outdoor) / removal
    return steady + (concentration - steady) * math.exp(-removal)


def _cli(measurements: Path, config: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "smokeroom",
            "validate",
            "--measurements",
            str(measurements),
            "--config",
            str(config),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
