# Die Karte

![Karte](https://raw.githubusercontent.com/Fade97/satisfactory-logistikkarte/main/docs/bilder/karte.png)

## Bewegen
| Maus / Tastatur | Handy |
|---|---|
| Ziehen = verschieben, Mausrad = zoomen | ein Finger ziehen, zwei Finger zoomen |
| Klick auf ein Objekt = Detailkarte | antippen |
| `+` / `−` zoomen, Pfeiltasten verschieben | Knöpfe links |
| `f` Fabrikgebiet, `g` ganze Karte | ⌂ / ⤢ |
| `/` Suche, `Esc` Auswahl bzw. Suche schließen | |
| `l` Beschriftungen, `m` Kartenbild an/aus | |

## Links
Links die **Stationen** (Truck/Zug, Beladen/Entladen) und **Waren**; oben die Spieler mit Status. Die Suche findet
Stationen, Waren und Maschinen und verzeiht Tippfehler („stel beam“ findet *Steel Beam*, „Stahlträger“ auch).

## Ebenen
Über **Ebenen** zuschaltbar (die Auswahl merkt sich der Browser):

| Ebene | Standard |
|---|---|
| Spielkarte, Fundamente & Wände (ab Zoom), Gleisnetz | an |
| Rohrleitungen, Förderbänder, Stromleitungen | aus |
| Stationen, Zugrouten, Fahrzeuge, Spieler, Spielerspuren (2 h) | an |
| Fabriken (Umriss nach Zustand), Ohne Stromanschluss, Notizen | an |
| Heatmap Materialmangel, Maschinen, Maschinen mit Materialmangel, Generatoren, Rohstoffknoten | aus |
| Sammelobjekte (fehlende Somersloops, Mercer Spheres, Power Slugs, offene Absturzstellen) | aus |

## Detailkarten
Jedes Objekt ist anklickbar:
- **Station**: Plattformen, Puffer, Fahrzeuge der Route mit Rundenzeit, Gegenstellen (wer liefert hierher?)
- **Fabrik**: Maschinen nach Zustand, Ein-/Ausgänge, Strom, **3D-Ansicht**, „Name und Status ändern“
- **Maschine**: Rezept, Takt, Soll/Ist-Rate, warum sie steht, Erbauer
- **Spieler / Fahrzeug**: Position, Tempo, Ladung, **Karte folgt …**

## Folge-Modus
In der Detailkarte eines Spielers, Zugs oder LKW **„Karte folgt …“** wählen. Die Karte gleitet mit, auch wenn die
Detailkarte geschlossen wird. Ist ein Spieler offline, pausiert das Folgen und startet beim nächsten Login von selbst.
Folgen braucht [Live-Daten](Live-Daten-mit-FRM) für flüssige Bewegung.

## Werkzeuge
| Knopf | Wozu |
|---|---|
| **Notiz** | Punkt, Linie oder Fläche mit Text und Kategorie (Geplant, Problem, Rohstoff, Treffpunkt, Notiz). Braucht das gemeinsame Passwort. |
| **Höhe** | Nur eine Etage zeigen — erkannte Stockwerke als Schnellauswahl, praktisch bei mehrstöckigen Fabriken |
| **Messen** | Strecke oder Fläche; zeigt Meter, Fundamente, Gleis- und Bandstücke |
| **Zeitreise** | Schieber über die letzten 24 h: wo waren Spieler und Züge, wie lief jede Fabrik (Minutenbilder) |
| **Warenfluss** | Eine Ware wählen: Erzeuger, Verbraucher, Stationen und die Bänder/Rohre, auf denen sie gerade liegt |

![Warenfluss](https://raw.githubusercontent.com/Fade97/satisfactory-logistikkarte/main/docs/bilder/warenfluss.png)

## Links auf Stellen teilen
Die Adresszeile enthält Position, Zoom und Auswahl, z. B.
`#/karte?x=-1650&y=-400&z=0.42&sel=player:Ada` — einfach kopieren und schicken (die Auswahl steht automatisch drin, sobald du etwas anklickst).
Weitere Parameter: `ware=Steel%20Beam` (Warenfluss öffnen).

## Kiosk (zweiter Monitor)
`#/kiosk` zeigt Karte, Kennzahlen, größten Mangel und Ereignisse ohne Bedienelemente.
- `#/kiosk?folge=<Spieler>` folgt einem bestimmten Spieler (sonst dem ersten, der online ist)
- `#/kiosk?rotate=30` wechselt alle 30 s zwischen Karte, Produktion, Strom und Logistik

![Kiosk](https://raw.githubusercontent.com/Fade97/satisfactory-logistikkarte/main/docs/bilder/kiosk.png)
