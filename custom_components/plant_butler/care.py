"""Care assistant: derive watering and fertilizing values from plant and pot."""

from __future__ import annotations

from typing import Any

from .const import (
    CONF_FEEDING,
    CONF_FERTILIZER_AMOUNT,
    CONF_FERTILIZER_DOSAGE,
    CONF_FERTILIZER_INTERVAL,
    CONF_FERTILIZER_TYPE,
    CONF_FERTILIZER_UNIT,
    CONF_FERTILIZER_WINTER_INTERVAL,
    CONF_LIGHT_NEED,
    CONF_LOCATION_LIGHT,
    CONF_POT_DIAMETER,
    CONF_POT_HEIGHT,
    CONF_POT_MATERIAL,
    CONF_SUBSTRATE,
    CONF_WATER_NEED,
    CONF_WATERING_AMOUNT,
    CONF_WATERING_INTERVAL,
    DEFAULT_FERTILIZER_DOSAGE,
    WATER_LEVELS,
)
from .logic import (
    fertilizer_plan,
    pot_volume_litres,
    watering_amount_ml,
    watering_interval_factor,
)


def pot_volume(values: dict[str, Any]) -> float | None:
    """Pot volume in litres, None if no pot diameter is known."""
    if not (diameter := values.get(CONF_POT_DIAMETER)):
        return None
    return pot_volume_litres(float(diameter), values.get(CONF_POT_HEIGHT))


def suggest_watering(values: dict[str, Any]) -> dict[str, Any]:
    """Suggested watering interval (days) and amount (ml, if pot known)."""
    level = values.get(CONF_WATER_NEED, "medium")
    base = WATER_LEVELS.get(level, WATER_LEVELS["medium"])[2]
    volume = pot_volume(values)
    light = values.get(CONF_LOCATION_LIGHT) or values.get(CONF_LIGHT_NEED)
    substrate = values.get(CONF_SUBSTRATE, "standard")
    factor = watering_interval_factor(
        volume, values.get(CONF_POT_MATERIAL, "plastic"), substrate, light
    )
    result: dict[str, Any] = {CONF_WATERING_INTERVAL: max(round(base * factor), 1)}
    if volume is not None:
        result[CONF_WATERING_AMOUNT] = watering_amount_ml(volume, level, substrate)
    return result


def suggest_fertilizer(
    values: dict[str, Any], season_interval: int, winter_interval: int
) -> dict[str, Any]:
    """Suggested fertilizer interval, winter interval, amount and unit."""
    plan = fertilizer_plan(
        values.get(CONF_FERTILIZER_TYPE, "liquid"),
        values.get(CONF_FEEDING, "medium"),
        values.get(CONF_FERTILIZER_DOSAGE, DEFAULT_FERTILIZER_DOSAGE),
        season_interval,
        winter_interval,
        values.get(CONF_POT_DIAMETER),
        pot_volume(values),
    )
    return {
        CONF_FERTILIZER_INTERVAL: plan["interval"],
        CONF_FERTILIZER_WINTER_INTERVAL: plan["winter_interval"],
        CONF_FERTILIZER_AMOUNT: plan["amount"],
        CONF_FERTILIZER_UNIT: plan["unit"],
    }


def fertilizer_per_watering_ml(settings: dict[str, Any]) -> float | None:
    """Total ml of liquid fertilizer for one watering, if computable."""
    if settings.get(CONF_FERTILIZER_UNIT, "ml_per_l") != "ml_per_l":
        return None
    amount = settings.get(CONF_FERTILIZER_AMOUNT)
    water = settings.get(CONF_WATERING_AMOUNT)
    if not amount or not water:
        return None
    return round(float(amount) * float(water) / 1000, 1)
