"""Fixtures for Plant Butler tests."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.plant_butler.const import DOMAIN

PLANT_ID = "plant1"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations."""


@pytest.fixture
def plant_data() -> dict[str, Any]:
    """Subentry data of a test plant without sensors."""
    return {
        "name": "Monstera",
        "species": "monstera",
        "water_need": "medium",
        "light_need": "bright_indirect",
        "location_light": "partial_shade",
        "temperature_min": 16,
        "temperature_max": 30,
        "fertilizer_interval": 14,
        "fertilizer_winter_interval": 0,
        "fertilizer_unit": "ml_per_l",
        "fertilizer_amount": 5,
        "watering_amount": 300,
        "icon": "mdi:leaf",
    }


@pytest.fixture
async def area(hass: HomeAssistant) -> ar.AreaEntry:
    """Create an area."""
    return ar.async_get(hass).async_create("Esszimmer")


@pytest.fixture
def make_entry(hass: HomeAssistant):
    """Create a hub entry with one plant."""

    def _make(
        data: dict[str, Any], options: dict[str, Any] | None = None
    ) -> MockConfigEntry:
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Plant Butler",
            data={},
            options=options or {},
            subentries_data=[
                ConfigSubentryDataWithId(
                    data=data,
                    subentry_id=PLANT_ID,
                    subentry_type="plant",
                    title=data["name"],
                    unique_id=None,
                )
            ],
        )
        entry.add_to_hass(hass)
        return entry

    return _make
