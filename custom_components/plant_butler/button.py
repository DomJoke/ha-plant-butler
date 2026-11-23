"""Buttons for Plant Butler."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import TASK_FERTILIZE, TASK_WATER
from .entity import PlantEntity
from .plant import PlantButlerConfigEntry, PlantRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantButlerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons."""
    for plant in entry.runtime_data.plants.values():
        async_add_entities(
            [
                PlantTaskButton(plant, "mark_watered", TASK_WATER),
                PlantTaskButton(plant, "mark_fertilized", TASK_FERTILIZE),
                UndoWateringButton(plant),
                ResetLearningButton(plant),
            ],
            config_subentry_id=plant.id,
        )


class PlantTaskButton(PlantEntity, ButtonEntity):
    """Confirm a care task."""

    _platform_domain = "button"

    def __init__(self, plant: PlantRuntime, key: str, task: str) -> None:
        """Initialize."""
        super().__init__(plant, key)
        self._task = task

    async def async_press(self) -> None:
        """Mark the task as done."""
        await self.plant.async_mark_done(self._task)


class UndoWateringButton(PlantEntity, ButtonEntity):
    """Undo the last watering (within 24 hours)."""

    _platform_domain = "button"

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "undo_watering")

    @property
    def available(self) -> bool:
        """Only while the last watering can be undone."""
        return self.plant.can_undo_watering()

    async def async_press(self) -> None:
        """Restore the state from before the last watering."""
        await self.plant.async_undo_watering()


class ResetLearningButton(PlantEntity, ButtonEntity):
    """Forget everything learned for this plant."""

    _platform_domain = "button"

    def __init__(self, plant: PlantRuntime) -> None:
        """Initialize."""
        super().__init__(plant, "reset_learning")

    async def async_press(self) -> None:
        """Reset the learned values."""
        await self.plant.async_reset_learning()
