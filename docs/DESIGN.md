# Design — Logistikkarte v2 („FICSIT-Look“)

Vorgabe (29.09.2026): an die Spiel-UI angelehnt, Orange-Grau, industrielle Typografie; UI deutsch.

## Idee
Die Karte ist eine **Leitstandtafel**, kein Dashboard. Vorbild ist das Terminal im HUB: Die Spielkarte
liegt als Fläche auf warmem Anthrazit, alles Menschengemachte (Gleise, Stationen, Fabriken) sitzt in
FICSIT-Orange und Signalfarben darauf. Das eine Wiedererkennungsmerkmal sind die **gestanzten Ecken**:
Panels und Knöpfe haben eine abgeschrägte obere rechte Ecke wie die Spielmenüs. Nur Panels bekommen
sie, Listenzeilen nicht. Sonst bleibt alles ruhig.

## Farben
| Name | Hex | Rolle |
|---|---|---|
| Stahl | `#1b1c1e` | Grundfläche, Panels |
| Blech | `#26282b` | angehobene Flächen, Kopfzeilen |
| Naht | `#3a3d41` | Trennlinien, Rahmen |
| FICSIT-Orange | `#f59a23` | Marke, aktive Auswahl, Beladen |
| Kobalt | `#5b9bd5` | Entladen, Züge, Rohre (das Spiel färbt Flüssiges blau) |
| Signal | `#e5484d` / `#4cc38a` | Störung / läuft |
Text: `#e8e6e1` (warmes Weiß), gedämpft `#9a968e`.

Beladen = Orange und Entladen = Blau ersetzt das alte Grün/Orange: Das ist farbenblind-sicherer und
passt zur Palette.

## Schrift
- **Barlow Condensed** 600/700: Überschriften, Kennzahlen, Navigation. Schmal und technisch wie die
  Beschriftung im Spiel, in Normalschreibung, nie gesperrt in Versalien.
- **Barlow** 400/500: Fließtext und Tabellen, `font-variant-numeric: tabular-nums` für Raten.
Skala: 12 / 14 / 16 / 20 / 28 / 40.

## Layout
```
Desktop                                          Handy
┌──────────────────────────────────────────┐    ┌──────────────┐
│ ▌FICSIT  Karte Produktion Strom Logistik …│    │ ▌ Karte   ◉ ⋯│
├────────┬─────────────────────────┬───────┤    │              │
│ Suche  │                         │Detail │    │    Karte     │
│ Liste  │        KARTE            │ (bei  │    │              │
│        │                         │Auswahl)│   ├──────────────┤
│        │               [Ebenen]  │       │    │ Bottom Sheet │
├────────┴─────────────────────────┴───────┤    ├──────────────┤
│ Ereignis-Leiste (einklappbar)            │    │ Tab-Leiste   │
└──────────────────────────────────────────┘    └──────────────┘
```
Die anderen Seiten (Produktion, Strom, Logistik, Verlauf) sind linksbündige Arbeitsflächen mit Tabellen
und Diagrammen. Jede Zeile mit Ort springt per Klick zur Karte (`#/karte?sel=…`).

## Grundsätze
1. Die Quelle ist immer sichtbar: „live“ (FRM) oder „Save von 22:19“. Nie eine alte Zahl als frisch ausgeben.
2. Karte zuerst: Jede Liste endet auf der Karte.
3. Farben tragen Bedeutung (Zustand, Richtung), keine Zier.
4. Bewegung nur als Antwort: Fahrzeuge gleiten, Panels schieben auf; keine Einblend-Effekte beim Laden.
