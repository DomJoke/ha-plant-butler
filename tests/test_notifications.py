"""Tests for phone notifications and announcements."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import (
    area_registry as ar,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.plant_butler.const import TOPICS
from custom_components.plant_butler.notifications import in_window

from .conftest import PLANT_ID


@pytest.fixture(autouse=True)
async def utc(hass: HomeAssistant) -> None:
    """Use UTC so quiet hours are easy to reason about."""
    await hass.config.async_set_time_zone("UTC")


@pytest.fixture
def phone(hass: HomeAssistant) -> dr.DeviceEntry:
    """A Companion app phone."""
    app = MockConfigEntry(domain="mobile_app")
    app.add_to_hass(hass)
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=app.entry_id,
        identifiers={("mobile_app", "dphone")},
        name="dPhone",
    )


@pytest.fixture
def notify_calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Captured notify.mobile_app_dphone calls."""
    return async_mock_service(hass, "notify", "mobile_app_dphone")


def phone_options(device_id: str, **overrides: Any) -> dict[str, Any]:
    """Phone options without quiet hours."""
    return {
        "phone": {
            "devices": [device_id],
            "topics": TOPICS,
            "info": "off",
            "warning": "immediate",
            "critical": "immediate",
            "summary_time": "08:00:00",
            "critical_repeat_hours": 0,
            "critical_breaks_dnd": False,
            "quiet_start": None,
            "quiet_end": None,
            "respect_dnd": True,
            "buttons": True,
            **overrides,
        }
    }


async def _setup(hass, make_entry, plant_data, options, temp: str = "14"):
    hass.states.async_set("sensor.room_temp", temp)
    plant_data["temperature_sensor"] = "sensor.room_temp"
    plant_data["location_light"] = "bright_indirect"
    entry = make_entry(plant_data, options)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def test_in_window() -> None:
    from homeassistant.util import dt as dt_util  # noqa: PLC0415

    def at(hour: int, minute: int = 0):
        return dt_util.as_utc(dt_util.now().replace(hour=hour, minute=minute))

    assert in_window(at(23), "22:00:00", "07:00:00")
    assert in_window(at(3), "22:00:00", "07:00:00")
    assert not in_window(at(7, 1), "22:00:00", "07:00:00")
    assert in_window(at(12), "09:00:00", "17:00:00")
    assert not in_window(at(12), None, "07:00:00")


async def test_warning_sent_immediately_with_buttons(
    hass: HomeAssistant, make_entry, plant_data, phone, notify_calls
) -> None:
    """A warning goes out immediately with title, text, tag and buttons."""
    await _setup(hass, make_entry, plant_data, phone_options(phone.id))
    assert len(notify_calls) == 1
    data = notify_calls[0].data
    assert data["title"] == "Monstera"
    assert data["message"] == "Too cold: 14 °C (minimum 16 °C)"
    assert data["data"]["tag"] == f"plant_butler_{PLANT_ID}_too_cold"
    assert data["data"]["clickAction"] == "entityId:sensor.monstera_status"
    assert [a["title"] for a in data["data"]["actions"]] == ["In 1 h", "Tomorrow"]
    # Resolved -> notification is removed from the phone
    hass.states.async_set("sensor.room_temp", "20")
    await hass.async_block_till_done()
    assert notify_calls[-1].data == {
        "message": "clear_notification",
        "data": {"tag": f"plant_butler_{PLANT_ID}_too_cold"},
    }


async def test_watered_button(
    hass: HomeAssistant, make_entry, plant_data, phone, notify_calls, freezer
) -> None:
    """'Watered' in the notification marks the plant as watered."""
    await _setup(hass, make_entry, plant_data, phone_options(phone.id), temp="20")
    await _tick(hass, freezer, timedelta(days=9))  # watering overdue -> warning
    water = [c for c in notify_calls if c.data["data"]["tag"].endswith("needs_water")]
    assert water[0].data["message"] == "Watering overdue for 2 days – 300 ml"
    assert water[0].data["data"]["actions"][0] == {
        "action": f"PLANT_BUTLER|DONE|{PLANT_ID}|water",
        "title": "Watered",
    }
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": f"PLANT_BUTLER|DONE|{PLANT_ID}|water"},
    )
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "off"
    assert notify_calls[-1].data["message"] == "clear_notification"


async def test_snooze(
    hass: HomeAssistant, make_entry, plant_data, phone, notify_calls, freezer
) -> None:
    """'In 1 h' sends the reminder again after an hour if still open."""
    await _setup(hass, make_entry, plant_data, phone_options(phone.id))
    assert len(notify_calls) == 1
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": f"PLANT_BUTLER|SNOOZE|{PLANT_ID}|too_cold|1"},
    )
    await hass.async_block_till_done()
    await _tick(hass, freezer, timedelta(minutes=30))
    assert len(notify_calls) == 1
    await _tick(hass, freezer, timedelta(minutes=31))
    assert len(notify_calls) == 2


async def test_quiet_hours_hold(
    hass: HomeAssistant, make_entry, plant_data, phone, notify_calls, freezer
) -> None:
    """Warnings wait until the quiet hours end; critical comes through."""
    freezer.move_to("2026-06-01 23:00:00+00:00")
    options = phone_options(phone.id, quiet_start="22:00:00", quiet_end="07:00:00")
    await _setup(hass, make_entry, plant_data, options)
    assert notify_calls == []
    hass.states.async_set("sensor.room_temp", "11")  # critical
    await hass.async_block_till_done()
    assert len(notify_calls) == 1
    hass.states.async_set("sensor.room_temp", "14")  # back to warning, nothing new
    await hass.async_block_till_done()
    assert len(notify_calls) == 1


async def test_quiet_hours_release(
    hass: HomeAssistant, make_entry, plant_data, phone, notify_calls, freezer
) -> None:
    """A held warning is sent when the quiet hours end."""
    freezer.move_to("2026-06-01 23:00:00+00:00")
    options = phone_options(phone.id, quiet_start="22:00:00", quiet_end="07:00:00")
    await _setup(hass, make_entry, plant_data, options)
    assert notify_calls == []
    await _tick(hass, freezer, timedelta(hours=7))  # 06:00
    assert notify_calls == []
    await _tick(hass, freezer, timedelta(hours=1, minutes=1))  # 07:01
    assert len(notify_calls) == 1


async def test_do_not_disturb_hold(
    hass: HomeAssistant, make_entry, plant_data, phone, notify_calls
) -> None:
    """With the phone in do-not-disturb, warnings wait until it ends."""
    er.async_get(hass).async_get_or_create(
        "sensor",
        "mobile_app",
        "dphone_dnd_sensor",
        device_id=phone.id,
        suggested_object_id="dphone_do_not_disturb_sensor",
    )
    hass.states.async_set("sensor.dphone_do_not_disturb_sensor", "priority_only")
    await _setup(hass, make_entry, plant_data, phone_options(phone.id))
    assert notify_calls == []
    hass.states.async_set("sensor.dphone_do_not_disturb_sensor", "off")
    await hass.async_block_till_done()
    assert len(notify_calls) == 1


async def test_critical_breaks_dnd_and_repeats(
    hass: HomeAssistant, make_entry, plant_data, phone, notify_calls, freezer
) -> None:
    """Critical uses the alarm channel when allowed and repeats."""
    options = phone_options(phone.id, critical_breaks_dnd=True, critical_repeat_hours=4)
    await _setup(hass, make_entry, plant_data, options, temp="11")
    assert len(notify_calls) == 1
    assert notify_calls[0].data["data"]["channel"] == "alarm_stream"
    assert notify_calls[0].data["data"]["push"]["interruption-level"] == "critical"
    await _tick(hass, freezer, timedelta(hours=3))
    assert len(notify_calls) == 1
    await _tick(hass, freezer, timedelta(hours=1, minutes=1))
    assert len(notify_calls) == 2


async def test_daily_summary(
    hass: HomeAssistant, make_entry, plant_data, phone, notify_calls, freezer
) -> None:
    """Notices are collected into the daily summary."""
    freezer.move_to("2026-06-01 07:55:00+00:00")
    area = ar.async_get(hass).async_create("Esszimmer")
    plant_data["area_id"] = area.id
    options = phone_options(phone.id, info="summary", warning="summary")
    await _setup(hass, make_entry, plant_data, options)
    assert notify_calls == []
    await _tick(hass, freezer, timedelta(minutes=5))  # 08:00
    assert len(notify_calls) == 1
    assert notify_calls[0].data["title"] == "Plant Butler – today"
    assert (
        notify_calls[0].data["message"]
        == "Esszimmer: Monstera: Too cold: 14 °C (minimum 16 °C)"
    )


async def test_topics_filter(
    hass: HomeAssistant, make_entry, plant_data, phone, notify_calls
) -> None:
    """A topic that is not selected sends nothing."""
    await _setup(
        hass, make_entry, plant_data, phone_options(phone.id, topics=["water"])
    )
    assert notify_calls == []


async def test_mute_switch(
    hass: HomeAssistant, make_entry, plant_data, phone, notify_calls
) -> None:
    """A muted plant sends nothing; unmuted it notifies again."""
    await _setup(hass, make_entry, plant_data, phone_options(phone.id), temp="20")
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.monstera_notifications"},
        blocking=True,
    )
    hass.states.async_set("sensor.room_temp", "14")
    await hass.async_block_till_done()
    assert notify_calls == []
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.monstera_notifications"},
        blocking=True,
    )
    hass.states.async_set("sensor.room_temp", "11")
    await hass.async_block_till_done()
    assert len(notify_calls) == 1


async def test_announcements_in_plant_room(
    hass: HomeAssistant, make_entry, plant_data
) -> None:
    """Announcements go to voice assistants and speakers in the plant's room."""
    areas = ar.async_get(hass)
    dining = areas.async_create("Esszimmer")
    kitchen = areas.async_create("Küche")
    ent_reg = er.async_get(hass)
    for entity_id, area in (
        ("assist_satellite.dining", dining),
        ("assist_satellite.kitchen", kitchen),
        ("media_player.dining_ma", dining),
        ("media_player.dining_speaker", dining),
    ):
        domain, object_id = entity_id.split(".")
        entry = ent_reg.async_get_or_create(
            domain, "test", object_id, suggested_object_id=object_id
        )
        ent_reg.async_update_entity(entry.entity_id, area_id=area.id)
    hass.states.async_set(
        "media_player.dining_ma",
        "playing",
        {"supported_features": MediaPlayerEntityFeature.MEDIA_ANNOUNCE},
    )
    hass.states.async_set("media_player.dining_speaker", "idle", {"volume_level": 0.2})
    hass.states.async_set("tts.piper", "unknown")
    announce = async_mock_service(hass, "assist_satellite", "announce")
    play = async_mock_service(hass, "media_player", "play_media")
    speak = async_mock_service(hass, "tts", "speak")
    volume = async_mock_service(hass, "media_player", "volume_set")
    plant_data["area_id"] = dining.id
    options = {
        "announce": {
            "satellites": ["assist_satellite.dining", "assist_satellite.kitchen"],
            "speakers": ["media_player.dining_ma", "media_player.dining_speaker"],
            "where": "room",
            "topics": TOPICS,
            "info": "off",
            "warning": "immediate",
            "critical": "immediate",
            "summary_time": "08:00:00",
            "quiet_start": None,
            "quiet_end": None,
            "critical_in_quiet": False,
            "volume": 50,
            "tts_engine": "tts.piper",
        }
    }
    await _setup(hass, make_entry, plant_data, options)
    assert len(announce) == 1
    assert announce[0].data["entity_id"] == ["assist_satellite.dining"]
    assert (
        announce[0].data["message"]
        == "Monstera, Esszimmer: it is too cold, 14 degrees."
    )
    assert play[0].data["announce"] is True
    assert play[0].data["entity_id"] == "media_player.dining_ma"
    assert (
        play[0]
        .data["media_content_id"]
        .startswith("media-source://tts/tts.piper?message=")
    )
    assert speak[0].data["media_player_entity_id"] == "media_player.dining_speaker"
    assert volume[0].data["volume_level"] == 0.5
