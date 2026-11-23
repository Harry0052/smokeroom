"""Well-mixed single-zone step.

The inflow on a piecewise-constant interval is outdoor penetration times
the air-exchange rate times the outdoor concentration. Removal is the
sum of exchange, deposition, and the declared filtration rate:

    L = a + k_dep + k_filt
    C_ss = (P * a * C_out) / L          when L > 0
    C_next = C_ss + (C - C_ss) * exp(-L * dt)

Inputs are nonnegative and in declared units. This function does not read
files and does not use later observations.
"""

from __future__ import annotations

import math

from smokeroom.errors import ContractError


def step_concentration(
    concentration_ug_m3: float,
    outdoor_ug_m3: float,
    dt_hours: float,
    penetration: float,
    air_exchange_per_h: float,
    deposition_per_h: float,
    filtration_per_h: float,
) -> float:
    """Advance indoor PM2.5 across one interval with constant inputs."""
    _require_nonnegative("concentration_ug_m3", concentration_ug_m3, "ug/m3")
    _require_nonnegative("outdoor_ug_m3", outdoor_ug_m3, "ug/m3")
    _require_nonnegative("dt_hours", dt_hours, "h")
    _require_unit_interval("penetration", penetration)
    _require_nonnegative("air_exchange_per_h", air_exchange_per_h, "1/h")
    _require_nonnegative("deposition_per_h", deposition_per_h, "1/h")
    _require_nonnegative("filtration_per_h", filtration_per_h, "1/h")

    removal = air_exchange_per_h + deposition_per_h + filtration_per_h
    inflow = penetration * air_exchange_per_h * outdoor_ug_m3
    if removal == 0.0:
        if inflow != 0.0:
            raise ContractError(
                "invalid_parameter",
                "air exchange, deposition, and filtration are all 0 1/h "
                "while outdoor inflow is positive; the steady state is undefined",
            )
        return concentration_ug_m3
    steady = inflow / removal
    return steady + (concentration_ug_m3 - steady) * math.exp(-removal * dt_hours)


def _require_nonnegative(name: str, value: float, unit: str) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise ContractError(
            "invalid_parameter",
            f"{name} must be a finite number >= 0 {unit}; got {value!r}",
        )


def _require_unit_interval(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        raise ContractError(
            "invalid_parameter",
            f"{name} must be dimensionless and within 0 to 1 inclusive; got {value!r}",
        )
