# Save-Quelle einrichten

Die Karte braucht den aktuellen Spielstand (`.sav`). Woher er kommt, legt `SAVE_SOURCE` fest. Die Karte prüft
**jede Minute**, ob es ein neueres Save gibt, und lädt es nur dann herunter. Genommen wird immer das **jüngste**
Save — normalerweise das letzte Autosave (Satisfactory speichert standardmäßig alle 5 Minuten).

| Variante | Wann nehmen | Was du brauchst |
|---|---|---|
| [Server-API](#a-server-api-empfohlen) | fast immer | Adresse + Admin-Passwort des Servers |
| [SFTP](#b-sftp) | Pterodactyl, eigener Linux-Server | SFTP-Zugang |
| [FTP/FTPS](#c-ftp--ftps) | gemietete Server bei Hostern | FTP-Zugang aus dem Hoster-Panel |
| [Ordner](#d-ordner-auf-demselben-rechner) | Server läuft auf demselben Rechner | Pfad zum Save-Ordner |
| [Von Hand](#e-von-hand-hochladen) | zum Ausprobieren | eine `.sav`-Datei |

## A. Server-API (empfohlen)
Jeder Satisfactory Dedicated Server (ab 1.0) hat eine HTTPS-API auf dem **Spielport** (Standard 7777, TCP).
Die Karte meldet sich mit dem Admin-Passwort an, fragt die laufende Session ab und lädt deren jüngstes Save
herunter. Es wird **kein** neues Save angelegt.
```ini
SAVE_SOURCE=api://mein-server.example:7777
SAVE_PASSWORD=admin-passwort
```
- Das Admin-Passwort ist das, das du beim ersten Einrichten des Servers im Spiel („Server Manager“) vergeben hast.
- Statt Passwort geht ein API-Token: in der Serverkonsole `server.GenerateAPIToken` eingeben und `SAVE_TOKEN=…` setzen.
- Das Zertifikat des Servers ist selbstsigniert — die Karte akzeptiert es.
- Mehrere Sessions auf dem Server? Die Karte nimmt die **gerade laufende**.

**Prüfen, ob der Server erreichbar ist:**
```sh
curl -k -X POST https://mein-server.example:7777/api/v1 -H 'Content-Type: application/json' \
     -d '{"function":"HealthCheck","data":{"ClientCustomData":""}}'
# → {"data":{"health":"healthy","serverCustomData":""}}
```

## B. SFTP
```ini
SAVE_SOURCE=sftp://benutzer@host:22/pfad/zum/SaveGames/server
SAVE_PASSWORD=passwort          # oder:
SAVE_KEY=/run/secrets/id_ed25519
```
**Pterodactyl:** SFTP-Daten stehen im Panel unter *Settings → SFTP Details*.
- Host/Port: meist `panel.example:2022`
- Benutzer: `<panel-benutzername>.<server-id>` (z. B. `spieler.1a2b3c4d`)
- Passwort: dein Panel-Passwort
- Pfad (relativ zum Server-Verzeichnis): `/.config/Epic/FactoryGame/Saved/SaveGames/server`
```ini
SAVE_SOURCE=sftp://spieler.1a2b3c4d@panel.example:2022/.config/Epic/FactoryGame/Saved/SaveGames/server
SAVE_PASSWORD=panel-passwort
```
**Eigener Linux-Server (SteamCMD):** Standardpfad ist `~/.config/Epic/FactoryGame/Saved/SaveGames/server/` des Benutzers,
unter dem der Server läuft.

Hinweis: Der Host-Schlüssel des SFTP-Servers wird nicht geprüft. Im Heimnetz unkritisch, über das Internet besser
die Server-API nehmen.

## C. FTP / FTPS
Viele Hoster (z. B. G-Portal, Nitrado) geben FTP-Zugang. Die Daten stehen im Hoster-Panel.
```ini
SAVE_SOURCE=ftps://benutzer@ftp.hoster.example:21/FactoryGame/Saved/SaveGames/server
SAVE_PASSWORD=ftp-passwort
```
`ftps://` = verschlüsselt (bevorzugt), `ftp://` = unverschlüsselt. Den genauen Pfad siehst du, wenn du dich einmal mit
einem FTP-Programm (z. B. FileZilla) anmeldest und zu den `.sav`-Dateien navigierst.

## D. Ordner auf demselben Rechner
```ini
SAVE_SOURCE=/saves
```
In `docker-compose.yml` den echten Ordner nach `/saves` einhängen (siehe [Installation mit Docker](Installation-mit-Docker)).
Ohne Docker direkt den Pfad angeben. Unterordner werden mit durchsucht — praktisch unter Windows, wo Saves in
`%LOCALAPPDATA%\FactoryGame\Saved\SaveGames\<ID>\` liegen.

| System | Typischer Save-Ordner |
|---|---|
| Linux Dedicated Server | `~/.config/Epic/FactoryGame/Saved/SaveGames/server/` |
| Windows Dedicated Server | `%LOCALAPPDATA%\FactoryGame\Saved\SaveGames\server\` |
| Pterodactyl (Wings-Host) | `/var/lib/pterodactyl/volumes/<uuid>/.config/Epic/FactoryGame/Saved/SaveGames/server/` |

## E. Von Hand hochladen
`SAVE_SOURCE` leer lassen und eine `.sav` in den Datenordner legen: bei Docker
`docker compose cp MeinSave.sav map:/data/saves/`, ohne Docker nach `saves/`.

## Mehrere Sessions
Liegen Saves mehrerer Welten im selben Ordner, grenzt `SAVE_PATTERN` ein:
```ini
SAVE_PATTERN=MeineWelt_*.sav
```

## Passwörter mit Sonderzeichen
Passwörter besser in `SAVE_PASSWORD` statt in die URL schreiben. In der URL müssten Zeichen wie `@ : / #` kodiert werden
(`@` → `%40`).
