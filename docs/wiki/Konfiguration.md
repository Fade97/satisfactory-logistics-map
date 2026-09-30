# Konfiguration

Alles wird über Umgebungsvariablen eingestellt — bei Docker in `.env`, sonst im systemd-Dienst oder in der Shell.

## Save-Quelle
| Variable | Standard | Bedeutung |
|---|---|---|
| `SAVE_SOURCE` | leer | `api://host:7777`, `sftp://user@host:port/pfad`, `ftp://…`, `ftps://…`, Ordnerpfad; leer = `saves/` bzw. `/data/saves` — siehe [Save-Quelle einrichten](Save-Quelle-einrichten) |
| `SAVE_PASSWORD` | – | Admin-Passwort (API) bzw. SFTP/FTP-Passwort |
| `SAVE_TOKEN` | – | API-Token statt Passwort (`server.GenerateAPIToken`) |
| `SAVE_KEY` | – | Pfad zu einem privaten SSH-Schlüssel (SFTP) |
| `SAVE_PATTERN` | `*.sav` | nur passende Dateien, z. B. `MeineWelt_*.sav` |

## Live-Daten
| Variable | Standard | Bedeutung |
|---|---|---|
| `FRM_URL` | leer = aus | Adresse von FicsIt Remote Monitoring, z. B. `http://server:8080` |
| `FRM_TIMEOUT` | `8` | Sekunden je Anfrage |

## Karte
| Variable | Standard | Bedeutung |
|---|---|---|
| `MAP_PIN_PASSWORD` | leer = Schreiben aus | gemeinsames Passwort für Notizen, Fabriknamen, Fabrikstatus. Alternativ Datei `data/pin_password` |
| `MAP_TITLE` | Sessionname | Name oben links und im Browser-Tab |
| `MAP_DATA` | `data/` · Docker: `/data` | Datenbank, Passwortdatei, erzeugte Blueprints |
| `MAP_SAVES` | `saves/` · Docker: `/data/saves` | Ablage des zuletzt geholten Saves |
| `MAP_DB` | `$MAP_DATA/map.db` | Pfad der SQLite-Datenbank |
| `TZ` | Docker: `Europe/Berlin` | Zeitzone für Uhrzeiten |

## Takte (fest)
| Was | Takt |
|---|---|
| Live-Positionen (FRM) | 5 s |
| Maschinen/Strom (FRM) | 60 s |
| Neues Save prüfen | 60 s |
| Zeitreise-Bild | 60 s (nur während gespielt wird) |
| Verlauf | Minutenwerte 48 h → Stundenmittel 90 Tage → Tageswerte für immer |
| Spielerspuren | 2 h |
| Ereignisse | 30 Tage |

Pausiert der Server (niemand online), zeichnet die Karte nichts auf — Diagramme zeigen dann eine Lücke statt einer Nulllinie.
