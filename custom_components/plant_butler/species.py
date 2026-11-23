"""Bundled plant species database."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_FERTILIZER_INTERVAL,
    CONF_FERTILIZER_WINTER_INTERVAL,
    CONF_ICON,
    CONF_LIGHT_NEED,
    CONF_TEMPERATURE_MAX,
    CONF_TEMPERATURE_MIN,
    CONF_WATER_NEED,
    CONF_WATERING_INTERVAL,
    DOMAIN,
    WATER_LEVELS,
)

_DB_PATH = Path(__file__).parent / "data" / "plants.json"
_DATA_KEY = f"{DOMAIN}_species"

CUSTOM_DEFAULTS: dict[str, Any] = {
    CONF_WATER_NEED: "medium",
    CONF_LIGHT_NEED: "bright_indirect",
    CONF_TEMPERATURE_MIN: 15,
    CONF_TEMPERATURE_MAX: 28,
    CONF_FERTILIZER_INTERVAL: 14,
    CONF_FERTILIZER_WINTER_INTERVAL: 0,
    CONF_ICON: "mdi:flower",
}


def _load() -> dict[str, dict[str, Any]]:
    raw = json.loads(_DB_PATH.read_text(encoding="utf-8"))
    return {s["id"]: s for s in raw["species"]}


async def async_get_species_db(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Return the species database (cached)."""
    if (db := hass.data.get(_DATA_KEY)) is None:
        db = await hass.async_add_executor_job(_load)
        hass.data[_DATA_KEY] = db
    return db


def species_name(species: dict[str, Any], language: str) -> str:
    """Return the display name of a species in the given language."""
    names = species["name"]
    return names.get(language[:2], names.get("en", species["id"]))


def species_defaults(species: dict[str, Any] | None) -> dict[str, Any]:
    """Return profile defaults (setting keys) for a species or custom plant."""
    if species is None:
        defaults = dict(CUSTOM_DEFAULTS)
    else:
        defaults = {
            CONF_WATER_NEED: species["water"],
            CONF_LIGHT_NEED: species["light"],
            CONF_TEMPERATURE_MIN: species["temperature"]["min"],
            CONF_TEMPERATURE_MAX: species["temperature"]["max"],
            CONF_FERTILIZER_INTERVAL: species["fertilizer"]["interval_days"],
            CONF_FERTILIZER_WINTER_INTERVAL: species["fertilizer"][
                "winter_interval_days"
            ],
            CONF_ICON: species.get("icon", "mdi:flower"),
        }
    defaults[CONF_WATERING_INTERVAL] = WATER_LEVELS[defaults[CONF_WATER_NEED]][2]
    return defaults
