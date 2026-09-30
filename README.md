<p align="center"><img src="docs/logo/banner.png" alt="Satisfactory Logistics Map" width="720"></p>

<p align="center">
  <a href="https://github.com/Fade97/satisfactory-logistics-map/actions/workflows/ci.yml"><img src="https://github.com/Fade97/satisfactory-logistics-map/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-f59a23" alt="MIT"></a>
  <a href="https://github.com/Fade97/satisfactory-logistics-map/wiki"><img src="https://img.shields.io/badge/Docs-Wiki-1b1c1e" alt="Wiki"></a>
</p>

# Satisfactory Logistics Map

Deutsche Kurzfassung: [README.de.md](README.de.md)

A web map for your own Satisfactory dedicated server. It reads the save and shows what is going on in your factory,
on your PC, on a second monitor or on your phone. The UI is in English by default; you can switch it to German under
**My view → Language**. Item names can be shown in English or German.

- **Overview**: what is stuck right now, shortages, what happened since your last visit
- **Map**: stations, trains, trucks, players (follow mode), rails/belts/pipes, foundations, heatmap of stopped machines,
  item flow per item, collectibles, height filter, measuring, notes, time travel over the last 24 h
- **Production**: item balance, factories (detected automatically from the belt network), stopped machines with reason, 3D view per factory
- **Power**: grids, load, fuel range, machines not connected to power
- **Logistics**: fill levels, train and truck throughput, schedule check, storage, AWESOME Sink
- **History**: production and power over hours to months, change log
- **Planner**: production chains using only unlocked recipes, use factory surplus, build site, blueprint export (experimental)
- Installable as an app (PWA), kiosk mode for a side screen (`#/kiosk?follow=<player>&rotate=30`)

![Map](docs/images/map.png)

<p><img src="docs/images/overview.png" width="49%"> <img src="docs/images/planner.png" width="49%"></p>

Without a mod, everything comes from the save, at the autosave interval (usually 5 min). With the optional mod
[FicsIt Remote Monitoring](docs/FRM.md), positions update every 5 s and machines and power every minute.

**Detailed guides in the [wiki](https://github.com/Fade97/satisfactory-logistics-map/wiki)**: installation,
save source per server type, live data, reverse proxy, how-tos, troubleshooting, API.

## Quick start with Docker

```sh
git clone https://github.com/Fade97/satisfactory-logistics-map.git
cd satisfactory-logistics-map
cp .env.example .env        # set the save source, see below
docker compose up -d        # builds the image on first start
```

Then open http://localhost:8050. As long as there is no save yet, the page shows the reason at the top,
for example a wrong password or a folder that was not found. The next attempt runs automatically after one minute.

## Choose a save source (`SAVE_SOURCE`)

| Option | `SAVE_SOURCE` | When |
|---|---|---|
| **Server API** | `api://server:7777` + `SAVE_PASSWORD` (admin password) | Easiest; works with every dedicated server and only needs the address and admin password. Reads the latest save of the running session without creating a new one. |
| **SFTP** | `sftp://user@host:2022/path` + `SAVE_PASSWORD` or `SAVE_KEY` | Pterodactyl (port 2022, user `<panelname>.<server-id>`, path `/.config/Epic/FactoryGame/Saved/SaveGames/server`) or your own Linux server |
| **FTP/FTPS** | `ftp://…` / `ftps://user@host/path` + `SAVE_PASSWORD` | many server hosters |
| **Folder** | `/saves` (mount the volume in `docker-compose.yml`) | the game server runs on the same machine |
| *(empty)* | – | put `*.sav` files into the data volume under `saves/` by hand |

Typical save folders: Linux server `~/.config/Epic/FactoryGame/Saved/SaveGames/server/`,
Windows server `%LOCALAPPDATA%\FactoryGame\Saved\SaveGames\server\`. The newest `*.sav` is used.
If the folder holds several sessions, narrow it down with `SAVE_PATTERN=Session_*.sav`.
The save is only loaded when it has changed. The check runs every minute.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `SAVE_SOURCE` | *(empty = `saves/`)* | see above |
| `SAVE_PASSWORD` / `SAVE_TOKEN` / `SAVE_KEY` | – | access to the save source; special characters in the password are less of a problem here than in the URL |
| `SAVE_PATTERN` | `*.sav` | file pattern |
| `FRM_URL` | *(empty = off)* | FicsIt Remote Monitoring, e.g. `http://server:8080`, see [docs/FRM.md](docs/FRM.md) |
| `MAP_PIN_PASSWORD` | *(empty = read-only)* | shared password for notes, factory names and status |
| `MAP_TITLE` | session name | name in the top left |
| `MAP_DATA` | `data/` (`/data` in the container) | history (SQLite), notes, generated blueprints |
| `TZ` | `Europe/Berlin` (container) | time zone for timestamps |

**Public access:** put the map behind a reverse proxy with HTTPS, for example Traefik, Caddy or nginx.
Reading is open. Writing requires the password; after 10 failed attempts the IP is blocked for 10 minutes.
Do not expose the FRM port publicly.

## Without Docker

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd frontend && pnpm install && pnpm run build && cd ..
SAVE_SOURCE=/path/to/SaveGames/server .venv/bin/python mapd.py --port 8050
```

For permanent operation, use a systemd service with the same environment variables (`Environment=` or `EnvironmentFile=`).

## Development

```sh
.venv/bin/pip install -r requirements-dev.txt
make test       # pytest (tests/) + vitest (frontend/tests/)
make check      # adds type checking, build and a smoke test of all pages against :8050 (desktop + phone)
cd frontend && pnpm dev   # Vite with a proxy to the running service
```

The save tests need `tests/fixtures/sample.sav`, any copy of a save. The file is not in the repo,
and the fixed numbers in `tests/test_backend.py` only apply to the original save. The save source tests
(`tests/test_source.py`) run without a fixture.

## Structure

| Part | Purpose |
|---|---|
| `mapd.py` | Entry point: one service with three loops (live 5 s, factory 60 s, save 60 s), serves `frontend/dist` and `/api/*` |
| `mapsvc/` | `core` (state, configuration), `source` (save sources), `collect` (loops), `factory` (balance, factory detection), `events`, `logistics` (throughput, schedule), `planner`, `http` |
| `sav.py`, `sbp.py` | Save and blueprint format (UE 5.4+ property tags), see [docs/BLUEPRINTS.md](docs/BLUEPRINTS.md) |
| `factory.py` | Factory from the save: machines, recipes, rates, power grids, belts, item flow, collectibles, storage |
| `stations.py`, `lightweight.py` | Stations, schedules, vehicles; foundations and walls (lightweight buildables) |
| `planner.py` | Production planner (linear program, scipy/HiGHS) |
| `store.py` | SQLite: time series (minute 48 h → hour 90 days → day), events, trails, notes |
| `frm.py`, `geo.py` | Client for FicsIt Remote Monitoring |
| `frontend/` | Svelte 5 + Vite, custom canvas map (`lib/mapview.ts`), three.js for 3D |
| `gamedata/` | Recipes, resource nodes, recipe paths, blueprint templates |
| `blueprints/`, `gen.py`, `bpgen.py` | Railway set blueprints and generator |
| `tools/` | `install_frm_pterodactyl.sh`: install SML + FRM on a Pterodactyl server |
| `docs/` | [DESIGN](docs/DESIGN.md) (visual design), [FRM](docs/FRM.md), [BLUEPRINTS](docs/BLUEPRINTS.md), [ROADMAP](ROADMAP.md) |

## License

Code under [MIT](LICENSE). Bundled data from other projects has its own licenses, see [THIRD_PARTY.md](THIRD_PARTY.md).
The map image is licensed CC BY-NC-SA and must not be used commercially.
Not an official project; Satisfactory is a trademark of Coffee Stain Studios.
