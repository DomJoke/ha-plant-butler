"""Plant photo as image entity."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_PHOTO
from .entity import PlantEntity
from .plant import PlantButlerConfigEntry, PlantRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantButlerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the photo entity for plants that have a photo."""
    for plant in entry.runtime_data.plants.values():
        if plant.settings.get(CONF_PHOTO):
            async_add_entities([PlantPhoto(hass, plant)], config_subentry_id=plant.id)


def local_photo_path(hass: HomeAssistant, photo: str) -> Path | None:
    """Map a /local/ url to the file in the www folder."""
    if not photo.startswith("/local/"):
        return None
    www = Path(hass.config.path("www")).resolve()
    path = (www / photo.removeprefix("/local/")).resolve()
    return path if path.is_relative_to(www) else None


class PlantPhoto(PlantEntity, ImageEntity):
    """The plant photo."""

    _platform_domain = "image"

    def __init__(self, hass: HomeAssistant, plant: PlantRuntime) -> None:
        """Initialize."""
        PlantEntity.__init__(self, plant, "photo")
        ImageEntity.__init__(self, hass)
        photo: str = plant.settings[CONF_PHOTO]
        self._photo = photo
        self._attr_image_last_updated = dt_util.utcnow()
        if photo.startswith(("http://", "https://")):
            self._attr_image_url = photo

    async def async_image(self) -> bytes | None:
        """Return the image bytes for local photos."""
        if isinstance(self._attr_image_url, str):
            return await super().async_image()
        path = local_photo_path(self.hass, self._photo)
        if path is None:
            return None
        guessed = mimetypes.guess_type(path.name)[0]
        if guessed:
            self._attr_content_type = guessed

        def _read() -> bytes | None:
            return path.read_bytes() if path.is_file() else None

        return await self.hass.async_add_executor_job(_read)
