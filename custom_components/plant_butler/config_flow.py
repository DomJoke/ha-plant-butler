"""Config flow for Plant Butler: the hub plus one subentry per plant."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

import voluptuous as vol
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    AreaSelector,
    EntitySelector,
    EntitySelectorConfig,
    FileSelector,
    FileSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)
from homeassistant.util import slugify

from .const import (
    CONF_AREA,
    CONF_CLIMATE_STRENGTH,
    CONF_FERTILIZER_AMOUNT,
    CONF_FERTILIZER_INTERVAL,
    CONF_FERTILIZER_UNIT,
    CONF_FERTILIZER_WINTER_INTERVAL,
    CONF_HUMIDITY_SENSOR,
    CONF_ICON,
    CONF_ILLUMINANCE_SENSOR,
    CONF_LIGHT_NEED,
    CONF_LOCATION_LIGHT,
    CONF_MOISTURE_MAX,
    CONF_MOISTURE_MIN,
    CONF_MOISTURE_SENSOR,
    CONF_NAME,
    CONF_NOTES,
    CONF_PHOTO,
    CONF_PHOTO_UPLOAD,
    CONF_SPECIES,
    CONF_TEMPERATURE_MAX,
    CONF_TEMPERATURE_MIN,
    CONF_TEMPERATURE_SENSOR,
    CONF_WATER_NEED,
    CONF_WATERING_AMOUNT,
    CONF_WATERING_INTERVAL,
    DEFAULT_CLIMATE_STRENGTH,
    DOMAIN,
    FERTILIZER_UNITS,
    LIGHT_LEVEL_KEYS,
    SENSOR_KEYS,
    SPECIES_CUSTOM,
    SUBENTRY_TYPE_PLANT,
    WATER_LEVEL_KEYS,
)
from .species import async_get_species_db, species_defaults, species_name

PROFILE_KEYS = (
    CONF_WATER_NEED,
    CONF_LIGHT_NEED,
    CONF_LOCATION_LIGHT,
    CONF_TEMPERATURE_MIN,
    CONF_TEMPERATURE_MAX,
    CONF_WATERING_AMOUNT,
    CONF_FERTILIZER_INTERVAL,
    CONF_FERTILIZER_WINTER_INTERVAL,
    CONF_FERTILIZER_AMOUNT,
    CONF_FERTILIZER_UNIT,
    CONF_PHOTO,
    CONF_NOTES,
)

_SENSOR_CLASSES = {
    CONF_MOISTURE_SENSOR: SensorDeviceClass.MOISTURE,
    CONF_ILLUMINANCE_SENSOR: SensorDeviceClass.ILLUMINANCE,
    CONF_TEMPERATURE_SENSOR: SensorDeviceClass.TEMPERATURE,
    CONF_HUMIDITY_SENSOR: SensorDeviceClass.HUMIDITY,
}


def _level_selector(key: str, options: list[str]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=options, translation_key=key, mode=SelectSelectorMode.DROPDOWN
        )
    )


def _number(
    min_: float, max_: float, step: float, unit: str | None = None
) -> NumberSelector:
    config = NumberSelectorConfig(
        min=min_, max=max_, step=step, mode=NumberSelectorMode.BOX
    )
    if unit:
        config["unit_of_measurement"] = unit
    return NumberSelector(config)


def suggest_sensors(hass: HomeAssistant, area_id: str | None) -> dict[str, str]:
    """Suggest sensors of an area for each role.

    Room temperature/humidity come from devices without a soil moisture sensor,
    so a soil probe's own temperature is not mistaken for the room climate.
    """
    if not area_id:
        return {}
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    entries: dict[str, er.RegistryEntry] = {
        e.entity_id: e for e in er.async_entries_for_area(ent_reg, area_id)
    }
    for device in dr.async_entries_for_area(dev_reg, area_id):
        for entry in er.async_entries_for_device(ent_reg, device.id):
            if entry.area_id is None:
                entries.setdefault(entry.entity_id, entry)
    by_class: dict[str, list[er.RegistryEntry]] = {}
    for entry in sorted(entries.values(), key=lambda e: e.entity_id):
        if entry.domain != "sensor" or entry.disabled_by:
            continue
        device_class = entry.device_class or entry.original_device_class
        if device_class:
            by_class.setdefault(device_class, []).append(entry)
    soil_devices = {
        e.device_id for e in by_class.get(SensorDeviceClass.MOISTURE, []) if e.device_id
    }
    suggestions: dict[str, str] = {}
    if moisture := by_class.get(SensorDeviceClass.MOISTURE):
        suggestions[CONF_MOISTURE_SENSOR] = moisture[0].entity_id
    lux = by_class.get(SensorDeviceClass.ILLUMINANCE, [])
    lux.sort(key=lambda e: e.device_id not in soil_devices)
    if lux:
        suggestions[CONF_ILLUMINANCE_SENSOR] = lux[0].entity_id
    for key, device_class in (
        (CONF_TEMPERATURE_SENSOR, SensorDeviceClass.TEMPERATURE),
        (CONF_HUMIDITY_SENSOR, SensorDeviceClass.HUMIDITY),
    ):
        room = [
            e for e in by_class.get(device_class, []) if e.device_id not in soil_devices
        ]
        if room:
            suggestions[key] = room[0].entity_id
    return suggestions


class PlantButlerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up the Plant Butler hub."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_PLANT: PlantSubentryFlow}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return PlantButlerOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the hub."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="Plant Butler", data={})
        return self.async_show_form(step_id="user")


class PlantButlerOptionsFlow(OptionsFlow):
    """Hub options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CLIMATE_STRENGTH,
                    default=self.config_entry.options.get(
                        CONF_CLIMATE_STRENGTH, DEFAULT_CLIMATE_STRENGTH
                    ),
                ): _number(0, 2, 0.1),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


class PlantSubentryFlow(ConfigSubentryFlow):
    """Add or change a plant."""

    def __init__(self) -> None:
        """Initialize."""
        self._data: dict[str, Any] = {}
        self._previous: dict[str, Any] = {}

    # ----------------------------------------------------------------- helpers
    @property
    def _is_new(self) -> bool:
        return self.source == "user"

    async def _species_options(self) -> list[SelectOptionDict]:
        db = await async_get_species_db(self.hass)
        lang = self.hass.config.language
        options = [
            SelectOptionDict(value=sid, label=f"{species_name(s, lang)} ({s['latin']})")
            for sid, s in db.items()
        ]
        options.sort(key=lambda o: o["label"].lower())
        custom_label = "Benutzerdefiniert" if lang.startswith("de") else "Custom"
        return [SelectOptionDict(value=SPECIES_CUSTOM, label=custom_label), *options]

    def _runtime_settings(self) -> dict[str, Any]:
        """Effective settings of the plant being reconfigured, if loaded."""
        entry = self._get_entry()
        hub = getattr(entry, "runtime_data", None)
        subentry_id = self.context.get("subentry_id")
        if hub is not None and subentry_id in getattr(hub, "plants", {}):
            return hub.plants[subentry_id].settings
        return dict(self._previous)

    # ------------------------------------------------------------------- steps
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Name, species and room."""
        errors: dict[str, str] = {}
        if user_input is not None:
            db = await async_get_species_db(self.hass)
            species = user_input.get(CONF_SPECIES) or SPECIES_CUSTOM
            if species != SPECIES_CUSTOM and species not in db:
                errors[CONF_SPECIES] = "unknown_species"
            else:
                self._data.update(user_input)
                self._data[CONF_SPECIES] = species
                self._data[CONF_AREA] = user_input.get(CONF_AREA)
                return await self.async_step_sensors()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): TextSelector(),
                vol.Required(CONF_SPECIES, default=SPECIES_CUSTOM): SelectSelector(
                    SelectSelectorConfig(
                        options=await self._species_options(),
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                        sort=False,
                    )
                ),
                vol.Optional(CONF_AREA): AreaSelector(),
            }
        )
        suggested = user_input or self._previous
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change an existing plant."""
        self._previous = dict(self._get_reconfigure_subentry().data)
        return await self.async_step_user()

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Optional sensors."""
        if user_input is not None:
            for key in SENSOR_KEYS:
                self._data[key] = user_input.get(key)
            return await self.async_step_profile()

        schema = vol.Schema(
            {
                vol.Optional(key): EntitySelector(
                    EntitySelectorConfig(domain="sensor", device_class=device_class)
                )
                for key, device_class in _SENSOR_CLASSES.items()
            }
        )
        if self._is_new:
            suggested = suggest_sensors(self.hass, self._data.get(CONF_AREA))
        else:
            suggested = {k: self._previous.get(k) for k in SENSOR_KEYS}
        return self.async_show_form(
            step_id="sensors",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
        )

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Target values, prefilled from the species database."""
        db = await async_get_species_db(self.hass)
        species_id = self._data[CONF_SPECIES]
        defaults = species_defaults(db.get(species_id))

        if user_input is not None:
            return await self._async_finish(user_input, defaults)

        if not self._is_new and species_id == self._previous.get(CONF_SPECIES):
            current = {**defaults, **self._runtime_settings()}
        else:
            current = dict(defaults)
            current.setdefault(CONF_FERTILIZER_UNIT, "ml_per_l")
            for key in (
                CONF_PHOTO,
                CONF_NOTES,
                CONF_WATERING_AMOUNT,
                CONF_FERTILIZER_AMOUNT,
            ):
                if self._previous.get(key) is not None:
                    current[key] = self._previous[key]

        fields: dict[Any, Any] = {
            vol.Required(CONF_WATER_NEED): _level_selector(
                CONF_WATER_NEED, WATER_LEVEL_KEYS
            ),
            vol.Required(CONF_LIGHT_NEED): _level_selector(
                "light_level", LIGHT_LEVEL_KEYS
            ),
        }
        if not self._data.get(CONF_ILLUMINANCE_SENSOR):
            fields[vol.Optional(CONF_LOCATION_LIGHT)] = _level_selector(
                "light_level", LIGHT_LEVEL_KEYS
            )
        fields.update(
            {
                vol.Required(CONF_TEMPERATURE_MIN): _number(-20, 40, 0.5, "°C"),
                vol.Required(CONF_TEMPERATURE_MAX): _number(-20, 45, 0.5, "°C"),
                vol.Optional(CONF_WATERING_AMOUNT): _number(0, 10000, 10, "ml"),
                vol.Required(CONF_FERTILIZER_INTERVAL): _number(0, 180, 1, "d"),
                vol.Required(CONF_FERTILIZER_WINTER_INTERVAL): _number(0, 180, 1, "d"),
                vol.Optional(CONF_FERTILIZER_AMOUNT): _number(0, 1000, 0.5),
                vol.Required(CONF_FERTILIZER_UNIT): _level_selector(
                    CONF_FERTILIZER_UNIT, FERTILIZER_UNITS
                ),
                vol.Optional(CONF_PHOTO_UPLOAD): FileSelector(
                    FileSelectorConfig(accept="image/*")
                ),
                vol.Optional(CONF_PHOTO): TextSelector(),
                vol.Optional(CONF_NOTES): TextSelector(
                    TextSelectorConfig(multiline=True)
                ),
            }
        )
        schema = vol.Schema(fields)
        return self.async_show_form(
            step_id="profile",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )

    async def _async_store_photo(self, file_id: str) -> str:
        """Move an uploaded photo to www/plant_butler and return its /local url."""
        hass = self.hass
        slug = slugify(self._data[CONF_NAME]) or "plant"

        def _move() -> str:
            with process_uploaded_file(hass, file_id) as path:
                suffix = path.suffix.lower() or ".jpg"
                target_dir = Path(hass.config.path("www", DOMAIN))
                target_dir.mkdir(parents=True, exist_ok=True)
                name = f"{slug}-{uuid4().hex[:8]}{suffix}"
                shutil.copyfile(path, target_dir / name)
            return f"/local/{DOMAIN}/{name}"

        return await hass.async_add_executor_job(_move)

    async def _async_finish(
        self, user_input: dict[str, Any], defaults: dict[str, Any]
    ) -> SubentryFlowResult:
        data = dict(self._data)
        profile = dict(user_input)
        if upload := profile.pop(CONF_PHOTO_UPLOAD, None):
            profile[CONF_PHOTO] = await self._async_store_photo(upload)
        for key in PROFILE_KEYS:
            data[key] = profile.get(key)
        data[CONF_ICON] = defaults[CONF_ICON]
        data = {k: v for k, v in data.items() if v not in (None, "")}
        title = data[CONF_NAME]

        if self._is_new:
            return self.async_create_entry(title=title, data=data)

        # Values set in the dialog replace overrides made via entities
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        hub = getattr(entry, "runtime_data", None)
        if hub is not None and (plant := hub.plants.get(subentry.subentry_id)):
            overrides: dict[str, Any] = plant.state["overrides"]
            for key in PROFILE_KEYS:
                overrides.pop(key, None)
            if data.get(CONF_WATER_NEED) != self._previous.get(CONF_WATER_NEED):
                for key in (
                    CONF_MOISTURE_MIN,
                    CONF_MOISTURE_MAX,
                    CONF_WATERING_INTERVAL,
                ):
                    overrides.pop(key, None)
        return self.async_update_and_abort(entry, subentry, title=title, data=data)
