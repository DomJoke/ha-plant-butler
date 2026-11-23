"""Binary sensors for Plant Butler."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import PlantEntity
from .plant import PlantButlerConfigEntry, PlantRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantButlerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    for plant in entry.runtime_data.plants.values():
        async_add_entities(
            [NeedsWaterBinarySensor(plant), NeedsFertilizerBinarySensor(plant)],
            config_subentry_id=plant.id,
        )


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
