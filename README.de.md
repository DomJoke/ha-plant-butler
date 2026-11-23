<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/wordmark-dark.png">
  <img src="docs/wordmark.png" alt="Plant Butler" width="420">
</picture>

# Plant Butler 🌿

*[English version](README.md)*

Home-Assistant-Integration für die Pflanzenpflege: Jede Pflanze ist ein Gerät mit Sollwerten aus einer Pflanzendatenbank, optionalen Sensoren, einem Pflege-Assistenten für Gießmenge und Düngerdosis, Gieß- und Düngeplan, Warnstufen und einer Checkliste, die sich selbst zurücksetzt.

> Status: **0.4** – Benachrichtigungs-Blueprint folgt.

## Funktionen

- **„+ Pflanze hinzufügen“** direkt auf der Integrationsseite, mit Raum aus deinen HA-Bereichen.
- **Pflanzendatenbank** mit 118 gängigen Zimmer-, Balkon- und Kräuterpflanzen. Die Art füllt alle Sollwerte vor; „Benutzerdefiniert“ für alles andere.
- **Pflege-Assistent** beim Anlegen: Aus Topfgröße, Topfmaterial, Substrat und deinem Dünger berechnet er Gießmenge, Gießintervall und Düngerdosis (siehe unten).
- **Sensoren optional**: Bodenfeuchte, Licht, Raumtemperatur, Raumfeuchte. Passende Sensoren des Raums werden vorgeschlagen.
- **Gießen** mit Bodensensor (Schwelle, Hysterese, Trendprognose, automatische Gieß-Erkennung) oder per Intervall, das Raumklima und Winterruhe im Betrieb anpassen.
- **Licht**: sechs Stufen für Soll und Ist. Mit Lichtsensor wird die Tageslichtsumme (DLI) berechnet, ohne Sensor wählst du den Standort per Dropdown.
- **Düngen** mit Intervall, Winterintervall (0 = Pause), Menge und Düngerart.
- **Status** OK / Info / Warnung / Kritisch mit Liste der Ursachen.
- **Checkliste** `todo.plant_butler` mit automatischem Zurücksetzen.
- **Ereignis** `plant_butler_notification` bei neuen oder eskalierenden Problemen.
- Entity-IDs immer englisch, Oberfläche deutsch oder englisch.

## Installation (HACS)

1. HACS → ⋮ → *Benutzerdefinierte Repositories* → `https://github.com/DomJoke/ha-plant-butler`, Typ *Integration*.
2. „Plant Butler“ installieren und Home Assistant neu starten.
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Plant Butler*.
4. Auf der Integrationsseite **„+ Pflanze hinzufügen“**.

## Pflege-Assistent

Der Assistent rechnet mit Faustregeln für Topfpflanzen. Alle Ergebnisse sind Vorschläge, die du im letzten Schritt oder später über die Entities der Pflanze ändern kannst.

| Wert | Berechnung |
| --- | --- |
| Topfvolumen | Zylinder aus Durchmesser und Höhe (Standard-Höhe 0,9 × Durchmesser) × 0,8 für die konische Form |
| Gießmenge | Topfvolumen × pflanzenverfügbares Wasser im Substrat (Blumenerde 25 %, mineralisch/Kakteenerde 15 %) × Anteil, der bis zum nächsten Gießen verbraucht wird (sehr wenig 90 %, wenig 70 %, mittel 50 %, viel 35 %, sehr viel 25 %), auf 10 ml gerundet |
| Gießintervall | Basisintervall der Wasserstufe × Topfgröße (2 l = 1,0, größere Töpfe trocknen langsamer) × Material (Terrakotta 0,8) × Substrat (mineralisch 0,85) × Licht am Standort (dunkel 1,25 … direkte Sonne 0,8), begrenzt auf 0,6–1,6 |
| Flüssigdünger | Dosierung laut Packung (ml/l) × Nährstoffbedarf (Schwachzehrer ½, mittel ¾, Starkzehrer voll); die Checkliste zeigt zusätzlich die ml pro Gießen |
| Düngestäbchen | 1–4 Stück je nach Topfdurchmesser, alle 90 Tage |
| Langzeitdünger (Granulat) | 2,5 g pro Liter Substrat (nach Nährstoffbedarf skaliert), alle 180 Tage |

Beispiel: Efeutute im 14-cm-Kunststofftopf an einem dunklen Standort → etwa 1,6 l → **190 ml alle 8 Tage**.

Im Betrieb passen Raumklima (warme, trockene Luft → kürzer) und Winterruhe (× 1,5) das Intervall zusätzlich an. Änderst du Wasserbedarf oder Lichtstufe einer Pflanze, rechnet der Assistent das Intervall neu.

## Wasserstufen

| Stufe | Beispiele | Gießen ab | Feuchte-Max. | Basisintervall |
| --- | --- | --- | --- | --- |
| Sehr wenig | Kakteen, Sukkulenten | 10 % | 35 % | 21 Tage |
| Wenig | Zamioculcas, Bogenhanf | 15 % | 45 % | 14 Tage |
| Mittel | Monstera, Ficus, Efeutute | 25 % | 60 % | 7 Tage |
| Viel | Farne, Calathea | 40 % | 75 % | 4 Tage |
| Sehr viel | Zyperngras, Balkonkräuter | 55 % | 90 % | 2 Tage |

Die Werte sind Richtwerte. Bodensensoren messen je nach Hersteller unterschiedlich – passe „Gießen ab“ an deine Messung an.

Sichtbarkeit: Sollwerte (Selects, Zahlen, Winterruhe) sind *Konfigurations*-Entities, Lichtstufe, DLI und die Licht-/Temperaturproblem-Sensoren *Diagnose*-Entities – beide erscheinen nicht in automatisch erzeugten Dashboards. Temperatur-Min/-Max, Feuchte-Maximum und das Winter-Düngeintervall sind **standardmäßig deaktiviert**; aktiviere sie auf der Geräteseite, wenn du sie fein einstellen willst.

## Pflanzen-Dashboard

Plant Butler bringt eine **Dashboard-Strategie** mit: Das Dashboard wird bei jedem Öffnen neu erzeugt – neue Pflanzen und Räume erscheinen automatisch. Neues Dashboard anlegen, im Raw-Konfigurationseditor eintragen:

```yaml
strategy:
  type: custom:plant-butler
```

Ansichten: **Übersicht** (alle Pflanzen nach Raum, Räume einklappbar) und **Fällig** (nur Pflanzen mit fälligen Aufgaben zum Abhaken plus To-do-Liste).

## Statusstufen

| Status | Bedeutung |
| --- | --- |
| OK | Nichts zu tun |
| Hinweis | Gut zu wissen oder bald zu tun: heute gießen, düngen fällig, Standort etwas dunkel, Erde etwas nass |
| Warnung | Sollte erledigt werden: Gießen über 1 Tag überfällig, Temperatur außerhalb des Bereichs, Licht 3 Tage unpassend |
| Kritisch | Sofort handeln: Erde sehr trocken oder Gießen lange überfällig, Temperatur weit außerhalb |

Das Attribut `summary` des Status-Sensors nennt die Gründe im Klartext.

## Pflanzenkarte

Die Integration bringt eine Dashboard-Karte mit und lädt sie automatisch – keine Ressource nötig. Im Dashboard-Editor **„Plant Butler“** aus der Kartenauswahl wählen, oder:

```yaml
type: custom:plant-butler-card
entity: sensor.monstera_status
compact: false      # optional: nur Kopf und Aufgaben
```

Die Karte zeigt Foto (oder Symbol), Status, Probleme, Bodenfeuchte / Licht / Raumtemperatur / Luftfeuchte gegen die Sollwerte und die nächsten Pflegeaufgaben. Ein Tipp auf den Kreis neben einer Aufgabe hakt sie ab.

Entities, Dienst und Benachrichtigungs-Beispiel: siehe [englische README](README.md).
