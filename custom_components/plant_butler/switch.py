"""Switches for Plant Butler."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import PlantEntity
from .plant import ButlerHub, PlantButlerConfigEntry, PlantRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantButlerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
    async_add_entities([LearningPausedSwitch(entry.runtime_data)])
    for plant in entry.runtime_data.plants.values():
        async_add_entities(
            [WinterRestSwitch(plant), NotificationsSwitch(plant)],
            config_subentry_id=plant.id,
        )


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


class NotificationsSwitch(PlantEntity, SwitchEntity):
    """Phone notifications and announcements for this plant."""

    _platform_domain = "switch"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "notifications")

    @property
    def is_on(self) -> bool:
        """Return whether notifications are enabled."""
        return bool(self.plant.state.get("notify_enabled", True))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable notifications."""
        await self.plant.async_set_notifications(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Mute notifications."""
        await self.plant.async_set_notifications(False)


class LearningPausedSwitch(SwitchEntity):
    """Pause learning for all plants (e.g. while someone else waters)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "learning_paused"

    def __init__(self, hub: ButlerHub) -> None:
        """Initialize."""
        self.hub = hub
        self._attr_unique_id = f"{hub.entry.entry_id}_learning_paused"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, hub.entry.entry_id)})
        self.entity_id = f"switch.{DOMAIN}_learning_paused"

    async def async_added_to_hass(self) -> None:
        """Follow hub updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self.hub.async_add_listener(self.async_write_ha_state))

    @property
    def is_on(self) -> bool:
        """Return whether learning is paused."""
        return self.hub.learning_paused

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Pause learning."""
        await self.hub.async_set_learning_paused(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Resume learning."""
        await self.hub.async_set_learning_paused(False)
