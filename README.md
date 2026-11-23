# Plant Butler 🌿

Home-Assistant-Integration für die Pflanzenpflege: Jede Pflanze ist ein Gerät mit Sollwerten aus einer Pflanzendatenbank, optionalen Sensoren, Gieß- und Düngeplan, Warnstufen und einer Checkliste, die sich selbst zurücksetzt.

> Status: **0.1 – Grundgerüst.** Pflanzenkarte, Dashboard und Benachrichtigungs-Blueprint folgen.

## Funktionen

- **„+ Pflanze hinzufügen“** direkt auf der Integrationsseite (Config-Subentries), mit Raum aus deinen HA-Bereichen.
- **Pflanzendatenbank** mit 118 gängigen Zimmer-, Balkon- und Kräuterpflanzen. Die Art wählen füllt alle Sollwerte vor; „Benutzerdefiniert“ für alles andere.
- **Sensoren optional**: Bodenfeuchte, Licht, Raumtemperatur, Raumfeuchte. Beim Raum werden passende Sensoren vorgeschlagen.
- **Gießen**
  - mit Bodensensor: Schwelle „Gießen ab“ mit Hysterese, Prognose aus dem Trend, Gießen wird am Feuchteanstieg automatisch erkannt;
  - ohne Bodensensor: Intervall der Wasserstufe, korrigiert durch das Raumklima (Dampfdruckdefizit aus Temperatur und Luftfeuchte) und die Winterruhe.
- **Licht**: sechs Stufen für Soll und Ist (Sehr dunkel … Direkte Sonne). Mit Lichtsensor wird die Tageslichtsumme (DLI) berechnet, ohne Sensor wählst du den Standort per Dropdown.
- **Düngen** mit Intervall, eigenem Winterintervall (0 = Pause), Menge und Düngerart.
- **Status** OK / Info / Warnung / Kritisch mit Liste der Ursachen.
- **Checkliste** `todo.plant_butler`: fällige Aufgaben erscheinen automatisch, Abhaken setzt den Zeitplan zurück, erledigte Einträge verschwinden nach 24 h.
- **Ereignis** `plant_butler_notification` bei neuen oder eskalierenden Problemen (für Benachrichtigungen).
- Entity-IDs immer englisch, Oberfläche deutsch oder englisch.

## Installation (HACS)

1. HACS → ⋮ → *Benutzerdefinierte Repositories* → `https://github.com/DomJoke/ha-plant-butler`, Typ *Integration*.
2. „Plant Butler“ installieren und Home Assistant neu starten.
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Plant Butler*.
4. Auf der Integrationsseite **„+ Pflanze hinzufügen“**.

## Entities pro Pflanze (Beispiel „Monstera“)

| Entity | Bedeutung |
| --- | --- |
| `sensor.monstera_status` | ok / info / warning / critical; Attribute für Karten (Probleme, Sollwerte, Sensoren, Pflege) |
| `sensor.monstera_next_watering` / `sensor.monstera_next_fertilizing` | Fälligkeit (Zeitstempel) |
| `sensor.monstera_light_level` / `sensor.monstera_dli` | Ist-Lichtstufe / Tageslichtsumme heute (nur mit Lichtsensor) |
| `binary_sensor.monstera_needs_water` / `_needs_fertilizer` / `_light_problem` / `_temperature_problem` | Einzelne Zustände |
| `button.monstera_mark_watered` / `_mark_fertilized` | Aufgabe erledigt |
| `select.monstera_water_need` / `_light_need` / `_location_light` | Sollwert-Stufen, Licht am Standort |
| `number.monstera_moisture_min` / `_moisture_max` / `_temperature_min` / `_temperature_max` / `_watering_interval` / `_watering_amount` / `_fertilizer_interval` / `_fertilizer_winter_interval` / `_fertilizer_amount` | Feinwerte |
| `switch.monstera_winter_rest` | Winterruhe: Gießintervall × 1,5, Düngen nach Winterintervall |
| `image.monstera_photo` | Foto (wenn hinterlegt) |

Änderst du die Wasserstufe, werden „Gießen ab“, Feuchte-Maximum und Gießintervall auf die Werte der Stufe gesetzt; danach kannst du sie fein anpassen.

## Wasserstufen

| Stufe | Beispiele | Gießen ab | Feuchte-Max. | Intervall ohne Sensor |
| --- | --- | --- | --- | --- |
| Sehr wenig | Kakteen, Sukkulenten | 10 % | 35 % | 21 Tage |
| Wenig | Zamioculcas, Bogenhanf | 15 % | 45 % | 14 Tage |
| Mittel | Monstera, Ficus, Efeutute | 25 % | 60 % | 7 Tage |
| Viel | Farne, Calathea | 40 % | 75 % | 4 Tage |
| Sehr viel | Zyperngras, Balkonkräuter | 55 % | 90 % | 2 Tage |

Die Werte sind Richtwerte. Bodensensoren messen je nach Hersteller unterschiedlich – passe „Gießen ab“ an deine Messung an.

## Dienst

```yaml
action: plant_butler.mark_done
data:
  entity_id: sensor.monstera_status   # oder device_id
  task: water                          # oder fertilize
```

## Benachrichtigungen (Beispiel bis zum Blueprint)

```yaml
triggers:
  - trigger: event
    event_type: plant_butler_notification
conditions:
  - condition: template
    value_template: "{{ trigger.event.data.severity in ['warning', 'critical'] }}"
actions:
  - action: notify.mobile_app_dphone
    data:
      title: "🌿 {{ trigger.event.data.plant }} ({{ trigger.event.data.area }})"
      message: "{{ trigger.event.data.problem }} – {{ trigger.event.data.severity }}"
```

## Entwicklung

```bash
pip install -r requirements_test.txt
pytest
```

Die Pflanzendatenbank liegt in `custom_components/plant_butler/data/plants.json`.
