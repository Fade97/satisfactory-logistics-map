# Live-Daten mit FicsIt Remote Monitoring (optional)

Ohne Mod zeigt die Karte den Stand des letzten Saves (Autosave-Takt, meist 5 min). Mit dem Mod
**FicsIt Remote Monitoring** (FRM, getestet mit FRM 1.5.3 + SML 3.12.0) kommen Spieler, Fahrzeuge,
Maschinen und Strom alle 5 s bzw. 60 s. FRM liefert per HTTP:

| Endpunkt | Genutzt für |
|---|---|
| `getPlayer` | Spielername, Position, **Online-Flag**, HP, Tempo, Inventar |
| `getTrains` / `getTruck` | Fahrzeugpositionen, Tempo, Status, Ladung |
| `getTruckStation` / `getTrainStation` | Aktivität (Idle/Transferring), Durchsatz, aktueller Pufferinhalt |
| `getSessionInfo` | Spielzeit, Tag, **Pausiert-Status** (Server pausiert ohne Spieler) |

Dazu `getFactory`/`getExtractor` (Maschinen), `getPower` (Stromnetze) und die Netzgeometrie. Stationsstruktur und
Be-/Entladerichtung kommen weiterhin aus dem Save — FRMs `LoadMode` ist die momentane *Aktivität*, nicht die Einstellung.

## Einrichten
1. SML und FRM (Variante *LinuxServer* bzw. *WindowsServer*) von https://ficsit.app auf den Server bringen —
   bei Pterodactyl hilft `tools/install_frm_pterodactyl.sh`, sonst per Hand (Fallen unten).
2. Alle Mitspieler installieren dieselben Mods im **Satisfactory Mod Manager** (siehe letzte Falle).
3. Der FRM-Webserver lauscht auf Port 8080 des Servers. `FRM_URL=http://server:8080` setzen. Liegt der Port nur in
   einem Container-Netz (Pterodactyl), einen SSH-Tunnel davorsetzen oder im Panel eine Allocation freigeben.
   Den Port **nicht öffentlich** freigeben — die Karte fragt ihn ab, Besucher brauchen ihn nicht.
4. Prüfen: `FRM_URL=… python3 frm.py probe` zeigt, welche Endpunkte antworten.

## Fallen
- FRM ist ein **Game-Feature-Plugin** (`GameFeature: true`). Liegt es unter `FactoryGame/Mods/<Name>/`,
  lädt SML zwar die Binaries und meldet die Version, das Weltmodul wird aber nie entdeckt und der Mod
  tut *nichts* — kein Log, keine Endpunkte. Richtig ist `FactoryGame/Mods/GameFeatures/<Name>/`.
- Die Konfiguration steht in `FactoryGame/Saved/Config/LinuxServer/GameUserSettings.ini` als
  `mIntValues=(("FicsitRemoteMonitoring.Server.uWS.Autostart", 1),…)`. Unbekannte Schlüssel wirft das
  Spiel beim Start weg — der Eintrag hält erst, nachdem FRM einmal geladen war. Und beim Herunterfahren
  schreibt das Spiel die Datei neu: nur im gestoppten Zustand editieren.
- `LogHttpServer: Port 8080 unavailable` im Log ist **kein** Fehler: uWS hat den Port bereits über IPv6
  belegt, danach scheitert UEs eigener HTTP-Server daran. Der Webserver läuft trotzdem.
- **Clients brauchen SML *und* FRM in derselben Version wie der Server.** FRMs eigene Beschreibung
  behauptet „can be a server-only mod … not required on the client" (`RequiredOnRemote: false` in der
  `.uplugin`), die SML-Doku sagt dagegen klar: *„client players must have the same mods installed as the
  server to be able to join."* In der Praxis gilt die SML-Aussage — ein Client mit SML, aber ohne FRM,
  kommt nicht rein und bricht schon vor dem Login-Request ab (im Serverlog taucht dann **gar nichts** auf;
  ein echter Versuch würde `LogNet: Login request … ?Name=…` und `Join succeeded:` schreiben).

## FRM hängt nach dem nächtlichen Session-Neustart
Der Dedicated Server lädt die Session regelmäßig neu (*Session Restart Time*), ohne den Prozess neu zu starten.
FRM behält dabei seinen Webserver-Thread mit der alten Welt und antwortet danach teils dauerhaft mit
`Blocked API call: World not ready.` (503). Belege: `docs/frm-issue-draft.md`. Abhilfe: den Server kurz nach dem
Session-Neustart einmal komplett neu starten (z. B. Pterodactyl-Zeitplan, „nur wenn online“). Bis dahin läuft die Karte aus dem Save.

## Spielerpositionen ohne Mod
Satisfactory hat **kein RCON**. Der Dedicated Server bietet eine HTTPS-API
(`https://server:7777/api/v1/`, selbstsigniert → `curl -k`), die aber **keine** Spielerdaten
außer `numConnectedPlayers` (in `QueryServerState`, admin-pflichtig) kennt. Nachweis: unbekannte
Funktionsnamen antworten `bad_function`, existierende ohne Token `insufficient_scope` — damit lässt
sich der Funktionsumfang ohne Zugangsdaten abklopfen; `GetPlayers`, `ListPlayers`,
`GetPlayerPositions`, `EnumeratePlayers` gibt es nicht.

Die Positionen stehen dafür im Save: jede `Char_Player_C` trägt `mCachedPlayerName`, die
Weltposition im Actor-Header und über `mSavedDrivenVehicle` das gerade gefahrene Fahrzeug.
Die Figur bleibt auch nach dem Abmelden stehen — „gerade online“ steht *nicht* im Save; die Karte zeigt ohne FRM
deshalb „online unbekannt“ und folgt niemandem automatisch.

Die API taugt aber als **Save-Quelle**: mit dem Admin-Passwort liefern `EnumerateSessions` + `DownloadSaveGame` das
jüngste Save, ohne ein neues anzulegen (`SAVE_SOURCE=api://server:7777`). `SaveGame` (erzwingt einen Speicherstand)
nutzt die Karte bewusst nicht.
