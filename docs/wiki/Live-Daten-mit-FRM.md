# Live-Daten mit FRM (optional)

Ohne Mod zeigt die Karte den Stand des **letzten Autosaves** (meist 5 Minuten alt). Mit dem Mod
[FicsIt Remote Monitoring](https://ficsit.app/mod/FicsitRemoteMonitoring) (FRM) wird sie live:

| | nur Save | mit FRM |
|---|---|---|
| Spieler, Züge, LKW | alle ~5 min, springen | alle 5 s, gleiten flüssig |
| „online“ / Folge-Modus | unbekannt | ja |
| Maschinen, Strom, Warenbilanz | alle ~5 min | jede Minute |
| Stationen, Fahrpläne, Bänder, Fundamente | aus dem Save | aus dem Save |
| Zug-Durchsatz, Rundenzeiten | – | ja |

Oben rechts steht immer ehrlich, woher die Daten kommen: **live** (grün) oder **Save vor N min** (gelb).

## ⚠ Vorher wissen
- **Alle Mitspieler brauchen dieselben Mods** (Satisfactory Mod Loader + FRM, gleiche Version). Ohne sie kommt man
  nicht mehr auf den Server — im Serverlog steht dann nicht einmal ein Verbindungsversuch. FRMs Beschreibung sagt zwar
  „server-only“, in der Praxis stimmt das nicht.
- Mods können nach Spiel-Updates kaputtgehen, bis sie aktualisiert sind. Dann einfach `FRM_URL` leeren — die Karte
  läuft aus dem Save weiter.

## Einrichten
1. **Clients:** Jeder Spieler installiert den [Satisfactory Mod Manager](https://smm.ficsit.app/) und darin
   *FicsIt Remote Monitoring* (bringt den Mod Loader mit).
2. **Server:** SML + FRM in der Variante für den Server (*LinuxServer* / *WindowsServer*) von https://ficsit.app
   herunterladen und installieren:
   - `.smod`-Dateien sind ZIP-Archive. SML nach `FactoryGame/Mods/SML/` entpacken,
     FRM nach **`FactoryGame/Mods/GameFeatures/FicsitRemoteMonitoring/`** (nicht direkt unter `Mods/` — sonst lädt
     der Mod, tut aber nichts).
   - Server einmal starten und wieder **stoppen**.
   - In `FactoryGame/Saved/Config/LinuxServer/GameUserSettings.ini` (Windows: `WindowsServer`) die Zeile
     `mIntValues=()` ersetzen durch
     `mIntValues=(("FicsitRemoteMonitoring.Server.uWS.Autostart", 1),("FicsitRemoteMonitoring.Server.uWS.Port", 8080))`
     — nur bei gestopptem Server editieren, sonst überschreibt das Spiel die Datei.
   - Server starten. `LogHttpServer: Port 8080 unavailable` im Log ist normal.
   - **Pterodactyl:** das Skript `tools/install_frm_pterodactyl.sh` erledigt all das per SSH auf dem Wings-Host.
3. **Karte:** in `.env` `FRM_URL=http://<server>:8080` setzen und `docker compose up -d`.
4. **Prüfen:** `curl http://<server>:8080/getSessionInfo` liefert JSON. Ohne Docker: `FRM_URL=… python3 frm.py probe`.

## Port 8080 nur intern
Der FRM-Port gehört **nicht** ins Internet — die Karte fragt ihn ab, Besucher brauchen ihn nicht. Liegt er nur in einem
Container-Netz (Pterodactyl), hilft ein SSH-Tunnel auf dem Rechner der Karte:
```sh
ssh -N -L 18080:<container-ip>:8080 root@wings-host
```
und `FRM_URL=http://127.0.0.1:18080` (bei Docker: `http://host.docker.internal:18080` mit
`extra_hosts: ["host.docker.internal:host-gateway"]` in `docker-compose.yml`).

## Bekanntes Problem: „World not ready“ nach dem Session-Neustart
Der Dedicated Server lädt die Session regelmäßig neu (*Session Restart Time*, standardmäßig nachts). Danach antwortet
FRM manchmal dauerhaft mit `Blocked API call: World not ready.` Die Karte zeigt dann „Save vor N min“ und läuft aus
dem Save weiter. **Abhilfe:** den Serverprozess kurz nach dem Session-Neustart einmal komplett neu starten
(z. B. Pterodactyl-Zeitplan „Power Action: restart“, nur wenn online). Technische Details: `docs/frm-issue-draft.md`.
