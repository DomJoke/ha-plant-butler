"""Human readable texts used in state attributes and the checklist."""

from __future__ import annotations

PROBLEM_TEXTS: dict[str, dict[str, str]] = {
    "de": {
        "needs_water": "Braucht Wasser",
        "too_wet": "Erde zu nass",
        "needs_fertilizer": "Braucht Dünger",
        "too_cold": "Zu kalt",
        "too_hot": "Zu warm",
        "too_dark": "Standort zu dunkel",
        "too_bright": "Standort zu hell",
        "sensor_unavailable": "Sensor nicht erreichbar",
    },
    "en": {
        "needs_water": "Needs water",
        "too_wet": "Soil too wet",
        "needs_fertilizer": "Needs fertilizer",
        "too_cold": "Too cold",
        "too_hot": "Too warm",
        "too_dark": "Location too dark",
        "too_bright": "Location too bright",
        "sensor_unavailable": "Sensor unavailable",
    },
}
ALL_GOOD = {"de": "Alles in Ordnung", "en": "All good"}


def problem_summary(problems: list[str], language: str) -> str:
    """Return a readable summary of the active problems."""
    lang = language[:2] if language[:2] in PROBLEM_TEXTS else "en"
    if not problems:
        return ALL_GOOD[lang]
    texts = PROBLEM_TEXTS[lang]
    return ", ".join(texts.get(p, p) for p in problems)
