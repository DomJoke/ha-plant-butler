"""Tests for the config flow and the plant subentry flow."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    area_registry as ar,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.plant_butler.config_flow import suggest_sensors
from custom_components.plant_butler.const import DOMAIN


async def test_hub_flow(hass: HomeAssistant) -> None:
    """The hub can be created once."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Plant Butler"
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT


async def _hub(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Plant Butler", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_add_plant_with_species_defaults(hass: HomeAssistant) -> None:
    """Adding a plant prefills the profile from the database."""
    area = ar.async_get(hass).async_create("Esszimmer")
    entry = await _hub(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "plant"), context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Kaktus Fenster", "species": "nope"}
    )
    assert result["errors"] == {"species": "unknown_species"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Kaktus Fenster", "species": "kaktus", "area_id": area.id},
    )
    assert result["step_id"] == "sensors"
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["step_id"] == "profile"
    suggested = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }
    assert suggested["water_need"] == "very_low"
    assert suggested["light_need"] == "full_sun"
    assert suggested["temperature_min"] == 5
    assert suggested["fertilizer_interval"] == 28

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], suggested | {"location_light": "full_sun"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert hass.states.get("sensor.kaktus_fenster_status").state == "ok"
    assert hass.states.get("select.kaktus_fenster_water_need").state == "very_low"
    assert hass.states.get("number.kaktus_fenster_watering_interval").state == "21.0"
    assert (
        hass.states.get("sensor.kaktus_fenster_status").attributes["icon"]
        == "mdi:cactus"
    )


async def test_reconfigure_plant(hass: HomeAssistant) -> None:
    """Reconfiguring keeps the plant and applies new values over overrides."""
    entry = await _hub(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "plant"), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Farn", "species": "farn_schwert"}
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    profile = {
        str(k): k.description["suggested_value"]
        for k in result["data_schema"].schema
        if k.description and "suggested_value" in k.description
    }
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], profile
    )
    await hass.async_block_till_done()
    subentry_id = next(iter(entry.subentries))

    # Override via entity, then reconfigure with a new temperature
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.farn_temperature_min", "value": 10},
        blocking=True,
    )
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "plant"),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Farn", "species": "farn_schwert"}
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    current = {
        str(k): k.description["suggested_value"]
        for k in result["data_schema"].schema
        if k.description and "suggested_value" in k.description
    }
    assert current["temperature_min"] == 10  # effective value shown
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], current | {"temperature_min": 12}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert hass.states.get("number.farn_temperature_min").state == "12.0"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Climate strength can be changed."""
    entry = await _hub(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"climate_strength": 0.5}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["climate_strength"] == 0.5


async def test_suggest_sensors(hass: HomeAssistant) -> None:
    """Room sensors are suggested, but not the soil probe's own temperature."""
    area = ar.async_get(hass).async_create("Esszimmer")
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    soil = dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("test", "soil")}
    )
    room = dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("test", "room")}
    )
    dev_reg.async_update_device(soil.id, area_id=area.id)
    dev_reg.async_update_device(room.id, area_id=area.id)
    for device, uid, device_class in (
        (soil, "soil_moisture", "moisture"),
        (soil, "soil_temperature", "temperature"),
        (soil, "soil_illuminance", "illuminance"),
        (room, "room_temperature", "temperature"),
        (room, "room_humidity", "humidity"),
    ):
        ent_reg.async_get_or_create(
            "sensor",
            "test",
            uid,
            device_id=device.id,
            original_device_class=device_class,
            suggested_object_id=uid,
        )
    assert suggest_sensors(hass, area.id) == {
        "moisture_sensor": "sensor.soil_moisture",
        "illuminance_sensor": "sensor.soil_illuminance",
        "temperature_sensor": "sensor.room_temperature",
        "humidity_sensor": "sensor.room_humidity",
    }
    assert suggest_sensors(hass, None) == {}
