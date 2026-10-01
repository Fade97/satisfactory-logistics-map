# Blueprint tools

Besides the map, the repo contains tools to read, generate and check Satisfactory blueprints (`.sbp` / `.sbpcfg`)
byte-exactly. Status: game version `++FactoryGame+rel-main-anniversary-2026`, build 502094,
blueprint header version 2, save version 60 (new UE 5.4+ property tag format — older community parsers do not fit).

| File | Purpose |
|---|---|
| `sbp.py` | Parser/writer for `.sbp`. `python3 sbp.py <folder>` = round-trip test (also `tests/test_sbp.py`), `python3 sbp.py dump <file.sbp> [full]` = show contents. |
| `sav.py` | Reader for `.sav` (read-only): `load_index(path)` returns all objects as `name -> (header, raw data)`, `show(idx, name)` prints properties. |
| `tools/railset_gen.py` | Generator for the railway set (below). Geometry is global in cm and is cut into 40 m boxes automatically. Needs a blueprint "Asphalt + Schiene - Gerade" from your own game as a template (folder via `BP_SRC`, name `TEMPLATE` at the top of the file; output folder `BP_OUT`, default `blueprints/rail-set`). |
| `bpgen.py` | Blueprint from the production planner (experimental): templates in `gamedata/templates/`, sets recipe and clock speed, removes surplus machines including their power cables, checks the round trip. |
| `blueprints/rail-set/` | Finished blueprints of the railway set plus overview drawings (`_*.png`). |
| `blueprints/from-server/` | Versions adjusted in the game (design reference). |

## Installing in the game
Copy the files into the session's blueprint folder: `…/FactoryGame/Saved/SaveGames/blueprints/<Session>/`
(dedicated server: in the server directory, with the same file owner as the other game files). The server only reads the folder when
loading the session — reload the save afterwards. New blueprints appear under "Undefined".

## Railway set (`tools/railset_gen.py` → `blueprints/rail-set/`)
Corridor 24 m wide, symmetrical, everything on asphalt foundations 8x1 (top edge z = 100):

| Element | Position (box coordinates, cm) |
|---|---|
| Foundation rows | y = −800 / 0 / +800 |
| Track B (runs +x) / track A (runs −x) | y = −800 / +800 → right-hand traffic, 16 m apart |
| Hypertube | y = 0, 1.75 m high; one support per 40 m with two street lights (±1.5 m) and cable |
| Decoration | Modern Railing (4 m) on both outer edges (yaw −90), H-beams (40 m) on the outer edges in the middle of the foundation |

Because the corridor is symmetrical, every piece can be rotated by 180°; track directions stay consistent.

| Blueprint | Boxes | Contents |
|---|---|---|
| Rail 01 Straight | 1 | Reference; the version adjusted in the game is in `blueprints/from-server/` |
| Rail 02 Straight Block Signals | 1 | Block signal per track 4 m behind the entry; use every 2–3 pieces |
| Rail 03 Junction Approach | 1 | Directly before a junction: path signal (incoming track) + block signal (outgoing track) at the +x end; rotate by 180° for the other side |
| Rail 05 Curve 90 | 4 | 90° curve, center line R 60 m (tracks 52/68 m). Entry "Bottom Left" from −x, exit "Top Right" towards +y; "Top Left" only contains the inner edge |
| Rail 10 T-Junction | 3 | "Top Left" + "Top Right" side by side, "Bottom" below (branch 4 m to the right of the seam, align with the foundations). 4 curves R 20 m, 6 switches, tube bridge (7 m) over the curves, the branch tube ends blind. Signals come from "Junction Approach" at all three ends |
| Rail 20 X-Crossing | 1 | Flat crossing without turning, both tubes as bridges (7 m / 8.5 m). "Junction Approach" at all four ends |
| Rail 30 Freight Station / Rail 31 Fluid Station | 1 | Own track (y = 0), direction +x: the train comes from −x through the freight/fluid platform (x −16…0) to the station (x 0…16). Container/pipe side −y. Block signals at both ends. Connect power |

### Signal and switch logic (derived from the save)
- The signal actor sits exactly on the track connection point, yaw = direction of travel. `mGuardedConnections` = ends of the tracks behind the signal, `mObservedConnections` = ends in front of it.
- Switch = `TrackConnection` with two entries in `mConnectedComponents`; plus a `Build_RailroadSwitchControl_C` on the point (yaw = direction away from the stem, `mControlledConnections`).
- Station: station/platform 16 m each with its own `Build_RailroadTrackIntegrated_C` (the spline starts at the platform side = local +x). The train enters in local −x direction, platforms attach at local +x. `PlatformConnection0` ↔ track end 0. Platform with the same yaw, not "reversed": container opposite the station building.
- Track ends on box edges are not connected internally; the game connects them when placing (auto-connect).

### Uncertain / not tested in the game
Flat track crossings (T: A curves cross track B; X) rely on the game treating overlapping tracks as one block.
Support heights 7 m/8.5 m (wiki: 1–7 m). Costs in the header are approximations.

## File format (summary)
- **Header (uncompressed):** `int32 2`, `int32 saveVersion`, `int32 build`, `int32[3] dims`, costs `{lvl,path,int32}`, recipes `{lvl,path}`, constant tail (engine/custom versions, copy 1:1).
- **Body:** zlib chunks with magic `C1 83 2A 9E`, 49-byte chunk header. Unpacked: `int32 total, int32 hdrSize, int32 n, object headers, int32 objSize, int32 n, n × (int32 size + data)`.
- **Object header:** actor `type=1, cls, root, name, int32 flags(8), int32 needTransform, quat f32[4], pos f32[3], scale f32[3], int32 placed`; component `type=0, cls, root, name, int32 flags, outer`.
- **Object data:** actor: `parent(lvl,path)`, component list; then 1 zero byte, property list until `None`, rest raw.
- **Property tag (UE 5.4+):** `name`, type tree (`name, int32 nParams, …`), `int32 size`, `uint8 flags` (1 index, 2 GUID, 4 extensions, 16 bool value). Struct arrays without an inner tag.
- **Save (`.sav`):** same chunks; body: `int64 size, int32 0, version block, grid section, then levels: [int32 60, list (lvl,path), int32 1, int32 0, version block, string name (main level without a name), int64 sz, int32 nH, headers, collectables list, int64 osz, int32 nO, nO × (int32 60, int32 0, int32 size, data, int32 0)]`.

## Map overlay (world coordinates → map image)
World coordinates are stored in the save in cm, **+X = east, +Y = south**. The game map covers
`X −324698.832031 … 425301.832031` and `Y −375000 … 375000` (the same constants as the
Satisfactory Calculator map); the 5000×5000 image maps this area linearly, i.e. 150 cm per pixel.
Cross-check: with this, all 490 resource nodes from the save lie on land. The white rectangle in the
northwest is an artifact of the game's map render and is present in every source.
