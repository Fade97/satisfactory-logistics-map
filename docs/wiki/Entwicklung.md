# Entwicklung

## Aufbau
```
mapd.py              Einstieg: startet drei Sammel-Takte + HTTP-Server
mapsvc/
  core.py            Zustand (vorgerenderte JSON-Blobs mit ETag), Konfiguration, Datenbank-Handle
  source.py          Save-Quellen: Ordner, SFTP, FTP/FTPS, Server-API
  collect.py         Takte: Save (60 s), FRM live (5 s), FRM Fabrik (60 s), Sink
  factory.py         Warenbilanz, Fabrik-Erkennung (Union-Find über Band-/Rohrnetz), Status
  events.py          Ereignisse mit Hysterese und 2-h-Sperre, Änderungsprotokoll
  logistics.py       Füllstände, Zug-Durchsatz aus Ladungsänderungen, Fahrplan-Prüfung
  planner.py         /api/plan
  http.py            API + statische Dateien (gzip, ETag, SPA-Fallback)
sav.py / sbp.py      Save- und Blueprint-Format (UE 5.4+ Property-Tags), byte-genau
factory.py           Fabrik aus dem Save: Maschinen, Raten, Stromnetze, Bänder, Warenfluss, Sammelobjekte …
stations.py          Stationen, Fahrpläne, Fahrzeuge
lightweight.py       Fundamente/Wände aus dem LightweightBuildableSubsystem
planner.py           LP-Rechner (scipy HiGHS)
store.py             SQLite: Zeitreihen in drei Stufen, Ereignisse, Spuren, Notizen, Zeitreise-Bilder
frm.py / geo.py      FicsIt-Remote-Monitoring-Client
frontend/            Svelte 5 + Vite; lib/mapview.ts = eigene Canvas-Karte, lib/Factory3D.svelte = three.js
gamedata/            Rezepte (SatisfactoryTools), Knoten, Rezeptpfade, Blueprint-Vorlagen
```
Das Backend nutzt nur die Python-Standardbibliothek plus numpy/scipy (Rechner) und paramiko (SFTP).

## Lokal entwickeln
```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
SAVE_SOURCE=/pfad/mit/einem/save .venv/bin/python mapd.py --port 8050   # Backend
cd frontend && pnpm install && pnpm dev                                  # Vite auf :5173, /api → :8050
```

## Tests
```sh
make test     # pytest + vitest
make check    # zusätzlich svelte-check, Build und Rauchtest aller Seiten (Desktop + Handy) gegen :8050
```
- `tests/test_source.py` — Save-Quellen gegen lokale FTP-/HTTPS-Testserver, läuft überall.
- `tests/test_backend.py` — braucht `tests/fixtures/sample.sav` (beliebiges eigenes Save; nicht im Repo). Die festen
  Zahlen darin passen nur zum ursprünglichen Save — für eigene Saves anpassen oder nur die Strukturtests nutzen.
- `frontend/tests/smoke.mjs` — Playwright-Rauchtest, erwartet Chromium unter `~/.cache/ms-playwright`
  (`pnpm exec playwright-core install chromium`).

## Neue Spielversion
1. Save laden lassen, Log auf Parser-Fehler prüfen.
2. `gamedata/data1.0.json` aus [SatisfactoryTools](https://github.com/greeny/SatisfactoryTools) aktualisieren, falls neue Rezepte/Gebäude.
3. `python3 sav.py`-Helfer (`load_index`, `show`) helfen beim Ansehen unbekannter Klassen.

## Beitragen
Issues und Pull Requests sind willkommen. Bitte vor einem PR `make test` laufen lassen. Die Oberfläche ist deutsch;
Übersetzungen wären ein guter Beitrag (Texte stehen direkt in den Svelte-Dateien).
