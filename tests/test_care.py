"""Tests for the care assistant calculations."""

import pytest

from custom_components.plant_butler.care import (
    fertilizer_per_watering_ml,
    suggest_fertilizer,
    suggest_watering,
)
from custom_components.plant_butler.logic import (
    fertilizer_plan,
    pot_volume_litres,
    sticks_for_pot,
    watering_amount_ml,
    watering_interval_factor,
)


def test_pot_volume() -> None:
    assert pot_volume_litres(14) == pytest.approx(1.55, abs=0.01)
    assert pot_volume_litres(24, 20) == pytest.approx(7.24, abs=0.01)


@pytest.mark.parametrize(
    ("volume", "level", "substrate", "expected"),
    [
        (1.55, "medium", "standard", 190),
        (7.82, "medium", "standard", 980),
        (1.55, "very_high", "standard", 100),
        (0.57, "very_low", "mineral", 80),
    ],
)
def test_watering_amount(volume, level, substrate, expected) -> None:
    assert watering_amount_ml(volume, level, substrate) == expected


def test_interval_factor() -> None:
    assert (
        watering_interval_factor(2.0, "plastic", "standard", "bright_indirect") == 1.0
    )
    assert watering_interval_factor(
        1.55, "plastic", "standard", "dark"
    ) == pytest.approx(1.173, abs=0.001)
    # Bigger pot -> longer, terracotta + sun -> shorter, clamped
    assert watering_interval_factor(100, "plastic", "standard", "very_dark") == 1.6
    assert watering_interval_factor(0.2, "terracotta", "mineral", "full_sun") == 0.6
    assert watering_interval_factor(None, "plastic", "standard", None) == 1.0


def test_suggest_watering() -> None:
    values = {"water_need": "medium", "pot_diameter": 14, "location_light": "dark"}
    assert suggest_watering(values) == {"watering_interval": 8, "watering_amount": 190}
    # No pot: interval only
    assert suggest_watering({"water_need": "high"}) == {"watering_interval": 4}


def test_fertilizer_plan() -> None:
    assert sticks_for_pot(10) == 1
    assert sticks_for_pot(20) == 3
    liquid = fertilizer_plan("liquid", "medium", 4, 14, 0, 14, 1.5)
    assert liquid == {
        "interval": 14,
        "winter_interval": 0,
        "amount": 3.0,
        "unit": "ml_per_l",
    }
    sticks = fertilizer_plan("sticks", "heavy", None, 7, 0, 20, 5)
    assert (
        sticks["unit"] == "sticks"
        and sticks["amount"] == 3
        and sticks["interval"] == 90
    )
    granules = fertilizer_plan("granules", "medium", None, 14, 0, 20, 4)
    assert granules["amount"] == 10.0 and granules["unit"] == "g"
    assert fertilizer_plan("liquid", "none", 4, 14, 0, 14, 1)["interval"] == 0
    assert fertilizer_plan("none", "heavy", 4, 14, 0, 14, 1)["interval"] == 0


def test_suggest_fertilizer_and_total() -> None:
    plan = suggest_fertilizer(
        {"fertilizer_type": "liquid", "feeding": "light", "fertilizer_dosage": 5},
        21,
        42,
    )
    assert plan == {
        "fertilizer_interval": 21,
        "fertilizer_winter_interval": 42,
        "fertilizer_amount": 2.5,
        "fertilizer_unit": "ml_per_l",
    }
    assert fertilizer_per_watering_ml({**plan, "watering_amount": 400}) == 1.0
    assert fertilizer_per_watering_ml({**plan}) is None
