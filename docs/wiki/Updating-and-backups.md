# Updating and backups

## Updating (Docker)
```sh
cd satisfactory-logistics-map
git pull
docker compose up -d --build
```
History, notes and factory names are stored in the `map-data` volume and are kept. Database changes are applied
automatically at startup.

Afterwards, reload the page once. Installed apps (PWA) pick up the new version the next time they are opened.

## Updating (without Docker)
```sh
git pull
.venv/bin/pip install -r requirements.txt
cd frontend && pnpm install && pnpm run build && cd ..
sudo systemctl restart satisfactory-map
```

## After a game update
The map reads the save format of Satisfactory 1.x. New buildings/recipes come from `gamedata/` — after major
game updates, watch out for a new version of the map. With FRM: the mod must match the game, otherwise clear `FRM_URL`.

## Backups
The only important file is the database `map.db` (history, notes, factory names). It runs in WAL mode — do **not** simply
copy it while the service is running, or the latest changes will be missing. This is the safe way:
```sh
# Docker
docker compose exec map python -c "import sqlite3; s=sqlite3.connect('/data/map.db'); s.execute(\"VACUUM INTO '/data/backup.db'\")"
docker compose cp map:/data/backup.db ./map-backup-$(date +%F).db

# without Docker
sqlite3 data/map.db "VACUUM INTO 'backup.db'"
```
To restore: stop the service, put the file into the data folder as `map.db` (delete old `map.db-wal`/`-shm`), start it.

## Moving to another machine
Back up the volume (see above) plus `.env`. On the new machine, clone the repository, put `.env` and `map.db` in place, start.

## Disk usage
After the first day, the database is about 10 MB (factory with ~1100 machines) and then grows slowly: minute values
are aggregated into hourly averages after 48 h and into daily values after 90 days; time travel snapshots are deleted after 24 h.
