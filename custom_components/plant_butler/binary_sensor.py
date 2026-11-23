"""Binary sensors for Plant Butler."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_TEMPERATURE_SENSOR
from .entity import PlantEntity
from .plant import PlantButlerConfigEntry, PlantRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantButlerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    for plant in entry.runtime_data.plants.values():
        entities: list[BinarySensorEntity] = [
            NeedsWaterBinarySensor(plant),
            NeedsFertilizerBinarySensor(plant),
            LightProblemBinarySensor(plant),
        ]
        if plant.sensor(CONF_TEMPERATURE_SENSOR):
            entities.append(TemperatureProblemBinarySensor(plant))
        async_add_entities(entities, config_subentry_id=plant.id)


class PlantBinarySensor(PlantEntity, BinarySensorEntity):
    """Base plant binary sensor."""

    _platform_domain = "binary_sensor"


class NeedsWaterBinarySensor(PlantBinarySensor):
    """On when the plant needs water."""

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "needs_water")

    @property
    def is_on(self) -> bool:
        """Return true if water is needed."""
        return self.plant.evaluation.needs_water

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return overdue days."""
        return {"overdue_days": round(self.plant.evaluation.water_overdue_days, 1)}


class NeedsFertilizerBinarySensor(PlantBinarySensor):
    """On when the plant needs fertilizer."""

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "needs_fertilizer")

    @property
    def is_on(self) -> bool:
        """Return true if fertilizer is needed."""
        return self.plant.evaluation.needs_fertilizer


class LightProblemBinarySensor(PlantBinarySensor):
    """On when the light does not fit the plant."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "light_problem")

    @property
    def is_on(self) -> bool:
        """Return true on a light problem."""
        return self.plant.evaluation.light_problem is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the kind of problem."""
        return {"problem": self.plant.evaluation.light_problem}


class TemperatureProblemBinarySensor(PlantBinarySensor):
    """On when the room temperature is out of range."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "temperature_problem")

    @property
    def is_on(self) -> bool:
        """Return true on a temperature problem."""
        return self.plant.evaluation.temperature_problem is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the kind of problem."""
        return {"problem": self.plant.evaluation.temperature_problem}
