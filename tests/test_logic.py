"""Tests for pure calculations."""

from datetime import datetime, timedelta

import pytest

from custom_components.plant_butler.logic import (
    climate_factor,
    dli_increment,
    light_level_for_dli,
    light_mismatch,
    moisture_slope_per_day,
    vpd_kpa,
    worst_severity,
)


def test_vpd_reference() -> None:
    assert vpd_kpa(22, 63) == pytest.approx(0.98, abs=0.01)
    assert vpd_kpa(26, 40) == pytest.approx(2.02, abs=0.01)


@pytest.mark.parametrize(
    ("t", "rh", "expected"),
    [(26, 40, 0.70), (22, 63, 1.01), (18, 60, 1.10), (35, 10, 0.6), (15, 95, 1.4)],
)
def test_climate_factor(t: float, rh: float, expected: float) -> None:
    assert climate_factor(t, rh) == pytest.approx(expected, abs=0.01)


def test_climate_factor_missing_or_off() -> None:
    assert climate_factor(None, 50) == 1.0
    assert climate_factor(25, None) == 1.0
    assert climate_factor(26, 40, strength=0) == 1.0


def test_light_levels() -> None:
    assert light_level_for_dli(0.5) == "very_dark"
    assert light_level_for_dli(3) == "dark"
    assert light_level_for_dli(10) == "bright_indirect"
    assert light_level_for_dli(30) == "full_sun"
    assert light_mismatch("dark", "bright_indirect") == "too_dark"
    assert light_mismatch("bright_some_sun", "bright_indirect") is None
    assert light_mismatch("full_sun", "partial_shade") == "too_bright"


def test_dli_increment() -> None:
    # 10,000 lux for 10 hours ≈ 6.7 mol/m²
    assert dli_increment(10000, 36000) == pytest.approx(6.66, abs=0.01)


def test_slope() -> None:
    t0 = datetime(2026, 1, 1)
    samples = [(t0 + timedelta(hours=h), 60 - h * 0.5) for h in range(0, 13, 3)]
    assert moisture_slope_per_day(samples) == pytest.approx(-12.0)
    assert moisture_slope_per_day(samples[:2]) is None


def test_worst() -> None:
    assert worst_severity([]) == "ok"
    assert worst_severity(["info", "critical", "warning"]) == "critical"
