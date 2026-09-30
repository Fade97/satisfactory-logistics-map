# Bedienung im Überblick

Oben die Seiten, rechts daneben die **Datenquelle** (live / Save vor N min / offline), **≡** Ereignisse,
**☺** Meine Ansicht und **⛶** Kiosk. Am Handy wandert die Navigation nach unten.

## Lage (Startseite)
Was gerade Aufmerksamkeit braucht: Stromnetze mit Auslastung, laufende Maschinen, Materialmangel, Fortschritt;
Liste der Probleme (Fabriken mit Mangel, Brennstoff geht aus, Maschinen ohne Strom, volle Lager) und **Mangelware**
(Zeile anklicken → Rechner mit der fehlenden Menge). Unten: was seit deinem letzten Besuch passiert ist.

![Lage](https://raw.githubusercontent.com/Fade97/satisfactory-logistikkarte/main/docs/bilder/lage.png)

## Karte
Siehe [Die Karte](Karte).

![Karte](https://raw.githubusercontent.com/Fade97/satisfactory-logistikkarte/main/docs/bilder/karte.png)

## Produktion
- **Warenbilanz**: je Ware erzeugt/verbraucht pro Minute, Filter „nur Mangel/Überschuss“, Klick zeigt den Verlauf 24 h.
- **Materialmangel**: stehende Maschinen mit Grund („wartet auf Iron Plate“), seit wann.
- **Fabriken**: automatisch erkannte Fabriken (Maschinen, die über Bänder/Rohre verbunden sind), mit Zustandsbalken,
  Hauptprodukten und Strom. Klick springt auf die Karte.
- **Rohstoffknoten**: alle Knoten mit Reinheit, belegt/frei.

Maschinen, die nur warten, weil ihr **Ausgang voll** ist, gelten als gewollter Puffer und sind grau statt rot.

![Fabriken](https://raw.githubusercontent.com/Fade97/satisfactory-logistikkarte/main/docs/bilder/fabriken.png)

## Strom
Jedes Stromnetz mit Erzeugung, Verbrauch, Kapazität und Batterien, Verlauf, Sicherungsauslösungen (mit FRM),
Brennstoff-Reichweite der Generatoren und Maschinen ohne Stromanschluss.

![Strom](https://raw.githubusercontent.com/Fade97/satisfactory-logistikkarte/main/docs/bilder/strom.png)

## Logistik
Truck- und Zugstationen mit Füllständen und Warnung bei leer/voll, gemessener Zug-Durchsatz (mit FRM),
**Fahrplan-Prüfung** (reicht die Kapazität einer Route für den Bedarf der Fabrik an der Entladestation?),
Lager-Übersicht je Ware und der AWESOME Sink (Punkte, Coupons).

![Logistik](https://raw.githubusercontent.com/Fade97/satisfactory-logistikkarte/main/docs/bilder/logistik.png)

## Verlauf
Produktion je Ware, Strom je Netz, Wachstum der Fabrik und ein Änderungsprotokoll (gebaut/abgerissen) — von 1 Stunde bis
zu Monaten. Lücken = Server war pausiert.

![Verlauf](https://raw.githubusercontent.com/Fade97/satisfactory-logistikkarte/main/docs/bilder/verlauf.png)

## Rechner
Siehe [Produktionsrechner](Produktionsrechner).

## Meine Ansicht (☺)
Gilt nur im jeweiligen Browser, kein Login nötig:
- **Ich bin**: dein Spielername
- **Karte folgt mir, wenn ich online bin**
- **Startseite**: Lage, Karte (letzte Position) oder Produktion
- **Warennamen**: Englisch (wie im Spiel) oder Deutsch — die Suche findet immer beide

## Ereignisse (≡)
Maschinen stehen/laufen wieder, Lager voll, Spieler online/offline/gestorben, gebaut/abgerissen, Freischaltungen,
Live-Daten ausgefallen. Klick auf ein Ereignis springt zur Stelle auf der Karte. Meldungen sind gedämpft: dieselbe
Meldung kommt höchstens alle 2 Stunden, Schwellen haben eine Hysterese.

## Am Handy
Alle Seiten sind für das Handy gebaut. Die Karte ist bildschirmfüllend, die Stationsliste eine Schublade (☰),
Detailkarten erscheinen als Blatt von unten (hochwischen für mehr). Über „Zum Startbildschirm hinzufügen“ wird die
Karte zur App (siehe [How-tos](How-tos#karte-als-app-installieren)).

<p><img src="https://raw.githubusercontent.com/Fade97/satisfactory-logistikkarte/main/docs/bilder/handy-lage.png" width="260"> <img src="https://raw.githubusercontent.com/Fade97/satisfactory-logistikkarte/main/docs/bilder/handy-karte.png" width="260"></p>
