# Installation mit Docker

Der empfohlene Weg. Du brauchst [Docker](https://docs.docker.com/engine/install/) mit dem Compose-Plugin
(`docker compose version` muss funktionieren). Unter Windows/macOS: Docker Desktop.

## 1. Repository holen
```sh
git clone https://github.com/Fade97/satisfactory-logistikkarte.git
cd satisfactory-logistikkarte
```
Ohne git: auf GitHub **Code → Download ZIP** und entpacken.

## 2. Einstellungen anlegen
```sh
cp .env.example .env
```
Öffne `.env` in einem Editor und wähle **eine** Save-Quelle. Am einfachsten ist die Server-API:
```ini
SAVE_SOURCE=api://mein-server.example:7777
SAVE_PASSWORD=dein-admin-passwort
MAP_PIN_PASSWORD=ein-passwort-fuer-mitspieler
```
Alle Varianten (SFTP, FTP, Ordner) erklärt [Save-Quelle einrichten](Save-Quelle-einrichten), alle Variablen stehen
unter [Konfiguration](Konfiguration).

## 3. Starten
```sh
docker compose up -d
```
Beim ersten Start baut Docker das Image (2–5 Minuten, danach Sekunden). Dann http://localhost:8050 öffnen —
oder `http://<IP-des-Rechners>:8050` von einem anderen Gerät im Heimnetz.

Solange noch kein Spielstand geladen ist, zeigt die Seite oben **„Noch kein Spielstand“** mit dem Grund
(z. B. falsches Passwort). Der Dienst versucht es jede Minute erneut — nach einer Korrektur in `.env` genügt
`docker compose up -d` (lädt die Einstellungen neu).

## 4. Kontrollieren
```sh
docker compose logs -f
```
So sollte es aussehen:
```
12:00:01 Save-Quelle: api://mein-server.example:7777 · FRM: aus
12:00:01 lade Save MeineWelt_autosave_1.sav …
12:00:09 Save MeineWelt_autosave_1.sav gelesen (7.8s): 1161 Maschinen, 121 Stationen
12:00:09 Logistikkarte auf http://0.0.0.0:8050
```

## Anderer Port
In `docker-compose.yml` die linke Zahl ändern, z. B. `"8080:8050"` → Karte auf Port 8080.

## Save-Ordner direkt einhängen
Läuft der Gameserver auf demselben Rechner, in `docker-compose.yml` die Volume-Zeile aktivieren:
```yaml
    volumes:
      - map-data:/data
      - /home/steam/.config/Epic/FactoryGame/Saved/SaveGames/server:/saves:ro
```
und in `.env` `SAVE_SOURCE=/saves` setzen. `:ro` = nur lesen, die Karte kann dort nichts verändern.

## SSH-Schlüssel für SFTP
```yaml
    volumes:
      - map-data:/data
      - ./id_ed25519:/run/secrets/id_ed25519:ro
```
und `SAVE_KEY=/run/secrets/id_ed25519`. Der Container läuft als Benutzer mit UID 1000; die Schlüsseldatei muss für
ihn lesbar sein (`chmod 644` auf der Kopie oder `chown 1000`).

## Weiter
- [Live-Daten mit FRM](Live-Daten-mit-FRM) für Echtzeit-Positionen
- [Öffentlich erreichbar machen](Oeffentlich-erreichbar-machen) für Mitspieler außerhalb des Heimnetzes
- [Aktualisieren und Sichern](Aktualisieren-und-Sichern)
