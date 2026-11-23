"""Pure calculation helpers for Plant Butler (no Home Assistant state)."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from datetime import datetime

from .const import (
    LIGHT_LEVEL_KEYS,
    LIGHT_LEVELS,
    LUX_TO_PPFD,
    SEVERITIES,
    SEVERITY_OK,
)

REFERENCE_VPD_KPA = 1.0
CLIMATE_FACTOR_MIN = 0.6
CLIMATE_FACTOR_MAX = 1.4


def vpd_kpa(temperature: float, humidity: float) -> float:
    """Vapour pressure deficit in kPa (Tetens formula)."""
    svp = 0.6108 * math.exp(17.27 * temperature / (temperature + 237.3))
    humidity = min(max(humidity, 0.0), 100.0)
    return svp * (1.0 - humidity / 100.0)


def climate_factor(
    temperature: float | None, humidity: float | None, strength: float = 1.0
) -> float:
    """Factor applied to the watering interval (<1 = dries faster).

    Warm, dry air (high VPD) shortens the interval, cool humid air lengthens it.
    """
    if temperature is None or humidity is None or strength <= 0:
        return 1.0
    vpd = max(vpd_kpa(temperature, humidity), 0.05)
    raw = math.sqrt(REFERENCE_VPD_KPA / vpd) ** strength
    return min(max(raw, CLIMATE_FACTOR_MIN), CLIMATE_FACTOR_MAX)


def dli_increment(lux: float, seconds: float) -> float:
    """Daily light integral contribution (mol/m²) of `lux` held for `seconds`."""
    return max(lux, 0.0) * LUX_TO_PPFD * seconds / 1_000_000


def light_level_for_dli(dli: float) -> str:
    """Map a daily light integral to a light level key."""
    level = LIGHT_LEVEL_KEYS[0]
    for key in LIGHT_LEVEL_KEYS:
        if dli >= LIGHT_LEVELS[key]:
            level = key
    return level


def light_index(level: str) -> int:
    """Return the ordinal of a light level."""
    return LIGHT_LEVEL_KEYS.index(level)


def light_mismatch(actual: str, need: str) -> str | None:
    """Return 'too_dark', 'too_bright' or None.

    A plant tolerates its own level and one level brighter.
    """
    a, n = light_index(actual), light_index(need)
    if a < n:
        return "too_dark"
    if a > n + 1:
        return "too_bright"
    return None


def worst_severity(severities: Iterable[str]) -> str:
    """Return the highest severity of the given ones (ok if none)."""
    worst = SEVERITY_OK
    for sev in severities:
        if SEVERITIES.index(sev) > SEVERITIES.index(worst):
            worst = sev
    return worst


def moisture_slope_per_day(samples: Sequence[tuple[datetime, float]]) -> float | None:
    """Least-squares slope of soil moisture in %-points per day.

    Needs at least 4 samples spanning 6 hours.
    """
    if len(samples) < 4:
        return None
    t0 = samples[0][0]
    xs = [(t - t0).total_seconds() / 86400 for t, _ in samples]
    if xs[-1] - xs[0] < 0.25:
        return None
    ys = [v for _, v in samples]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sxx


# --------------------------------------------------------------------------
# Care assistant: watering amount, watering interval and fertilizer dosage
# --------------------------------------------------------------------------
# All values are rules of thumb for potted plants. They give a sensible
# starting point that the user can fine-tune per plant.

# Pots are usually tapered; a cylinder overestimates the volume by ~20 %.
POT_SHAPE_FACTOR = 0.8
# Share of the pot volume that the substrate holds as plant-available water.
SUBSTRATE_WATER_CAPACITY = {"standard": 0.25, "mineral": 0.15}
# Share of that available water used up before the plant is watered again.
WATER_DEPLETION = {
    "very_low": 0.9,
    "low": 0.7,
    "medium": 0.5,
    "high": 0.35,
    "very_high": 0.25,
}
# Brighter locations dry out faster.
LIGHT_DRYING_FACTOR = {
    "very_dark": 1.4,
    "dark": 1.25,
    "partial_shade": 1.1,
    "bright_indirect": 1.0,
    "bright_some_sun": 0.9,
    "full_sun": 0.8,
}
# Terracotta evaporates through the wall, mineral substrate drains faster.
MATERIAL_DRYING_FACTOR = {"plastic": 1.0, "terracotta": 0.8}
SUBSTRATE_DRYING_FACTOR = {"standard": 1.0, "mineral": 0.85}
INTERVAL_FACTOR_MIN = 0.6
INTERVAL_FACTOR_MAX = 1.6
# Strength relative to the package dosage of a liquid fertilizer.
FEEDING_STRENGTH = {"none": 0.0, "light": 0.5, "medium": 0.75, "heavy": 1.0}
# Slow-release products
STICK_INTERVAL_DAYS = 90
GRANULE_INTERVAL_DAYS = 180
GRANULES_G_PER_LITRE = 2.5


def pot_volume_litres(diameter_cm: float, height_cm: float | None = None) -> float:
    """Approximate substrate volume of a pot in litres."""
    height = height_cm or diameter_cm * 0.9
    radius = diameter_cm / 2
    return math.pi * radius**2 * height * POT_SHAPE_FACTOR / 1000


def watering_amount_ml(volume_l: float, water_need: str, substrate: str) -> int:
    """Water needed to re-wet the pot, rounded to 10 ml."""
    amount = (
        volume_l
        * 1000
        * SUBSTRATE_WATER_CAPACITY.get(substrate, 0.25)
        * WATER_DEPLETION.get(water_need, 0.5)
    )
    return max(int(round(amount / 10) * 10), 10)


def watering_interval_factor(
    volume_l: float | None, material: str, substrate: str, light: str | None
) -> float:
    """Factor applied to the base interval of the water need level.

    Larger pots hold more water and dry out more slowly (2 l = 1.0).
    """
    size = 1.0
    if volume_l:
        size = min(max((volume_l / 2.0) ** 0.25, 0.7), 1.5)
    factor = (
        size
        * MATERIAL_DRYING_FACTOR.get(material, 1.0)
        * SUBSTRATE_DRYING_FACTOR.get(substrate, 1.0)
        * LIGHT_DRYING_FACTOR.get(light or "bright_indirect", 1.0)
    )
    return round(min(max(factor, INTERVAL_FACTOR_MIN), INTERVAL_FACTOR_MAX), 3)


def sticks_for_pot(diameter_cm: float | None) -> int:
    """Number of fertilizer sticks by pot diameter (typical package table)."""
    if not diameter_cm or diameter_cm < 12:
        return 1
    if diameter_cm < 17:
        return 2
    if diameter_cm < 24:
        return 3
    return 4


def fertilizer_plan(
    fertilizer_type: str,
    feeding: str,
    dosage_ml_per_l: float | None,
    season_interval: int,
    winter_interval: int,
    diameter_cm: float | None,
    volume_l: float | None,
) -> dict[str, float | int | str]:
    """Return interval, winter interval, amount and unit for a fertilizer."""
    strength = FEEDING_STRENGTH.get(feeding, 0.75)
    if fertilizer_type == "none" or strength == 0:
        return {"interval": 0, "winter_interval": 0, "amount": 0, "unit": "ml_per_l"}
    if fertilizer_type == "sticks":
        return {
            "interval": STICK_INTERVAL_DAYS,
            "winter_interval": 0,
            "amount": sticks_for_pot(diameter_cm),
            "unit": "sticks",
        }
    if fertilizer_type == "granules":
        grams = GRANULES_G_PER_LITRE * (volume_l or 1.0) * strength / 0.75
        return {
            "interval": GRANULE_INTERVAL_DAYS,
            "winter_interval": 0,
            "amount": max(round(grams * 2) / 2, 0.5),
            "unit": "g",
        }
    amount = (dosage_ml_per_l or 4.0) * strength
    return {
        "interval": season_interval,
        "winter_interval": winter_interval,
        "amount": max(round(amount * 2) / 2, 0.5),
        "unit": "ml_per_l",
    }
