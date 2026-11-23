"""Plant Butler: plant care helper for Home Assistant."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
    AMOUNT_ANSWERS,
    CONF_ILLUMINANCE_SENSOR,
    CONF_SPECIES,
    DOMAIN,
    FEEDBACK_ANSWERS,
    SERVICE_FEEDBACK,
    SERVICE_MARK_DONE,
    SERVICE_UNDO,
    SPECIES_CUSTOM,
    STORAGE_VERSION,
    TASKS,
)
from .plant import ButlerHub, PlantButlerConfigEntry, PlantRuntime
from .species import async_get_species_db, species_name

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.IMAGE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TODO,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

TARGET_SCHEMA = {
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
}
FEEDBACK_SCHEMA = vol.All(
    vol.Schema(
        {
            **TARGET_SCHEMA,
            vol.Optional("answer"): vol.In(FEEDBACK_ANSWERS),
            vol.Optional("amount"): vol.In(AMOUNT_ANSWERS),
        }
    ),
    cv.has_at_least_one_key("answer", "amount"),
)
UNDO_SCHEMA = vol.Schema(TARGET_SCHEMA)

MARK_DONE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("task"): vol.In(TASKS),
    }
)


def _plants_for_call(hass: HomeAssistant, call: ServiceCall) -> list[PlantRuntime]:
    """Resolve the plants targeted by a service call."""
    subentry_ids: set[str] = set()
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    for entity_id in call.data.get(ATTR_ENTITY_ID, []):
        if (entry := ent_reg.async_get(entity_id)) and entry.config_subentry_id:
            subentry_ids.add(entry.config_subentry_id)
    for device_id in call.data.get(ATTR_DEVICE_ID, []):
        if device := dev_reg.async_get(device_id):
            subentry_ids.update(
                ident[1] for ident in device.identifiers if ident[0] == DOMAIN
            )
    plants: list[PlantRuntime] = []
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        hub: ButlerHub = entry.runtime_data
        plants.extend(p for sid, p in hub.plants.items() if sid in subentry_ids)
    if not plants:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_plant_found"
        )
    return plants


REMOVED_ENTITY_SUFFIXES = ("_light_problem", "_temperature_problem")

CARD_URL_BASE = f"/{DOMAIN}_static"
CARD_FILE = "plant-butler-card.js"


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the dashboard card and load it on every dashboard."""
    if "frontend" not in hass.config.components or hass.http is None:
        return
    folder = Path(__file__).parent / "frontend"

    def _file_hash() -> str:
        return hashlib.sha1((folder / CARD_FILE).read_bytes()).hexdigest()[:8]

    version = await hass.async_add_executor_job(_file_hash)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_BASE, str(folder), cache_headers=False)]
    )
    add_extra_js_url(hass, f"{CARD_URL_BASE}/{CARD_FILE}?v={version}")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services and the dashboard card."""
    await _async_register_card(hass)

    async def mark_done(call: ServiceCall) -> None:
        for plant in _plants_for_call(hass, call):
            await plant.async_mark_done(call.data["task"])

    async def feedback(call: ServiceCall) -> None:
        for plant in _plants_for_call(hass, call):
            if "answer" in call.data:
                await plant.async_feedback(call.data["answer"])
            if "amount" in call.data:
                await plant.async_amount_feedback(call.data["amount"])

    async def undo(call: ServiceCall) -> None:
        for plant in _plants_for_call(hass, call):
            await plant.async_undo_watering()

    hass.services.async_register(
        DOMAIN, SERVICE_MARK_DONE, mark_done, schema=MARK_DONE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_FEEDBACK, feedback, schema=FEEDBACK_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_UNDO, undo, schema=UNDO_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PlantButlerConfigEntry) -> bool:
    """Set up Plant Butler from a config entry."""
    hub = ButlerHub(hass, entry)
    await hub.async_load()
    db = await async_get_species_db(hass)
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Plant Butler",
        manufacturer="Plant Butler",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    for plant in hub.plants.values():
        species_id = plant.subentry.data.get(CONF_SPECIES, SPECIES_CUSTOM)
        species = db.get(species_id)
        model = species_name(species, hass.config.language) if species else None
        device = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            config_subentry_id=plant.id,
            identifiers={(DOMAIN, plant.id)},
            name=plant.name,
            manufacturer="Plant Butler",
            model=model,
            model_id=species_id,
        )
        plant.device_id = device.id
        # Apply the configured area once (later manual changes in the UI win)
        if plant.area_id != plant.state.get("applied_area"):
            if plant.area_id:
                dev_reg.async_update_device(device.id, area_id=plant.area_id)
            plant.state["applied_area"] = plant.area_id

    # Entities replaced in 0.4: problem binary sensors -> condition sensors
    # Light level exists only with a light sensor since 0.5
    ent_reg = er.async_get(hass)
    without_lux = {
        f"{plant.id}_light_level"
        for plant in hub.plants.values()
        if not plant.sensor(CONF_ILLUMINANCE_SENSOR)
    }
    for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if reg_entry.unique_id.endswith(REMOVED_ENTITY_SUFFIXES) or (
            reg_entry.unique_id in without_lux
        ):
            ent_reg.async_remove(reg_entry.entity_id)

    entry.runtime_data = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hub.async_start()
    entry.async_on_unload(hub.async_stop)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: PlantButlerConfigEntry
) -> None:
    """Reload on any change (options, plants added/changed/removed)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: PlantButlerConfigEntry
) -> bool:
    """Unload a config entry."""
    hub = entry.runtime_data
    await hub.async_save_now()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: PlantButlerConfigEntry
) -> None:
    """Remove persisted data when the integration is removed."""
    await Store[dict[str, Any]](
        hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
    ).async_remove()
