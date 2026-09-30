# Glossary (German UI term → English)

Use these exact English terms everywhere (UI, README, wiki) so the app and the docs match.

## Pages and routes
| German | English | Route |
|---|---|---|
| Lage | Overview | `#/overview` |
| Karte | Map | `#/map` |
| Produktion | Production | `#/production` |
| Strom | Power | `#/power` |
| Logistik | Logistics | `#/logistics` |
| Verlauf | History | `#/history` |
| Rechner | Planner | `#/planner` |
| Kiosk | Kiosk | `#/kiosk?follow=<player>&rotate=30` |

URL parameters: `x`, `y`, `z`, `sel`, `item` (was `ware`), `follow` (was `folge`), `pick=site` (was `pick=bauplatz`), `rotate`.
Old German routes/params still work (aliases in `lib/router.ts`).

## Terms
| German | English |
|---|---|
| Logistikkarte | Logistics Map |
| Meine Ansicht | My view |
| Ich bin | I am |
| Karte folgt mir | Map follows me |
| Karte folgt … / Folgen beenden | Follow … / Stop following |
| Ereignisse | Events |
| Ebenen | Layers |
| Fabrik (Knopf: Fabrikgebiet) | Factory |
| Ganze Karte | Whole map |
| Notiz | Note |
| Höhe | Height |
| Messen | Measure |
| Zeitreise | Time travel |
| Warenfluss | Item flow |
| Stationen / Waren | Stations / Items |
| Beladen / Entladen / gemischt | Load / Unload / mixed |
| Truck / Zug / LKW | Truck / Train / Truck |
| Spielerspuren | Player trails |
| Fundamente & Wände | Foundations & walls |
| Rohstoffknoten | Resource nodes |
| Sammelobjekte | Collectibles |
| Heatmap: Materialmangel | Heatmap: missing input |
| Materialmangel | Missing input |
| Ausgang voll (Puffer) | Output full (buffer) |
| Braucht Aufmerksamkeit | Needs attention |
| Mangelware | Shortages |
| Seit deinem letzten Besuch | Since your last visit |
| Warenbilanz | Item balance |
| Fabriken | Factories |
| Name und Status ändern | Rename / set status |
| aktiv / im Aufbau / Puffer / stillgelegt | active / under construction / buffer / decommissioned |
| läuft / teilweise / steht / pausiert / aus | running / partial / stopped / paused / off |
| Stromnetz / Netz | Power grid / grid |
| Sicherung ausgelöst | Fuse tripped |
| Brennstoff-Reichweite | Fuel range |
| Ohne Stromanschluss | Not connected to power |
| Füllstand | Fill level |
| Fahrplan-Prüfung | Schedule check |
| Durchsatz | Throughput |
| Rundenzeit | Round-trip time |
| Lager | Storage |
| Überschüsse der Fabrik nutzen | Use factory surplus |
| Optimieren auf: wenig Rohstoffe / wenig Maschinen / wenig Strom | Optimize for: fewest resources / fewest machines / least power |
| Takt bis | Clock up to |
| Produktionskette (Diagramm / Baum) | Production chain (Diagram / Tree) |
| Bauliste | Build list |
| Freie Knoten | Free nodes |
| Bauplatz | Build site |
| Plan als Notiz auf die Karte | Save plan as map note |
| Weiteres Ziel | Add target |
| Berechnen | Calculate |
| Noch kein Spielstand | No save yet |
| live · Spiel pausiert | live · game paused |
| Save vor N min | save N min ago |
| offline · letzter Stand | offline · last known state |
| Passwort | Password |
| Kategorien: Geplant / Problem / Rohstoff / Treffpunkt / Notiz | Planned / Problem / Resource / Meeting point / Note |
| Punkt / Linie / Fläche | Point / Line / Area |
| Spieler | Player |
| online / offline / unterwegs | online / offline / on the move |

Style: sentence case for labels ("Item flow", not "Item Flow"), short, no exclamation marks, "you" for the reader.
Item and building names stay as in the game (English); the separate "Item names" setting can switch them to German.
