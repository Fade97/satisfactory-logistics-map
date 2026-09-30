# How-tos

Kurze Anleitungen für typische Aufgaben.

## Karte als App installieren
- **Android (Chrome):** Menü ⋮ → *App installieren* bzw. *Zum Startbildschirm hinzufügen*.
- **iPhone (Safari):** Teilen □↑ → *Zum Home-Bildschirm*.
- **PC (Chrome/Edge):** Symbol ⊕ rechts in der Adresszeile.

Die App startet ohne Browserleiste und zeigt offline den letzten Stand („offline · letzter Stand“). Voraussetzung: HTTPS
(siehe [Öffentlich erreichbar machen](Oeffentlich-erreichbar-machen)) oder Aufruf über `localhost`.

## Zweiter Monitor / Wand-Display
Browser im Vollbild (F11) auf `https://deine-karte/#/kiosk?rotate=30` öffnen. Mit `folge=<Spieler>` bleibt die Karte
bei dir. Tipp: in *Meine Ansicht* „Ich bin“ setzen, dann folgt auch die normale Karte dir, sobald du online bist.

## Mir selbst folgen lassen
**☺ → Ich bin** auf deinen Namen, **Karte folgt mir, wenn ich online bin** anhaken. Braucht [FRM](Live-Daten-mit-FRM).

## Herausfinden, warum eine Fabrik steht
1. **Lage** zeigt Fabriken mit Materialmangel. Klick → Karte.
2. In der Fabrik-Detailkarte stehen die Maschinen nach Zustand; eine Maschine anklicken zeigt den Grund
   („wartet auf Steel Beam“).
3. **Warenfluss** für die fehlende Ware öffnen: Wer erzeugt sie, wo liegt sie auf Bändern, welche Station liefert?
4. Fehlt sie insgesamt: in der Lage auf die Zeile in **Mangelware** klicken → Rechner mit der fehlenden Menge.

## Fabriken benennen und stilllegen
Fabrik auf der Karte anklicken → **Name und Status ändern** (Passwort). Status: *aktiv*, *im Aufbau*, *Puffer*,
*stillgelegt*. Nur **aktive** Fabriken erzeugen Warnungen — Baustellen und bewusste Puffer bleiben still.

## Notiz setzen („hier Kohle-Kraftwerk bauen“)
**Notiz** → Punkt/Linie/Fläche → auf die Karte klicken → Text und Kategorie → Passwort (einmal je Browser).

## Einen Zug-Fahrplan prüfen
**Logistik → Fahrplan-Prüfung**: für jede Route die Kapazität (Waggons × Rundenzeit) gegen den Bedarf der Fabriken an
den Entladestationen. Rot = zu wenig. Rundenzeiten misst die Karte selbst mit (braucht FRM und etwas Spielzeit).

## Eine neue Fabrik planen
**Rechner** → Ziel eingeben → Bauplatz auf der Karte wählen → freie Knoten ansehen → **Plan als Notiz**.

## Zurückschauen: Was war vor 3 Stunden los?
**Karte → Zeitreise**, Schieber zurückziehen. Spieler, Züge und der Zustand jeder Fabrik werden minutengenau abgespielt
(letzte 24 h, nur Zeiten, in denen gespielt wurde).

## Deutsche Warennamen
**☺ → Warennamen → Deutsch**. Die Suche findet immer beide Sprachen.

## Link auf eine Stelle schicken
Auf der Karte hinzoomen, etwas anklicken, Adresszeile kopieren. Der Link öffnet genau diese Ansicht.
