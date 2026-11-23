"""Write the bundled synthetic trials.

The noiseless indoor column is the closed-form step, not a fit. The noisy
trial starts from that series, adds deterministic Gaussian noise from seed
20241123, then applies the documented gaps and spike. Run from the
repository root:

    python3 scripts/generate_fixtures.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = 20241123
START = datetime(2024, 1, 1, tzinfo=timezone.utc)
HOURS = 6
PENETRATION = 0.8
AIR_EXCHANGE_PER_H = 0.5
DEPOSITION_PER_H = 0.2
OUTDOOR = 20.0
INITIAL = 40.0

HEADER = [
    "timestamp",
    "indoor_pm25_ug_m3",
    "outdoor_pm25_ug_m3",
    "indoor_quality",
    "outdoor_quality",
]


def step(concentration: float, outdoor: float, filtration: float) -> float:
    removal = AIR_EXCHANGE_PER_H + DEPOSITION_PER_H + filtration
    steady = (PENETRATION * AIR_EXCHANGE_PER_H * outdoor) / removal
    return steady + (concentration - steady) * math.exp(-removal)


def filtration_at(hour: int) -> float:
    return 0.0 if hour < 3 else 1.5


def base_series() -> list[dict]:
    concentration = INITIAL
    rows = []
    for hour in range(HOURS + 1):
        rows.append(
            {
                "timestamp": START + timedelta(hours=hour),
                "indoor": concentration,
                "outdoor": OUTDOOR,
                "indoor_quality": "ok",
                "outdoor_quality": "ok",
            }
        )
        if hour < HOURS:
            concentration = step(concentration, OUTDOOR, filtration_at(hour))
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            indoor = "" if row["indoor"] is None else f"{row['indoor']:.12f}"
            outdoor = "" if row["outdoor"] is None else f"{row['outdoor']:.12f}"
            writer.writerow(
                {
                    "timestamp": row["timestamp"].isoformat(),
                    "indoor_pm25_ug_m3": indoor,
                    "outdoor_pm25_ug_m3": outdoor,
                    "indoor_quality": row["indoor_quality"],
                    "outdoor_quality": row["outdoor_quality"],
                }
            )


def config(trial_id: str, description: str) -> dict:
    return {
        "schema_version": "1",
        "trial_id": trial_id,
        "description": description,
        "timezone": "UTC",
        "room_volume_m3": 48.0,
        "initial_indoor_ug_m3": INITIAL,
        "parameters": {
            "penetration": PENETRATION,
            "air_exchange_per_h": AIR_EXCHANGE_PER_H,
            "deposition_per_h": DEPOSITION_PER_H,
        },
        "parameter_bounds": {
            "penetration": [0.2, 1.0],
            "air_exchange_per_h": [0.1, 1.5],
            "deposition_per_h": [0.0, 1.0],
            "filtration_per_h": [0.0, 4.0],
        },
        "fit_parameters": ["penetration", "deposition_per_h"],
        "filtration_schedule": [
            {
                "start": "2024-01-01T00:00:00+00:00",
                "end": "2024-01-01T03:00:00+00:00",
                "filtration_per_h": 0.0,
            },
            {
                "start": "2024-01-01T03:00:00+00:00",
                "end": "2024-01-01T06:00:00+00:00",
                "filtration_per_h": 1.5,
            },
        ],
        "calibration_end": "2024-01-01T04:00:00+00:00",
        "limits": {
            "max_rows": 10000,
            "max_bytes": 2000000,
            "min_concentration_ug_m3": 0.0,
            "max_concentration_ug_m3": 1000.0,
        },
    }


def noisy_rows(clean: list[dict]) -> list[dict]:
    rng = random.Random(SEED)
    rows = []
    for hour, source in enumerate(clean):
        indoor = source["indoor"] + rng.gauss(0.0, 0.4)
        outdoor = source["outdoor"] + rng.gauss(0.0, 0.3)
        indoor = max(0.0, indoor)
        outdoor = max(0.0, outdoor)
        stamp = source["timestamp"]
        indoor_quality = "ok"
        if hour == 2:
            indoor = None
            indoor_quality = "missing"
        elif hour == 4:
            stamp = stamp.astimezone(timezone(timedelta(hours=-8)))
        elif hour == 5:
            indoor_quality = "channel_disagree"
        elif hour == 6:
            indoor = indoor + 30.0
        rows.append(
            {
                "timestamp": stamp,
                "indoor": indoor,
                "outdoor": outdoor,
                "indoor_quality": indoor_quality,
                "outdoor_quality": "ok",
            }
        )
    duplicate = dict(rows[1])
    rows.append(duplicate)
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    clean = base_series()
    noiseless_csv = ROOT / "fixtures" / "noiseless" / "measurements.csv"
    noiseless_cfg = ROOT / "fixtures" / "noiseless" / "config.json"
    noisy_csv = ROOT / "fixtures" / "noisy" / "measurements.csv"
    noisy_cfg = ROOT / "fixtures" / "noisy" / "config.json"
    write_csv(noiseless_csv, clean)
    write_csv(noisy_csv, noisy_rows(clean))
    noiseless_cfg.write_text(
        json.dumps(
            config(
                "noiseless",
                "Closed-form hourly trial. Filtration increases from 0 to 1.5 1/h at 03:00Z.",
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    noisy_cfg.write_text(
        json.dumps(
            config(
                "noisy",
                "Same schedule as noiseless, with seed-20241123 noise, a gap, a timezone offset, sensor disagreement, a duplicate, and an evaluation spike.",
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    steps = []
    for hour, row in enumerate(clean):
        filtration = None if hour == HOURS else filtration_at(hour)
        steps.append(
            {
                "hour": hour,
                "timestamp": row["timestamp"].isoformat(),
                "indoor_ug_m3": f"{row['indoor']:.12f}",
                "outdoor_ug_m3": f"{row['outdoor']:.12f}",
                "filtration_per_h_on_following_step": filtration,
            }
        )
    oracle = ROOT / "fixtures" / "oracle" / "noiseless_steps.json"
    oracle.parent.mkdir(parents=True, exist_ok=True)
    oracle.write_text(json.dumps({"steps": steps}, indent=2) + "\n", encoding="utf-8")

    invalid_csv = ROOT / "fixtures" / "invalid" / "negative_indoor.csv"
    invalid_cfg = ROOT / "fixtures" / "invalid" / "config.json"
    invalid_csv.parent.mkdir(parents=True, exist_ok=True)
    invalid_csv.write_text(
        "timestamp,indoor_pm25_ug_m3,outdoor_pm25_ug_m3,indoor_quality,outdoor_quality\n"
        "2024-01-01T00:00:00+00:00,10.000000000000,20.000000000000,ok,ok\n"
        "2024-01-01T01:00:00+00:00,-1.500000000000,20.000000000000,ok,ok\n",
        encoding="utf-8",
    )
    invalid = config(
        "invalid-negative",
        "Two-row trial whose second indoor concentration is negative.",
    )
    invalid["filtration_schedule"] = [
        {
            "start": "2024-01-01T00:00:00+00:00",
            "end": "2024-01-01T01:00:00+00:00",
            "filtration_per_h": 0.0,
        }
    ]
    invalid["calibration_end"] = "2024-01-01T01:00:00+00:00"
    invalid_cfg.write_text(json.dumps(invalid, indent=2) + "\n", encoding="utf-8")

    tracked = [
        noiseless_csv,
        noiseless_cfg,
        noisy_csv,
        noisy_cfg,
        invalid_csv,
        invalid_cfg,
        oracle,
    ]
    manifest = {
        "schema_version": "1",
        "generated_on": "2026-11-23",
        "generator": "scripts/generate_fixtures.py",
        "seed": SEED,
        "seed_note": "The seed drives Gaussian noise on the noisy trial only. The noiseless trial is the closed form and does not use the seed.",
        "equation": "C_next = C_ss + (C - C_ss) * exp(-(a + k_dep + k_filt) * dt), C_ss = (P * a * C_out) / (a + k_dep + k_filt)",
        "license": "CC0-1.0. These traces were generated for SmokeRoom. They are not measurements from a monitoring network.",
        "source_urls": [],
        "attribution": "Original synthetic data. The mass-balance form is the standard well-mixed single-zone balance documented in docs/overlap.md. No third-party series is copied.",
        "files": [
            {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
            for path in tracked
        ],
    }
    (ROOT / "fixtures" / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print("wrote", len(tracked), "fixture files")
    for step_row in steps:
        print(step_row["hour"], step_row["indoor_ug_m3"])


if __name__ == "__main__":
    main()
