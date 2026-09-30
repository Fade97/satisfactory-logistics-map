# Design — Logistics Map v2 ("FICSIT look")

Brief (2026-09-29): modeled on the game UI, orange-grey, industrial typography; UI originally German (now English by default, German optional).

## Idea
The map is a **control room panel**, not a dashboard. The model is the terminal in the HUB: the game map
lies as a surface on warm anthracite, and everything man-made (tracks, stations, factories) sits on top in
FICSIT orange and signal colors. The one distinctive feature is the **punched corners**:
panels and buttons have a chamfered top right corner like the game menus. Only panels get
them, list rows do not. Everything else stays calm.

## Colors
| Name | Hex | Role |
|---|---|---|
| Steel | `#1b1c1e` | base surface, panels |
| Sheet metal | `#26282b` | raised surfaces, headers |
| Seam | `#3a3d41` | dividers, borders |
| FICSIT orange | `#f59a23` | brand, active selection, loading |
| Cobalt | `#5b9bd5` | unloading, trains, pipes (the game colors fluids blue) |
| Signal | `#e5484d` / `#4cc38a` | fault / running |
Text: `#e8e6e1` (warm white), muted `#9a968e`.

Loading = orange and unloading = blue replace the old green/orange: this is safer for color-blind users and
fits the palette.

## Typography
- **Barlow Condensed** 600/700: headings, key figures, navigation. Narrow and technical like the
  lettering in the game, in normal case, never letter-spaced capitals.
- **Barlow** 400/500: body text and tables, `font-variant-numeric: tabular-nums` for rates.
Scale: 12 / 14 / 16 / 20 / 28 / 40.

## Layout
```
Desktop                                          Phone
┌──────────────────────────────────────────┐    ┌──────────────┐
│ ▌FICSIT  Map Production Power Logistics …│    │ ▌ Map     ◉ ⋯│
├────────┬─────────────────────────┬───────┤    │              │
│ Search │                         │Detail │    │     Map      │
│ List   │           MAP           │ (on   │    │              │
│        │                         │select)│    ├──────────────┤
│        │               [Layers]  │       │    │ Bottom sheet │
├────────┴─────────────────────────┴───────┤    ├──────────────┤
│ Event bar (collapsible)                  │    │ Tab bar      │
└──────────────────────────────────────────┘    └──────────────┘
```
The other pages (Production, Power, Logistics, History) are left-aligned work areas with tables
and charts. Every row with a location jumps to the map on click (`#/map?sel=…`).

## Principles
1. The source is always visible: "live" (FRM) or "save from 22:19". Never present an old number as fresh.
2. Map first: every list ends on the map.
3. Colors carry meaning (status, direction), not decoration.
4. Motion only as a response: vehicles glide, panels slide open; no fade-in effects on load.
