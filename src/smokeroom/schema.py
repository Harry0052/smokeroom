"""Versioned input shapes for schema 1.

Concentration is PM2.5 in micrograms per cubic meter (µg/m³). Rates are
per hour. Volume is cubic meters. Timestamps are ISO-8601 with an offset.
"""

SCHEMA_VERSION = "1"

MEASUREMENT_COLUMNS = (
    "timestamp",
    "indoor_pm25_ug_m3",
    "outdoor_pm25_ug_m3",
    "indoor_quality",
    "outdoor_quality",
)

QUALITY_FLAGS = ("ok", "missing", "channel_disagree")

# Hard ceilings. A trial config may set a lower limit, never a higher one.
HARD_MAX_ROWS = 10_000
HARD_MAX_BYTES = 2_000_000
HARD_MAX_CONCENTRATION_UG_M3 = 10_000.0
HARD_MAX_VOLUME_M3 = 10_000.0
HARD_MAX_RATE_PER_H = 20.0

FIT_PARAMETER_NAMES = (
    "penetration",
    "air_exchange_per_h",
    "deposition_per_h",
)
