# API

All data on the website comes from an open JSON API — handy for your own analyses, Discord bots or
Home Assistant. Responses carry an `ETag`; with `If-None-Match` you get `304` if nothing has changed.
Coordinates: save world coordinates in **centimeters** (`pos`) or **meters** where stated; +X = east, +Y = south.

Note: some enum values in the API are still German internally, e.g. factory status `aktiv|aufbau|puffer|stillgelegt`
(active, under construction, buffer, decommissioned) and machine state `läuft|teilweise|steht|pausiert|aus`
(running, partial, stopped, paused, off).

## Read (GET)
| Endpoint | Contents | Updated |
|---|---|---|
| `/api/status` | title, FRM status, save state, last error | 5 s |
| `/api/live` | players, trains, trucks, session (time of day, paused) | 5 s (FRM) / save |
| `/api/factory` | machines, generators, power grids, item balance, factories | 60 s |
| `/api/stations` | truck/train stations, platforms, schedules, vehicles | save |
| `/api/geo` | rails, pipes, belts as polylines (m) | save / FRM |
| `/api/nodes` | resource nodes with purity and occupancy | save |
| `/api/powerlines` | power lines | save |
| `/api/flow` | per item, the belts/pipes carrying it | save |
| `/api/collectibles` | missing Somersloops, Mercer Spheres, Power Slugs, crash sites | save |
| `/api/storage` | storage per item, fill level | save |
| `/api/sink` | AWESOME Sink: points, coupons, progress | 60 s |
| `/api/progress` | unlocks, phase, milestones | save |
| `/api/recipes` | unlocked recipes | save |
| `/api/detail` | foundations and walls (binary format Int16) | save |
| `/api/events?since=<id>&limit=200` | events from an ID | continuous |
| `/api/series?k=<key>&k=…&since=<unix>` | time series, e.g. `prod:Iron Plate`, `cons:Iron Plate`, `power:<grid>:prod` | 60 s |
| `/api/series-keys?prefix=prod:` | available series | |
| `/api/train-flow?h=24` | measured train throughput per station and item | |
| `/api/schedule` | schedule check (capacity vs. demand) | |
| `/api/frames?h=6&step=60` | time travel snapshots (max. 24 h) | 60 s |
| `/api/trails` | player trails (2 h) | |
| `/api/pins` | notes | |

## Write (POST, header `X-Map-Password`)
| Endpoint | Body |
|---|---|
| `/api/auth` | – (only checks the password) |
| `/api/pins` | `{author, cat, color, text, shape: point\|line\|area, geom: [[x,y],…]}` |
| `/api/pins/<id>/delete` | – |
| `/api/factory-name` | `{key, name, status: aktiv\|aufbau\|puffer\|stillgelegt}` |

## Calculate (POST, no password)
| Endpoint | Body |
|---|---|
| `/api/plan` | `{targets: [{item, rate}], use_surplus, goal: raw\|machines\|power, max_clock, sloop, allow, exclude}` |
| `/api/blueprint` | one step from `/api/plan` → ZIP |

## Example: power in Home Assistant
```yaml
sensor:
  - platform: rest
    name: Satisfactory Power
    resource: https://map.example.com/api/factory
    value_template: "{{ value_json.circuits | map(attribute='use') | sum | round(0) }}"
    unit_of_measurement: MW
    scan_interval: 60
```
