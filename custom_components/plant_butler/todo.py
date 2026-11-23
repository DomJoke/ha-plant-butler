"""Care checklist as a to-do list."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FERTILIZER_AMOUNT,
    CONF_FERTILIZER_UNIT,
    CONF_WATERING_AMOUNT,
    DOMAIN,
    TASK_FERTILIZE,
    TASK_WATER,
    TODO_DONE_VISIBLE_HOURS,
)
from .number import FERTILIZER_UNIT_LABELS
from .plant import ButlerHub, PlantButlerConfigEntry, PlantRuntime, _parse

TEXTS = {
    "de": {
        TASK_WATER: "Gießen",
        TASK_FERTILIZE: "Düngen",
        "overdue": "überfällig seit {} Tagen",
    },
    "en": {
        TASK_WATER: "Water",
        TASK_FERTILIZE: "Fertilize",
        "overdue": "overdue for {} days",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantButlerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the checklist."""
    async_add_entities([PlantChecklist(entry.runtime_data)])


def _fmt(value: float) -> str:
    return f"{value:g}"


class PlantChecklist(TodoListEntity):
    """All due plant care tasks, sorted by urgency."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "checklist"
    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

    def __init__(self, hub: ButlerHub) -> None:
        """Initialize."""
        self.hub = hub
        self._attr_unique_id = f"{hub.entry.entry_id}_checklist"
        self.entity_id = f"todo.{DOMAIN}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to plant updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self.hub.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    def _texts(self) -> dict[str, str]:
        return TEXTS.get(self.hass.config.language[:2], TEXTS["en"])

    def _item(self, plant: PlantRuntime, task: str) -> TodoItem | None:
        ev = plant.evaluation
        texts = self._texts()
        settings = plant.settings
        if task == TASK_WATER:
            due, last = ev.needs_water, plant.state["last_watered"]
            when, overdue = ev.next_watering, ev.water_overdue_days
            amount = settings.get(CONF_WATERING_AMOUNT)
            amount_text = f"{_fmt(float(amount))} ml" if amount else None
        else:
            due, last = ev.needs_fertilizer, plant.state["last_fertilized"]
            when, overdue = ev.next_fertilizing, ev.fertilizer_overdue_days
            amount = settings.get(CONF_FERTILIZER_AMOUNT)
            unit = FERTILIZER_UNIT_LABELS.get(
                settings.get(CONF_FERTILIZER_UNIT) or "", ""
            )
            amount_text = f"{_fmt(float(amount))} {unit}".strip() if amount else None
        last_dt = _parse(last)
        recently_done = last_dt is not None and dt_util.utcnow() - last_dt < timedelta(
            hours=TODO_DONE_VISIBLE_HOURS
        )
        if not due and not recently_done:
            return None
        prefix = f"{plant.area_name} · " if plant.area_name else ""
        summary = f"{prefix}{plant.name}: {texts[task]}"
        if amount_text:
            summary += f" – {amount_text}"
        description = None
        if due and overdue >= 1:
            description = texts["overdue"].format(int(overdue))
        return TodoItem(
            uid=f"{plant.id}:{task}",
            summary=summary,
            status=TodoItemStatus.NEEDS_ACTION if due else TodoItemStatus.COMPLETED,
            due=dt_util.as_local(when).date() if due and when else None,
            description=description,
        )

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return the checklist."""
        items = [
            item
            for plant in self.hub.plants.values()
            for task in (TASK_WATER, TASK_FERTILIZE)
            if (item := self._item(plant, task)) is not None
        ]

        def sort_key(item: TodoItem) -> tuple:
            open_ = item.status == TodoItemStatus.NEEDS_ACTION
            return (not open_, item.due or dt_util.now().date(), item.summary or "")

        return sorted(items, key=sort_key)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Ticking an item marks the care task as done."""
        plant_id, _, task = (item.uid or "").partition(":")
        if (plant := self.hub.plants.get(plant_id)) is None or task not in (
            TASK_WATER,
            TASK_FERTILIZE,
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="unknown_task"
            )
        if item.status == TodoItemStatus.COMPLETED:
            await plant.async_mark_done(task)
        else:
            # Un-ticking is not supported; restore the real state
            self.async_write_ha_state()
