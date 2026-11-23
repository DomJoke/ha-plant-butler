"""Tests for learning the watering rhythm."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.plant_butler.const import DOMAIN, TOPICS
from custom_components.plant_butler.learning import apply_vote, target_factor

from .conftest import PLANT_ID


# --------------------------------------------------------------- pure logic
def test_target_factor() -> None:
    # 8 days passed, interval 8: moist -> 1.3, ok -> 1.0, dry -> 0.75
    assert target_factor(8, 8, "moist") == pytest.approx(1.3)
    assert target_factor(8, 8, "ok") == 1.0
    assert target_factor(8, 8, "dry") == 0.75
    assert target_factor(30, 8, "moist") == 2.0  # bounded


def test_votes_need_agreement() -> None:
    # normal: 2 of the last 3 votes must agree, max 10 % per step
    factor, votes = apply_vote(1.0, 1.3, [], "normal", kind="at_least")
    assert factor == 1.0 and votes == [1]
    factor, votes = apply_vote(factor, 1.3, votes, "normal", kind="at_least")
    assert factor == 1.1
    # strong: immediately, max 15 %
    assert apply_vote(1.0, 1.5, [], "strong")[0] == 1.15
    # gentle: 3 of 4, max 5 %
    factor, votes = 1.0, []
    for _ in range(2):
        factor, votes = apply_vote(factor, 1.5, votes, "gentle")
    assert factor == 1.0
    factor, votes = apply_vote(factor, 1.5, votes, "gentle")
    assert factor == 1.05


def test_bounds_from_answers() -> None:
    """Late + very dry and early + moist carry no information."""
    # 12 days instead of 8, very dry: at most 9 days -> no lengthening
    late_dry = target_factor(12, 8, "dry")
    assert apply_vote(1.0, late_dry, [], "strong", kind="at_most") == (1.0, [0])
    # 12 days, still moist -> lengthen
    late_moist = target_factor(12, 8, "moist")
    assert apply_vote(1.0, late_moist, [], "strong", kind="at_least")[0] == 1.15
    # 4 days, still moist -> nothing
    early_moist = target_factor(4, 8, "moist")
    assert apply_vote(1.0, early_moist, [], "strong", kind="at_least") == (1.0, [0])
    # 4 days, very dry -> shorten
    early_dry = target_factor(4, 8, "dry")
    assert apply_vote(1.0, early_dry, [], "strong", kind="at_most")[0] == 0.85
    # never below 0.5 / above 2.0
    assert apply_vote(0.52, 0.1, [], "strong")[0] == 0.5


# -------------------------------------------------------------- integration
async def _setup(hass, make_entry, plant_data, options: dict[str, Any] | None = None):
    plant_data["location_light"] = "bright_indirect"  # 7-day interval
    entry = make_entry(plant_data, options)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _water(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        DOMAIN,
        "mark_done",
        {"entity_id": "sensor.monstera_status", "task": "water"},
        blocking=True,
    )


async def _feedback(hass: HomeAssistant, answer: str) -> None:
    await hass.services.async_call(
        DOMAIN,
        "watering_feedback",
        {"entity_id": "sensor.monstera_status", "answer": answer},
        blocking=True,
    )


async def test_feedback_lengthens_interval(
    hass: HomeAssistant, make_entry, plant_data, freezer
) -> None:
    """Two 'still moist' answers make the interval 10 % longer."""
    await _setup(hass, make_entry, plant_data)
    await _water(hass)
    for _ in range(2):
        await _advance(hass, freezer, timedelta(days=7))
        await _water(hass)
        await _feedback(hass, "moist")
    state = hass.states.get("sensor.monstera_learned_interval")
    assert state.state == "10"
    assert state.attributes["interval_effective_days"] == 7.7
    assert [h["answer"] for h in state.attributes["history"]] == ["moist", "moist"]
    # Applied to the schedule: due after 7.7 days, not 7
    await _advance(hass, freezer, timedelta(days=7, hours=6))
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "off"
    await _advance(hass, freezer, timedelta(hours=12))
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "on"


async def test_feedback_without_previous_watering_is_ignored(
    hass: HomeAssistant, make_entry, plant_data
) -> None:
    """The first watering has nothing to compare with."""
    await _setup(hass, make_entry, plant_data)
    await _water(hass)
    await _feedback(hass, "dry")
    history = hass.states.get("sensor.monstera_learned_interval").attributes["history"]
    assert history[0]["applied"] is False


async def test_undo_watering(
    hass: HomeAssistant, make_entry, plant_data, freezer
) -> None:
    """Undo restores schedule and learned values from before the watering."""
    await _setup(hass, make_entry, plant_data, {"learning_strength": "strong"})
    await _water(hass)
    await _advance(hass, freezer, timedelta(days=8))
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "on"
    await _water(hass)
    await _feedback(hass, "moist")  # strong: applied at once
    assert hass.states.get("sensor.monstera_learned_interval").state == "15"
    assert hass.states.get("button.monstera_undo_watering").state != "unavailable"
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.monstera_undo_watering"}, blocking=True
    )
    assert hass.states.get("binary_sensor.monstera_needs_water").state == "on"
    assert hass.states.get("sensor.monstera_learned_interval").state == "0"
    assert hass.states.get("button.monstera_undo_watering").state == "unavailable"


async def test_pause_and_off(
    hass: HomeAssistant, make_entry, plant_data, freezer
) -> None:
    """Paused: nothing new is learned. Off: learned values are not applied but kept."""
    entry = await _setup(hass, make_entry, plant_data, {"learning_strength": "strong"})
    await _water(hass)
    await _advance(hass, freezer, timedelta(days=7))
    await _water(hass)
    await _feedback(hass, "moist")
    assert hass.states.get("sensor.monstera_learned_interval").state == "15"

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.plant_butler_learning_paused"},
        blocking=True,
    )
    await _advance(hass, freezer, timedelta(days=8))
    await _water(hass)
    await _feedback(hass, "moist")
    assert hass.states.get("sensor.monstera_learned_interval").state == "15"
    assert (
        hass.states.get("sensor.monstera_learned_interval").attributes["paused"] is True
    )

    hass.config_entries.async_update_entry(
        entry, options={"learn_interval": False, "learn_amount": False}
    )
    await hass.async_block_till_done()
    attrs = hass.states.get("sensor.monstera_learned_interval").attributes
    assert attrs["interval_effective_days"] == attrs["interval_base_days"] == 7.0
    hass.config_entries.async_update_entry(
        entry, options={"learning_strength": "normal"}
    )
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.monstera_learned_interval").attributes[
            "interval_factor"
        ]
        == 1.15
    )


async def test_reset_learning(
    hass: HomeAssistant, make_entry, plant_data, freezer
) -> None:
    """The reset button forgets everything."""
    await _setup(hass, make_entry, plant_data, {"learning_strength": "strong"})
    await _water(hass)
    await _advance(hass, freezer, timedelta(days=7))
    await _water(hass)
    await _feedback(hass, "dry")
    assert hass.states.get("sensor.monstera_learned_interval").state == "-12"
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.monstera_reset_learning"},
        blocking=True,
    )
    assert hass.states.get("sensor.monstera_learned_interval").state == "0"


async def test_sensor_drying_time_and_amount(
    hass: HomeAssistant, make_entry, plant_data, freezer
) -> None:
    """A soil sensor teaches the interval and the amount without questions."""
    hass.states.async_set("sensor.soil", "20")
    plant_data["moisture_sensor"] = "sensor.soil"
    await _setup(hass, make_entry, plant_data, {"learning_strength": "strong"})
    # Watering detected by a sharp rise, but only to 38 % (target range 25-60, mid 42.5)
    freezer.tick(timedelta(minutes=5))
    hass.states.async_set("sensor.soil", "38")
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=5))
    hass.states.async_set("sensor.soil", "37")
    await hass.async_block_till_done()
    await _advance(hass, freezer, timedelta(hours=4))
    assert hass.states.get("sensor.monstera_learned_amount").state == "10"
    assert (
        hass.states.get("sensor.monstera_status").attributes["care"]["watering_amount"]
        == 330
    )
    # Soil reaches 'water below' after 10 days -> longer interval (7 calculated)
    await _advance(hass, freezer, timedelta(days=10))
    hass.states.async_set("sensor.soil", "20")
    await hass.async_block_till_done()
    history = hass.states.get("sensor.monstera_learned_interval").attributes["history"]
    assert history[-1]["answer"] == "sensor"
    assert hass.states.get("sensor.monstera_learned_interval").state == "15"


async def test_phone_feedback_and_info(
    hass: HomeAssistant, make_entry, plant_data, freezer
) -> None:
    """'Watered' on the phone asks for feedback; a changed rhythm is announced."""
    app = MockConfigEntry(domain="mobile_app")
    app.add_to_hass(hass)
    phone = dr.async_get(hass).async_get_or_create(
        config_entry_id=app.entry_id,
        identifiers={("mobile_app", "dphone")},
        name="dPhone",
    )
    calls = async_mock_service(hass, "notify", "mobile_app_dphone")
    options = {
        "learning_strength": "strong",
        "phone": {
            "devices": [phone.id],
            "topics": TOPICS,
            "info": "off",
            "warning": "immediate",
            "critical": "immediate",
            "summary_time": "08:00:00",
            "critical_repeat_hours": 0,
            "critical_breaks_dnd": False,
            "quiet_start": None,
            "quiet_end": None,
            "respect_dnd": False,
            "buttons": True,
        },
    }
    await _setup(hass, make_entry, plant_data, options)
    await _water(hass)
    await _advance(hass, freezer, timedelta(days=9))  # overdue -> warning with buttons
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": f"PLANT_BUTLER|DONE|{PLANT_ID}|water"},
    )
    await hass.async_block_till_done()
    question = next(
        c for c in calls if c.data["data"].get("tag", "").endswith("feedback")
    )
    assert question.data["message"].startswith("Watered ✓ – How was the soil before?")
    assert [a["title"] for a in question.data["data"]["actions"]] == [
        "Still moist",
        "Slightly dry",
        "Very dry",
    ]
    assert (
        question.data["data"]["clickAction"] == "entityId:button.monstera_undo_watering"
    )
    # 9 days passed and it was still moist -> interval 7 -> 8 days
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": f"PLANT_BUTLER|FEEDBACK|{PLANT_ID}|moist"},
    )
    await hass.async_block_till_done()
    info = [
        c for c in calls if c.data.get("data", {}).get("tag", "").endswith("learning")
    ]
    assert (
        info[0].data["message"]
        == "Learned: I will remind you every 8 instead of 7 days."
    )
    # then the amount question follows
    questions = [
        c for c in calls if c.data.get("data", {}).get("tag", "").endswith("feedback")
    ]
    assert questions[-1].data["message"].startswith("How was the amount?")
    assert [a["title"] for a in questions[-1].data["data"]["actions"]] == [
        "Too much",
        "Just right",
        "Too little",
    ]
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": f"PLANT_BUTLER|AMOUNT|{PLANT_ID}|too_little"},
    )
    await hass.async_block_till_done()
    info = [
        c for c in calls if c.data.get("data", {}).get("tag", "").endswith("learning")
    ]
    assert (
        info[-1].data["message"]
        == "Learned: watering amount from now on 330 instead of 300 ml."
    )


async def _amount(hass: HomeAssistant, answer: str) -> None:
    await hass.services.async_call(
        DOMAIN,
        "watering_feedback",
        {"entity_id": "sensor.monstera_status", "amount": answer},
        blocking=True,
    )


def _amount_ml(hass: HomeAssistant) -> int:
    return hass.states.get("sensor.monstera_status").attributes["care"][
        "watering_amount"
    ]


async def test_amount_feedback(
    hass: HomeAssistant, make_entry, plant_data, freezer
) -> None:
    """'Too little' raises the amount, 'too much' lowers it, only once per watering."""
    await _setup(hass, make_entry, plant_data, {"learning_strength": "strong"})
    assert _amount_ml(hass) == 300
    await _water(hass)
    await _amount(hass, "too_little")
    assert _amount_ml(hass) == 330  # +10 % (half the way to +20 %)
    await _amount(hass, "too_little")  # no open question any more
    assert _amount_ml(hass) == 330
    await _advance(hass, freezer, timedelta(days=7))
    await _water(hass)
    await _amount(hass, "too_much")
    assert _amount_ml(hass) < 330
    history = hass.states.get("sensor.monstera_status").attributes["care"]["learning"]
    assert history["amount_change_percent"] != 0


async def test_amount_checkbox_off(hass: HomeAssistant, make_entry, plant_data) -> None:
    """With 'learn watering amount' off nothing is collected or applied."""
    await _setup(
        hass,
        make_entry,
        plant_data,
        {"learning_strength": "strong", "learn_amount": False},
    )
    await _water(hass)
    learning = hass.states.get("sensor.monstera_status").attributes["care"]["learning"]
    assert learning["awaiting_amount"] is False
    await _amount(hass, "too_little")
    assert _amount_ml(hass) == 300


async def test_feedback_service_needs_a_value(
    hass: HomeAssistant, make_entry, plant_data
) -> None:
    await _setup(hass, make_entry, plant_data)
    with pytest.raises(Exception):  # noqa: B017
        await hass.services.async_call(
            DOMAIN,
            "watering_feedback",
            {"entity_id": "sensor.monstera_status"},
            blocking=True,
        )
