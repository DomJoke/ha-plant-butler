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


# ------------------------------------------------------------ notification texts
MESSAGES: dict[str, dict[str, str]] = {
    "de": {
        "water_due": "Gießen fällig",
        "water_overdue": "Gießen seit {days} Tagen überfällig",
        "water_overdue_1": "Gießen seit 1 Tag überfällig",
        "fertilize_due": "Düngen fällig",
        "too_wet": "Erde zu nass ({value} %)",
        "too_cold": "Zu kalt: {value} °C (Minimum {limit} °C)",
        "too_hot": "Zu warm: {value} °C (Maximum {limit} °C)",
        "too_dark": "Standort zu dunkel",
        "too_bright": "Standort zu hell",
        "sensor_unavailable": "Sensor nicht erreichbar",
        "summary_title": "Plant Butler – heute",
        "task_water": "{plant} gießen",
        "task_fertilize": "{plant} düngen",
        "no_room": "Ohne Raum",
        "btn_watered": "Gegossen",
        "btn_fertilized": "Gedüngt",
        "btn_1h": "In 1 Std.",
        "btn_tomorrow": "Morgen",
        "say_intro": "Plant Butler.",
        "say_attention": "Achtung!",
        "say_water": "{plant}, {room}: braucht Wasser{amount}.",
        "say_water_overdue": "{plant}, {room}: braucht seit {days} Tagen Wasser{amount}.",
        "say_amount": ", {value} Milliliter",
        "say_fertilize": "{plant}, {room}: möchte gedüngt werden.",
        "say_too_wet": "{plant}, {room}: die Erde ist zu nass.",
        "say_too_cold": "{plant}, {room}: es ist zu kalt, {value} Grad.",
        "say_too_hot": "{plant}, {room}: es ist zu warm, {value} Grad.",
        "say_too_dark": "{plant}, {room}: der Standort ist zu dunkel.",
        "say_too_bright": "{plant}, {room}: der Standort ist zu hell.",
        "say_sensor_unavailable": "{plant}, {room}: ein Sensor ist nicht erreichbar.",
    },
    "en": {
        "water_due": "Watering due",
        "water_overdue": "Watering overdue for {days} days",
        "water_overdue_1": "Watering overdue for 1 day",
        "fertilize_due": "Fertilizing due",
        "too_wet": "Soil too wet ({value} %)",
        "too_cold": "Too cold: {value} °C (minimum {limit} °C)",
        "too_hot": "Too warm: {value} °C (maximum {limit} °C)",
        "too_dark": "Location too dark",
        "too_bright": "Location too bright",
        "sensor_unavailable": "Sensor unavailable",
        "summary_title": "Plant Butler – today",
        "task_water": "water {plant}",
        "task_fertilize": "fertilize {plant}",
        "no_room": "No room",
        "btn_watered": "Watered",
        "btn_fertilized": "Fertilized",
        "btn_1h": "In 1 h",
        "btn_tomorrow": "Tomorrow",
        "say_intro": "Plant Butler.",
        "say_attention": "Attention!",
        "say_water": "{plant}, {room}: needs water{amount}.",
        "say_water_overdue": "{plant}, {room}: has needed water for {days} days{amount}.",
        "say_amount": ", {value} millilitres",
        "say_fertilize": "{plant}, {room}: would like to be fertilized.",
        "say_too_wet": "{plant}, {room}: the soil is too wet.",
        "say_too_cold": "{plant}, {room}: it is too cold, {value} degrees.",
        "say_too_hot": "{plant}, {room}: it is too warm, {value} degrees.",
        "say_too_dark": "{plant}, {room}: the location is too dark.",
        "say_too_bright": "{plant}, {room}: the location is too bright.",
        "say_sensor_unavailable": "{plant}, {room}: a sensor is unavailable.",
    },
}


def messages(language: str) -> dict[str, str]:
    """Return the message texts for a language (English fallback)."""
    return MESSAGES.get(language[:2], MESSAGES["en"])


def fmt_number(value: float, language: str) -> str:
    """Format a number with up to one decimal in the local style."""
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if language.startswith("de") else text
