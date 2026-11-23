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
from homeassistant.data_entry_flow import section
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    AreaSelector,
    BooleanSelector,
    DeviceSelector,
    DeviceSelectorConfig,
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
    TimeSelector,
)
from homeassistant.util import slugify

from .care import (
    fertilizer_per_watering_ml,
    pot_volume,
    suggest_fertilizer,
    suggest_watering,
)
from .const import (
    CLIMATE_LEVELS,
    CONF_AREA,
    CONF_CLIMATE_LEVEL,
    CONF_CLIMATE_STRENGTH,
    CONF_FEEDING,
    CONF_FERTILIZER_AMOUNT,
    CONF_FERTILIZER_DOSAGE,
    CONF_FERTILIZER_INTERVAL,
    CONF_FERTILIZER_TYPE,
    CONF_FERTILIZER_UNIT,
    CONF_FERTILIZER_WINTER_INTERVAL,
    CONF_HUMIDITY_SENSOR,
    CONF_ICON,
    CONF_ILLUMINANCE_SENSOR,
    CONF_LEARN_AMOUNT,
    CONF_LEARN_INTERVAL,
    CONF_LEARNING_STRENGTH,
    CONF_LIGHT_NEED,
    CONF_LOCATION_LIGHT,
    CONF_MOISTURE_MAX,
    CONF_MOISTURE_MIN,
    CONF_MOISTURE_SENSOR,
    CONF_NAME,
    CONF_NOTES,
    CONF_PHOTO,
    CONF_PHOTO_UPLOAD,
    CONF_PLANT_SIZE,
    CONF_POT_DIAMETER,
    CONF_POT_HEIGHT,
    CONF_POT_MATERIAL,
    CONF_SPECIES,
    CONF_SUBSTRATE,
    CONF_TEMPERATURE_MAX,
    CONF_TEMPERATURE_MIN,
    CONF_TEMPERATURE_SENSOR,
    CONF_WATER_NEED,
    CONF_WATERING_AMOUNT,
    CONF_WATERING_INTERVAL,
    DEFAULT_ANNOUNCE_OPTIONS,
    DEFAULT_CLIMATE_STRENGTH,
    DEFAULT_FERTILIZER_DOSAGE,
    DEFAULT_LEARNING_STRENGTH,
    DEFAULT_PHONE_OPTIONS,
    DOMAIN,
    FEEDING_LEVELS,
    FERTILIZER_TYPES,
    FERTILIZER_UNITS,
    LEARNING_STRENGTHS,
    LIGHT_LEVEL_KEYS,
    MODE_IMMEDIATE,
    MODE_OFF,
    MODE_SUMMARY,
    OPT_ANNOUNCE,
    OPT_PHONE,
    PLANT_SIZES,
    POT_MATERIALS,
    SENSOR_KEYS,
    SPECIES_CUSTOM,
    SUBENTRY_TYPE_PLANT,
    SUBSTRATES,
    TOPICS,
    WATER_LEVEL_KEYS,
)
from .species import async_get_species_db, species_defaults, species_name

# Inputs of the care assistant step
ASSISTANT_KEYS = (
    CONF_WATER_NEED,
    CONF_LIGHT_NEED,
    CONF_LOCATION_LIGHT,
    CONF_PLANT_SIZE,
    CONF_FEEDING,
    CONF_POT_DIAMETER,
    CONF_POT_HEIGHT,
    CONF_POT_MATERIAL,
    CONF_SUBSTRATE,
    CONF_FERTILIZER_TYPE,
    CONF_FERTILIZER_DOSAGE,
)
# Results of the assistant, editable in the profile step
CARE_KEYS = (
    CONF_WATERING_INTERVAL,
    CONF_WATERING_AMOUNT,
    CONF_FERTILIZER_INTERVAL,
    CONF_FERTILIZER_WINTER_INTERVAL,
    CONF_FERTILIZER_AMOUNT,
    CONF_FERTILIZER_UNIT,
)
PROFILE_KEYS = (
    *CARE_KEYS,
    CONF_TEMPERATURE_MIN,
    CONF_TEMPERATURE_MAX,
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


def _flatten(user_input: dict[str, Any]) -> dict[str, Any]:
    """Merge the values of form sections into one dict."""
    flat: dict[str, Any] = {}
    for value in (
        user_input.values()
        if all(isinstance(v, dict) for v in user_input.values())
        else [user_input]
    ):
        flat.update(value)
    return flat


def _mode_selector(key: str, modes: list[str]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=modes, translation_key=key, mode=SelectSelectorMode.DROPDOWN
        )
    )


def _topics_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=TOPICS,
            translation_key="topics",
            multiple=True,
            mode=SelectSelectorMode.LIST,
        )
    )


class PlantButlerOptionsFlow(OptionsFlow):
    """Settings page: general, phone notifications, announcements."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the settings menu."""
        return self.async_show_menu(
            step_id="init", menu_options=["general", OPT_PHONE, OPT_ANNOUNCE]
        )

    def _save(self, key: str | None, values: dict[str, Any]) -> ConfigFlowResult:
        options = dict(self.config_entry.options)
        if key is None:
            options.update(values)
        else:
            options[key] = values
        return self.async_create_entry(data=options)

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """General settings."""
        if user_input is not None:
            options = dict(self.config_entry.options)
            options.pop(CONF_CLIMATE_STRENGTH, None)  # replaced by the level
            options.update(user_input)
            return self.async_create_entry(data=options)
        options = self.config_entry.options
        if CONF_CLIMATE_LEVEL in options:
            climate = options[CONF_CLIMATE_LEVEL]
        else:  # numeric setting from before 0.7 -> nearest level
            strength = float(
                options.get(CONF_CLIMATE_STRENGTH, DEFAULT_CLIMATE_STRENGTH)
            )
            climate = min(
                CLIMATE_LEVELS, key=lambda k: abs(CLIMATE_LEVELS[k] - strength)
            )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LEARNING_STRENGTH,
                    default=options.get(
                        CONF_LEARNING_STRENGTH, DEFAULT_LEARNING_STRENGTH
                    ),
                ): _mode_selector(CONF_LEARNING_STRENGTH, LEARNING_STRENGTHS),
                vol.Required(
                    CONF_LEARN_INTERVAL, default=options.get(CONF_LEARN_INTERVAL, True)
                ): BooleanSelector(),
                vol.Required(
                    CONF_LEARN_AMOUNT, default=options.get(CONF_LEARN_AMOUNT, True)
                ): BooleanSelector(),
                vol.Required(CONF_CLIMATE_LEVEL, default=climate): _mode_selector(
                    CONF_CLIMATE_LEVEL, list(CLIMATE_LEVELS)
                ),
            }
        )
        return self.async_show_form(step_id="general", data_schema=schema)

    async def async_step_phone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Phone notifications (Companion app)."""
        if user_input is not None:
            values = _flatten(user_input)
            for key in ("quiet_start", "quiet_end"):
                values.setdefault(key, None)
            return self._save(OPT_PHONE, {**DEFAULT_PHONE_OPTIONS, **values})
        current = {
            **DEFAULT_PHONE_OPTIONS,
            **self.config_entry.options.get(OPT_PHONE, {}),
        }
        immediate_summary = [MODE_OFF, MODE_SUMMARY, MODE_IMMEDIATE]
        schema = vol.Schema(
            {
                vol.Required("recipients"): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                "devices", default=current["devices"]
                            ): DeviceSelector(
                                DeviceSelectorConfig(
                                    integration="mobile_app", multiple=True
                                )
                            ),
                        }
                    ),
                    {"collapsed": False},
                ),
                vol.Required("topics_section"): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                "topics", default=current["topics"]
                            ): _topics_selector()
                        }
                    ),
                    {"collapsed": False},
                ),
                vol.Required("levels"): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "info", default=current["info"]
                            ): _mode_selector("notify_mode", immediate_summary),
                            vol.Required(
                                "warning", default=current["warning"]
                            ): _mode_selector("notify_mode", immediate_summary),
                            vol.Required(
                                "critical", default=current["critical"]
                            ): _mode_selector(
                                "notify_mode", [MODE_OFF, MODE_IMMEDIATE]
                            ),
                            vol.Required(
                                "summary_time", default=current["summary_time"]
                            ): TimeSelector(),
                            vol.Required(
                                "critical_repeat_hours",
                                default=current["critical_repeat_hours"],
                            ): _number(0, 48, 1, "h"),
                            vol.Required(
                                "critical_breaks_dnd",
                                default=current["critical_breaks_dnd"],
                            ): BooleanSelector(),
                        }
                    ),
                    {"collapsed": False},
                ),
                vol.Required("quiet"): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                "quiet_start",
                                description={"suggested_value": current["quiet_start"]},
                            ): TimeSelector(),
                            vol.Optional(
                                "quiet_end",
                                description={"suggested_value": current["quiet_end"]},
                            ): TimeSelector(),
                            vol.Required(
                                "respect_dnd", default=current["respect_dnd"]
                            ): BooleanSelector(),
                        }
                    ),
                    {"collapsed": False},
                ),
                vol.Required("buttons_section"): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "buttons", default=current["buttons"]
                            ): BooleanSelector()
                        }
                    ),
                    {"collapsed": True},
                ),
            }
        )
        return self.async_show_form(step_id=OPT_PHONE, data_schema=schema)

    async def async_step_announce(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Announcements on voice assistants and speakers."""
        if user_input is not None:
            values = _flatten(user_input)
            for key in ("volume", "tts_engine", "quiet_start", "quiet_end"):
                values.setdefault(key, None)
            return self._save(OPT_ANNOUNCE, {**DEFAULT_ANNOUNCE_OPTIONS, **values})
        current = {
            **DEFAULT_ANNOUNCE_OPTIONS,
            **self.config_entry.options.get(OPT_ANNOUNCE, {}),
        }
        tts_default = current["tts_engine"] or next(
            iter(sorted(self.hass.states.async_entity_ids("tts"))), None
        )
        schema = vol.Schema(
            {
                vol.Required("targets"): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                "satellites", default=current["satellites"]
                            ): EntitySelector(
                                EntitySelectorConfig(
                                    domain="assist_satellite", multiple=True
                                )
                            ),
                            vol.Optional(
                                "speakers", default=current["speakers"]
                            ): EntitySelector(
                                EntitySelectorConfig(
                                    domain="media_player", multiple=True
                                )
                            ),
                            vol.Required(
                                "where", default=current["where"]
                            ): _mode_selector("announce_where", ["room", "all"]),
                        }
                    ),
                    {"collapsed": False},
                ),
                vol.Required("topics_section"): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                "topics", default=current["topics"]
                            ): _topics_selector()
                        }
                    ),
                    {"collapsed": False},
                ),
                vol.Required("levels"): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "info", default=current["info"]
                            ): _mode_selector("notify_mode", [MODE_OFF, MODE_SUMMARY]),
                            vol.Required(
                                "warning", default=current["warning"]
                            ): _mode_selector(
                                "notify_mode", [MODE_OFF, MODE_SUMMARY, MODE_IMMEDIATE]
                            ),
                            vol.Required(
                                "critical", default=current["critical"]
                            ): _mode_selector(
                                "notify_mode", [MODE_OFF, MODE_IMMEDIATE]
                            ),
                            vol.Required(
                                "summary_time", default=current["summary_time"]
                            ): TimeSelector(),
                        }
                    ),
                    {"collapsed": False},
                ),
                vol.Required("quiet"): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                "quiet_start",
                                description={"suggested_value": current["quiet_start"]},
                            ): TimeSelector(),
                            vol.Optional(
                                "quiet_end",
                                description={"suggested_value": current["quiet_end"]},
                            ): TimeSelector(),
                            vol.Required(
                                "critical_in_quiet",
                                default=current["critical_in_quiet"],
                            ): BooleanSelector(),
                        }
                    ),
                    {"collapsed": False},
                ),
                vol.Required("sound"): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                "volume",
                                description={"suggested_value": current["volume"]},
                            ): _number(0, 100, 5, "%"),
                            vol.Optional(
                                "tts_engine",
                                description={"suggested_value": tts_default},
                            ): EntitySelector(EntitySelectorConfig(domain="tts")),
                        }
                    ),
                    {"collapsed": True},
                ),
            }
        )
        return self.async_show_form(step_id=OPT_ANNOUNCE, data_schema=schema)


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
            return await self.async_step_assistant()

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

    async def _async_species(self) -> dict[str, Any] | None:
        db = await async_get_species_db(self.hass)
        return db.get(self._data[CONF_SPECIES])

    def _keeps_species(self) -> bool:
        return not self._is_new and self._data[CONF_SPECIES] == self._previous.get(
            CONF_SPECIES
        )

    async def async_step_assistant(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Care assistant: what the plant needs and what pot it lives in."""
        defaults = species_defaults(await self._async_species())
        if user_input is not None:
            for key in ASSISTANT_KEYS:
                self._data[key] = user_input.get(key)
            return await self.async_step_profile()

        current: dict[str, Any] = {
            CONF_PLANT_SIZE: "normal",
            CONF_POT_MATERIAL: "plastic",
            CONF_SUBSTRATE: "standard",
            CONF_FERTILIZER_TYPE: "liquid",
            CONF_FERTILIZER_DOSAGE: DEFAULT_FERTILIZER_DOSAGE,
            **defaults,
        }
        if not self._is_new:
            runtime = self._runtime_settings()
            keep = (
                ASSISTANT_KEYS
                if self._keeps_species()
                else (
                    CONF_LOCATION_LIGHT,
                    CONF_POT_DIAMETER,
                    CONF_POT_HEIGHT,
                    CONF_POT_MATERIAL,
                    CONF_SUBSTRATE,
                    CONF_FERTILIZER_TYPE,
                    CONF_FERTILIZER_DOSAGE,
                )
            )
            current.update({k: runtime[k] for k in keep if runtime.get(k) is not None})

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
                vol.Required(CONF_PLANT_SIZE): _level_selector(
                    CONF_PLANT_SIZE, PLANT_SIZES
                ),
                vol.Optional(CONF_POT_DIAMETER): _number(4, 100, 1, "cm"),
                vol.Optional(CONF_POT_HEIGHT): _number(4, 100, 1, "cm"),
                vol.Required(CONF_POT_MATERIAL): _level_selector(
                    CONF_POT_MATERIAL, POT_MATERIALS
                ),
                vol.Required(CONF_SUBSTRATE): _level_selector(
                    CONF_SUBSTRATE, SUBSTRATES
                ),
                vol.Required(CONF_FEEDING): _level_selector(
                    CONF_FEEDING, FEEDING_LEVELS
                ),
                vol.Required(CONF_FERTILIZER_TYPE): _level_selector(
                    CONF_FERTILIZER_TYPE, FERTILIZER_TYPES
                ),
                vol.Optional(CONF_FERTILIZER_DOSAGE): _number(0, 50, 0.5, "ml/l"),
            }
        )
        return self.async_show_form(
            step_id="assistant",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(fields), current
            ),
        )

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Results of the assistant plus temperature, photo and notes."""
        defaults = species_defaults(await self._async_species())

        if user_input is not None:
            return await self._async_finish(user_input, defaults)

        values = {**defaults, **{k: v for k, v in self._data.items() if v is not None}}
        suggestion = {
            **suggest_watering(values),
            **suggest_fertilizer(
                values,
                int(defaults[CONF_FERTILIZER_INTERVAL]),
                int(defaults[CONF_FERTILIZER_WINTER_INTERVAL]),
            ),
        }
        current: dict[str, Any] = {
            CONF_TEMPERATURE_MIN: defaults[CONF_TEMPERATURE_MIN],
            CONF_TEMPERATURE_MAX: defaults[CONF_TEMPERATURE_MAX],
            **suggestion,
        }
        if not self._is_new:
            runtime = self._runtime_settings()
            for key in (CONF_PHOTO, CONF_NOTES):
                if runtime.get(key):
                    current[key] = runtime[key]
            if self._keeps_species():
                current[CONF_TEMPERATURE_MIN] = runtime.get(
                    CONF_TEMPERATURE_MIN, current[CONF_TEMPERATURE_MIN]
                )
                current[CONF_TEMPERATURE_MAX] = runtime.get(
                    CONF_TEMPERATURE_MAX, current[CONF_TEMPERATURE_MAX]
                )
                # Unchanged assistant inputs: keep the values tuned so far
                if all(self._data.get(k) == runtime.get(k) for k in ASSISTANT_KEYS):
                    current.update(
                        {k: runtime[k] for k in CARE_KEYS if runtime.get(k) is not None}
                    )

        volume = pot_volume(values)
        per_watering = fertilizer_per_watering_ml(current)
        placeholders = {
            "volume": f"{volume:.1f}" if volume else "–",
            "watering_amount": str(suggestion.get(CONF_WATERING_AMOUNT, "–")),
            "watering_interval": str(suggestion[CONF_WATERING_INTERVAL]),
            "fertilizer_total": f"{per_watering:g}" if per_watering else "–",
        }

        fields: dict[Any, Any] = {
            vol.Required(CONF_WATERING_INTERVAL): _number(1, 90, 1, "d"),
            vol.Optional(CONF_WATERING_AMOUNT): _number(0, 10000, 10, "ml"),
            vol.Required(CONF_TEMPERATURE_MIN): _number(-20, 40, 0.5, "°C"),
            vol.Required(CONF_TEMPERATURE_MAX): _number(-20, 45, 0.5, "°C"),
            vol.Required(CONF_FERTILIZER_INTERVAL): _number(0, 365, 1, "d"),
            vol.Required(CONF_FERTILIZER_WINTER_INTERVAL): _number(0, 365, 1, "d"),
            vol.Optional(CONF_FERTILIZER_AMOUNT): _number(0, 1000, 0.5),
            vol.Required(CONF_FERTILIZER_UNIT): _level_selector(
                CONF_FERTILIZER_UNIT, FERTILIZER_UNITS
            ),
            vol.Optional(CONF_PHOTO_UPLOAD): FileSelector(
                FileSelectorConfig(accept="image/*")
            ),
            vol.Optional(CONF_PHOTO): TextSelector(),
            vol.Optional(CONF_NOTES): TextSelector(TextSelectorConfig(multiline=True)),
        }
        return self.async_show_form(
            step_id="profile",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(fields), current
            ),
            description_placeholders=placeholders,
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
        if data.get(CONF_FERTILIZER_AMOUNT) == 0:
            data[CONF_FERTILIZER_AMOUNT] = None
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
