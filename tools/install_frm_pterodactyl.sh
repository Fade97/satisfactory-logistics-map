#!/usr/bin/env bash
# Installiert Satisfactory Mod Loader + FicsIt Remote Monitoring auf einem Pterodactyl-Gameserver
# (Root-SSH auf den Wings-Host) und startet ihn über die Pterodactyl-Client-API neu.
# --uninstall entfernt beides wieder. Anleitung und Fallen: docs/FRM.md.
#
#   SF_HOST=root@wings-host SF_KEY=~/.ssh/id_ed25519 PTERO_UUID=<server-uuid> PTERO_ENV=pfad/.env \
#     tools/install_frm_pterodactyl.sh [--dry-run|--uninstall]
#
# PTERO_ENV enthält PTERODACTYL_PANEL_URL und PTERODACTYL_CLIENT_API_KEY.
# Die .smod-Archive (LinuxServer) vorher von https://ficsit.app nach mods/ laden.
set -euo pipefail

HOST=${SF_HOST:?SF_HOST fehlt (root@wings-host)}
KEY=${SF_KEY:?SF_KEY fehlt (SSH-Schlüssel)}
UUID=${PTERO_UUID:?PTERO_UUID fehlt (volle Server-UUID aus dem Panel)}
API_PORT=${SF_API_PORT:-7777}
VOL=/var/lib/pterodactyl/volumes/$UUID
MODS=$VOL/FactoryGame/Mods
# FRM ist ein Game-Feature-Plugin (GameFeature=true in der .uplugin): liegt es direkt
# unter Mods/, lädt SML zwar die Binaries, das Weltmodul wird aber nie entdeckt und der
# Mod tut nichts. Game Features gehören nach Mods/GameFeatures/.
FRMDIR=$MODS/GameFeatures/FicsitRemoteMonitoring
INI=$VOL/FactoryGame/Saved/Config/LinuxServer/GameUserSettings.ini
HERE=$(cd "$(dirname "$0")/.." && pwd)
ENVFILE=${PTERO_ENV:?PTERO_ENV fehlt (.env mit Panel-URL und Client-API-Key)}
SSH=(ssh -i "$KEY" -o IdentitiesOnly=yes -o BatchMode=yes)

DRY=0; MODE=install
for a in "$@"; do
  case $a in --dry-run) DRY=1;; --uninstall) MODE=uninstall;; *) echo "unbekannt: $a"; exit 2;; esac
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
  echo "→ Server stoppen"
  power stop
  [ $DRY = 1 ] && return
  until [ "$(state)" = offline ]; do sleep 4; done
  echo "→ offline"
}

start_server() {
  echo "→ Server starten"
  power start
  [ $DRY = 1 ] && return
  for _ in $(seq 1 90); do
    sleep 5
    if curl -sk -m 5 -X POST "https://${HOST#*@}:$API_PORT/api/v1/" -H 'Content-Type: application/json' \
         -d '{"function":"HealthCheck","data":{"clientCustomData":""}}' 2>/dev/null | grep -q healthy; then
      echo "→ Server ist wieder da"; return
    fi
  done
  echo "!! Server meldet sich nicht — im Panel nachsehen"; exit 1
}

restart_server() { stop_server; start_server; }

if [ $MODE = uninstall ]; then
  echo "→ Mods entfernen"
  run "${SSH[@]}" "$HOST" "rm -rf $MODS/SML $MODS/GameFeatures"
  restart_server
  echo "Fertig — Server läuft wieder vanilla."
  exit 0
fi

for f in SML-3.12.0-LinuxServer.smod FRM-1.5.3-LinuxServer.smod; do
  [ -f "$HERE/mods/$f" ] || { echo "fehlt: mods/$f"; exit 1; }
done

echo "→ Mods-Verzeichnis anlegen"
run "${SSH[@]}" "$HOST" "mkdir -p $MODS/SML $FRMDIR"

echo "→ Archive hochladen"
run scp -i "$KEY" -o IdentitiesOnly=yes "$HERE/mods/SML-3.12.0-LinuxServer.smod" \
    "$HERE/mods/FRM-1.5.3-LinuxServer.smod" "$HOST:/tmp/"

echo "→ Entpacken (Mods liegen je in einem Ordner mit dem Plugin-Namen)"
run "${SSH[@]}" "$HOST" "command -v unzip >/dev/null || (apt-get update -qq && apt-get install -y -qq unzip)"
run "${SSH[@]}" "$HOST" "unzip -oq /tmp/SML-3.12.0-LinuxServer.smod -d $MODS/SML && \
                         unzip -oq /tmp/FRM-1.5.3-LinuxServer.smod -d $FRMDIR && \
                         chown -R pterodactyl:pterodactyl $MODS && \
                         rm -f /tmp/SML-3.12.0-LinuxServer.smod /tmp/FRM-1.5.3-LinuxServer.smod && \
                         ls -la $MODS"
echo "→ Erster Neustart: SML lädt FRM und registriert dessen Einstellungen"
restart_server

stop_server
echo "→ Webserver-Autostart setzen (Port 8080, nur im Container-Netz erreichbar)"
# Zwei Fallen: (1) Das Spiel verwirft beim Start unbekannte Schlüssel aus der INI — erst nachdem
# FRM einmal geladen war, ist die Option registriert und der Eintrag bleibt stehen. (2) Beim
# Herunterfahren schreibt das Spiel die INI neu; deshalb nur im gestoppten Zustand editieren.
run "${SSH[@]}" "$HOST" "grep -q 'uWS.Autostart' $INI || \
  sed -i 's|^mIntValues=()\$|mIntValues=((\"FicsitRemoteMonitoring.Server.uWS.Autostart\", 1),(\"FicsitRemoteMonitoring.Server.uWS.Port\", 8080))|' $INI; \
  chown pterodactyl:pterodactyl $INI; grep -n mIntValues $INI"

echo "→ Zweiter Start: mit laufendem Webserver"
start_server

echo "→ FRM-Endpunkte prüfen (FRM_URL muss auf Port 8080 des Servers zeigen, ggf. per SSH-Tunnel)"
run python3 "$HERE/frm.py" probe
