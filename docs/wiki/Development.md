# Development

## Structure
```
mapd.py              entry point: starts three collection loops + HTTP server
mapsvc/
  core.py            state (pre-rendered JSON blobs with ETag), configuration, database handle
  source.py          save sources: folder, SFTP, FTP/FTPS, server API
  collect.py         loops: save (60 s), FRM live (5 s), FRM factory (60 s), sink
  factory.py         item balance, factory detection (union-find over the belt/pipe network), status
  events.py          events with hysteresis and 2 h cooldown, change log
  logistics.py       fill levels, train throughput from cargo changes, schedule check
  planner.py         /api/plan
  http.py            API + static files (gzip, ETag, SPA fallback)
sav.py / sbp.py      save and blueprint format (UE 5.4+ property tags), byte-exact
factory.py           factory from the save: machines, rates, power grids, belts, item flow, collectibles …
stations.py          stations, schedules, vehicles
lightweight.py       foundations/walls from the LightweightBuildableSubsystem
planner.py           LP planner (scipy HiGHS)
store.py             SQLite: time series in three tiers, events, trails, notes, time travel snapshots
frm.py / geo.py      FicsIt Remote Monitoring client
frontend/            Svelte 5 + Vite; lib/mapview.ts = custom canvas map, lib/Factory3D.svelte = three.js
gamedata/            recipes (SatisfactoryTools), nodes, recipe paths, blueprint templates
```
The backend only uses the Python standard library plus numpy/scipy (planner) and paramiko (SFTP).

## Local development
```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
SAVE_SOURCE=/path/with/a/save .venv/bin/python mapd.py --port 8050   # backend
cd frontend && pnpm install && pnpm dev                              # Vite on :5173, /api → :8050
```

## Tests
```sh
make test     # pytest + vitest
make check    # additionally svelte-check, build and a smoke test of all pages (desktop + phone) against :8050
```
- `tests/test_source.py` — save sources against local FTP/HTTPS test servers, runs anywhere.
- `tests/test_backend.py` — needs `tests/fixtures/sample.sav` (any save of your own; not in the repo). The fixed
  numbers in it only match the original save — adapt them for your own saves or only use the structure tests.
- `frontend/tests/smoke.mjs` — Playwright smoke test, expects Chromium under `~/.cache/ms-playwright`
  (`pnpm exec playwright-core install chromium`).

## New game version
1. Let the map load a save and check the log for parser errors.
2. Update `gamedata/data1.0.json` from [SatisfactoryTools](https://github.com/greeny/SatisfactoryTools) if there are new recipes/buildings.
3. The `python3 sav.py` helpers (`load_index`, `show`) help with inspecting unknown classes.

## Contributing
Issues and pull requests are welcome. Please run `make test` before opening a PR. The UI is in English by default,
with German as an option (`frontend/src/lib/i18n/`, terms in `GLOSSARY.md`). More translations would be a good contribution.
