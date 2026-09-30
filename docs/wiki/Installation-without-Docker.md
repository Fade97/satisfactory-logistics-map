# Installation without Docker

For Linux servers where you prefer to work with Python directly.

## Requirements
- Python 3.11 or newer (`python3 --version`)
- Node.js 20+ and [pnpm](https://pnpm.io/installation) — only for building the website
- git

## Install
```sh
git clone https://github.com/Fade97/satisfactory-logistics-map.git
cd satisfactory-logistics-map
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd frontend && pnpm install && pnpm run build && cd ..
```

## Start
```sh
SAVE_SOURCE=/path/to/SaveGames/server .venv/bin/python mapd.py --port 8050
```
Options: `--port` (default 8050), `--bind` (default `0.0.0.0`; `127.0.0.1` for local only),
`--no-fetch` (only read the last fetched `saves/latest.sav`, fetch nothing — handy for testing).

## As a systemd service
`/etc/systemd/system/satisfactory-map.service` (adjust the paths):
```ini
[Unit]
Description=Satisfactory Logistics Map
After=network-online.target

[Service]
User=satisfactory
WorkingDirectory=/opt/satisfactory-logistics-map
EnvironmentFile=/opt/satisfactory-logistics-map/.env
ExecStart=/opt/satisfactory-logistics-map/.venv/bin/python -u mapd.py --port 8050
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
The `.env` has the same format as for Docker (see `.env.example`). Without root, it also works as a user service
under `~/.config/systemd/user/` with `systemctl --user` (then run `loginctl enable-linger <user>` so it runs without a login).

## Where the data lives
| Folder | Contents |
|---|---|
| `data/` (`MAP_DATA`) | `map.db` (history, events, notes, factory names), `pin_password`, generated blueprints |
| `saves/` (`MAP_SAVES`) | `latest.sav` = last fetched save, `latest.stamp` = which one it was |

## Windows without Docker
Works the same way in principle (PowerShell: `py -3 -m venv .venv`, `.venv\Scripts\python mapd.py`), but is not
tested. Set environment variables there with `$env:SAVE_SOURCE="C:\…\SaveGames\server"`.
