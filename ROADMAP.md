# Logistics Map — relaunch (from 2026-09-29)

Requirements from the survey on 2026-09-29. Order = build plan; each block goes live when finished.

## Framework
| Topic | Decision |
|---|---|
| Users | operator on the second monitor, other players, planning on the phone — all pages fully mobile |
| Data source | **Mixed**: FRM preferred, automatic fallback to the save (every 5 min) |
| Stack | Python backend (stdlib/SQLite) + **Svelte/Vite** frontend, map as a **custom canvas/WebGL renderer** |
| Layout | map = start page, plus the pages Production · Power · Logistics · History; a click jumps to the map |
| Design | **FICSIT look**: orange/grey, industrial typography |
| Language | UI German, items/buildings English (now: UI English by default, German optional) |
| Visibility | everything publicly readable; writing (pins, factory names) with a shared password |
| Server | read-only; agree on every change to the game server beforehand, **no restarts** |
| Recipe data | public community dataset, matched against the recipe paths in the save |
| Switchover | the new site replaces the old one directly; rollback via git |
| Acceptance | deploy live after each block + short note with a screenshot |

## Blocks
1. **Robustness** — detect and show FRM hangs, save fallback for machines/grid, SQLite history
   (1 min → 48 h, hourly averages → 90 days, daily values forever), collect events from now on.
2. **Production** — item balance (target/actual per item), stopped machines with reason + since when (list + heatmap),
   factory clusters automatically (proximity + belts), renamable; resource nodes with purity/occupied/extractor.
3. **Power** — grid overview (production, consumption, capacity, battery), power lines as a layer colored by grid,
   history with fuse trips, fuel range.
4. **Logistics** — throughput per route vs. demand, fill level bars + empty/full warning, drones, network diagram.
5. **History** — production per item, power per grid, factory growth, change log (new/dismantled, builder).
6. **Live / 2nd monitor** — follow mode (player/train/truck), event feed (faults, supply, players, progress),
   live every 5 s, kiosk (map + feed, key figures, rotating pages).
7. **Other players** — pins with category/color/author, draw lines/areas, builder filter,
   player trails (last 2 h); check whether pins can become in-game markers via FRM (uncertain).

No push notifications — events only in the map.

## Status 2026-09-29 (first pass, live)
| Block | Status | Open |
|---|---|---|
| 1 Robustness | save fallback, source indicator, SQLite history, events, Pterodactyl restart 00:10 UTC, issue draft | FRM path (`frm_factory`) only verified live after the first restart |
| 2 Production | item balance, stopped machines with reason, factory clusters (renamable), resource nodes | heatmap instead of a point layer; clusters also via belt connections |
| 3 Power | grid overview, power lines by grid, history, fuel range + balance | fuse trips only with FRM |
| 4 Logistics | truck throughput (upper bound), fill levels + warning, network diagram, vehicle list | drones (none present), real train throughput |
| 5 History | production per item, machine status, growth, change log with builder | builder often unknown (PlayerInfoHandle not unique) |
| 6 Live | live every 5 s, follow mode, event feed, kiosk (`#/kiosk?follow=<player>&rotate=30`) | – |
| 7 Other players | notes (point/line/area, category, author), player trails 2 h | in-game: FRM can only `createPing`, no markers |

## Round 2 (2026-09-30)
Answers: the map was empty after switching pages (fixed) · "Output full" is normal → quiet · stoppage as a heatmap **and**
factory outline · separate factories via conveyor belts · full production planner (only unlocked recipes,
few resources, use surplus, diagram + build list + free nodes + as a note) · the steel stoppage went unnoticed →
make hints prominent · factory status (active/under construction/buffer/decommissioned) · start page = Overview.

FRM path verified after the 02:10 restart: works; extractors were missing from `getFactory` (fixed via `getExtractor`).

## Round 3 (2026-09-30)
Fuzzy search everywhere · new chain diagram (layout, tree) · do not record pauses, gaps in charts ·
item flow on the map (choose an item → producers, consumers, stations, belts/pipes from the save) ·
planner: optimize for resources/machines/power, choose recipes per item, clock up to 250 % (shards), Somersloops,
build site via map click · "My view" per browser (I am, map follows me, start page, last map position) ·
events with hysteresis and a 2 h cooldown (factories near the threshold reported every few minutes).

## Round 4 (2026-09-30)
Tests (`make check`: pytest, vitest, smoke test of all pages on desktop and phone) · height filter with detected floors ·
measure (distance, area, foundations, rail/belt pieces) · machines not connected to power (map, Power, Overview, event) ·
real train throughput from cargo changes of docked trains (`/api/train-flow`) · 3D view per factory (three.js, lazy-loaded) ·
German item names optional (search finds both languages).

## Round 5 (2026-09-30)
Collectibles as layers (missing Somersloops, Mercer Spheres, Power Slugs, unopened crash sites; counters) ·
storage overview per item + "storage full, factory backed up" · AWESOME Sink (coupons, points/min, progress) ·
schedule check (capacity per route vs. demand of the factory at the unloading stations, train round-trip time measured) ·
blueprint from the planner (experimental, only Constructor/Smelter, based on players' templates).

Open: test the blueprint in the game; more templates (Assembler/Foundry/Manufacturer) from player blueprints; train round-trip times only fill up with gameplay.

## Round 6 (2026-09-30)
Backend split into modules (`mapsvc/`), map into components (`lib/map/`) · time travel (minute snapshots 24 h, time slider, gaps marked) ·
PWA (installable, offline with the last known state, honest offline indicator) · detail layer instead of map tiles: foundations and walls
from the save (83 k lightweight objects, 180 KB) — higher-resolution game maps are not available with a clean license.

## Round 7 (2026-09-30) — shareable
Docker package (`docker compose up -d`, `.env.example`) · configurable save source: folder, SFTP, FTP/FTPS, server API
(`mapsvc/source.py`) · FRM optional (`FRM_URL` empty = off) · title from the session name · setup hint without a save ·
v1 map removed, blueprints moved to `blueprints/`, templates to `gamedata/templates/` · new README, `docs/FRM.md`,
`docs/BLUEPRINTS.md`, MIT license + `THIRD_PARTY.md` · bug fixed: leaving the map quickly → a delayed
address update sent you back to the map.
