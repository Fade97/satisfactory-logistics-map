# Aktualisieren und Sichern

## Aktualisieren (Docker)
```sh
cd satisfactory-logistikkarte
git pull
docker compose up -d --build
```
Verlauf, Notizen und Fabriknamen liegen im Volume `map-data` und bleiben erhalten. Datenbank-Änderungen passieren
automatisch beim Start.

Danach einmal die Seite neu laden. Installierte Apps (PWA) holen die neue Version beim nächsten Öffnen.

## Aktualisieren (ohne Docker)
```sh
git pull
.venv/bin/pip install -r requirements.txt
cd frontend && pnpm install && pnpm run build && cd ..
sudo systemctl restart satisfactory-map
```

## Nach einem Spiel-Update
Die Karte liest das Save-Format von Satisfactory 1.x. Neue Gebäude/Rezepte kommen aus `gamedata/` — nach größeren
Spiel-Updates auf eine neue Version der Karte achten. Mit FRM: der Mod muss zum Spiel passen, sonst `FRM_URL` leeren.

## Sichern
Wichtig ist nur die Datenbank `map.db` (Verlauf, Notizen, Fabriknamen). Sie läuft im WAL-Modus — **nicht** einfach
im laufenden Betrieb kopieren, sonst fehlen die letzten Änderungen. Sicher geht es so:
```sh
# Docker
docker compose exec map python -c "import sqlite3; s=sqlite3.connect('/data/map.db'); s.execute(\"VACUUM INTO '/data/backup.db'\")"
docker compose cp map:/data/backup.db ./map-backup-$(date +%F).db

# ohne Docker
sqlite3 data/map.db "VACUUM INTO 'backup.db'"
```
Zurückspielen: Dienst stoppen, Datei als `map.db` in den Datenordner legen (alte `map.db-wal`/`-shm` löschen), starten.

## Umziehen
Volume sichern (siehe oben) plus `.env`. Auf dem neuen Rechner Repository klonen, `.env` und `map.db` hinlegen, starten.

## Speicherbedarf
Die Datenbank ist nach dem ersten Tag etwa 10 MB groß (Fabrik mit ~1100 Maschinen) und wächst danach langsam: Minutenwerte
werden nach 48 h zu Stundenmitteln, nach 90 Tagen zu Tageswerten zusammengefasst; Zeitreise-Bilder nach 24 h gelöscht.
