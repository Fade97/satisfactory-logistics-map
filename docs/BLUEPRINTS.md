# Blueprint-Werkzeuge

Neben der Karte enthält das Repo Werkzeuge, um Satisfactory-Blueprints (`.sbp` / `.sbpcfg`) byte-genau zu lesen,
zu erzeugen und zu prüfen. Stand: Spielversion `++FactoryGame+rel-main-anniversary-2026`, Build 502094,
Blueprint-Header-Version 2, Save-Version 60 (neues UE-5.4+-Property-Tag-Format — ältere Community-Parser passen nicht).

| Datei | Zweck |
|---|---|
| `sbp.py` | Parser/Writer für `.sbp`. `python3 sbp.py <ordner>` = Round-Trip-Test, `python3 sbp.py dump <datei.sbp> [full]` = Inhalt anzeigen. |
| `sav.py` | Reader für `.sav` (nur lesen): `load_index(pfad)` liefert alle Objekte als `name -> (header, rohdaten)`, `show(idx, name)` druckt Properties. |
| `gen.py` | Generator des Bahn-Sets (unten). Geometrie global in cm, wird automatisch in 40-m-Boxen zerschnitten. Braucht als Vorlage ein Blueprint „Asphalt + Schiene - Gerade“ aus dem eigenen Spiel (Pfad `SRC` oben in der Datei). |
| `bpgen.py` | Blueprint aus dem Produktionsrechner (experimentell): Vorlagen in `gamedata/templates/`, setzt Rezept und Takt, entfernt überzählige Maschinen samt Stromkabeln, prüft den Rundlauf. |
| `blueprints/bahn-set/` | Fertige Blueprints des Bahn-Sets plus Übersichtszeichnungen (`_*.png`). |
| `blueprints/vom-server/` | Im Spiel angepasste Fassungen (Design-Referenz). |

## Installation im Spiel
Dateien in den Blueprint-Ordner der Session kopieren: `…/FactoryGame/Saved/SaveGames/blueprints/<Session>/`
(Dedicated Server: im Server-Verzeichnis, Dateibesitzer wie die übrigen Spieldateien). Der Server liest den Ordner nur beim
Laden der Session ein — danach den Spielstand neu laden. Neue Blueprints erscheinen unter „Undefined“.

## Bahn-Set (`gen.py` → `blueprints/bahn-set/`)
Korridor 24 m breit, symmetrisch, alles auf Asphalt-Fundamenten 8x1 (Oberkante z = 100):

| Element | Position (Box-Koordinaten, cm) |
|---|---|
| Fundamentreihen | y = −800 / 0 / +800 |
| Gleis B (fährt +x) / Gleis A (fährt −x) | y = −800 / +800 → Rechtsverkehr, 16 m Abstand |
| Hypertube | y = 0, 1,75 m hoch; eine Stütze pro 40 m mit zwei Straßenlaternen (±1,5 m) und Kabel |
| Deko | Modern Railing (4 m) auf beiden Außenkanten (Yaw −90), H-Träger (40 m) auf den Außenkanten in Fundament-Mitte |

Weil der Korridor symmetrisch ist, kann jedes Stück um 180° gedreht werden; Gleisrichtungen bleiben konsistent.

| Blueprint | Boxen | Inhalt |
|---|---|---|
| Bahn 01 Gerade | 1 | Referenz; die im Spiel angepasste Fassung liegt in `blueprints/vom-server/` |
| Bahn 02 Gerade Blocksignale | 1 | Blocksignal je Gleis 4 m hinter der Einfahrt; alle 2–3 Stücke einsetzen |
| Bahn 03 Uebergang Kreuzung | 1 | Direkt vor eine Kreuzung: Pfadsignal (einfahrendes Gleis) + Blocksignal (ausfahrendes Gleis) am +x-Ende; für die andere Seite um 180° drehen |
| Bahn 05 Kurve 90 | 4 | 90°-Kurve, Mittellinie R 60 m (Gleise 52/68 m). Einfahrt „unten links“ von −x, Ausfahrt „oben rechts“ nach +y; „oben links“ enthält nur die Innenkante |
| Bahn 10 T-Kreuzung | 3 | „oben links“ + „oben rechts“ nebeneinander, „unten“ darunter (Abzweig 4 m rechts der Naht, an Fundamenten ausrichten). 4 Kurven R 20 m, 6 Weichen, Tube-Brücke (7 m) über die Kurven, Abzweig-Tube endet blind. Signale kommen von „Uebergang Kreuzung“ an allen drei Enden |
| Bahn 20 X-Kreuzung | 1 | Flache Kreuzung ohne Abbiegen, beide Tubes als Brücke (7 m / 8,5 m). „Uebergang Kreuzung“ an alle vier Enden |
| Bahn 30/31 Bahnhof | 1 | Eigenes Gleis (y = 0), Fahrtrichtung +x: Zug kommt von −x durch die Fracht-/Flüssigplattform (x −16…0) zur Station (x 0…16). Container-/Rohrseite −y. Blocksignale an beiden Enden. Strom anschließen |

### Signal- und Weichenlogik (aus dem Save abgeleitet)
- Signal-Actor steht exakt auf dem Gleis-Verbindungspunkt, Yaw = Fahrtrichtung. `mGuardedConnections` = Enden der Gleise hinter dem Signal, `mObservedConnections` = Enden davor.
- Weiche = `TrackConnection` mit zwei Einträgen in `mConnectedComponents`; dazu ein `Build_RailroadSwitchControl_C` auf dem Punkt (Yaw = Richtung vom Stamm weg, `mControlledConnections`).
- Bahnhof: Station/Plattform je 16 m mit eigenem `Build_RailroadTrackIntegrated_C` (Spline beginnt an der Plattformseite = lokal +x). Zug fährt in lokal −x-Richtung ein, Plattformen hängen an lokal +x. `PlatformConnection0` ↔ Gleisende 0. Plattform mit gleichem Yaw, nicht „reversed“: Container gegenüber dem Stationsgebäude.
- Gleisenden auf Box-Kanten werden nicht intern verbunden; das Spiel verbindet sie beim Platzieren (Auto-Connect).

### Unsicher / nicht im Spiel geprüft
Flache Gleiskreuzungen (T: A-Kurven kreuzen Gleis B; X) verlassen sich darauf, dass das Spiel überlappende Gleise als einen Block behandelt.
Stützenhöhen 7 m/8,5 m (Wiki: 1–7 m). Kosten im Header sind Näherungen.

## Dateiformat (Kurzfassung)
- **Header (unkomprimiert):** `int32 2`, `int32 saveVersion`, `int32 build`, `int32[3] dims`, Kosten `{lvl,path,int32}`, Rezepte `{lvl,path}`, konstanter Tail (Engine-/Custom-Versions, 1:1 kopieren).
- **Body:** zlib-Chunks mit Magic `C1 83 2A 9E`, 49-Byte-Chunk-Header. Entpackt: `int32 total, int32 hdrSize, int32 n, Objekt-Header, int32 objSize, int32 n, n × (int32 size + Daten)`.
- **Objekt-Header:** Actor `type=1, cls, root, name, int32 flags(8), int32 needTransform, quat f32[4], pos f32[3], scale f32[3], int32 placed`; Komponente `type=0, cls, root, name, int32 flags, outer`.
- **Objekt-Daten:** Actor: `parent(lvl,path)`, Komponentenliste; dann 1 Nullbyte, Property-Liste bis `None`, Rest roh.
- **Property-Tag (UE 5.4+):** `name`, Typbaum (`name, int32 nParams, …`), `int32 size`, `uint8 flags` (1 index, 2 GUID, 4 Extensions, 16 Bool-Wert). Struct-Arrays ohne inneren Tag.
- **Save (`.sav`):** gleiche Chunks; Body: `int64 size, int32 0, Versionsblock, Grid-Abschnitt, dann Level: [int32 60, Liste (lvl,path), int32 1, int32 0, Versionsblock, string name (Hauptlevel ohne Namen), int64 sz, int32 nH, Header, Sammelliste, int64 osz, int32 nO, nO × (int32 60, int32 0, int32 size, Daten, int32 0)]`.

## Kartenüberlagerung (Weltkoordinaten → Kartenbild)
Weltkoordinaten stehen im Save in cm, **+X = Ost, +Y = Süd**. Die Spielkarte deckt
`X −324698,832031 … 425301,832031` und `Y −375000 … 375000` ab (dieselben Konstanten wie die
Satisfactory-Calculator-Map); das 5000×5000-Bild bildet diesen Bereich linear ab, also 150 cm je Pixel.
Gegenprobe: alle 490 Rohstoffknoten aus dem Save liegen damit auf Land. Das weiße Rechteck im
Nordwesten ist ein Artefakt des Spiel-Maprenders und steckt in jeder Quelle.
