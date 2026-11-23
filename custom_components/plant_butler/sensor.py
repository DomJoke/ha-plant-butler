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
from .texts import problem_summary


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantButlerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    for plant in entry.runtime_data.plants.values():
        entities: list[SensorEntity] = [
            PlantStatusSensor(plant),
            HintsSensor(plant),
            NextWateringSensor(plant),
            NextFertilizingSensor(plant),
        ]
        entities.append(LightConditionSensor(plant))
        if plant.sensor(CONF_TEMPERATURE_SENSOR):
            entities.append(TemperatureConditionSensor(plant))
        if plant.sensor(CONF_ILLUMINANCE_SENSOR):
            # Without a light sensor the level is just the location dropdown
            entities.append(LightLevelSensor(plant))
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
            "summary": problem_summary(
                [p.key for p in ev.problems], self.hass.config.language
            ),
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

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = LIGHT_LEVEL_KEYS

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "light_level")

    @property
    def native_value(self) -> str | None:
        """Return the light level."""
        return self.plant.evaluation.light_level


class LightConditionSensor(PlantSensor):
    """Light conditions: ok, too dark or too bright."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["ok", "too_dark", "too_bright"]

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "light_condition")

    @property
    def native_value(self) -> str | None:
        """Return the light condition (unknown until a level is known)."""
        ev = self.plant.evaluation
        if ev.light_problem:
            return ev.light_problem
        return "ok" if ev.light_level else None


class TemperatureConditionSensor(PlantSensor):
    """Temperature conditions: ok, too cold or too warm."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["ok", "too_cold", "too_hot"]

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "temperature_condition")

    @property
    def native_value(self) -> str | None:
        """Return the temperature condition."""
        ev = self.plant.evaluation
        if ev.temperature is None:
            return None
        return ev.temperature_problem or "ok"


class HintsSensor(PlantSensor):
    """The reasons behind the status in plain words."""

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "hints")

    @property
    def native_value(self) -> str:
        """Return the readable reasons (Home Assistant limits states to 255)."""
        text = problem_summary(
            [p.key for p in self.plant.evaluation.problems], self.hass.config.language
        )
        return text if len(text) <= 255 else text[:254] + "…"

    @property
    def icon(self) -> str:
        """Icon by status."""
        status = self.plant.evaluation.status
        return {
            "ok": "mdi:check-circle-outline",
            "info": "mdi:information-outline",
            "warning": "mdi:alert-outline",
            "critical": "mdi:alert-octagon-outline",
        }.get(status, "mdi:information-outline")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return each reason with its level."""
        return {
            "status": self.plant.evaluation.status,
            "problems": {p.key: p.severity for p in self.plant.evaluation.problems},
        }
