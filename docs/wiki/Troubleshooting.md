# Troubleshooting

Always check the log first: `docker compose logs --tail 50` (without Docker: `journalctl -u satisfactory-map -n 50`).

## "No save yet" does not go away
The message below it gives the reason:

| Message | Solution |
|---|---|
| `no save (*.sav) in folder /data/saves` | `SAVE_SOURCE` is empty or points to an empty folder. Set a source, see [Save source](Save-source). |
| `folder /saves not found` | Volume not mounted in `docker-compose.yml` or wrong path. |
| `Server API PasswordLogin: 401 wrong_password` | Wrong admin password. |
| `Server API … not reachable` | Wrong address/port or a firewall. Test with the `curl` command on [Save source](Save-source#a-server-api-recommended). The port is the **game port** (TCP), default 7777. |
| `Server API … 403 insufficient_scope` | Token without admin rights. Use the admin password instead of the token. |
| `SFTP …: Authentication failed` | User/password; on Pterodactyl the user has the format `name.serverid`. |
| `SFTP …: [Errno 2] No such file` | Wrong path. Check with an SFTP client where the `.sav` files are. |
| `FTP …: 530 Login incorrect` | Check the FTP credentials from the hoster panel. |
| `Save not readable: …` | Save from an unsupported game version, or corrupted. Please open an [issue](https://github.com/Fade97/satisfactory-logistics-map/issues) with the message. |

## The top right always shows "save N min ago"
Normal without [FRM](Live-data-with-FRM). With FRM: hovering over the box shows the error. Common ones:
- `FRM not configured` — `FRM_URL` is missing.
- `Connection refused` / timeout — port 8080 not reachable (container network? firewall?).
- `World not ready` (503) — FRM hangs after the session restart; restart the server, see [Live data with FRM](Live-data-with-FRM#known-issue-world-not-ready-after-a-session-restart).

## Players jump instead of moving smoothly / "online unknown"
Without FRM, positions come from the autosave (every ~5 min). This is expected.

## The map shows an old state
- Satisfactory only autosaves every 5 minutes (server setting *Autosave Interval*).
- The **server pauses** when no players are online — then no new saves are created.
- Browser: reload once. An installed app shows "offline · last known state" when offline.

## Notes/renaming: "Wrong password"
Check `MAP_PIN_PASSWORD` in `.env` and reload the service with `docker compose up -d`. After 10 failed attempts the
IP is blocked for 10 minutes.

## 3D view stays empty
Requires WebGL. Enable hardware acceleration in the browser. On very old phones, graphics memory can run short —
then a notice appears instead of the view.

## High memory or CPU usage
While reading a large save (1000+ machines), the service briefly needs ~1 GB of RAM and a few seconds of CPU, and
hardly anything afterwards. If it stays high, please report the log and the save size in an issue.

## The page is broken after an update
Do a hard reload once (Ctrl+Shift+R). Installed apps: close and reopen the app.
