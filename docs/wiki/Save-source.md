# Save source

The map needs the current save (`.sav`). `SAVE_SOURCE` defines where it comes from. The map checks
**every minute** whether there is a newer save and only downloads it then. It always uses the **newest**
save — normally the last autosave (by default, Satisfactory saves every 5 minutes).

| Option | When to use | What you need |
|---|---|---|
| [Server API](#a-server-api-recommended) | almost always | address + admin password of the server |
| [SFTP](#b-sftp) | Pterodactyl, your own Linux server | SFTP access |
| [FTP/FTPS](#c-ftp--ftps) | rented servers from hosters | FTP access from the hoster panel |
| [Folder](#d-folder-on-the-same-machine) | the server runs on the same machine | path to the save folder |
| [By hand](#e-upload-by-hand) | for trying it out | a `.sav` file |

## A. Server API (recommended)
Every Satisfactory dedicated server (1.0 and later) has an HTTPS API on the **game port** (default 7777, TCP).
The map logs in with the admin password, queries the running session and downloads its newest save.
It does **not** create a new save.
```ini
SAVE_SOURCE=api://my-server.example:7777
SAVE_PASSWORD=admin-password
```
- The admin password is the one you set in the game ("Server Manager") when you first set up the server.
- Instead of the password you can use an API token: enter `server.GenerateAPIToken` in the server console and set `SAVE_TOKEN=…`.
- The server's certificate is self-signed — the map accepts it.
- Several sessions on the server? The map uses the **one currently running**.

**Check whether the server is reachable:**
```sh
curl -k -X POST https://my-server.example:7777/api/v1 -H 'Content-Type: application/json' \
     -d '{"function":"HealthCheck","data":{"ClientCustomData":""}}'
# → {"data":{"health":"healthy","serverCustomData":""}}
```

## B. SFTP
```ini
SAVE_SOURCE=sftp://user@host:22/path/to/SaveGames/server
SAVE_PASSWORD=password          # or:
SAVE_KEY=/run/secrets/id_ed25519
```
**Pterodactyl:** the SFTP details are in the panel under *Settings → SFTP Details*.
- Host/port: usually `panel.example:2022`
- User: `<panel-username>.<server-id>` (e.g. `player.1a2b3c4d`)
- Password: your panel password
- Path (relative to the server directory): `/.config/Epic/FactoryGame/Saved/SaveGames/server`
```ini
SAVE_SOURCE=sftp://player.1a2b3c4d@panel.example:2022/.config/Epic/FactoryGame/Saved/SaveGames/server
SAVE_PASSWORD=panel-password
```
**Your own Linux server (SteamCMD):** the default path is `~/.config/Epic/FactoryGame/Saved/SaveGames/server/` of the user
the server runs as.

Note: the SFTP server's host key is not verified. On a home network that is fine; over the internet, prefer
the server API.

## C. FTP / FTPS
Many hosters (e.g. G-Portal, Nitrado) provide FTP access. The details are in the hoster panel.
```ini
SAVE_SOURCE=ftps://user@ftp.hoster.example:21/FactoryGame/Saved/SaveGames/server
SAVE_PASSWORD=ftp-password
```
`ftps://` = encrypted (preferred), `ftp://` = unencrypted. To find the exact path, log in once with an FTP client
(e.g. FileZilla) and navigate to the `.sav` files.

## D. Folder on the same machine
```ini
SAVE_SOURCE=/saves
```
In `docker-compose.yml`, mount the real folder at `/saves` (see [Installation with Docker](Installation-with-Docker)).
Without Docker, give the path directly. Subfolders are searched too — handy on Windows, where saves are in
`%LOCALAPPDATA%\FactoryGame\Saved\SaveGames\<ID>\`.

| System | Typical save folder |
|---|---|
| Linux dedicated server | `~/.config/Epic/FactoryGame/Saved/SaveGames/server/` |
| Windows dedicated server | `%LOCALAPPDATA%\FactoryGame\Saved\SaveGames\server\` |
| Pterodactyl (Wings host) | `/var/lib/pterodactyl/volumes/<uuid>/.config/Epic/FactoryGame/Saved/SaveGames/server/` |

## E. Upload by hand
Leave `SAVE_SOURCE` empty and put a `.sav` into the data folder: with Docker
`docker compose cp MySave.sav map:/data/saves/`, without Docker into `saves/`.

## Several sessions
If saves of several worlds are in the same folder, narrow it down with `SAVE_PATTERN`:
```ini
SAVE_PATTERN=MyWorld_*.sav
```

## Passwords with special characters
Put passwords in `SAVE_PASSWORD` rather than in the URL. In the URL, characters such as `@ : / #` would have to be encoded
(`@` → `%40`).
