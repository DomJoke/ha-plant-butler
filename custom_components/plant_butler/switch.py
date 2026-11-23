"""Switches for Plant Butler."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import PlantEntity
from .plant import PlantButlerConfigEntry, PlantRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantButlerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
    for plant in entry.runtime_data.plants.values():
        async_add_entities([WinterRestSwitch(plant)], config_subentry_id=plant.id)


class WinterRestSwitch(PlantEntity, SwitchEntity):
    """Winter rest: longer watering, paused or reduced fertilizing."""

    _platform_domain = "switch"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "winter_rest")

    @property
    def is_on(self) -> bool:
        """Return winter rest state."""
        return self.plant.winter_rest

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable winter rest."""
        await self.plant.async_set_winter_rest(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable winter rest."""
        await self.plant.async_set_winter_rest(False)
