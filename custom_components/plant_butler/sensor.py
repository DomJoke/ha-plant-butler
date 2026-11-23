"""Sensors for Plant Butler."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .care import fertilizer_per_watering_ml, pot_volume
from .const import (
    CONF_FERTILIZER_AMOUNT,
    CONF_FERTILIZER_UNIT,
    CONF_HUMIDITY_SENSOR,
    CONF_ICON,
    CONF_ILLUMINANCE_SENSOR,
    CONF_LIGHT_NEED,
    CONF_MOISTURE_MAX,
    CONF_MOISTURE_MIN,
    CONF_MOISTURE_SENSOR,
    CONF_NOTES,
    CONF_PHOTO,
    CONF_SPECIES,
    CONF_TEMPERATURE_MAX,
    CONF_TEMPERATURE_MIN,
    CONF_TEMPERATURE_SENSOR,
    CONF_WATER_NEED,
    CONF_WATERING_AMOUNT,
    LIGHT_LEVEL_KEYS,
    SEVERITIES,
)
from .entity import PlantEntity
from .plant import PlantButlerConfigEntry, PlantRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantButlerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    for plant in entry.runtime_data.plants.values():
        entities: list[SensorEntity] = [
            PlantStatusSensor(plant),
            NextWateringSensor(plant),
            NextFertilizingSensor(plant),
            LightLevelSensor(plant),
        ]
        if plant.sensor(CONF_ILLUMINANCE_SENSOR):
            entities.append(DliSensor(plant))
        async_add_entities(entities, config_subentry_id=plant.id)


class PlantSensor(PlantEntity, SensorEntity):
    """Base plant sensor."""

    _platform_domain = "sensor"


class PlantStatusSensor(PlantSensor):
    """Overall status: ok / info / warning / critical."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = SEVERITIES
    _unrecorded_attributes = frozenset(
        {
            "problems",
            "problem_severities",
            "species",
            "photo",
            "notes",
            "sensors",
            "targets",
            "care",
        }
    )

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "status")

    @property
    def native_value(self) -> str:
        """Return the status."""
        return self.plant.evaluation.status

    @property
    def icon(self) -> str | None:
        """Return the species icon."""
        return self.plant.settings.get(CONF_ICON) or "mdi:flower"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return everything a dashboard card needs."""
        plant = self.plant
        ev = plant.evaluation
        s = plant.settings
        return {
            "plant_name": plant.name,
            "species": s.get(CONF_SPECIES),
            "area": plant.area_name,
            "photo": s.get(CONF_PHOTO) or None,
            "notes": s.get(CONF_NOTES) or None,
            "problems": [p.key for p in ev.problems],
            "problem_severities": {p.key: p.severity for p in ev.problems},
            "needs_water": ev.needs_water,
            "needs_fertilizer": ev.needs_fertilizer,
            "winter_rest": plant.winter_rest,
            "sensors": {
                "moisture": plant.sensor(CONF_MOISTURE_SENSOR),
                "illuminance": plant.sensor(CONF_ILLUMINANCE_SENSOR),
                "temperature": plant.sensor(CONF_TEMPERATURE_SENSOR),
                "humidity": plant.sensor(CONF_HUMIDITY_SENSOR),
            },
            "targets": {
                "water_need": s.get(CONF_WATER_NEED),
                "light_need": s.get(CONF_LIGHT_NEED),
                "moisture_min": s.get(CONF_MOISTURE_MIN),
                "moisture_max": s.get(CONF_MOISTURE_MAX),
                "temperature_min": s.get(CONF_TEMPERATURE_MIN),
                "temperature_max": s.get(CONF_TEMPERATURE_MAX),
            },
            "care": {
                "watering_amount": s.get(CONF_WATERING_AMOUNT),
                "fertilizer_amount": s.get(CONF_FERTILIZER_AMOUNT),
                "fertilizer_unit": s.get(CONF_FERTILIZER_UNIT),
                "last_watered": plant.state["last_watered"],
                "last_fertilized": plant.state["last_fertilized"],
                "watering_interval_effective": ev.watering_interval_effective,
                "pot_volume_l": round(vol, 1) if (vol := pot_volume(s)) else None,
                "fertilizer_per_watering_ml": fertilizer_per_watering_ml(s),
                "climate_factor": ev.climate_factor,
            },
            "light": {
                "level": ev.light_level,
                "dli_today": ev.dli_today,
                "dli_yesterday": ev.dli_yesterday,
            },
        }


class NextWateringSensor(PlantSensor):
    """When the plant needs water next (or since when it is due)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "next_watering")

    @property
    def native_value(self) -> datetime | None:
        """Return the due time."""
        return self.plant.evaluation.next_watering

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details."""
        ev = self.plant.evaluation
        return {
            "due": ev.needs_water,
            "overdue_days": round(ev.water_overdue_days, 1),
            "interval_days": ev.watering_interval_effective,
            "climate_factor": ev.climate_factor,
        }


class NextFertilizingSensor(PlantSensor):
    """When the plant needs fertilizer next."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "next_fertilizing")

    @property
    def native_value(self) -> datetime | None:
        """Return the due time (None when paused or disabled)."""
        return self.plant.evaluation.next_fertilizing

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details."""
        ev = self.plant.evaluation
        return {
            "due": ev.needs_fertilizer,
            "overdue_days": round(ev.fertilizer_overdue_days, 1),
            "enabled": ev.fertilizing_enabled,
        }


class DliSensor(PlantSensor):
    """Daily light integral accumulated today."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    _attr_native_unit_of_measurement = "mol/(m²·d)"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "dli")

    @property
    def native_value(self) -> float | None:
        """Return today's DLI so far."""
        return self.plant.evaluation.dli_today

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the history of complete days."""
        return {"history": self.plant.state["dli_history"]}


class LightLevelSensor(PlantSensor):
    """Actual light level (from sensor or chosen location)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = LIGHT_LEVEL_KEYS

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "light_level")

    @property
    def native_value(self) -> str | None:
        """Return the light level."""
        return self.plant.evaluation.light_level
