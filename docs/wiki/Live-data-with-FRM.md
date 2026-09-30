# Live data with FRM (optional)

Without a mod, the map shows the state of the **last autosave** (usually 5 minutes old). With the mod
[FicsIt Remote Monitoring](https://ficsit.app/mod/FicsitRemoteMonitoring) (FRM) it becomes live:

| | save only | with FRM |
|---|---|---|
| Players, trains, trucks | every ~5 min, jumping | every 5 s, moving smoothly |
| "online" / follow mode | unknown | yes |
| Machines, power, item balance | every ~5 min | every minute |
| Stations, schedules, belts, foundations | from the save | from the save |
| Train throughput, round-trip times | – | yes |

The top right always shows honestly where the data comes from: **live** (green) or **save N min ago** (yellow).

## ⚠ Know this first
- **All players need the same mods** (Satisfactory Mod Loader + FRM, same version). Without them, you can no longer
  join the server — the server log does not even show a connection attempt. FRM's description says
  "server-only", but in practice that is not true.
- Mods can break after game updates until they are updated. In that case, simply clear `FRM_URL` — the map
  keeps running from the save.

## Setup
1. **Clients:** every player installs the [Satisfactory Mod Manager](https://smm.ficsit.app/) and, in it,
   *FicsIt Remote Monitoring* (which brings the mod loader along).
2. **Server:** download SML + FRM in the server variant (*LinuxServer* / *WindowsServer*) from https://ficsit.app
   and install them:
   - `.smod` files are ZIP archives. Unpack SML to `FactoryGame/Mods/SML/`,
     FRM to **`FactoryGame/Mods/GameFeatures/FicsitRemoteMonitoring/`** (not directly under `Mods/` — otherwise
     the mod loads but does nothing).
   - Start the server once and **stop** it again.
   - In `FactoryGame/Saved/Config/LinuxServer/GameUserSettings.ini` (Windows: `WindowsServer`), replace the line
     `mIntValues=()` with
     `mIntValues=(("FicsitRemoteMonitoring.Server.uWS.Autostart", 1),("FicsitRemoteMonitoring.Server.uWS.Port", 8080))`
     — only edit while the server is stopped, otherwise the game overwrites the file.
   - Start the server. `LogHttpServer: Port 8080 unavailable` in the log is normal.
   - **Pterodactyl:** the script `tools/install_frm_pterodactyl.sh` does all of this via SSH on the Wings host.
3. **Map:** set `FRM_URL=http://<server>:8080` in `.env` and run `docker compose up -d`.
4. **Check:** `curl http://<server>:8080/getSessionInfo` returns JSON. Without Docker: `FRM_URL=… python3 frm.py probe`.

## Keep port 8080 internal
The FRM port does **not** belong on the internet — the map queries it, visitors do not need it. If it is only available in a
container network (Pterodactyl), an SSH tunnel on the map's machine helps:
```sh
ssh -N -L 18080:<container-ip>:8080 root@wings-host
```
and `FRM_URL=http://127.0.0.1:18080` (with Docker: `http://host.docker.internal:18080` with
`extra_hosts: ["host.docker.internal:host-gateway"]` in `docker-compose.yml`).

## Known issue: "World not ready" after a session restart
The dedicated server reloads the session regularly (*Session Restart Time*, at night by default). Afterwards,
FRM sometimes keeps answering `Blocked API call: World not ready.` The map then shows "save N min ago" and keeps running
from the save. **Workaround:** fully restart the server process once, shortly after the session restart
(e.g. a Pterodactyl schedule "Power Action: restart", only when online). Technical details: `docs/frm-issue-draft.md`.
