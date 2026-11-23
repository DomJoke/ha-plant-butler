"""Constants for Plant Butler."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "plant_butler"
SUBENTRY_TYPE_PLANT: Final = "plant"
STORAGE_VERSION: Final = 1

# Subentry / settings keys
CONF_NAME: Final = "name"
CONF_SPECIES: Final = "species"
CONF_AREA: Final = "area_id"
CONF_MOISTURE_SENSOR: Final = "moisture_sensor"
CONF_ILLUMINANCE_SENSOR: Final = "illuminance_sensor"
CONF_TEMPERATURE_SENSOR: Final = "temperature_sensor"
CONF_HUMIDITY_SENSOR: Final = "humidity_sensor"
CONF_WATER_NEED: Final = "water_need"
CONF_LIGHT_NEED: Final = "light_need"
CONF_LOCATION_LIGHT: Final = "location_light"
CONF_MOISTURE_MIN: Final = "moisture_min"
CONF_MOISTURE_MAX: Final = "moisture_max"
CONF_TEMPERATURE_MIN: Final = "temperature_min"
CONF_TEMPERATURE_MAX: Final = "temperature_max"
CONF_WATERING_INTERVAL: Final = "watering_interval"
CONF_WATERING_AMOUNT: Final = "watering_amount"
CONF_FERTILIZER_INTERVAL: Final = "fertilizer_interval"
CONF_FERTILIZER_WINTER_INTERVAL: Final = "fertilizer_winter_interval"
CONF_FERTILIZER_AMOUNT: Final = "fertilizer_amount"
CONF_FERTILIZER_UNIT: Final = "fertilizer_unit"
CONF_PHOTO: Final = "photo"
CONF_PHOTO_UPLOAD: Final = "photo_upload"
CONF_ICON: Final = "icon"
CONF_NOTES: Final = "notes"

# Hub options
CONF_CLIMATE_STRENGTH: Final = "climate_strength"
DEFAULT_CLIMATE_STRENGTH: Final = 1.0

SPECIES_CUSTOM: Final = "custom"

SENSOR_KEYS: Final = (
    CONF_MOISTURE_SENSOR,
    CONF_ILLUMINANCE_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_HUMIDITY_SENSOR,
)

# Water need levels: (moisture_min = "water below", moisture_max, base interval days)
WATER_LEVELS: Final[dict[str, tuple[int, int, int]]] = {
    "very_low": (10, 35, 21),
    "low": (15, 45, 14),
    "medium": (25, 60, 7),
    "high": (40, 75, 4),
    "very_high": (55, 90, 2),
}
WATER_LEVEL_KEYS: Final = list(WATER_LEVELS)

# Light levels with daily light integral (DLI, mol/m²/day) lower bound
LIGHT_LEVELS: Final[dict[str, float]] = {
    "very_dark": 0.0,
    "dark": 2.0,
    "partial_shade": 4.0,
    "bright_indirect": 8.0,
    "bright_some_sun": 15.0,
    "full_sun": 25.0,
}
LIGHT_LEVEL_KEYS: Final = list(LIGHT_LEVELS)

FERTILIZER_UNITS: Final = ["ml_per_l", "ml", "sticks", "g"]

# Lux -> PPFD (µmol/m²/s) conversion factor for daylight
LUX_TO_PPFD: Final = 0.0185

# Severity
SEVERITY_OK: Final = "ok"
SEVERITY_INFO: Final = "info"
SEVERITY_WARNING: Final = "warning"
SEVERITY_CRITICAL: Final = "critical"
SEVERITIES: Final = [SEVERITY_OK, SEVERITY_INFO, SEVERITY_WARNING, SEVERITY_CRITICAL]

TASK_WATER: Final = "water"
TASK_FERTILIZE: Final = "fertilize"
TASKS: Final = [TASK_WATER, TASK_FERTILIZE]

MOISTURE_HYSTERESIS: Final = 10.0
WATERING_DETECT_RISE: Final = 15.0
WINTER_WATER_FACTOR: Final = 1.5
TODO_DONE_VISIBLE_HOURS: Final = 24

SERVICE_MARK_DONE: Final = "mark_done"
EVENT_NOTIFICATION: Final = "plant_butler_notification"
