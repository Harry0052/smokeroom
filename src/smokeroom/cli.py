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
from smokeroom.report import render_report
from smokeroom.validate import load_trial, validate_trial


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="smokeroom",
        description=(
            "Check a SmokeRoom trial. Concentrations are PM2.5 in ug/m3. "
            "This comparison is not a room-safety rating."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"smokeroom {__version__}"
    )
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
    show = sub.add_parser(
        "show",
        help="Load a saved result.json and print the human summary",
    )
    show.add_argument("result", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            payload = validate_trial(args.measurements, args.config)
            print(json.dumps(payload, indent=2, sort_keys=True))
        elif args.command == "run":
            loaded = load_trial(args.measurements, args.config)
            payload = evaluate_trial(loaded)
            payload["inputs"] = {
                "measurements": str(args.measurements),
                "config": str(args.config),
                "measurements_sha256": _sha256(args.measurements),
                "config_sha256": _sha256(args.config),
            }
            payload["configuration"] = _configuration(loaded)
            _write_run(args.output, payload)
            print(json.dumps(payload, indent=2, sort_keys=True))
            print(_diagnostic(payload), file=sys.stderr)
        else:
            payload = _load_saved(args.result)
            print(_summary_text(payload, args.result))
            print(_diagnostic(payload), file=sys.stderr)
    except ContractError as exc:
        print(f"{exc.category}: {exc.message}", file=sys.stderr)
        return 2
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
    (output / "report.html").write_text(render_report(payload), encoding="utf-8")


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
    lines.append("held-out MAE ug/m3: " + _format_metric(metrics["mae_ug_m3"]))
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
    html_path = result_path.with_name("report.html")
    if html_path.is_file() or result_path.name == "result.json":
        lines.append(f"html report: {html_path}")
    lines.append("")
    return "\n".join(lines)


def _diagnostic(payload: dict) -> str:
    metrics = payload["metrics"]["held_out"]
    return (
        "diagnostic: "
        f"conclusion={payload['conclusion']} "
        f"status={payload['status']} "
        f"held_out_usable_fraction={metrics['usable_fraction']:.4f}"
    )


def _configuration(loaded: dict) -> dict:
    config = loaded["config"]
    return {
        "schema_version": "1",
        "trial_id": config["trial_id"],
        "timezone": "UTC",
        "room_volume_m3": config["room_volume_m3"],
        "initial_indoor_ug_m3": config["initial_indoor_ug_m3"],
        "parameters": config["parameters"],
        "parameter_bounds": {
            name: [low, high]
            for name, (low, high) in config["parameter_bounds"].items()
        },
        "fit_parameters": config["fit_parameters"],
        "filtration_schedule": [
            {
                "start": item["start"].isoformat(),
                "end": item["end"].isoformat(),
                "filtration_per_h": item["filtration_per_h"],
            }
            for item in config["filtration_schedule"]
        ],
        "calibration_end": config["calibration_end"].isoformat(),
    }


def _load_saved(path: Path) -> dict:
    if not path.is_file():
        raise ContractError("invalid_result", f"saved result does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError(
            "invalid_result",
            f"saved result is not JSON ({exc.msg} at line {exc.lineno})",
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != "1":
        raise ContractError("invalid_result", "saved result schema_version must be '1'")
    for key in ("trial_id", "rows", "metrics", "fit", "parameters_used", "conclusion"):
        if key not in payload:
            raise ContractError("invalid_result", f"saved result is missing {key}")
    return payload


def _format_metric(value: float | None) -> str:
    if value is None:
        return "not available"
    return f"{value:.6g}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
