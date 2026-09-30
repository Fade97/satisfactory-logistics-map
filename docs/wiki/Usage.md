# Usage overview

At the top are the pages, to the right the **data source** (live / save N min ago / offline), **≡** Events,
**☺** My view and **⛶** Kiosk. On a phone, the navigation moves to the bottom.

## Overview (start page)
What needs attention right now: power grids with load, running machines, missing input, progress;
a list of problems (factories with missing input, fuel running out, machines without power, full storage) and **Shortages**
(click a row → Planner with the missing amount). At the bottom: **Since your last visit**.

![Overview](https://raw.githubusercontent.com/Fade97/satisfactory-logistics-map/main/docs/images/overview.png)

## Map
See [The map](Map).

![Map](https://raw.githubusercontent.com/Fade97/satisfactory-logistics-map/main/docs/images/map.png)

## Production
- **Item balance**: produced/consumed per minute for each item, filter "only shortage/surplus", a click shows the last 24 h.
- **Missing input**: stopped machines with the reason ("waiting for Iron Plate") and since when.
- **Factories**: automatically detected factories (machines connected by belts/pipes), with a status bar,
  main products and power. A click jumps to the map.
- **Resource nodes**: all nodes with purity, occupied/free.

Machines that only wait because their **output is full** count as an intended buffer and are grey instead of red.

![Factories](https://raw.githubusercontent.com/Fade97/satisfactory-logistics-map/main/docs/images/factories.png)

## Power
Every power grid with production, consumption, capacity and batteries, history, fuse trips (with FRM),
fuel range of the generators and machines not connected to power.

![Power](https://raw.githubusercontent.com/Fade97/satisfactory-logistics-map/main/docs/images/power.png)

## Logistics
Truck and train stations with fill levels and a warning when empty/full, measured train throughput (with FRM),
**Schedule check** (is a route's capacity enough for the demand of the factory at the unloading station?),
storage overview per item and the AWESOME Sink (points, coupons).

![Logistics](https://raw.githubusercontent.com/Fade97/satisfactory-logistics-map/main/docs/images/logistics.png)

## History
Production per item, power per grid, factory growth and a change log (built/dismantled) — from 1 hour up
to months. Gaps = the server was paused.

![History](https://raw.githubusercontent.com/Fade97/satisfactory-logistics-map/main/docs/images/history.png)

## Planner
See [Planner](Planner).

## My view (☺)
Applies only to the current browser, no login needed:
- **I am**: your player name
- **Map follows me when I'm online**
- **Start page**: Overview, Map (last position) or Production
- **Language**: English (default) or German
- **Item names**: English (as in the game) or German — search always finds both

## Events (≡)
Machines stopped/running again, storage full, players online/offline/died, built/dismantled, unlocks,
live data unavailable. Clicking an event jumps to the spot on the map. Notifications are damped: the same
notification appears at most every 2 hours, and thresholds have hysteresis.

## On a phone
All pages are built for phones. The map fills the screen, the station list is a drawer (☰),
detail cards appear as a sheet from the bottom (swipe up for more). With "Add to Home Screen" the
map becomes an app (see [How-to](How-to#install-the-map-as-an-app)).

<p><img src="https://raw.githubusercontent.com/Fade97/satisfactory-logistics-map/main/docs/images/mobile-overview.png" width="260"> <img src="https://raw.githubusercontent.com/Fade97/satisfactory-logistics-map/main/docs/images/mobile-map.png" width="260"></p>
