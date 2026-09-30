# Live data with FicsIt Remote Monitoring (optional)

Without a mod, the map shows the state of the last save (autosave interval, usually 5 min). With the mod
**FicsIt Remote Monitoring** (FRM, tested with FRM 1.5.3 + SML 3.12.0), players, vehicles,
machines and power update every 5 s or 60 s. FRM provides via HTTP:

| Endpoint | Used for |
|---|---|
| `getPlayer` | player name, position, **online flag**, HP, speed, inventory |
| `getTrains` / `getTruck` | vehicle positions, speed, status, cargo |
| `getTruckStation` / `getTrainStation` | activity (Idle/Transferring), throughput, current buffer contents |
| `getSessionInfo` | play time, day, **paused state** (the server pauses without players) |

Plus `getFactory`/`getExtractor` (machines), `getPower` (power grids) and the network geometry. Station structure and
load/unload direction still come from the save — FRM's `LoadMode` is the current *activity*, not the setting.

## Setup
1. Put SML and FRM (variant *LinuxServer* or *WindowsServer*) from https://ficsit.app on the server —
   on Pterodactyl, `tools/install_frm_pterodactyl.sh` helps; otherwise do it by hand (pitfalls below).
2. All players install the same mods in the **Satisfactory Mod Manager** (see the last pitfall).
3. The FRM web server listens on port 8080 of the server. Set `FRM_URL=http://server:8080`. If the port is only available in
   a container network (Pterodactyl), put an SSH tunnel in front of it or open an allocation in the panel.
   Do **not** expose the port publicly — the map queries it, visitors do not need it.
4. Check: `FRM_URL=… python3 frm.py probe` shows which endpoints respond.

## Pitfalls
- FRM is a **game feature plugin** (`GameFeature: true`). If it is placed under `FactoryGame/Mods/<Name>/`,
  SML loads the binaries and reports the version, but the world module is never discovered and the mod
  does *nothing* — no log, no endpoints. The correct location is `FactoryGame/Mods/GameFeatures/<Name>/`.
- The configuration lives in `FactoryGame/Saved/Config/LinuxServer/GameUserSettings.ini` as
  `mIntValues=(("FicsitRemoteMonitoring.Server.uWS.Autostart", 1),…)`. The game discards unknown keys
  at startup — the entry only sticks after FRM has been loaded once. And on shutdown
  the game rewrites the file: only edit it while the server is stopped.
- `LogHttpServer: Port 8080 unavailable` in the log is **not** an error: uWS has already bound the port via IPv6,
  and UE's own HTTP server then fails on it. The web server runs anyway.
- **Clients need SML *and* FRM in the same version as the server.** FRM's own description
  claims "can be a server-only mod … not required on the client" (`RequiredOnRemote: false` in the
  `.uplugin`), while the SML docs clearly say: *"client players must have the same mods installed as the
  server to be able to join."* In practice, the SML statement applies — a client with SML but without FRM
  cannot join and aborts even before the login request (the server log then shows **nothing at all**;
  a real attempt would write `LogNet: Login request … ?Name=…` and `Join succeeded:`).

## FRM hangs after the nightly session restart
The dedicated server reloads the session regularly (*Session Restart Time*) without restarting the process.
FRM keeps its web server thread with the old world and afterwards sometimes keeps answering
`Blocked API call: World not ready.` (503). Evidence: `docs/frm-issue-draft.md`. Workaround: fully restart the server
once, shortly after the session restart (e.g. a Pterodactyl schedule, "only when online"). Until then the map runs from the save.

## Player positions without a mod
Satisfactory has **no RCON**. The dedicated server offers an HTTPS API
(`https://server:7777/api/v1/`, self-signed → `curl -k`), but it knows **no** player data
apart from `numConnectedPlayers` (in `QueryServerState`, requires admin). Proof: unknown
function names answer `bad_function`, existing ones without a token answer `insufficient_scope` — this lets you
probe the available functions without credentials; `GetPlayers`, `ListPlayers`,
`GetPlayerPositions`, `EnumeratePlayers` do not exist.

The positions are in the save instead: every `Char_Player_C` carries `mCachedPlayerName`, the
world position in the actor header and, via `mSavedDrivenVehicle`, the vehicle currently being driven.
The character stays in the world after logging out — "currently online" is *not* in the save; without FRM the map
therefore shows "online unknown" and does not follow anyone automatically.

The API does work as a **save source**, though: with the admin password, `EnumerateSessions` + `DownloadSaveGame` return the
newest save without creating a new one (`SAVE_SOURCE=api://server:7777`). The map deliberately does not use `SaveGame`
(which forces a save).
