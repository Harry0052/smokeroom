"""Local HTML report for one saved SmokeRoom result."""

from __future__ import annotations

import html
from datetime import datetime


def render_report(payload: dict) -> str:
    """Return a standalone HTML document for ``payload``."""
    rows = payload["rows"]
    metrics = payload["metrics"]["held_out"]
    conclusion = payload["conclusion"]
    title = f"SmokeRoom {payload['trial_id']}"
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<link rel="icon" href="data:,">',
        f"<title>{_esc(title)}</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        '<a class="skip" href="#findings">Skip to findings</a>',
        f"<h1>{_esc(title)}</h1>",
        (
            f'<p id="status" role="status" aria-live="polite">'
            f"Conclusion {_esc(conclusion)}. Status {_esc(payload['status'])}. "
            "Concentrations are PM2.5 in ug/m3. This is not a room-safety rating."
            "</p>"
        ),
        _coverage(payload),
        "<h2>Timeline</h2>",
        _chart(rows),
        '<h2 id="findings">Held-out error and residuals</h2>',
        _metrics(metrics),
        _reasons(payload),
        _table(rows),
        _assumptions(payload),
        _provenance(payload),
        "</body>",
        "</html>",
    ]
    return "\n".join(parts) + "\n"


def _coverage(payload: dict) -> str:
    rows = payload["rows"]
    flagged = sum(1 for row in rows if row["flags"])
    eligible = sum(1 for row in rows if row["eligible"])
    return (
        "<h2>Alignment and coverage</h2>"
        "<ul>"
        f"<li>{len(rows)} aligned rows, {eligible} eligible for scores.</li>"
        f"<li>{flagged} rows carry a quality flag. Flags stay on the row after UTC alignment.</li>"
        "<li>Calibration rows are strictly before calibration_end. Later rows are held out.</li>"
        "<li>Shaded bands on the chart are gaps or unsupported intervals, not confidence in a health sense.</li>"
        "</ul>"
    )


def _metrics(metrics: dict) -> str:
    mae = _num(metrics["mae_ug_m3"])
    bias = _num(metrics["bias_ug_m3"])
    return (
        "<dl>"
        f"<dt>Held-out MAE</dt><dd>{mae} ug/m3</dd>"
        f"<dt>Held-out bias (observed minus predicted)</dt><dd>{bias} ug/m3</dd>"
        "<dt>Held-out usable fraction</dt>"
        f"<dd>{metrics['usable_fraction']:.4f} "
        f"({metrics['n_eligible']} of {metrics['n_rows']})</dd>"
        "</dl>"
    )


def _reasons(payload: dict) -> str:
    reasons = payload["weak_reasons"]
    if not reasons:
        return "<p>No weak-evidence rule fired on the eligible rows.</p>"
    items = "".join(f"<li>{_esc(reason)}</li>" for reason in reasons)
    return f'<ul class="weak">{items}</ul>'


def _table(rows: list[dict]) -> str:
    body = []
    for row in rows:
        classes = []
        if row["prediction_state"] in {"missing_observation", "unavailable_input"}:
            classes.append("unsupported")
        residual = row["residual_ug_m3"]
        if residual is not None and abs(residual) > 10.0 and row["eligible"]:
            classes.append("large-residual")
        flags = ", ".join(row["flags"]) if row["flags"] else "none"
        body.append(
            '<tr class="{klass}">'
            "<td>{row}</td><td>{stamp}</td><td>{segment}</td>"
            "<td>{indoor}</td><td>{outdoor}</td><td>{predicted}</td>"
            "<td>{residual}</td><td>{state}</td><td>{eligible}</td><td>{flags}</td>"
            "</tr>".format(
                klass=" ".join(classes),
                row=row["row"],
                stamp=_esc(row["timestamp"]),
                segment=_esc(row["segment"]),
                indoor=_num(row["indoor_ug_m3"]),
                outdoor=_num(row["outdoor_ug_m3"]),
                predicted=_num(row["predicted_ug_m3"]),
                residual=_num(residual),
                state=_esc(row["prediction_state"]),
                eligible="yes" if row["eligible"] else "no",
                flags=_esc(flags),
            )
        )
    return (
        '<div class="table-wrap"><table>'
        "<caption>Row-level residuals. Eligible rows are the only rows in the held-out MAE, bias, and usable fraction.</caption>"
        "<thead><tr>"
        "<th>Row</th><th>Timestamp</th><th>Segment</th>"
        "<th>Indoor ug/m3</th><th>Outdoor ug/m3</th><th>Predicted ug/m3</th>"
        "<th>Residual ug/m3</th><th>State</th><th>Eligible</th><th>Flags</th>"
        "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>"
    )


def _assumptions(payload: dict) -> str:
    used = payload["parameters_used"]
    declared = payload["declared_parameters"]
    fit = payload["fit"]
    schedule = payload.get("configuration", {}).get("filtration_schedule", [])
    schedule_lines = "".join(
        "<li>{start} to {end}: filtration {rate:.4g} 1/h</li>".format(
            start=_esc(item["start"]),
            end=_esc(item["end"]),
            rate=item["filtration_per_h"],
        )
        for item in schedule
    )
    alternatives = fit.get("alternatives") or []
    if alternatives:
        alt = "".join(
            "<li>{params} SSE {sse:.6g}</li>".format(
                params=_esc(str(item["parameters"])),
                sse=item["objective_sse"],
            )
            for item in alternatives
        )
        alt_block = f"<p>Other calibration choices within the similarity rule:</p><ul>{alt}</ul>"
    else:
        alt_block = "<p>No other grid point matched the calibration loss closely enough to mark the fit unidentifiable.</p>"
    limits = "".join(f"<li>{_esc(item)}</li>" for item in payload["limitations"])
    return (
        "<h2>Parameter assumptions</h2>"
        "<ul>"
        f"<li>Penetration used {used['penetration']:.6g} (declared {declared['penetration']:.6g}).</li>"
        f"<li>Air exchange used {used['air_exchange_per_h']:.6g} 1/h.</li>"
        f"<li>Deposition used {used['deposition_per_h']:.6g} 1/h (declared {declared['deposition_per_h']:.6g}).</li>"
        f"<li>Initial indoor state {declared['initial_indoor_ug_m3']:.6g} ug/m3. "
        f"Room volume {declared['room_volume_m3']:.6g} m3.</li>"
        f"<li>Fit status { _esc(fit['status']) }. {_esc(fit.get('detail', ''))}</li>"
        "</ul>"
        f"<ul>{schedule_lines}</ul>"
        f"{alt_block}"
        f"<h2>Limitations</h2><ul>{limits}</ul>"
    )


def _provenance(payload: dict) -> str:
    inputs = payload.get("inputs", {})
    return (
        "<h2>Provenance</h2>"
        "<ul>"
        f"<li>Measurements file {_esc(str(inputs.get('measurements', 'not recorded')))}.</li>"
        f"<li>Measurements SHA-256 {_esc(str(inputs.get('measurements_sha256', 'not recorded')))}.</li>"
        f"<li>Config SHA-256 {_esc(str(inputs.get('config_sha256', 'not recorded')))}.</li>"
        "<li>Compare a residual in the table with the same row number in result.json and with the source CSV.</li>"
        "</ul>"
    )


def _chart(rows: list[dict]) -> str:
    stamped = []
    for row in rows:
        if "duplicate_timestamp" in row["flags"]:
            continue
        stamped.append((datetime.fromisoformat(row["timestamp"]).timestamp(), row))
    if len(stamped) < 2:
        return "<p>Not enough unique timestamps to draw a timeline.</p>"
    stamped.sort(key=lambda item: item[0])
    times = [item[0] for item in stamped]
    values = [
        value
        for _, row in stamped
        for value in (row["indoor_ug_m3"], row["outdoor_ug_m3"], row["predicted_ug_m3"])
        if value is not None
    ]
    y_max = max(values + [1.0]) * 1.15
    t0, t1 = times[0], times[-1]
    span = max(t1 - t0, 1.0)
    left, top, width, height = 64, 16, 720, 250

    def x_of(instant: float) -> float:
        return left + (instant - t0) / span * width

    def y_of(value: float) -> float:
        return top + (1.0 - value / y_max) * height

    shapes = [
        f'<rect x="{left}" y="{top}" width="{width}" height="{height}" class="frame"></rect>'
    ]
    holdout_times = [
        instant for instant, row in stamped if row["segment"] == "evaluation"
    ]
    if holdout_times:
        shapes.append(
            '<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" class="holdout"></rect>'.format(
                x=x_of(min(holdout_times)),
                y=top,
                w=max(x_of(max(holdout_times)) - x_of(min(holdout_times)), 8),
                h=height,
            )
        )
    for instant, row in stamped:
        if row["prediction_state"] not in {"missing_observation", "unavailable_input"}:
            continue
        shapes.append(
            '<rect x="{x:.1f}" y="{y}" width="18" height="{h}" class="gap"></rect>'.format(
                x=x_of(instant) - 9,
                y=top,
                h=height,
            )
        )
    predicted = [
        (instant, row["predicted_ug_m3"])
        for instant, row in stamped
        if row["predicted_ug_m3"] is not None
        and row["prediction_state"] != "unavailable_input"
    ]
    if len(predicted) >= 2:
        points = " ".join(
            f"{x_of(instant):.1f},{y_of(value):.1f}" for instant, value in predicted
        )
        shapes.append(f'<polyline points="{points}" class="predicted"></polyline>')
    for instant, row in stamped:
        indoor = row["indoor_ug_m3"]
        if indoor is None:
            continue
        mark = "observed" if row["eligible"] else "ineligible"
        shapes.append(
            f'<circle cx="{x_of(instant):.1f}" cy="{y_of(indoor):.1f}" r="4" class="{mark}"></circle>'
        )
    axis = (
        f'<text x="{left}" y="{top + height + 28}">time, left to right</text>'
        f'<text x="8" y="{top + 12}">ug/m3</text>'
        f'<text x="{left}" y="{top + height + 4}">{_esc(_stamp(stamped[0][1]))}</text>'
    )
    return (
        "<figure>"
        '<svg viewBox="0 0 800 310" role="img" aria-labelledby="chart-title chart-desc">'
        '<title id="chart-title">Observed and predicted indoor PM2.5</title>'
        '<desc id="chart-desc">Filled circles are eligible indoor observations. '
        "Open circles are ineligible. The dashed line is the model. "
        "Vertical hatching marks a missing or unsupported interval. "
        "The shaded right side is the held-out segment.</desc>"
        + "".join(shapes)
        + axis
        + "</svg>"
        "<figcaption>Filled circles: eligible indoor observations. Open circles: ineligible. "
        "Dashed line: prediction. Hatched band: missing comparison or unsupported interval. "
        "Right-hand shade: held-out segment.</figcaption>"
        "</figure>"
    )


def _stamp(row: dict) -> str:
    return row["timestamp"]


def _num(value: float | None) -> str:
    if value is None:
        return "not available"
    return f"{value:.4f}"


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


_CSS = """
body { font-family: sans-serif; line-height: 1.45; margin: 1rem; color: #142033; background: #fff; overflow-wrap: anywhere; }
h1 { font-size: 1.5rem; }
.skip { position: absolute; left: -999px; top: 0; background: #fff; color: #142033; padding: 0.4rem 0.6rem; }
.skip:focus { left: 0.5rem; top: 0.5rem; outline: 3px solid #0b3d91; z-index: 1; }
a:focus, button:focus { outline: 3px solid #0b3d91; }
#status { border-left: 4px solid #0b3d91; padding: 0.4rem 0.7rem; background: #f4f7fb; }
.weak { border-left: 4px solid #8a3b12; padding-left: 0.7rem; }
.table-wrap { max-width: 100%; overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
th, td { border: 1px solid #9aa6b2; padding: 0.3rem 0.4rem; text-align: left; white-space: nowrap; }
.unsupported { background: repeating-linear-gradient(45deg, #fff, #fff 4px, #ece7df 4px, #ece7df 8px); }
.large-residual { background: #fde8d8; }
svg { width: 100%; height: auto; }
.frame { fill: #fff; stroke: #142033; }
.holdout { fill: #d9e4f5; opacity: 0.45; }
.gap { fill: url(#none); stroke: #8a3b12; stroke-dasharray: 3 2; fill: #f3e6c8; }
.predicted { fill: none; stroke: #142033; stroke-width: 2; stroke-dasharray: 6 4; }
.observed { fill: #0b3d91; stroke: #142033; }
.ineligible { fill: #fff; stroke: #142033; stroke-width: 2; }
@media (max-width: 40rem) {
  body { margin: 0.5rem; }
}
"""
