# How-to

Short guides for common tasks.

## Install the map as an app
- **Android (Chrome):** menu ⋮ → *Install app* or *Add to Home screen*.
- **iPhone (Safari):** Share □↑ → *Add to Home Screen*.
- **PC (Chrome/Edge):** the ⊕ icon on the right of the address bar.

The app starts without a browser bar and shows the last known state when offline ("offline · last known state"). Requirement: HTTPS
(see [Public access](Public-access)) or access via `localhost`.

## Second monitor / wall display
Open `https://your-map/#/kiosk?rotate=30` in a full-screen browser (F11). With `follow=<player>` the map stays
with you. Tip: set "I am" in *My view*; then the normal map follows you as well as soon as you are online.

## Make the map follow you
Set **☺ → I am** to your name and tick **Map follows me when I'm online**. Requires [FRM](Live-data-with-FRM).

## Find out why a factory is stopped
1. **Overview** shows factories with missing input. Click → map.
2. The factory detail card lists the machines by status; clicking a machine shows the reason
   ("waiting for Steel Beam").
3. Open **Item flow** for the missing item: who produces it, where is it on belts, which station delivers it?
4. If it is missing overall: on the Overview, click its row in **Shortages** → Planner with the missing amount.

## Name and decommission factories
Click the factory on the map → **Rename / set status** (password). Status: *active*, *under construction*, *buffer*,
*decommissioned*. Only **active** factories raise warnings — construction sites and intended buffers stay quiet.

## Place a note ("build a coal power plant here")
**Note** → Point/Line/Area → click on the map → text and category → password (once per browser).

## Check a train schedule
**Logistics → Schedule check**: for each route, the capacity (wagons × round-trip time) against the demand of the factories at
the unloading stations. Red = not enough. The map measures round-trip times itself (requires FRM and some play time).

## Plan a new factory
**Planner** → enter the target → choose a build site on the map → look at the free nodes → **Save plan as map note**.

## Look back: what happened 3 hours ago?
**Map → Time travel**, drag the slider back. Players, trains and the status of every factory are replayed minute by minute
(last 24 h, only times when the game was being played).

## German UI
**☺ → Language → German**. English is the default.

## German item names
**☺ → Item names → German**. Search always finds both languages.

## Send a link to a spot
Zoom in on the map, click something, copy the address bar. The link opens exactly this view.
