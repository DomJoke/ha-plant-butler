"""Base entity for Plant Butler."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .plant import PlantRuntime


class PlantEntity(Entity):
    """An entity belonging to a plant device."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _platform_domain: str = ""

    def __init__(self, plant: PlantRuntime, key: str) -> None:
        """Initialize the entity."""
        self.plant = plant
        self._attr_translation_key = key
        self._attr_unique_id = f"{plant.id}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, plant.id)})
        # English entity ids, independent of the UI language
        self.entity_id = f"{self._platform_domain}.{plant.slug}_{key}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to plant updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self.plant.async_add_listener(self._handle_plant_update))

    @callback
    def _handle_plant_update(self) -> None:
        self.async_write_ha_state()
