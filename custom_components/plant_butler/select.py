"""Selects for Plant Butler (target levels)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_ILLUMINANCE_SENSOR,
    CONF_LIGHT_NEED,
    CONF_LOCATION_LIGHT,
    CONF_WATER_NEED,
    LIGHT_LEVEL_KEYS,
    WATER_LEVEL_KEYS,
)
from .entity import PlantEntity
from .plant import PlantButlerConfigEntry, PlantRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantButlerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects."""
    for plant in entry.runtime_data.plants.values():
        entities = [
            PlantSettingSelect(plant, CONF_WATER_NEED, WATER_LEVEL_KEYS),
            PlantSettingSelect(plant, CONF_LIGHT_NEED, LIGHT_LEVEL_KEYS),
        ]
        if not plant.sensor(CONF_ILLUMINANCE_SENSOR):
            entities.append(
                PlantSettingSelect(plant, CONF_LOCATION_LIGHT, LIGHT_LEVEL_KEYS)
            )
        async_add_entities(entities, config_subentry_id=plant.id)


class PlantSettingSelect(PlantEntity, SelectEntity):
    """A level setting of the plant."""

    _platform_domain = "select"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, plant: PlantRuntime, key: str, options: list[str]) -> None:
        """Initialize."""
        super().__init__(plant, key)
        self._key = key
        self._attr_options = options

    @property
    def current_option(self) -> str | None:
        """Return the current level."""
        return self.plant.settings.get(self._key)

    async def async_select_option(self, option: str) -> None:
        """Change the level."""
        await self.plant.async_set_setting(self._key, option)
