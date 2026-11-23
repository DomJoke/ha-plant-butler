"""Numbers for Plant Butler (fine-tuned target values)."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_FERTILIZER_AMOUNT,
    CONF_FERTILIZER_INTERVAL,
    CONF_FERTILIZER_UNIT,
    CONF_FERTILIZER_WINTER_INTERVAL,
    CONF_MOISTURE_MAX,
    CONF_MOISTURE_MIN,
    CONF_MOISTURE_SENSOR,
    CONF_TEMPERATURE_MAX,
    CONF_TEMPERATURE_MIN,
    CONF_WATERING_AMOUNT,
    CONF_WATERING_INTERVAL,
)
from .entity import PlantEntity
from .plant import PlantButlerConfigEntry, PlantRuntime

FERTILIZER_UNIT_LABELS = {"ml_per_l": "ml/l", "ml": "ml", "sticks": "pcs", "g": "g"}


@dataclass(frozen=True, kw_only=True)
class PlantNumberDescription(NumberEntityDescription):
    """Describes a plant number."""

    requires_moisture_sensor: bool = False


NUMBERS: tuple[PlantNumberDescription, ...] = (
    PlantNumberDescription(
        key=CONF_MOISTURE_MIN,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        device_class=NumberDeviceClass.MOISTURE,
        requires_moisture_sensor=True,
    ),
    PlantNumberDescription(
        key=CONF_MOISTURE_MAX,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        device_class=NumberDeviceClass.MOISTURE,
        requires_moisture_sensor=True,
    ),
    PlantNumberDescription(
        key=CONF_TEMPERATURE_MIN,
        native_min_value=-20,
        native_max_value=40,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    PlantNumberDescription(
        key=CONF_TEMPERATURE_MAX,
        native_min_value=-20,
        native_max_value=45,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    PlantNumberDescription(
        key=CONF_WATERING_INTERVAL,
        native_min_value=1,
        native_max_value=60,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.DAYS,
    ),
    PlantNumberDescription(
        key=CONF_WATERING_AMOUNT,
        native_min_value=0,
        native_max_value=10000,
        native_step=10,
        native_unit_of_measurement="ml",
    ),
    PlantNumberDescription(
        key=CONF_FERTILIZER_INTERVAL,
        native_min_value=0,
        native_max_value=180,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.DAYS,
    ),
    PlantNumberDescription(
        key=CONF_FERTILIZER_WINTER_INTERVAL,
        native_min_value=0,
        native_max_value=180,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.DAYS,
    ),
    PlantNumberDescription(
        key=CONF_FERTILIZER_AMOUNT,
        native_min_value=0,
        native_max_value=1000,
        native_step=0.5,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantButlerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up numbers."""
    for plant in entry.runtime_data.plants.values():
        has_moisture = plant.sensor(CONF_MOISTURE_SENSOR) is not None
        async_add_entities(
            [
                PlantSettingNumber(plant, desc)
                for desc in NUMBERS
                if has_moisture or not desc.requires_moisture_sensor
            ],
            config_subentry_id=plant.id,
        )


class PlantSettingNumber(PlantEntity, NumberEntity):
    """A numeric target value of the plant."""

    _platform_domain = "number"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    entity_description: PlantNumberDescription

    def __init__(
        self, plant: PlantRuntime, description: PlantNumberDescription
    ) -> None:
        """Initialize."""
        super().__init__(plant, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        value = self.plant.settings.get(self.entity_description.key)
        return None if value is None else float(value)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Fertilizer amount unit follows the configured fertilizer type."""
        if self.entity_description.key == CONF_FERTILIZER_AMOUNT:
            unit = self.plant.settings.get(CONF_FERTILIZER_UNIT) or "ml_per_l"
            return FERTILIZER_UNIT_LABELS.get(unit, unit)
        return self.entity_description.native_unit_of_measurement

    async def async_set_native_value(self, value: float) -> None:
        """Override the value."""
        await self.plant.async_set_setting(self.entity_description.key, value)
