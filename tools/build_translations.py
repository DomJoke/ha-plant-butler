"""Generate strings.json and translations/{en,de}.json."""
import json
import sys
from pathlib import Path

base = Path(sys.argv[1])

LEVELS = {
    "water": {
        "en": {"very_low": "Very low (cacti, succulents)", "low": "Low (ZZ plant, snake plant)",
               "medium": "Medium (monstera, ficus, pothos)", "high": "High (ferns, calathea)",
               "very_high": "Very high (papyrus, herbs on the balcony)"},
        "de": {"very_low": "Sehr wenig (Kakteen, Sukkulenten)", "low": "Wenig (Zamioculcas, Bogenhanf)",
               "medium": "Mittel (Monstera, Ficus, Efeutute)", "high": "Viel (Farne, Calathea)",
               "very_high": "Sehr viel (Zyperngras, Balkonkräuter)"},
    },
    "light": {
        "en": {"very_dark": "Very dark", "dark": "Dark", "partial_shade": "Partial shade",
               "bright_indirect": "Bright, indirect", "bright_some_sun": "Bright with some sun",
               "full_sun": "Direct sun"},
        "de": {"very_dark": "Sehr dunkel", "dark": "Dunkel", "partial_shade": "Halbschatten",
               "bright_indirect": "Hell, indirekt", "bright_some_sun": "Hell mit etwas Sonne",
               "full_sun": "Direkte Sonne"},
    },
    "unit": {
        "en": {"ml_per_l": "ml per litre of water (liquid)", "ml": "ml", "sticks": "Sticks (pieces)", "g": "Gram (granules)"},
        "de": {"ml_per_l": "ml pro Liter Gießwasser (flüssig)", "ml": "ml", "sticks": "Stäbchen (Stück)", "g": "Gramm (Granulat)"},
    },
    "severity": {
        "en": {"ok": "OK", "info": "Info", "warning": "Warning", "critical": "Critical"},
        "de": {"ok": "OK", "info": "Info", "warning": "Warnung", "critical": "Kritisch"},
    },
    "task": {
        "en": {"water": "Water", "fertilize": "Fertilize"},
        "de": {"water": "Gießen", "fertilize": "Düngen"},
    },
}

T = {
    "en": {
        "hub_desc": "Plant Butler keeps track of your plants. After setup, add plants with \"+ Add plant\" on the integration page.",
        "single": "Plant Butler is already set up. Add plants on its integration page.",
        "climate": "Strength of the room climate correction",
        "climate_desc": "0 = off, 1 = default, 2 = strong. Warm, dry air shortens the watering interval for plants without a soil sensor.",
        "plant": "Plant", "add": "Add plant", "reconf": "Edit plant",
        "user_title": "Plant", "user_desc": "Choose the species to prefill all target values from the database, or \"Custom\" to enter them yourself.",
        "name": "Name", "species": "Species", "area": "Room",
        "sensors_title": "Sensors (all optional)",
        "sensors_desc": "Without a soil sensor a schedule is used. Room temperature and humidity correct it for evaporation.",
        "moisture": "Soil moisture sensor", "illum": "Light sensor", "temp": "Room temperature sensor", "hum": "Room humidity sensor",
        "profile_title": "Care profile",
        "profile_desc": "Target values from the database – change anything you like. Water need: very low = let the soil dry out completely, medium = water when the top few cm are dry, very high = keep constantly moist.",
        "water_need": "Water need", "light_need": "Light need", "location_light": "Light at the location (without light sensor)",
        "tmin": "Minimum temperature", "tmax": "Maximum temperature", "wamount": "Watering amount",
        "fint": "Fertilizing interval (0 = never)", "fwint": "Fertilizing interval in winter rest (0 = pause)",
        "famount": "Fertilizer amount", "funit": "Fertilizer type / unit", "upload": "Upload photo",
        "photo": "Photo URL or /local/ path", "notes": "Notes",
        "unknown_species": "Unknown species – pick one from the list or \"Custom\".",
        "reconf_ok": "Plant updated.",
        "e": {
            "status": "Status", "next_watering": "Next watering", "next_fertilizing": "Next fertilizing",
            "dli": "Daily light", "light_level": "Light level",
            "needs_water": "Needs water", "needs_fertilizer": "Needs fertilizer", "light_problem": "Light problem",
            "temperature_problem": "Temperature problem", "mark_watered": "Watered", "mark_fertilized": "Fertilized",
            "water_need": "Water need", "light_need": "Light need", "location_light": "Light at location",
            "moisture_min": "Water below", "moisture_max": "Moisture maximum", "temperature_min": "Temperature minimum",
            "temperature_max": "Temperature maximum", "watering_interval": "Watering interval",
            "watering_amount": "Watering amount", "fertilizer_interval": "Fertilizing interval",
            "fertilizer_winter_interval": "Fertilizing interval winter", "fertilizer_amount": "Fertilizer amount",
            "winter_rest": "Winter rest", "photo": "Photo", "checklist": "Plant care",
        },
        "svc_name": "Mark care task done", "svc_desc": "Marks watering or fertilizing as done for the given plants and restarts the schedule.",
        "svc_ent": "Plant entities", "svc_ent_d": "Any entity of the plant.", "svc_dev": "Plant devices",
        "svc_dev_d": "The plant devices.", "svc_task": "Task", "svc_task_d": "Which task was done.",
        "no_plant": "No Plant Butler plant found for the given target.", "unknown_task": "Unknown checklist item.",
    },
    "de": {
        "hub_desc": "Plant Butler kümmert sich um deine Pflanzen. Nach der Einrichtung fügst du Pflanzen auf der Integrationsseite mit „+ Pflanze hinzufügen“ hinzu.",
        "single": "Plant Butler ist bereits eingerichtet. Pflanzen fügst du auf der Integrationsseite hinzu.",
        "climate": "Stärke der Raumklima-Korrektur",
        "climate_desc": "0 = aus, 1 = Standard, 2 = stark. Warme, trockene Luft verkürzt das Gießintervall bei Pflanzen ohne Bodensensor.",
        "plant": "Pflanze", "add": "Pflanze hinzufügen", "reconf": "Pflanze bearbeiten",
        "user_title": "Pflanze", "user_desc": "Wähle die Art, um alle Sollwerte aus der Datenbank vorzubefüllen, oder „Benutzerdefiniert“, um sie selbst einzutragen.",
        "name": "Name", "species": "Art", "area": "Raum",
        "sensors_title": "Sensoren (alle optional)",
        "sensors_desc": "Ohne Bodensensor wird ein Zeitplan verwendet. Raumtemperatur und -feuchte korrigieren ihn für die Verdunstung.",
        "moisture": "Bodenfeuchtesensor", "illum": "Lichtsensor", "temp": "Raumtemperatursensor", "hum": "Raumfeuchtesensor",
        "profile_title": "Pflegeprofil",
        "profile_desc": "Sollwerte aus der Datenbank – alles änderbar. Wasserbedarf: sehr wenig = Erde ganz austrocknen lassen, mittel = gießen, wenn die oberen cm trocken sind, sehr viel = dauerhaft feucht halten.",
        "water_need": "Wasserbedarf", "light_need": "Lichtbedarf", "location_light": "Licht am Standort (ohne Lichtsensor)",
        "tmin": "Mindesttemperatur", "tmax": "Höchsttemperatur", "wamount": "Gießmenge",
        "fint": "Düngeintervall (0 = nie)", "fwint": "Düngeintervall in der Winterruhe (0 = Pause)",
        "famount": "Düngermenge", "funit": "Düngerart / Einheit", "upload": "Foto hochladen",
        "photo": "Foto-URL oder /local/-Pfad", "notes": "Notizen",
        "unknown_species": "Unbekannte Art – wähle eine aus der Liste oder „Benutzerdefiniert“.",
        "reconf_ok": "Pflanze aktualisiert.",
        "e": {
            "status": "Status", "next_watering": "Nächstes Gießen", "next_fertilizing": "Nächstes Düngen",
            "dli": "Tageslicht", "light_level": "Lichtstufe",
            "needs_water": "Braucht Wasser", "needs_fertilizer": "Braucht Dünger", "light_problem": "Lichtproblem",
            "temperature_problem": "Temperaturproblem", "mark_watered": "Gegossen", "mark_fertilized": "Gedüngt",
            "water_need": "Wasserbedarf", "light_need": "Lichtbedarf", "location_light": "Licht am Standort",
            "moisture_min": "Gießen ab", "moisture_max": "Feuchte-Maximum", "temperature_min": "Temperatur-Minimum",
            "temperature_max": "Temperatur-Maximum", "watering_interval": "Gießintervall",
            "watering_amount": "Gießmenge", "fertilizer_interval": "Düngeintervall",
            "fertilizer_winter_interval": "Düngeintervall Winter", "fertilizer_amount": "Düngermenge",
            "winter_rest": "Winterruhe", "photo": "Foto", "checklist": "Pflanzenpflege",
        },
        "svc_name": "Pflegeaufgabe erledigt", "svc_desc": "Markiert Gießen oder Düngen für die gewählten Pflanzen als erledigt und startet den Zeitplan neu.",
        "svc_ent": "Pflanzen-Entities", "svc_ent_d": "Beliebige Entity der Pflanze.", "svc_dev": "Pflanzen-Geräte",
        "svc_dev_d": "Die Pflanzen-Geräte.", "svc_task": "Aufgabe", "svc_task_d": "Welche Aufgabe erledigt wurde.",
        "no_plant": "Keine Plant-Butler-Pflanze für das angegebene Ziel gefunden.", "unknown_task": "Unbekannter Checklisten-Eintrag.",
    },
}


def build(lang: str) -> dict:
    t = T[lang]
    e = t["e"]
    lv = {k: v[lang] for k, v in LEVELS.items()}
    named = lambda key: {"name": e[key]}  # noqa: E731
    profile_fields = {
        "water_need": t["water_need"], "light_need": t["light_need"], "location_light": t["location_light"],
        "temperature_min": t["tmin"], "temperature_max": t["tmax"], "watering_amount": t["wamount"],
        "fertilizer_interval": t["fint"], "fertilizer_winter_interval": t["fwint"],
        "fertilizer_amount": t["famount"], "fertilizer_unit": t["funit"], "photo_upload": t["upload"],
        "photo": t["photo"], "notes": t["notes"],
    }
    flow_steps = {
        "user": {"title": t["user_title"], "description": t["user_desc"],
                 "data": {"name": t["name"], "species": t["species"], "area_id": t["area"]}},
        "sensors": {"title": t["sensors_title"], "description": t["sensors_desc"],
                    "data": {"moisture_sensor": t["moisture"], "illuminance_sensor": t["illum"],
                             "temperature_sensor": t["temp"], "humidity_sensor": t["hum"]}},
        "profile": {"title": t["profile_title"], "description": t["profile_desc"], "data": profile_fields},
    }
    return {
        "config": {
            "step": {"user": {"title": "Plant Butler", "description": t["hub_desc"]}},
            "abort": {"single_instance_allowed": t["single"]},
        },
        "options": {
            "step": {"init": {"title": "Plant Butler", "data": {"climate_strength": t["climate"]},
                              "data_description": {"climate_strength": t["climate_desc"]}}},
        },
        "config_subentries": {
            "plant": {
                "entry_type": t["plant"],
                "initiate_flow": {"user": t["add"], "reconfigure": t["reconf"]},
                "step": flow_steps,
                "error": {"unknown_species": t["unknown_species"]},
                "abort": {"reconfigure_successful": t["reconf_ok"]},
            }
        },
        "selector": {
            "water_need": {"options": lv["water"]},
            "light_level": {"options": lv["light"]},
            "fertilizer_unit": {"options": lv["unit"]},
            "task": {"options": lv["task"]},
        },
        "entity": {
            "binary_sensor": {k: named(k) for k in ["needs_water", "needs_fertilizer", "light_problem", "temperature_problem"]},
            "button": {k: named(k) for k in ["mark_watered", "mark_fertilized"]},
            "image": {"photo": named("photo")},
            "number": {k: named(k) for k in ["moisture_min", "moisture_max", "temperature_min", "temperature_max",
                                              "watering_interval", "watering_amount", "fertilizer_interval",
                                              "fertilizer_winter_interval", "fertilizer_amount"]},
            "select": {
                "water_need": {"name": e["water_need"], "state": {k: v.split(" (")[0] for k, v in lv["water"].items()}},
                "light_need": {"name": e["light_need"], "state": lv["light"]},
                "location_light": {"name": e["location_light"], "state": lv["light"]},
            },
            "sensor": {
                "status": {"name": e["status"], "state": lv["severity"]},
                "next_watering": named("next_watering"),
                "next_fertilizing": named("next_fertilizing"),
                "dli": named("dli"),
                "light_level": {"name": e["light_level"], "state": lv["light"]},
            },
            "switch": {"winter_rest": named("winter_rest")},
            "todo": {"checklist": named("checklist")},
        },
        "services": {
            "mark_done": {
                "name": t["svc_name"], "description": t["svc_desc"],
                "fields": {
                    "entity_id": {"name": t["svc_ent"], "description": t["svc_ent_d"]},
                    "device_id": {"name": t["svc_dev"], "description": t["svc_dev_d"]},
                    "task": {"name": t["svc_task"], "description": t["svc_task_d"]},
                },
            }
        },
        "exceptions": {
            "no_plant_found": {"message": t["no_plant"]},
            "unknown_task": {"message": t["unknown_task"]},
        },
    }


(base / "translations").mkdir(parents=True, exist_ok=True)
for lang in ("en", "de"):
    content = json.dumps(build(lang), ensure_ascii=False, indent=2) + "\n"
    (base / "translations" / f"{lang}.json").write_text(content, encoding="utf-8")
    if lang == "en":
        (base / "strings.json").write_text(content, encoding="utf-8")
print("ok")
