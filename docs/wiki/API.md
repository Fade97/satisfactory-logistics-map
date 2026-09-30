# API

Alle Daten der Website kommen aus einer offenen JSON-API — praktisch für eigene Auswertungen, Discord-Bots oder
Home-Assistant. Antworten tragen ein `ETag`; mit `If-None-Match` gibt es `304`, wenn sich nichts geändert hat.
Koordinaten: Save-Weltkoordinaten in **Zentimetern** (`pos`) bzw. **Metern**, wo angegeben; +X = Ost, +Y = Süd.

## Lesen (GET)
| Endpunkt | Inhalt | Aktualisiert |
|---|---|---|
| `/api/status` | Titel, FRM-Status, Save-Stand, letzter Fehler | 5 s |
| `/api/live` | Spieler, Züge, LKW, Session (Uhrzeit, pausiert) | 5 s (FRM) / Save |
| `/api/factory` | Maschinen, Generatoren, Stromnetze, Warenbilanz, Fabriken | 60 s |
| `/api/stations` | Truck-/Zugstationen, Plattformen, Fahrpläne, Fahrzeuge | Save |
| `/api/geo` | Gleise, Rohre, Bänder als Linienzüge (m) | Save / FRM |
| `/api/nodes` | Rohstoffknoten mit Reinheit und Belegung | Save |
| `/api/powerlines` | Stromleitungen | Save |
| `/api/flow` | je Ware die Bänder/Rohre, auf denen sie liegt | Save |
| `/api/collectibles` | fehlende Somersloops, Mercer Spheres, Power Slugs, Absturzstellen | Save |
| `/api/storage` | Lager je Ware, Füllstand | Save |
| `/api/sink` | AWESOME Sink: Punkte, Coupons, Fortschritt | 60 s |
| `/api/progress` | Freischaltungen, Phase, Meilensteine | Save |
| `/api/recipes` | freigeschaltete Rezepte | Save |
| `/api/detail` | Fundamente und Wände (Binärformat Int16) | Save |
| `/api/events?since=<id>&limit=200` | Ereignisse ab ID | laufend |
| `/api/series?k=<schlüssel>&k=…&since=<unix>` | Zeitreihen, z. B. `prod:Iron Plate`, `cons:Iron Plate`, `power:<netz>:prod` | 60 s |
| `/api/series-keys?prefix=prod:` | verfügbare Reihen | |
| `/api/train-flow?h=24` | gemessener Zug-Durchsatz je Station und Ware | |
| `/api/schedule` | Fahrplan-Prüfung (Kapazität vs. Bedarf) | |
| `/api/frames?h=6&step=60` | Zeitreise-Bilder (max. 24 h) | 60 s |
| `/api/trails` | Spielerspuren (2 h) | |
| `/api/pins` | Notizen | |

## Schreiben (POST, Header `X-Map-Password`)
| Endpunkt | Body |
|---|---|
| `/api/auth` | – (prüft nur das Passwort) |
| `/api/pins` | `{author, cat, color, text, shape: point\|line\|area, geom: [[x,y],…]}` |
| `/api/pins/<id>/delete` | – |
| `/api/factory-name` | `{key, name, status: aktiv\|aufbau\|puffer\|stillgelegt}` |

## Rechnen (POST, ohne Passwort)
| Endpunkt | Body |
|---|---|
| `/api/plan` | `{targets: [{item, rate}], use_surplus, goal: raw\|machines\|power, max_clock, sloop, allow, exclude}` |
| `/api/blueprint` | ein Schritt aus `/api/plan` → ZIP |

## Beispiel: Strom in Home Assistant
```yaml
sensor:
  - platform: rest
    name: Satisfactory Strom
    resource: https://karte.example.de/api/factory
    value_template: "{{ value_json.circuits | map(attribute='use') | sum | round(0) }}"
    unit_of_measurement: MW
    scan_interval: 60
```
