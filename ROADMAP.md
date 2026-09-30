# Logistikkarte — Neuauflage (ab 29.09.2026)

Anforderungen aus der Abfrage vom 29.09.2026. Reihenfolge = Bauplan, jeder Block geht fertig live.

## Rahmen
| Thema | Entscheidung |
|---|---|
| Nutzer | Betreiber am zweiten Monitor, Mitspieler, Planung am Handy — alle Seiten voll mobil |
| Datenquelle | **Gemischt**: FRM bevorzugt, bei Ausfall automatisch Save (alle 5 min) |
| Unterbau | Python-Backend (stdlib/SQLite) + **Svelte/Vite**-Frontend, Karte als **eigener Canvas/WebGL-Renderer** |
| Layout | Karte = Startseite, dazu Seiten Produktion · Strom · Logistik · Verlauf; Klick springt zur Karte |
| Design | **FICSIT-Look**: Orange/Grau, industrielle Typografie |
| Sprache | UI deutsch, Waren/Gebäude englisch |
| Sichtbarkeit | alles öffentlich lesbar; Schreiben (Pins, Fabriknamen) mit gemeinsamem Passwort |
| Server | nur lesen; jede Änderung am Gameserver vorher absprechen, **keine Neustarts** |
| Rezeptdaten | öffentlicher Community-Datensatz, gegen Rezeptpfade im Save abgeglichen |
| Umstieg | neue Seite ersetzt die alte direkt; Rollback über git |
| Abnahme | nach jedem Block live deployen + kurze Notiz mit Screenshot |

## Blöcke
1. **Robustheit** — FRM-Hänger erkennen und anzeigen, Save-Fallback für Maschinen/Netz, SQLite-Verlauf
   (1 min → 48 h, Stundenmittel → 90 Tage, Tageswerte für immer), Ereignisse ab sofort sammeln.
2. **Produktion** — Warenbilanz (Soll/Ist je Ware), stehende Maschinen mit Grund + seit wann (Liste + Heatmap),
   Fabrik-Cluster automatisch (Nähe + Bänder), umbenennbar; Rohstoffknoten mit Reinheit/belegt/Extraktor.
3. **Strom** — Netzübersicht (Erzeugung, Verbrauch, Kapazität, Batterie), Leitungen als Ebene nach Netz gefärbt,
   Verlauf mit Sicherungsauslösungen, Brennstoff-Reichweite.
4. **Logistik** — Durchsatz je Route vs. Bedarf, Füllstandsbalken + leer/voll-Warnung, Drohnen, Liniennetzplan.
5. **Verlauf** — Produktion je Ware, Strom je Netz, Fabrikwachstum, Änderungsprotokoll (neu/abgerissen, Erbauer).
6. **Live / 2. Monitor** — Folge-Modus (Spieler/Zug/LKW), Ereignis-Feed (Störungen, Versorgung, Spieler, Fortschritt),
   Live alle 5 s, Kiosk (Karte + Feed, Kennzahlen, rotierende Seiten).
7. **Mitspieler** — Pins mit Kategorie/Farbe/Autor, Linien/Flächen zeichnen, Erbauer-Filter,
   Spielerspuren (letzte 2 h); prüfen, ob Pins per FRM als Ingame-Marker gehen (unsicher).

Keine Push-Benachrichtigungen — Ereignisse nur in der Karte.

## Stand 29.09.2026 (erster Durchgang, live)
| Block | Stand | Offen |
|---|---|---|
| 1 Robustheit | Save-Fallback, Quellenanzeige, SQLite-Verlauf, Ereignisse, Pterodactyl-Neustart 00:10 UTC, Issue-Entwurf | FRM-Pfad (`frm_factory`) erst nach dem ersten Neustart live geprüft |
| 2 Produktion | Warenbilanz, stehende Maschinen mit Grund, Fabrik-Cluster (umbenennbar), Rohstoffknoten | Heatmap statt Punkt-Ebene; Cluster auch über Band-Verbindungen |
| 3 Strom | Netzübersicht, Leitungen nach Netz, Verlauf, Brennstoff-Reichweite + -Bilanz | Sicherungsauslösungen nur mit FRM |
| 4 Logistik | Truck-Durchsatz (Obergrenze), Füllstände + Warnung, Liniennetzplan, Fahrzeugliste | Drohnen (keine vorhanden), echter Zugdurchsatz |
| 5 Verlauf | Produktion je Ware, Maschinenzustand, Wachstum, Änderungsprotokoll mit Erbauer | Erbauer oft unbekannt (PlayerInfoHandle nicht eindeutig) |
| 6 Live | Live alle 5 s, Folge-Modus, Ereignis-Feed, Kiosk (`#/kiosk?folge=<Spieler>&rotate=30`) | – |
| 7 Mitspieler | Notizen (Punkt/Linie/Fläche, Kategorie, Autor), Spielerspuren 2 h | Ingame: FRM kann nur `createPing`, keine Marker |

## Runde 2 (30.09.2026)
Antworten: Karte war nach Seitenwechsel leer (behoben) · „Ausgang voll“ ist normal → leise · Stillstand als Heatmap **und**
Fabrik-Umriss · Fabriken über Förderbänder trennen · vollwertiger Produktionsrechner (nur freigeschaltete Rezepte,
wenig Rohstoffe, Überschüsse nutzen, Diagramm + Bauliste + freie Knoten + als Notiz) · Stahl-Stillstand war unbekannt →
Hinweise prominent · Fabrik-Status (aktiv/Aufbau/Puffer/stillgelegt) · Startseite = Lage-Übersicht.

FRM-Pfad nach dem Neustart 02:10 geprüft: läuft; Extraktoren fehlten in `getFactory` (behoben über `getExtractor`).

## Runde 3 (30.09.2026)
Fuzzy-Suche überall · Kettendiagramm neu (Layout, Baum) · Pausen nicht aufzeichnen, Lücken in Diagrammen ·
Warenfluss auf der Karte (Ware wählen → Erzeuger, Verbraucher, Stationen, Bänder/Rohre aus dem Save) ·
Rechner: Ziel Rohstoffe/Maschinen/Strom, Rezepte je Ware wählen, Takt bis 250 % (Shards), Somersloops,
Bauplatz per Kartenklick · „Meine Ansicht“ je Browser (ich bin, Karte folgt mir, Startseite, letzte Kartenposition) ·
Ereignisse mit Hysterese und 2-h-Sperre (Fabriken nahe der Schwelle meldeten sich alle paar Minuten).

## Runde 4 (30.09.2026)
Tests (`make check`: pytest, vitest, Rauchtest aller Seiten auf Desktop und Handy) · Höhenfilter mit erkannten Etagen ·
Messen (Strecke, Fläche, Fundamente, Gleis-/Bandstücke) · Maschinen ohne Stromanschluss (Karte, Strom, Lage, Ereignis) ·
echter Zugdurchsatz aus Ladungsänderungen angedockter Züge (`/api/train-flow`) · 3D-Ansicht je Fabrik (three.js, nachgeladen) ·
deutsche Warennamen zuschaltbar (Suche findet beide Sprachen).

## Runde 5 (30.09.2026)
Sammelobjekte als Ebenen (fehlende Somersloops, Mercer Spheres, Power Slugs, offene Absturzstellen; Zähler) ·
Lager-Übersicht je Ware + „Lager voll, Fabrik staut“ · AWESOME Sink (Coupons, Punkte/min, Fortschritt) ·
Fahrplan-Prüfung (Kapazität je Route vs. Bedarf der Fabrik an den Entladestationen, Zug-Rundenzeit gemessen) ·
Blueprint aus dem Rechner (experimentell, nur Constructor/Smelter, auf Basis der Spieler-Vorlagen).

Offen: Blueprint im Spiel testen; weitere Vorlagen (Assembler/Foundry/Manufacturer) aus Spieler-Blueprints; Zug-Rundenzeiten füllen sich erst mit Spielbetrieb.

## Runde 6 (30.09.2026)
Backend in Module (`mapsvc/`), Karte in Komponenten (`lib/map/`) · Zeitreise (Minutenbilder 24 h, Zeitschieber, Lücken markiert) ·
PWA (installierbar, offline mit letztem Stand, ehrliche Offline-Anzeige) · Detailebene statt Kartenkacheln: Fundamente und Wände
aus dem Save (83 k Leichtbau-Objekte, 180 KB) — höher aufgelöste Spielkarten gibt es nicht mit sauberer Lizenz.

## Runde 7 (30.09.2026) — teilbar
Docker-Paket (`docker compose up -d`, `.env.example`) · Save-Quelle einstellbar: Ordner, SFTP, FTP/FTPS, Server-API
(`mapsvc/source.py`) · FRM optional (`FRM_URL` leer = aus) · Titel aus dem Sessionnamen · Einrichtungs-Hinweis ohne Save ·
v1-Karte entfernt, Blueprints nach `blueprints/`, Vorlagen nach `gamedata/templates/` · README neu, `docs/FRM.md`,
`docs/BLUEPRINTS.md`, MIT-Lizenz + `THIRD_PARTY.md` · Fehler behoben: Karte schnell verlassen → verzögertes
Adress-Update schickte zurück auf die Karte.
