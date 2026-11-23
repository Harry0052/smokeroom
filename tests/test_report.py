"""User-facing save, load, help, and HTML report."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOISELESS = ROOT / "fixtures" / "noiseless"
NOISY = ROOT / "fixtures" / "noisy"
INVALID = ROOT / "fixtures" / "invalid"


def test_help_exits_zero() -> None:
    completed = _command(["--help"])
    assert completed.returncode == 0
    assert "validate" in completed.stdout
    assert "run" in completed.stdout
    assert "show" in completed.stdout
    assert completed.stderr == ""


def test_demo_save_load_and_html(tmp_path: Path) -> None:
    output = tmp_path / "demo"
    completed = _command(
        [
            "run",
            "--measurements",
            str(NOISELESS / "measurements.csv"),
            "--config",
            str(NOISELESS / "config.json"),
            "--output",
            str(output),
        ]
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.startswith("{")
    assert completed.stderr.startswith("diagnostic: conclusion=supported")
    saved = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert saved["configuration"]["filtration_schedule"][1]["filtration_per_h"] == 1.5
    html = (output / "report.html").read_text(encoding="utf-8")
    assert 'href="#findings"' in html
    assert 'aria-live="polite"' in html
    assert saved["inputs"]["measurements_sha256"] in html
    loaded = _command(["show", str(output / "result.json")])
    assert loaded.returncode == 0, loaded.stderr
    assert "trial: noiseless" in loaded.stdout
    assert "residual_ug_m3=" in loaded.stdout
    assert loaded.stderr.startswith("diagnostic:")


def test_noisy_report_shows_gap_and_spike(tmp_path: Path) -> None:
    output = tmp_path / "noisy"
    completed = _command(
        [
            "run",
            "--measurements",
            str(NOISY / "measurements.csv"),
            "--config",
            str(NOISY / "config.json"),
            "--output",
            str(output),
        ]
    )
    assert completed.returncode == 0, completed.stderr
    html = (output / "report.html").read_text(encoding="utf-8")
    assert "missing_observation" in html
    assert "29.9399" in html
    assert "Held-out usable fraction is" in html
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    eligible_rows = [row["row"] for row in result["rows"] if row["eligible"]]
    for row_number in eligible_rows:
        assert f"<td>{row_number}</td>" in html


def test_malformed_run_explains_the_rejection(tmp_path: Path) -> None:
    completed = _command(
        [
            "run",
            "--measurements",
            str(INVALID / "negative_indoor.csv"),
            "--config",
            str(INVALID / "config.json"),
            "--output",
            str(tmp_path / "bad"),
        ]
    )
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "negative_concentration:" in completed.stderr
    assert "ug/m3" in completed.stderr
    assert not (tmp_path / "bad").exists()


def _command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "smokeroom", *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
