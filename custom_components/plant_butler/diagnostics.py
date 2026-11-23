"""Diagnostics download: settings, inputs and intermediate results."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, SENSOR_KEYS
from .plant import PlantButlerConfigEntry, PlantRuntime


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _plant_diagnostics(hass: HomeAssistant, plant: PlantRuntime) -> dict[str, Any]:
    sensors = {}
    for key in SENSOR_KEYS:
        if entity_id := plant.sensor(key):
            state = hass.states.get(entity_id)
            sensors[key] = {
                "entity_id": entity_id,
                "state": state.state if state else None,
                "unit": state.attributes.get("unit_of_measurement") if state else None,
                "last_updated": state.last_updated.isoformat() if state else None,
            }
    fertilizer_interval = plant.fertilizer_interval_now()
    return {
        "name": plant.name,
        "area": plant.area_name,
        "subentry_data": dict(plant.subentry.data),
        "overrides": plant.state["overrides"],
        "effective_settings": plant.settings,
        "sensors": sensors,
        "calculation": {
            "climate_factor": round(plant.climate_factor(), 3),
            "watering_interval_now_days": round(plant.watering_interval_now(), 2),
            "fertilizer_interval_now_days": fertilizer_interval,
            "watering_progress_percent": round(plant.state["water_progress"] * 100, 1),
            "fertilizer_progress_percent": round(plant.state["fert_progress"] * 100, 1),
            "winter_rest": plant.winter_rest,
        },
        "persisted_state": plant.state,
        "evaluation": asdict(plant.evaluation),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PlantButlerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for all plants."""
    hub = entry.runtime_data
    return _jsonable(
        {
            "options": dict(entry.options),
            "plants": {
                plant.id: _plant_diagnostics(hass, plant)
                for plant in hub.plants.values()
            },
        }
    )


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: PlantButlerConfigEntry, device: dr.DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for one plant."""
    hub = entry.runtime_data
    for domain, plant_id in device.identifiers:
        if domain == DOMAIN and plant_id in hub.plants:
            return _jsonable(
                {
                    "options": dict(entry.options),
                    "plant": _plant_diagnostics(hass, hub.plants[plant_id]),
                }
            )
    return {}
