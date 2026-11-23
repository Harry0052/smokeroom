"""Command line entry point."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from smokeroom import __version__
from smokeroom.analysis import evaluate_trial
from smokeroom.errors import ContractError
from smokeroom.validate import load_trial, validate_trial


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="smokeroom",
        description=(
            "Check a SmokeRoom trial. Concentrations are PM2.5 in ug/m3. "
            "This comparison is not a room-safety rating."
        ),
    )
    parser.add_argument("--version", action="version", version=f"smokeroom {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser(
        "validate",
        help="Accept a schema-1 trial or print an actionable error",
    )
    validate.add_argument("--measurements", required=True, type=Path)
    validate.add_argument("--config", required=True, type=Path)
    run = sub.add_parser(
        "run",
        help="Fit the calibration segment and score the held-out segment",
    )
    run.add_argument("--measurements", required=True, type=Path)
    run.add_argument("--config", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            payload = validate_trial(args.measurements, args.config)
        else:
            loaded = load_trial(args.measurements, args.config)
            payload = evaluate_trial(loaded)
            payload["inputs"] = {
                "measurements": str(args.measurements),
                "config": str(args.config),
                "measurements_sha256": _sha256(args.measurements),
                "config_sha256": _sha256(args.config),
            }
            _write_run(args.output, payload)
    except ContractError as exc:
        print(f"{exc.category}: {exc.message}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _write_run(output: Path, payload: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    result_path = output / "result.json"
    summary_path = output / "summary.txt"
    result_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(_summary_text(payload, result_path), encoding="utf-8")


def _summary_text(payload: dict, result_path: Path) -> str:
    metrics = payload["metrics"]["held_out"]
    fit = payload["fit"]
    lines = [
        f"trial: {payload['trial_id']}",
        f"status: {payload['status']}",
        f"conclusion: {payload['conclusion']}",
        f"fit: {fit['status']}",
        "parameters_used:",
    ]
    for name, value in payload["parameters_used"].items():
        lines.append(f"  {name}: {value:.6g}")
    lines.append(
        "held-out MAE ug/m3: "
        + _format_metric(metrics["mae_ug_m3"])
    )
    lines.append(
        "held-out bias ug/m3 (observed minus predicted): "
        + _format_metric(metrics["bias_ug_m3"])
    )
    lines.append(
        "held-out usable fraction: "
        f"{metrics['usable_fraction']:.6g} "
        f"({metrics['n_eligible']} of {metrics['n_rows']})"
    )
    lines.append("rows:")
    for row in payload["rows"]:
        residual = _format_metric(row["residual_ug_m3"])
        flags = ",".join(row["flags"]) if row["flags"] else "-"
        lines.append(
            f"  row {row['row']} {row['timestamp']} {row['segment']} "
            f"state={row['prediction_state']} eligible={row['eligible']} "
            f"residual_ug_m3={residual} flags={flags}"
        )
    if payload["weak_reasons"]:
        lines.append("weak evidence:")
        lines.extend(f"  - {reason}" for reason in payload["weak_reasons"])
    lines.append(f"machine-readable result: {result_path}")
    lines.append("")
    return "\n".join(lines)


def _format_metric(value: float | None) -> str:
    if value is None:
        return "not available"
    return f"{value:.6g}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
