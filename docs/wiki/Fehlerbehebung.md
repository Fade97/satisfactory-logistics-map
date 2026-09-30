# Fehlerbehebung

Erster Blick immer in das Log: `docker compose logs --tail 50` (ohne Docker: `journalctl -u satisfactory-map -n 50`).

## „Noch kein Spielstand“ bleibt stehen
Die Meldung darunter nennt den Grund:

| Meldung | Lösung |
|---|---|
| `kein Save (*.sav) in Ordner /data/saves` | `SAVE_SOURCE` ist leer oder zeigt auf einen leeren Ordner. Quelle eintragen, siehe [Save-Quelle einrichten](Save-Quelle-einrichten). |
| `Ordner /saves fehlt` | Volume in `docker-compose.yml` nicht eingehängt oder Pfad falsch. |
| `Server-API PasswordLogin: 401 wrong_password` | Admin-Passwort falsch. |
| `Server-API … nicht erreichbar` | Adresse/Port falsch oder Firewall. Test mit dem `curl`-Befehl auf [Save-Quelle einrichten](Save-Quelle-einrichten#a-server-api-empfohlen). Port ist der **Spielport** (TCP), Standard 7777. |
| `Server-API … 403 insufficient_scope` | Token ohne Admin-Rechte. Admin-Passwort statt Token nehmen. |
| `SFTP …: Authentication failed` | Benutzer/Passwort; bei Pterodactyl Benutzer im Format `name.serverid`. |
| `SFTP …: [Errno 2] No such file` | Pfad falsch. Mit einem SFTP-Programm nachsehen, wo die `.sav` liegen. |
| `FTP …: 530 Login incorrect` | FTP-Zugangsdaten aus dem Hoster-Panel prüfen. |
| `Save nicht lesbar: …` | Save aus einer nicht unterstützten Spielversion oder beschädigt. Bitte ein [Issue](https://github.com/Fade97/satisfactory-logistikkarte/issues) mit der Meldung anlegen. |

## Oben rechts steht immer „Save vor N min“
Normal ohne [FRM](Live-Daten-mit-FRM). Mit FRM: der Mauszeiger auf dem Kasten zeigt den Fehler. Häufig:
- `FRM nicht eingerichtet` — `FRM_URL` fehlt.
- `Connection refused` / Timeout — Port 8080 nicht erreichbar (Container-Netz? Firewall?).
- `World not ready` (503) — FRM hängt nach dem Session-Neustart; Server neu starten, siehe [Live-Daten mit FRM](Live-Daten-mit-FRM#bekanntes-problem-world-not-ready-nach-dem-session-neustart).

## Spieler springen statt zu gleiten / „online unbekannt“
Ohne FRM stammen Positionen aus dem Autosave (alle ~5 min). Das ist erwartet.

## Die Karte zeigt einen alten Stand
- Satisfactory speichert nur alle 5 Minuten automatisch (Einstellung *Autosave Interval* am Server).
- **Server pausiert** ohne Spieler — dann entstehen keine neuen Saves.
- Browser: einmal neu laden. Eine installierte App zeigt offline „offline · letzter Stand“.

## Notizen/Umbenennen: „Passwort falsch“
`MAP_PIN_PASSWORD` in `.env` prüfen und Dienst mit `docker compose up -d` neu laden. Nach 10 Fehlversuchen ist die
IP 10 Minuten gesperrt.

## 3D-Ansicht bleibt leer
Braucht WebGL. Im Browser Hardwarebeschleunigung einschalten. Auf sehr alten Handys kann der Grafikspeicher knapp sein —
dann erscheint ein Hinweis statt der Ansicht.

## Hohe Speicher- oder CPU-Last
Beim Einlesen eines großen Saves (1000+ Maschinen) braucht der Dienst kurz ~1 GB RAM und einige Sekunden CPU, danach
kaum noch etwas. Läuft er dauerhaft hoch, bitte Log und Save-Größe in einem Issue melden.

## Nach einem Update ist die Seite kaputt
Einmal hart neu laden (Strg+Umschalt+R). Installierte Apps: App schließen und neu öffnen.
