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
