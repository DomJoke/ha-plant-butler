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
        "en": {"ok": "OK", "info": "Notice", "warning": "Warning", "critical": "Critical"},
        "de": {"ok": "OK", "info": "Hinweis", "warning": "Warnung", "critical": "Kritisch"},
    },
    "pot_material": {
        "en": {"plastic": "Plastic / glazed ceramic", "terracotta": "Terracotta (unglazed clay)"},
        "de": {"plastic": "Kunststoff / glasierte Keramik", "terracotta": "Terrakotta (unglasierter Ton)"},
    },
    "plant_size": {
        "en": {"small": "Small / freshly repotted (plenty of free soil)", "normal": "Normal (plant fits the pot)",
               "large": "Large / lush (lots of foliage, pot rather tight)"},
        "de": {"small": "Klein / frisch umgetopft (viel freie Erde)", "normal": "Normal (Pflanze passt zum Topf)",
               "large": "Groß / üppig (viel Laub, Topf eher knapp)"},
    },
    "substrate": {
        "en": {"standard": "Potting soil", "mineral": "Mineral / cactus soil"},
        "de": {"standard": "Blumenerde", "mineral": "Mineralisch / Kakteenerde"},
    },
    "feeding": {
        "en": {"none": "None (e.g. carnivorous plants)", "light": "Light feeder (½ package dose)",
               "medium": "Medium (¾ package dose)", "heavy": "Heavy feeder (full package dose)"},
        "de": {"none": "Keinen (z. B. fleischfressende Pflanzen)", "light": "Schwachzehrer (½ Packungsdosis)",
               "medium": "Mittel (¾ Packungsdosis)", "heavy": "Starkzehrer (volle Packungsdosis)"},
    },
    "fertilizer_type": {
        "en": {"liquid": "Liquid fertilizer", "sticks": "Fertilizer sticks", "granules": "Slow-release granules", "none": "No fertilizer"},
        "de": {"liquid": "Flüssigdünger", "sticks": "Düngestäbchen", "granules": "Langzeitdünger (Granulat)", "none": "Kein Dünger"},
    },
    "yesno": {
        "en": {"on": "Yes", "off": "No"},
        "de": {"on": "Ja", "off": "Nein"},
    },
    "light_cond": {
        "en": {"ok": "OK", "too_dark": "Too dark", "too_bright": "Too bright"},
        "de": {"ok": "OK", "too_dark": "Zu dunkel", "too_bright": "Zu hell"},
    },
    "temp_cond": {
        "en": {"ok": "OK", "too_cold": "Too cold", "too_hot": "Too warm"},
        "de": {"ok": "OK", "too_cold": "Zu kalt", "too_hot": "Zu warm"},
    },
    "status_attr": {
        "en": {"summary": "Summary", "plant_name": "Plant", "area": "Room", "photo": "Photo", "notes": "Notes",
               "problems": "Problem keys", "problem_severities": "Problem levels", "needs_water": "Needs water",
               "needs_fertilizer": "Needs fertilizer", "winter_rest": "Winter rest", "sensors": "Sensors",
               "targets": "Targets", "care": "Care", "light": "Light", "species": "Species"},
        "de": {"summary": "Zusammenfassung", "plant_name": "Pflanze", "area": "Raum", "photo": "Foto", "notes": "Notizen",
               "problems": "Problem-Schlüssel", "problem_severities": "Problem-Stufen", "needs_water": "Braucht Wasser",
               "needs_fertilizer": "Braucht Dünger", "winter_rest": "Winterruhe", "sensors": "Sensoren",
               "targets": "Sollwerte", "care": "Pflege", "light": "Licht", "species": "Art"},
    },
    "notify_mode": {
        "en": {"off": "Off", "summary": "Daily summary", "immediate": "Immediately"},
        "de": {"off": "Aus", "summary": "Tägliche Zusammenfassung", "immediate": "Sofort"},
    },
    "topics": {
        "en": {"water": "Watering due", "fertilize": "Fertilizing due", "wet": "Soil too wet",
               "temperature": "Temperature", "light": "Light", "sensor": "Sensor unavailable"},
        "de": {"water": "Gießen fällig", "fertilize": "Düngen fällig", "wet": "Erde zu nass",
               "temperature": "Temperatur", "light": "Licht", "sensor": "Sensor nicht erreichbar"},
    },
    "announce_where": {
        "en": {"room": "Only in the plant's room (if it has none: all selected)", "all": "All selected"},
        "de": {"room": "Nur im Raum der Pflanze (hat er keine: alle ausgewählten)", "all": "Alle ausgewählten"},
    },
    "learning_strength": {
        "en": {"gentle": "Cautious", "normal": "Balanced", "strong": "Strong"},
        "de": {"gentle": "Vorsichtig", "normal": "Ausgewogen", "strong": "Stark"},
    },
    "climate_level": {
        "en": {"off": "Off", "low": "Weak", "normal": "Medium", "strong": "Strong"},
        "de": {"off": "Aus", "low": "Schwach", "normal": "Mittel", "strong": "Stark"},
    },
    "feedback_amount": {
        "en": {"too_much": "Too much – water in the saucer / ran out at the bottom", "ok": "Just right", "too_little": "Too little – soil not fully moist"},
        "de": {"too_much": "Zu viel – Wasser im Untersetzer / lief unten raus", "ok": "Passt", "too_little": "Zu wenig – Erde nicht ganz durchfeuchtet"},
    },
    "feedback": {
        "en": {"moist": "Still moist", "ok": "Slightly dry", "dry": "Very dry"},
        "de": {"moist": "Noch feucht", "ok": "Leicht trocken", "dry": "Sehr trocken"},
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
        "options": {
            "init": {"title": "Plant Butler", "menu_options": {"general": "General", "phone": "Phone notifications", "announce": "Announcements (voice assistants & speakers)"}},
            "general": {"title": "General", "data": {"learning_strength": "Learning strength", "learn_interval": "Learn watering interval", "learn_amount": "Learn watering amount", "climate_level": "Room climate correction"},
                        "data_description": {"learning_strength": "How quickly Plant Butler adapts to your answers. Cautious: ±5 % when 3 of the last 4 answers agree. Balanced: ±10 % when 2 of 3 agree. Strong: ±15 % after a single answer. Learned values stay between half and double the calculated interval and between 50 % and 150 % of the calculated amount.",
                                             "learn_interval": "After watering, Plant Butler asks how the soil was (still moist / slightly dry / very dry) and adjusts each plant's watering interval. Plants with a soil sensor also learn from the measured drying time.",
                                             "learn_amount": "After watering, Plant Butler asks whether the amount was right (too much / just right / too little) and adjusts each plant's watering amount. Plants with a soil sensor also learn from the measured moisture. Turning a checkbox off applies the calculated values again – everything learned stays saved and is back when you switch it on. To pause temporarily (e.g. holidays), use the switch 'Pause learning'.",
                                             "climate_level": "Only for plants without a soil moisture sensor. Plant Butler uses room temperature and humidity to estimate how fast the soil dries out: warm, dry air shortens the watering interval, cool, humid air lengthens it (at most 0.6× to 1.4×). Off: fixed interval. Weak / Medium / Strong: how much the room climate counts. Choose 'Strong' if your plants are regularly dry before the reminder, 'Weak' if they are still moist."}},
            "phone": {"title": "Phone notifications", "description": "Only Companion app phones are listed – they support buttons, urgent alerts and do-not-disturb detection. To hold messages during do-not-disturb, enable the 'Do Not Disturb' sensor in the Companion app (Settings → Companion app → Manage sensors).",
                      "sections": {
                        "recipients": {"name": "Recipients", "data": {"devices": "Phones"}},
                        "topics_section": {"name": "What to notify", "data": {"topics": "Topics"}},
                        "levels": {"name": "Levels", "data": {"info": "Notices", "warning": "Warnings", "critical": "Critical", "summary_time": "Time of the daily summary", "critical_repeat_hours": "Repeat critical every … hours (0 = never)", "critical_breaks_dnd": "Critical overrides do-not-disturb"},
                                   "data_description": {"critical_breaks_dnd": "Critical messages are sent as an alarm that sounds even in do-not-disturb mode."}},
                        "quiet": {"name": "Quiet times", "data": {"quiet_start": "Quiet hours from", "quiet_end": "Quiet hours until", "respect_dnd": "Respect the phone's do-not-disturb"},
                                  "data_description": {"quiet_start": "Notices and warnings wait until the quiet hours end; critical messages always come through. Leave empty for no quiet hours.", "respect_dnd": "Notices and warnings wait until do-not-disturb ends on the phone."}},
                        "buttons_section": {"name": "Buttons", "data": {"buttons": "Buttons in the notification"},
                                            "data_description": {"buttons": "Watered / Fertilized, In 1 h, Tomorrow."}}}},
            "announce": {"title": "Announcements", "description": "Voice assistants announce with a chime. Music Assistant players lower the music for the announcement; other speakers use text-to-speech.",
                         "sections": {
                           "targets": {"name": "Targets", "data": {"satellites": "Voice assistants", "speakers": "Speakers", "where": "Where to announce"}},
                           "topics_section": {"name": "What to announce", "data": {"topics": "Topics"}},
                           "levels": {"name": "Levels", "data": {"info": "Notices", "warning": "Warnings", "critical": "Critical", "summary_time": "Time of the daily summary"}},
                           "quiet": {"name": "Quiet times", "data": {"quiet_start": "Quiet hours from", "quiet_end": "Quiet hours until", "critical_in_quiet": "Announce critical during quiet hours too"},
                                     "data_description": {"quiet_start": "Announcements wait until the quiet hours end. Leave empty for no quiet hours."}},
                           "sound": {"name": "Sound", "data": {"volume": "Volume", "tts_engine": "Text-to-speech engine"},
                                     "data_description": {"volume": "Empty = unchanged. Applies to normal speakers and is restored afterwards; Music Assistant uses its own announcement volume.", "tts_engine": "Used for speakers; voice assistants use their own voice."}}}}
        },
        "climate": "Strength of the room climate correction",
        "climate_desc": "0 = off, 1 = default, 2 = strong. Warm, dry air shortens the watering interval for plants without a soil sensor.",
        "plant": "Plant", "add": "Add plant", "reconf": "Edit plant",
        "user_title": "Plant", "user_desc": "Choose the species to prefill all target values from the database, or \"Custom\" to enter them yourself.",
        "name": "Name", "species": "Species", "area": "Room",
        "sensors_title": "Sensors (all optional)",
        "sensors_desc": "Without a soil sensor a schedule is used. Room temperature and humidity correct it for evaporation.",
        "moisture": "Soil moisture sensor", "illum": "Light sensor", "temp": "Room temperature sensor", "hum": "Room humidity sensor",
        "assist_title": "Care assistant",
        "assist_desc": "Prefilled from the database. Tell the assistant about the pot and your fertilizer – it calculates watering amount, interval and fertilizer dose in the next step. Water need: very low = let the soil dry out completely, medium = water when the top few cm are dry, very high = keep constantly moist.",
        "feeding": "Nutrient demand", "psize": "Plant size relative to the pot",
        "psize_d": "A plant with lots of foliage for its pot needs water more often (interval −20 %), a small one less often (+20 %).",
        "pot_d": "Pot diameter (top)", "pot_h": "Pot height",
        "pot_m": "Pot material", "substrate": "Substrate", "ftype": "Fertilizer", "fdose": "Fertilizer dose on the package",
        "pot_d_d": "Leave empty if unknown – then no watering amount is calculated.",
        "pot_h_d": "Optional, default 0.9 × diameter.",
        "fdose_d": "Liquid fertilizer only: ml per litre of water as printed on the package.",
        "profile_title": "Care plan",
        "profile_desc": "Assistant result: pot ≈ {volume} l → about {watering_amount} ml every {watering_interval} days; liquid fertilizer per watering ≈ {fertilizer_total} ml. Adjust anything you like – the room climate and winter rest also adjust the interval while running.",
        "winterval": "Watering interval",
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
            "needs_water": "Needs water", "needs_fertilizer": "Needs fertilizer", "light_condition": "Light conditions",
            "temperature_condition": "Temperature conditions", "mark_watered": "Watered", "mark_fertilized": "Fertilized",
            "water_need": "Water need", "light_need": "Light need", "location_light": "Light at location",
            "moisture_min": "Water below", "moisture_max": "Moisture max", "temperature_min": "Temperature min",
            "temperature_max": "Temperature max", "watering_interval": "Watering interval",
            "watering_amount": "Watering amount", "fertilizer_interval": "Fertilizing interval",
            "fertilizer_winter_interval": "Fertilizing interval winter", "fertilizer_amount": "Fertilizer amount",
            "winter_rest": "Winter rest", "photo": "Photo", "plant_size": "Plant size", "hints": "Hints", "notifications": "Notifications",
            "learned_interval": "Learned watering interval", "learned_amount": "Learned watering amount",
            "undo_watering": "Undo last watering", "reset_learning": "Reset learned values", "learning_paused": "Pause learning", "checklist": "Plant care",
        },
        "svc_name": "Mark care task done", "svc_desc": "Marks watering or fertilizing as done for the given plants and restarts the schedule.",
        "svc_ent": "Plant entities", "svc_ent_d": "Any entity of the plant.", "svc_dev": "Plant devices",
        "svc_dev_d": "The plant devices.", "svc_task": "Task", "svc_task_d": "Which task was done.",
        "svc_fb_name": "Watering feedback", "svc_fb_desc": "Feedback on the last watering. Adjusts the learned watering interval and/or amount.",
        "svc_fb_amount": "Amount", "svc_fb_amount_d": "Was the watering amount right?", "svc_fb_answer_d": "How was the soil before watering?",
        "svc_fb_answer": "Answer", "svc_undo_name": "Undo last watering", "svc_undo_desc": "Restores the state from before the last watering (within 24 hours).",
        "no_plant": "No Plant Butler plant found for the given target.", "unknown_task": "Unknown checklist item.",
    },
    "de": {
        "hub_desc": "Plant Butler kümmert sich um deine Pflanzen. Nach der Einrichtung fügst du Pflanzen auf der Integrationsseite mit „+ Pflanze hinzufügen“ hinzu.",
        "single": "Plant Butler ist bereits eingerichtet. Pflanzen fügst du auf der Integrationsseite hinzu.",
        "options": {
            "init": {"title": "Plant Butler", "menu_options": {"general": "Allgemein", "phone": "Handy-Benachrichtigungen", "announce": "Ansagen (Sprachassistenten & Lautsprecher)"}},
            "general": {"title": "Allgemein", "data": {"learning_strength": "Lernstärke", "learn_interval": "Gießintervall lernen", "learn_amount": "Gießmenge lernen", "climate_level": "Raumklima-Korrektur"},
                        "data_description": {"learning_strength": "Wie schnell sich Plant Butler an deine Antworten anpasst. Vorsichtig: ±5 %, wenn 3 der letzten 4 Antworten übereinstimmen. Ausgewogen: ±10 %, wenn 2 von 3 übereinstimmen. Stark: ±15 % schon nach einer Antwort. Gelernte Werte bleiben zwischen halbem und doppeltem berechnetem Intervall und zwischen 50 % und 150 % der berechneten Menge.",
                                             "learn_interval": "Nach dem Gießen fragt Plant Butler, wie die Erde war (noch feucht / leicht trocken / sehr trocken), und passt das Gießintervall jeder Pflanze an. Pflanzen mit Bodensensor lernen zusätzlich aus der gemessenen Austrocknungszeit.",
                                             "learn_amount": "Nach dem Gießen fragt Plant Butler, ob die Menge gepasst hat (zu viel / passt / zu wenig), und passt die Gießmenge jeder Pflanze an. Pflanzen mit Bodensensor lernen zusätzlich aus der gemessenen Feuchte. Ein Häkchen entfernen verwendet wieder die berechneten Werte – das Gelernte bleibt gespeichert und ist beim Einschalten sofort zurück. Zum vorübergehenden Pausieren (z. B. Urlaub) gibt es den Schalter „Dazulernen pausieren“.",
                                             "climate_level": "Nur für Pflanzen ohne Bodenfeuchtesensor. Plant Butler schätzt aus Raumtemperatur und Luftfeuchte, wie schnell die Erde austrocknet: Warme, trockene Luft verkürzt das Gießintervall, kühle, feuchte Luft verlängert es (höchstens 0,6- bis 1,4-fach). Aus: festes Intervall. Schwach / Mittel / Stark: wie stark das Raumklima wirkt. „Stark“ wählen, wenn deine Pflanzen vor der Erinnerung regelmäßig schon trocken sind, „Schwach“, wenn sie noch feucht sind."}},
            "phone": {"title": "Handy-Benachrichtigungen", "description": "Aufgelistet werden nur Handys mit der Companion-App – nur diese unterstützen Buttons, dringende Meldungen und „Nicht stören“. Damit Meldungen während „Nicht stören“ warten, aktiviere in der Companion-App den Sensor „Do Not Disturb“ (Einstellungen → Companion-App → Sensoren verwalten).",
                      "sections": {
                        "recipients": {"name": "Empfänger", "data": {"devices": "Handys"}},
                        "topics_section": {"name": "Was melden", "data": {"topics": "Themen"}},
                        "levels": {"name": "Stufen", "data": {"info": "Hinweise", "warning": "Warnungen", "critical": "Kritisch", "summary_time": "Uhrzeit der täglichen Zusammenfassung", "critical_repeat_hours": "Kritisch wiederholen alle … Stunden (0 = nie)", "critical_breaks_dnd": "Kritisch durchbricht „Nicht stören“"},
                                   "data_description": {"critical_breaks_dnd": "Kritische Meldungen kommen als Alarm, der auch bei „Nicht stören“ klingelt."}},
                        "quiet": {"name": "Ruhe", "data": {"quiet_start": "Ruhezeit von", "quiet_end": "Ruhezeit bis", "respect_dnd": "„Nicht stören“ des Handys beachten"},
                                  "data_description": {"quiet_start": "Hinweise und Warnungen warten bis zum Ende der Ruhezeit; Kritisches kommt immer durch. Leer lassen = keine Ruhezeit.", "respect_dnd": "Hinweise und Warnungen warten, bis „Nicht stören“ am Handy endet."}},
                        "buttons_section": {"name": "Buttons", "data": {"buttons": "Buttons in der Benachrichtigung"},
                                            "data_description": {"buttons": "Gegossen / Gedüngt, In 1 Std., Morgen."}}}},
            "announce": {"title": "Ansagen", "description": "Sprachassistenten sagen mit Signalton an. Music-Assistant-Player senken für die Ansage die Musik ab; andere Lautsprecher nutzen die Sprachausgabe.",
                         "sections": {
                           "targets": {"name": "Ziele", "data": {"satellites": "Sprachassistenten", "speakers": "Lautsprecher", "where": "Wo ansagen"}},
                           "topics_section": {"name": "Was ansagen", "data": {"topics": "Themen"}},
                           "levels": {"name": "Stufen", "data": {"info": "Hinweise", "warning": "Warnungen", "critical": "Kritisch", "summary_time": "Uhrzeit der täglichen Zusammenfassung"}},
                           "quiet": {"name": "Ruhe", "data": {"quiet_start": "Ruhezeit von", "quiet_end": "Ruhezeit bis", "critical_in_quiet": "Kritisches auch in der Ruhezeit ansagen"},
                                     "data_description": {"quiet_start": "Ansagen warten bis zum Ende der Ruhezeit. Leer lassen = keine Ruhezeit."}},
                           "sound": {"name": "Ton", "data": {"volume": "Lautstärke", "tts_engine": "Sprachausgabe"},
                                     "data_description": {"volume": "Leer = unverändert. Gilt für normale Lautsprecher und wird danach zurückgesetzt; Music Assistant nutzt seine eigene Ansage-Lautstärke.", "tts_engine": "Für Lautsprecher; Sprachassistenten nutzen ihre eigene Stimme."}}}}
        },
        "climate": "Stärke der Raumklima-Korrektur",
        "climate_desc": "0 = aus, 1 = Standard, 2 = stark. Warme, trockene Luft verkürzt das Gießintervall bei Pflanzen ohne Bodensensor.",
        "plant": "Pflanze", "add": "Pflanze hinzufügen", "reconf": "Pflanze bearbeiten",
        "user_title": "Pflanze", "user_desc": "Wähle die Art, um alle Sollwerte aus der Datenbank vorzubefüllen, oder „Benutzerdefiniert“, um sie selbst einzutragen.",
        "name": "Name", "species": "Art", "area": "Raum",
        "sensors_title": "Sensoren (alle optional)",
        "sensors_desc": "Ohne Bodensensor wird ein Zeitplan verwendet. Raumtemperatur und -feuchte korrigieren ihn für die Verdunstung.",
        "moisture": "Bodenfeuchtesensor", "illum": "Lichtsensor", "temp": "Raumtemperatursensor", "hum": "Raumfeuchtesensor",
        "assist_title": "Pflege-Assistent",
        "assist_desc": "Aus der Datenbank vorbefüllt. Erzähl dem Assistenten vom Topf und deinem Dünger – im nächsten Schritt berechnet er Gießmenge, Intervall und Düngerdosis. Wasserbedarf: sehr wenig = Erde ganz austrocknen lassen, mittel = gießen, wenn die oberen cm trocken sind, sehr viel = dauerhaft feucht halten.",
        "feeding": "Nährstoffbedarf", "psize": "Pflanzengröße im Verhältnis zum Topf",
        "psize_d": "Eine Pflanze mit viel Laub für ihren Topf braucht öfter Wasser (Intervall −20 %), eine kleine seltener (+20 %).",
        "pot_d": "Topfdurchmesser (oben)", "pot_h": "Topfhöhe",
        "pot_m": "Topfmaterial", "substrate": "Substrat", "ftype": "Dünger", "fdose": "Dosierung laut Packung",
        "pot_d_d": "Leer lassen, wenn unbekannt – dann wird keine Gießmenge berechnet.",
        "pot_h_d": "Optional, Standard 0,9 × Durchmesser.",
        "fdose_d": "Nur Flüssigdünger: ml pro Liter Wasser laut Packung.",
        "profile_title": "Pflegeplan",
        "profile_desc": "Ergebnis des Assistenten: Topf ≈ {volume} l → etwa {watering_amount} ml alle {watering_interval} Tage; Flüssigdünger pro Gießen ≈ {fertilizer_total} ml. Alles änderbar – Raumklima und Winterruhe passen das Intervall im Betrieb zusätzlich an.",
        "winterval": "Gießintervall",
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
            "needs_water": "Braucht Wasser", "needs_fertilizer": "Braucht Dünger", "light_condition": "Lichtverhältnisse",
            "temperature_condition": "Temperaturverhältnisse", "mark_watered": "Gegossen", "mark_fertilized": "Gedüngt",
            "water_need": "Wasserbedarf", "light_need": "Lichtbedarf", "location_light": "Licht am Standort",
            "moisture_min": "Gießen ab", "moisture_max": "Feuchte max", "temperature_min": "Temperatur min",
            "temperature_max": "Temperatur max", "watering_interval": "Gießintervall",
            "watering_amount": "Gießmenge", "fertilizer_interval": "Düngeintervall",
            "fertilizer_winter_interval": "Düngeintervall Winter", "fertilizer_amount": "Düngermenge",
            "winter_rest": "Winterruhe", "photo": "Foto", "plant_size": "Pflanzengröße", "hints": "Hinweise", "notifications": "Benachrichtigungen",
            "learned_interval": "Gelerntes Gießintervall", "learned_amount": "Gelernte Gießmenge",
            "undo_watering": "Letztes Gießen rückgängig", "reset_learning": "Gelerntes zurücksetzen", "learning_paused": "Dazulernen pausieren", "checklist": "Pflanzenpflege",
        },
        "svc_name": "Pflegeaufgabe erledigt", "svc_desc": "Markiert Gießen oder Düngen für die gewählten Pflanzen als erledigt und startet den Zeitplan neu.",
        "svc_ent": "Pflanzen-Entities", "svc_ent_d": "Beliebige Entity der Pflanze.", "svc_dev": "Pflanzen-Geräte",
        "svc_dev_d": "Die Pflanzen-Geräte.", "svc_task": "Aufgabe", "svc_task_d": "Welche Aufgabe erledigt wurde.",
        "svc_fb_name": "Rückmeldung zum Gießen", "svc_fb_desc": "Rückmeldung zum letzten Gießen. Passt das gelernte Gießintervall und/oder die Gießmenge an.",
        "svc_fb_amount": "Menge", "svc_fb_amount_d": "Hat die Gießmenge gepasst?", "svc_fb_answer_d": "Wie war die Erde vor dem Gießen?",
        "svc_fb_answer": "Antwort", "svc_undo_name": "Letztes Gießen rückgängig", "svc_undo_desc": "Stellt den Zustand vor dem letzten Gießen wieder her (innerhalb von 24 Stunden).",
        "no_plant": "Keine Plant-Butler-Pflanze für das angegebene Ziel gefunden.", "unknown_task": "Unbekannter Checklisten-Eintrag.",
    },
}


def build(lang: str) -> dict:
    t = T[lang]
    e = t["e"]
    lv = {k: v[lang] for k, v in LEVELS.items()}
    named = lambda key: {"name": e[key]}  # noqa: E731
    assistant_fields = {
        "water_need": t["water_need"], "light_need": t["light_need"], "location_light": t["location_light"],
        "feeding": t["feeding"], "plant_size": t["psize"], "pot_diameter": t["pot_d"], "pot_height": t["pot_h"],
        "pot_material": t["pot_m"], "substrate": t["substrate"], "fertilizer_type": t["ftype"],
        "fertilizer_dosage": t["fdose"],
    }
    profile_fields = {
        "watering_interval": t["winterval"],
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
        "assistant": {"title": t["assist_title"], "description": t["assist_desc"], "data": assistant_fields,
                      "data_description": {"plant_size": t["psize_d"], "pot_diameter": t["pot_d_d"], "pot_height": t["pot_h_d"],
                                           "fertilizer_dosage": t["fdose_d"]}},
        "profile": {"title": t["profile_title"], "description": t["profile_desc"], "data": profile_fields},
    }
    return {
        "config": {
            "step": {"user": {"title": "Plant Butler", "description": t["hub_desc"]}},
            "abort": {"single_instance_allowed": t["single"]},
        },
        "options": {"step": t["options"]},
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
            "pot_material": {"options": lv["pot_material"]},
            "plant_size": {
        "en": {"small": "Small / freshly repotted (plenty of free soil)", "normal": "Normal (plant fits the pot)",
               "large": "Large / lush (lots of foliage, pot rather tight)"},
        "de": {"small": "Klein / frisch umgetopft (viel freie Erde)", "normal": "Normal (Pflanze passt zum Topf)",
               "large": "Groß / üppig (viel Laub, Topf eher knapp)"},
    },
    "substrate": {"options": lv["substrate"]},
            "feeding": {"options": lv["feeding"]},
            "fertilizer_type": {"options": lv["fertilizer_type"]},
            "notify_mode": {"options": lv["notify_mode"]},
            "topics": {"options": lv["topics"]},
            "announce_where": {"options": lv["announce_where"]},
            "learning_strength": {"options": lv["learning_strength"]},
            "feedback_amount": {"options": lv["feedback_amount"]},
            "climate_level": {"options": lv["climate_level"]},
            "feedback": {"options": lv["feedback"]},
            "pot_material": {
        "en": {"plastic": "Plastic / glazed ceramic", "terracotta": "Terracotta (unglazed clay)"},
        "de": {"plastic": "Kunststoff / glasierte Keramik", "terracotta": "Terrakotta (unglasierter Ton)"},
    },
    "plant_size": {
        "en": {"small": "Small / freshly repotted (plenty of free soil)", "normal": "Normal (plant fits the pot)",
               "large": "Large / lush (lots of foliage, pot rather tight)"},
        "de": {"small": "Klein / frisch umgetopft (viel freie Erde)", "normal": "Normal (Pflanze passt zum Topf)",
               "large": "Groß / üppig (viel Laub, Topf eher knapp)"},
    },
    "substrate": {
        "en": {"standard": "Potting soil", "mineral": "Mineral / cactus soil"},
        "de": {"standard": "Blumenerde", "mineral": "Mineralisch / Kakteenerde"},
    },
    "feeding": {
        "en": {"none": "None (e.g. carnivorous plants)", "light": "Light feeder (½ package dose)",
               "medium": "Medium (¾ package dose)", "heavy": "Heavy feeder (full package dose)"},
        "de": {"none": "Keinen (z. B. fleischfressende Pflanzen)", "light": "Schwachzehrer (½ Packungsdosis)",
               "medium": "Mittel (¾ Packungsdosis)", "heavy": "Starkzehrer (volle Packungsdosis)"},
    },
    "fertilizer_type": {
        "en": {"liquid": "Liquid fertilizer", "sticks": "Fertilizer sticks", "granules": "Slow-release granules", "none": "No fertilizer"},
        "de": {"liquid": "Flüssigdünger", "sticks": "Düngestäbchen", "granules": "Langzeitdünger (Granulat)", "none": "Kein Dünger"},
    },
    "task": {"options": lv["task"]},
        },
        "entity": {
            "binary_sensor": {k: {"name": e[k], "state": lv["yesno"]} for k in ["needs_water", "needs_fertilizer"]},
            "button": {k: named(k) for k in ["mark_watered", "mark_fertilized", "undo_watering", "reset_learning"]},
            "image": {"photo": named("photo")},
            "number": {k: named(k) for k in ["moisture_min", "moisture_max", "temperature_min", "temperature_max",
                                              "watering_interval", "watering_amount", "fertilizer_interval",
                                              "fertilizer_winter_interval", "fertilizer_amount"]},
            "select": {
                "water_need": {"name": e["water_need"], "state": {k: v.split(" (")[0] for k, v in lv["water"].items()}},
                "light_need": {"name": e["light_need"], "state": lv["light"]},
                "location_light": {"name": e["location_light"], "state": lv["light"]},
                "plant_size": {"name": e["plant_size"], "state": {k: v.split(" (")[0] for k, v in lv["plant_size"].items()}},
            },
            "sensor": {
                "status": {"name": e["status"], "state": lv["severity"],
                           "state_attributes": {k: {"name": v} for k, v in lv["status_attr"].items()}},
                "light_condition": {"name": e["light_condition"], "state": lv["light_cond"]},
                "temperature_condition": {"name": e["temperature_condition"], "state": lv["temp_cond"]},
                "hints": named("hints"),
                "learned_interval": named("learned_interval"),
                "learned_amount": named("learned_amount"),
                "next_watering": named("next_watering"),
                "next_fertilizing": named("next_fertilizing"),
                "dli": named("dli"),
                "light_level": {"name": e["light_level"], "state": lv["light"]},
            },
            "switch": {"winter_rest": named("winter_rest"), "notifications": named("notifications"), "learning_paused": named("learning_paused")},
            "todo": {"checklist": named("checklist")},
        },
        "services": {
            "watering_feedback": {
                "name": t["svc_fb_name"], "description": t["svc_fb_desc"],
                "fields": {
                    "entity_id": {"name": t["svc_ent"], "description": t["svc_ent_d"]},
                    "device_id": {"name": t["svc_dev"], "description": t["svc_dev_d"]},
                    "answer": {"name": t["svc_fb_answer"], "description": t["svc_fb_answer_d"]},
                    "amount": {"name": t["svc_fb_amount"], "description": t["svc_fb_amount_d"]},
                },
            },
            "undo_watering": {
                "name": t["svc_undo_name"], "description": t["svc_undo_desc"],
                "fields": {
                    "entity_id": {"name": t["svc_ent"], "description": t["svc_ent_d"]},
                    "device_id": {"name": t["svc_dev"], "description": t["svc_dev_d"]},
                },
            },
            "mark_done": {
                "name": t["svc_name"], "description": t["svc_desc"],
                "fields": {
                    "entity_id": {"name": t["svc_ent"], "description": t["svc_ent_d"]},
                    "device_id": {"name": t["svc_dev"], "description": t["svc_dev_d"]},
                    "pot_material": {
        "en": {"plastic": "Plastic / glazed ceramic", "terracotta": "Terracotta (unglazed clay)"},
        "de": {"plastic": "Kunststoff / glasierte Keramik", "terracotta": "Terrakotta (unglasierter Ton)"},
    },
    "plant_size": {
        "en": {"small": "Small / freshly repotted (plenty of free soil)", "normal": "Normal (plant fits the pot)",
               "large": "Large / lush (lots of foliage, pot rather tight)"},
        "de": {"small": "Klein / frisch umgetopft (viel freie Erde)", "normal": "Normal (Pflanze passt zum Topf)",
               "large": "Groß / üppig (viel Laub, Topf eher knapp)"},
    },
    "substrate": {
        "en": {"standard": "Potting soil", "mineral": "Mineral / cactus soil"},
        "de": {"standard": "Blumenerde", "mineral": "Mineralisch / Kakteenerde"},
    },
    "feeding": {
        "en": {"none": "None (e.g. carnivorous plants)", "light": "Light feeder (½ package dose)",
               "medium": "Medium (¾ package dose)", "heavy": "Heavy feeder (full package dose)"},
        "de": {"none": "Keinen (z. B. fleischfressende Pflanzen)", "light": "Schwachzehrer (½ Packungsdosis)",
               "medium": "Mittel (¾ Packungsdosis)", "heavy": "Starkzehrer (volle Packungsdosis)"},
    },
    "fertilizer_type": {
        "en": {"liquid": "Liquid fertilizer", "sticks": "Fertilizer sticks", "granules": "Slow-release granules", "none": "No fertilizer"},
        "de": {"liquid": "Flüssigdünger", "sticks": "Düngestäbchen", "granules": "Langzeitdünger (Granulat)", "none": "Kein Dünger"},
    },
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
