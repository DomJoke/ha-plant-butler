"""Tests for plant runtime, entities, checklist and service."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.plant_butler.const import DOMAIN

from .conftest import PLANT_ID


async def _setup(hass: HomeAssistant, make_entry, data: dict[str, Any]):
    entry = make_entry(data)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


async def _advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    # step in 10-minute ticks would be slow; one tick covers the whole span
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _todo_items(hass: HomeAssistant) -> list[dict[str, Any]]:
    result = await hass.services.async_call(
        TODO_DOMAIN,
        "get_items",
        {"entity_id": "todo.plant_butler"},
        blocking=True,
        return_response=True,
    )
    return result["todo.plant_butler"]["items"]


async def test_entities_created_with_english_ids(
    hass: HomeAssistant, make_entry, plant_data, area: ar.AreaEntry
) -> None:
    """All entities exist with English ids and the device lands in the room."""
    plant_data["area_id"] = area.id
    plant_data["photo"] = "https://example.com/monstera.jpg"
    await _setup(hass, make_entry, plant_data)

    for entity_id in (
        "sensor.monstera_status",
        "sensor.monstera_next_watering",
        "sensor.monstera_next_fertilizing",
        "sensor.monstera_light_level",
        "binary_sensor.monstera_needs_water",
        "binary_sensor.monstera_needs_fertilizer",
        "binary_sensor.monstera_light_problem",
        "button.monstera_mark_watered",
        "button.monstera_mark_fertilized",
        "select.monstera_water_need",
        "select.monstera_light_need",
        "select.monstera_location_light",
        "number.monstera_temperature_min",
        "number.monstera_watering_interval",
        "number.monstera_fertilizer_amount",
        "switch.monstera_winter_rest",
        "image.monstera_photo",
        "todo.plant_butler",
    ):
        assert hass.states.get(entity_id) is not None, entity_id

    # No moisture sensor -> no moisture thresholds, no DLI sensor
    assert hass.states.get("number.monstera_moisture_min") is None
    assert hass.states.get("sensor.monstera_dli") is None

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, PLANT_ID)})
    assert device.area_id == area.id
    assert device.model_id == "monstera"

    status = hass.states.get("sensor.monstera_status")
    assert status.state == "info"  # location partial_shade < need bright_indirect
    assert status.attributes["problems"] == ["too_dark"]
    assert status.attributes["area"] == "Esszimmer"
    assert hass.states.get("sensor.monstera_light_level").state == "partial_shade"


async def test_schedule_without_sensor(
    hass: HomeAssistant, make_entry, plant_data, freezer: FrozenDateTimeFactory
) -> None:
    """Watering becomes due after the interval and resets when done."""
    plant_data["location_light"] = "bright_indirect"
    await _setup(hass, make_entry, plant_data)
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "off"
    assert hass.states.get("sensor.monstera_status").state == "ok"
    assert await _todo_items(hass) == []

    await _advance(hass, freezer, timedelta(days=7, hours=1))
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "on"
    assert hass.states.get("sensor.monstera_status").state == "info"
    items = await _todo_items(hass)
    assert len(items) == 1
    assert items[0]["summary"] == "Monstera: Water – 300 ml"
    assert items[0]["status"] == "needs_action"
    assert hass.states.get("todo.plant_butler").state == "1"

    # Overdue escalates: >1 day warning, >50 % of interval critical
    await _advance(hass, freezer, timedelta(days=2))
    assert hass.states.get("sensor.monstera_status").state == "warning"
    await _advance(hass, freezer, timedelta(days=2))
    assert hass.states.get("sensor.monstera_status").state == "critical"

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.monstera_mark_watered"}, blocking=True
    )
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "off"
    items = await _todo_items(hass)
    assert [i["status"] for i in items if "Water" in i["summary"]] == ["completed"]

    # Done items disappear after 24 h, then come back when due again
    await _advance(hass, freezer, timedelta(hours=25))
    assert not [i for i in await _todo_items(hass) if "Water" in i["summary"]]
    await _advance(hass, freezer, timedelta(days=6))
    water = [i for i in await _todo_items(hass) if "Water" in i["summary"]]
    assert water and water[0]["status"] == "needs_action"


async def test_fertilizer_and_todo_tick(
    hass: HomeAssistant, make_entry, plant_data, freezer: FrozenDateTimeFactory
) -> None:
    """Ticking a checklist item marks the task done."""
    await _setup(hass, make_entry, plant_data)
    await _advance(hass, freezer, timedelta(days=14, hours=1))
    assert hass.states.get("binary_sensor.monstera_needs_fertilizer").state == "on"
    items = await _todo_items(hass)
    fert = next(i for i in items if "Fertilize" in i["summary"])
    assert fert["summary"] == "Monstera: Fertilize – 5 ml/l"

    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {"entity_id": "todo.plant_butler", "item": fert["uid"], "status": "completed"},
        blocking=True,
    )
    assert hass.states.get("binary_sensor.monstera_needs_fertilizer").state == "off"


async def test_winter_rest_pauses_fertilizer(
    hass: HomeAssistant, make_entry, plant_data, freezer: FrozenDateTimeFactory
) -> None:
    """Winter rest pauses fertilizing (winter interval 0) and stretches watering."""
    await _setup(hass, make_entry, plant_data)
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.monstera_winter_rest"}, blocking=True
    )
    assert hass.states.get("sensor.monstera_next_fertilizing").state == "unknown"
    await _advance(hass, freezer, timedelta(days=8))
    # 7 days * 1.5 = 10.5 days in winter
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "off"
    assert hass.states.get("binary_sensor.monstera_needs_fertilizer").state == "off"
    await _advance(hass, freezer, timedelta(days=3))
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "on"


async def test_climate_shortens_interval(
    hass: HomeAssistant, make_entry, plant_data, freezer: FrozenDateTimeFactory
) -> None:
    """Warm dry air makes the plant due earlier."""
    hass.states.async_set("sensor.room_temp", "26")
    hass.states.async_set("sensor.room_hum", "40")
    plant_data["temperature_sensor"] = "sensor.room_temp"
    plant_data["humidity_sensor"] = "sensor.room_hum"
    await _setup(hass, make_entry, plant_data)
    attrs = hass.states.get("sensor.monstera_next_watering").attributes
    assert attrs["climate_factor"] == 0.7
    assert attrs["interval_days"] == 4.93
    await _advance(hass, freezer, timedelta(days=5))
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "on"


async def test_moisture_sensor(
    hass: HomeAssistant, make_entry, plant_data, freezer: FrozenDateTimeFactory
) -> None:
    """Soil sensor drives watering, with hysteresis and automatic detection."""
    hass.states.async_set("sensor.soil", "40")
    plant_data["moisture_sensor"] = "sensor.soil"
    plant_data["location_light"] = "bright_indirect"
    await _setup(hass, make_entry, plant_data)
    assert hass.states.get("number.monstera_moisture_min").state == "25.0"
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "off"

    hass.states.async_set("sensor.soil", "20")
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "on"
    # Hysteresis: 30 is above the limit but below limit + 10
    hass.states.async_set("sensor.soil", "30")
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "on"
    # Very dry -> critical
    hass.states.async_set("sensor.soil", "10")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.monstera_status").state == "critical"

    # Watering detected by a sharp rise
    freezer.tick(timedelta(minutes=5))
    hass.states.async_set("sensor.soil", "55")
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "off"
    status = hass.states.get("sensor.monstera_status")
    assert status.attributes["care"]["last_watered"] is not None

    # Too wet
    hass.states.async_set("sensor.soil", "97")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.monstera_status").attributes[
        "problem_severities"
    ] == {"too_wet": "warning"}


async def test_temperature_problem(hass: HomeAssistant, make_entry, plant_data) -> None:
    """Room temperature outside the range raises a problem."""
    hass.states.async_set("sensor.room_temp", "14")
    plant_data["temperature_sensor"] = "sensor.room_temp"
    plant_data["location_light"] = "bright_indirect"
    await _setup(hass, make_entry, plant_data)
    assert hass.states.get("binary_sensor.monstera_temperature_problem").state == "on"
    assert hass.states.get("sensor.monstera_status").state == "warning"
    hass.states.async_set("sensor.room_temp", "12")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.monstera_status").state == "critical"


async def test_light_sensor_dli(
    hass: HomeAssistant, make_entry, plant_data, freezer: FrozenDateTimeFactory
) -> None:
    """DLI is integrated per day and compared after three days."""
    freezer.move_to("2026-06-01 00:30:00+05:30")
    hass.states.async_set("sensor.lux", "1000")
    plant_data["illuminance_sensor"] = "sensor.lux"
    plant_data.pop("location_light")
    await _setup(hass, make_entry, plant_data)
    assert hass.states.get("select.monstera_location_light") is None
    for _ in range(3 * 24):
        await _advance(hass, freezer, timedelta(hours=1))
    dli = hass.states.get("sensor.monstera_dli")
    assert dli is not None
    # 1000 lux all day = 1.6 mol/m²/day -> very dark, plant needs bright indirect
    assert hass.states.get("sensor.monstera_light_level").state == "very_dark"
    assert hass.states.get("binary_sensor.monstera_light_problem").state == "on"


async def test_mark_done_service(
    hass: HomeAssistant, make_entry, plant_data, freezer: FrozenDateTimeFactory
) -> None:
    """The service accepts a device id or any plant entity."""
    await _setup(hass, make_entry, plant_data)
    await _advance(hass, freezer, timedelta(days=8))
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "on"
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, PLANT_ID)})
    await hass.services.async_call(
        DOMAIN, "mark_done", {"device_id": device.id, "task": "water"}, blocking=True
    )
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "off"

    await _advance(hass, freezer, timedelta(days=15))
    await hass.services.async_call(
        DOMAIN,
        "mark_done",
        {"entity_id": "sensor.monstera_status", "task": "fertilize"},
        blocking=True,
    )
    assert hass.states.get("binary_sensor.monstera_needs_fertilizer").state == "off"


async def test_settings_override_and_persistence(
    hass: HomeAssistant, make_entry, plant_data
) -> None:
    """Changing the water level via select updates thresholds and survives reload."""
    hass.states.async_set("sensor.soil", "50")
    plant_data["moisture_sensor"] = "sensor.soil"
    entry = await _setup(hass, make_entry, plant_data)
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.monstera_water_need", "option": "high"},
        blocking=True,
    )
    assert hass.states.get("number.monstera_moisture_min").state == "40.0"
    assert hass.states.get("number.monstera_watering_interval").state == "4.0"
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.monstera_moisture_min", "value": 35},
        blocking=True,
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("select.monstera_water_need").state == "high"
    assert hass.states.get("number.monstera_moisture_min").state == "35.0"


async def test_notification_event(
    hass: HomeAssistant, make_entry, plant_data, freezer: FrozenDateTimeFactory
) -> None:
    """An event is fired once per new or escalated problem."""
    plant_data["location_light"] = "bright_indirect"
    events = []
    hass.bus.async_listen("plant_butler_notification", events.append)
    await _setup(hass, make_entry, plant_data)
    await _advance(hass, freezer, timedelta(days=7, hours=1))
    await _advance(hass, freezer, timedelta(minutes=10))
    assert [(e.data["problem"], e.data["severity"]) for e in events] == [
        ("needs_water", "info")
    ]
    await _advance(hass, freezer, timedelta(days=2))
    assert events[-1].data["severity"] == "warning"
    assert events[-1].data["plant"] == "Monstera"
