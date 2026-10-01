#!/usr/bin/env bash
# Installs Satisfactory Mod Loader + FicsIt Remote Monitoring on a Pterodactyl game server
# (root SSH to the Wings host) and restarts it via the Pterodactyl client API.
# Guide and pitfalls: docs/FRM.md.
#
#   SF_HOST=root@wings-host SF_KEY=~/.ssh/id_ed25519 PTERO_UUID=<server-uuid> PTERO_ENV=path/.env \
#     tools/install_frm_pterodactyl.sh [--dry-run|--uninstall]
#
#   --uninstall  deletes FactoryGame/Mods/SML and the WHOLE FactoryGame/Mods/GameFeatures directory —
#                including any other game-feature mods installed there — then restarts the server.
#
# PTERO_ENV contains PTERODACTYL_PANEL_URL and PTERODACTYL_CLIENT_API_KEY.
# Download the .smod archives (LinuxServer) from https://ficsit.app into mods/ beforehand
# (versions: SML_VERSION / FRM_VERSION below, or set them in the environment).
set -euo pipefail

SML_VERSION=${SML_VERSION:-3.12.0}
FRM_VERSION=${FRM_VERSION:-1.5.3}
SML_SMOD=SML-$SML_VERSION-LinuxServer.smod
FRM_SMOD=FRM-$FRM_VERSION-LinuxServer.smod

HOST=${SF_HOST:?SF_HOST missing (root@wings-host)}
KEY=${SF_KEY:?SF_KEY missing (SSH key)}
UUID=${PTERO_UUID:?PTERO_UUID missing (full server UUID from the panel)}
API_PORT=${SF_API_PORT:-7777}
VOL=/var/lib/pterodactyl/volumes/$UUID
MODS=$VOL/FactoryGame/Mods
# FRM is a game feature plugin (GameFeature=true in the .uplugin): if it sits directly
# under Mods/, SML loads the binaries, but the world module is never discovered and the
# mod does nothing. Game features belong in Mods/GameFeatures/.
FRMDIR=$MODS/GameFeatures/FicsitRemoteMonitoring
INI=$VOL/FactoryGame/Saved/Config/LinuxServer/GameUserSettings.ini
HERE=$(cd "$(dirname "$0")/.." && pwd)
ENVFILE=${PTERO_ENV:?PTERO_ENV missing (.env with panel URL and client API key)}
SSH=(ssh -i "$KEY" -o IdentitiesOnly=yes -o BatchMode=yes)

DRY=0; MODE=install
for a in "$@"; do
  case $a in --dry-run) DRY=1;; --uninstall) MODE=uninstall;; *) echo "unknown: $a"; exit 2;; esac
done

run() { if [ $DRY = 1 ]; then echo "[dry] $*"; else "$@"; fi }

power() {   # $1 = start|stop|restart
  # shellcheck disable=SC1090
  set -a; . "$ENVFILE"; set +a
  if [ $DRY = 1 ]; then echo "[dry] POST /api/client/servers/${UUID:0:8}/power $1"; return; fi
  curl -sf -X POST "$PTERODACTYL_PANEL_URL/api/client/servers/${UUID:0:8}/power" \
       -H "Authorization: Bearer $PTERODACTYL_CLIENT_API_KEY" \
       -H "Content-Type: application/json" -H "Accept: application/json" \
       -d "{\"signal\":\"$1\"}" -o /dev/null
}

state() {
  # shellcheck disable=SC1090
  set -a; . "$ENVFILE"; set +a
  curl -s "$PTERODACTYL_PANEL_URL/api/client/servers/${UUID:0:8}/resources" \
       -H "Authorization: Bearer $PTERODACTYL_CLIENT_API_KEY" -H "Accept: application/json" |
    python3 -c "import json,sys;print(json.load(sys.stdin)['attributes']['current_state'])"
}

stop_server() {
  echo "→ Stopping server"
  power stop
  [ $DRY = 1 ] && return
  for _ in $(seq 1 75); do               # up to 5 minutes
    if [ "$(state)" = offline ]; then echo "→ offline"; return; fi
    sleep 4
  done
  echo "!! Server does not stop — check the panel"; exit 1
}

start_server() {
  echo "→ Starting server"
  power start
  [ $DRY = 1 ] && return
  for _ in $(seq 1 90); do
    sleep 5
    if curl -sk -m 5 -X POST "https://${HOST#*@}:$API_PORT/api/v1/" -H 'Content-Type: application/json' \
         -d '{"function":"HealthCheck","data":{"clientCustomData":""}}' 2>/dev/null | grep -q healthy; then
      echo "→ Server is back"; return
    fi
  done
  echo "!! Server does not respond — check the panel"; exit 1
}

restart_server() { stop_server; start_server; }

if [ $MODE = uninstall ]; then
  echo "→ Removing mods"
  run "${SSH[@]}" "$HOST" "rm -rf $MODS/SML $MODS/GameFeatures"
  restart_server
  echo "Done — server is running vanilla again."
  exit 0
fi

for f in "$SML_SMOD" "$FRM_SMOD"; do
  [ -f "$HERE/mods/$f" ] || { echo "missing: mods/$f"; exit 1; }
done

echo "→ Creating mods directory"
run "${SSH[@]}" "$HOST" "mkdir -p $MODS/SML $FRMDIR"

echo "→ Uploading archives"
run scp -i "$KEY" -o IdentitiesOnly=yes "$HERE/mods/$SML_SMOD" "$HERE/mods/$FRM_SMOD" "$HOST:/tmp/"

echo "→ Unpacking (each mod goes into a folder named after the plugin)"
run "${SSH[@]}" "$HOST" "command -v unzip >/dev/null || (apt-get update -qq && apt-get install -y -qq unzip)"
run "${SSH[@]}" "$HOST" "unzip -oq /tmp/$SML_SMOD -d $MODS/SML && \
                         unzip -oq /tmp/$FRM_SMOD -d $FRMDIR && \
                         chown -R pterodactyl:pterodactyl $MODS && \
                         rm -f /tmp/$SML_SMOD /tmp/$FRM_SMOD && \
                         ls -la $MODS"
echo "→ First restart: SML loads FRM and registers its settings"
restart_server

stop_server
echo "→ Enabling web server autostart (port 8080, only reachable in the container network)"
# Two pitfalls: (1) At startup the game discards unknown keys from the INI — only after
# FRM has been loaded once is the option registered and the entry sticks. (2) On
# shutdown the game rewrites the INI; so only edit it while the server is stopped.
run "${SSH[@]}" "$HOST" "grep -q 'uWS.Autostart' $INI || \
  sed -i 's|^mIntValues=()\$|mIntValues=((\"FicsitRemoteMonitoring.Server.uWS.Autostart\", 1),(\"FicsitRemoteMonitoring.Server.uWS.Port\", 8080))|' $INI; \
  chown pterodactyl:pterodactyl $INI; grep -n mIntValues $INI"

echo "→ Second start: with the web server running"
start_server

echo "→ Checking FRM endpoints (FRM_URL must point to port 8080 of the server, via SSH tunnel if needed)"
run python3 "$HERE/frm.py" probe
