# Installation ohne Docker

Für Linux-Server, auf denen du lieber direkt mit Python arbeitest.

## Voraussetzungen
- Python 3.11 oder neuer (`python3 --version`)
- Node.js 20+ und [pnpm](https://pnpm.io/installation) — nur zum Bauen der Website
- git

## Installieren
```sh
git clone https://github.com/Fade97/satisfactory-logistikkarte.git
cd satisfactory-logistikkarte
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd frontend && pnpm install && pnpm run build && cd ..
```

## Starten
```sh
SAVE_SOURCE=/pfad/zu/SaveGames/server .venv/bin/python mapd.py --port 8050
```
Optionen: `--port` (Standard 8050), `--bind` (Standard `0.0.0.0`, für nur-lokal `127.0.0.1`),
`--no-fetch` (nur das zuletzt geholte `saves/latest.sav` lesen, nichts holen — praktisch zum Testen).

## Als systemd-Dienst
`/etc/systemd/system/satisfactory-map.service` (Pfade anpassen):
```ini
[Unit]
Description=Satisfactory-Logistikkarte
After=network-online.target

[Service]
User=satisfactory
WorkingDirectory=/opt/satisfactory-logistikkarte
EnvironmentFile=/opt/satisfactory-logistikkarte/.env
ExecStart=/opt/satisfactory-logistikkarte/.venv/bin/python -u mapd.py --port 8050
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
```sh
sudo systemctl daemon-reload
sudo systemctl enable --now satisfactory-map
journalctl -u satisfactory-map -f
```
Die `.env` hat dasselbe Format wie für Docker (siehe `.env.example`). Ohne Root geht es auch als User-Dienst
unter `~/.config/systemd/user/` mit `systemctl --user` (dann `loginctl enable-linger <user>`, damit er ohne Anmeldung läuft).

## Wo die Daten liegen
| Ordner | Inhalt |
|---|---|
| `data/` (`MAP_DATA`) | `map.db` (Verlauf, Ereignisse, Notizen, Fabriknamen), `pin_password`, erzeugte Blueprints |
| `saves/` (`MAP_SAVES`) | `latest.sav` = zuletzt geholtes Save, `latest.stamp` = welches es war |

## Windows ohne Docker
Geht grundsätzlich genauso (PowerShell: `py -3 -m venv .venv`, `.venv\Scripts\python mapd.py`), ist aber nicht
getestet. Umgebungsvariablen dort mit `$env:SAVE_SOURCE="C:\…\SaveGames\server"` setzen.
