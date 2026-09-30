# Installation with Docker

The recommended way. You need [Docker](https://docs.docker.com/engine/install/) with the Compose plugin
(`docker compose version` must work). On Windows/macOS: Docker Desktop.

## 1. Get the repository
```sh
git clone https://github.com/Fade97/satisfactory-logistics-map.git
cd satisfactory-logistics-map
```
Without git: on GitHub, choose **Code → Download ZIP** and unpack it.

## 2. Create the settings
```sh
cp .env.example .env
```
Open `.env` in an editor and choose **one** save source. The server API is the easiest:
```ini
SAVE_SOURCE=api://my-server.example:7777
SAVE_PASSWORD=your-admin-password
MAP_PIN_PASSWORD=a-password-for-other-players
```
[Save source](Save-source) explains all options (SFTP, FTP, folder); all variables are listed under
[Configuration](Configuration).

## 3. Start
```sh
docker compose up -d
```
On the first start, Docker builds the image (2–5 minutes, seconds afterwards). Then open http://localhost:8050 —
or `http://<machine-IP>:8050` from another device on your home network.

As long as no save has been loaded, the page shows **"No save yet"** at the top, together with the reason
(e.g. wrong password). The service retries every minute — after fixing `.env`, running
`docker compose up -d` is enough (it reloads the settings).

## 4. Check
```sh
docker compose logs -f
```
It should look like this:
```
12:00:01 Save source: api://my-server.example:7777 · FRM: off
12:00:01 fetching save MyWorld_autosave_1.sav …
12:00:09 Save MyWorld_autosave_1.sav read (7.8s): 1161 machines, 121 stations
12:00:09 Logistics map on http://0.0.0.0:8050
```

## Different port
Change the left number in `docker-compose.yml`, e.g. `"8080:8050"` → map on port 8080.

## Mount the save folder directly
If the game server runs on the same machine, enable the volume line in `docker-compose.yml`:
```yaml
    volumes:
      - map-data:/data
      - /home/steam/.config/Epic/FactoryGame/Saved/SaveGames/server:/saves:ro
```
and set `SAVE_SOURCE=/saves` in `.env`. `:ro` = read-only; the map cannot change anything there.

## SSH key for SFTP
```yaml
    volumes:
      - map-data:/data
      - ./id_ed25519:/run/secrets/id_ed25519:ro
```
and `SAVE_KEY=/run/secrets/id_ed25519`. The container runs as a user with UID 1000; the key file must be readable
for that user (`chmod 644` on the copy or `chown 1000`).

## Next steps
- [Live data with FRM](Live-data-with-FRM) for real-time positions
- [Public access](Public-access) for players outside your home network
- [Updating and backups](Updating-and-backups)
