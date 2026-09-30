# Configuration

Everything is configured through environment variables — with Docker in `.env`, otherwise in the systemd service or in the shell.

## Save source
| Variable | Default | Meaning |
|---|---|---|
| `SAVE_SOURCE` | empty | `api://host:7777`, `sftp://user@host:port/path`, `ftp://…`, `ftps://…`, folder path; empty = `saves/` or `/data/saves` — see [Save source](Save-source) |
| `SAVE_PASSWORD` | – | admin password (API) or SFTP/FTP password |
| `SAVE_TOKEN` | – | API token instead of a password (`server.GenerateAPIToken`) |
| `SAVE_KEY` | – | path to a private SSH key (SFTP) |
| `SAVE_PATTERN` | `*.sav` | only matching files, e.g. `MyWorld_*.sav` |

## Live data
| Variable | Default | Meaning |
|---|---|---|
| `FRM_URL` | empty = off | address of FicsIt Remote Monitoring, e.g. `http://server:8080` |
| `FRM_TIMEOUT` | `8` | seconds per request |

## Map
| Variable | Default | Meaning |
|---|---|---|
| `MAP_PIN_PASSWORD` | empty = writing off | shared password for notes, factory names, factory status. Alternatively the file `data/pin_password` |
| `MAP_TITLE` | session name | name in the top left and in the browser tab |
| `MAP_DATA` | `data/` · Docker: `/data` | database, password file, generated blueprints |
| `MAP_SAVES` | `saves/` · Docker: `/data/saves` | storage for the last fetched save |
| `MAP_DB` | `$MAP_DATA/map.db` | path of the SQLite database |
| `TZ` | Docker: `Europe/Berlin` | time zone for times of day |

## Intervals (fixed)
| What | Interval |
|---|---|
| Live positions (FRM) | 5 s |
| Machines/power (FRM) | 60 s |
| Check for a new save | 60 s |
| Time travel snapshot | 60 s (only while the game is being played) |
| History | minute values 48 h → hourly averages 90 days → daily values forever |
| Player trails | 2 h |
| Events | 30 days |

When the server is paused (nobody online), the map records nothing — charts then show a gap instead of a zero line.
