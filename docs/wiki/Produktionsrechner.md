# Produktionsrechner

Plant Produktionsketten **nur mit Rezepten, die auf deinem Server freigeschaltet sind**, und rechnet vorhandene
Überschüsse deiner Fabrik ein.

![Rechner](https://raw.githubusercontent.com/Fade97/satisfactory-logistikkarte/main/docs/bilder/rechner.png)

## So geht's
1. Ware wählen (Tippfehler und deutsche Namen gehen), Menge pro Minute eingeben. **Weiteres Ziel** für mehrere Waren.
2. Optionen:
   - **Überschüsse der Fabrik nutzen** — was deine Fabrik heute übrig hat, wird zuerst verbraucht (bis 90 %).
   - **Optimieren auf** *wenig Rohstoffe* (seltene Rohstoffe zählen stärker), *wenig Maschinen* oder *wenig Strom*.
   - **Takt bis** 100–250 % — mit Power Shards weniger Maschinen, aber überproportional mehr Strom.
   - **Somersloops** — doppelte Ausgabe je Maschine, vierfacher Strom.
3. **Berechnen**.

## Ergebnis
- **Produktionskette** als *Diagramm* (Linienstärke = Menge; orange = von Rohstoffknoten, grün = aus Überschuss) oder als *Baum*.
- **Bauliste**: je Schritt Rezept, Maschinen (mit krummem Takt für die letzte), Strom. Über **Rezepte wählen** lassen
  sich Alternativrezepte je Ware erlauben oder sperren.
- **Rohstoffe**, **Nebenprodukte**, benötigte Power Shards und Somersloops.
- **Freie Knoten**: passende unbelegte Rohstoffknoten, sortiert nach Reinheit und Entfernung — zur größten Fabrik oder
  zu einem **Bauplatz**, den du auf der Karte anklickst.
- **Plan als Notiz auf die Karte** speichert Ziel und Bauliste als Notiz am Bauplatz (Passwort nötig).

## Blueprint-Export (experimentell)
Für Schritte mit Constructor oder Smelter erscheint **Blueprint ⤓**: ein ZIP mit `.sbp`/`.sbpcfg`, das Maschinen in
der richtigen Anzahl mit gesetztem Rezept und Takt enthält (auf Basis mitgelieferter Vorlagen). **Im Spiel noch nicht
geprüft** — erst in einer Testwelt ausprobieren. Installation: ZIP entpacken und nach
`…/SaveGames/blueprints/<Session>/` kopieren, dann den Spielstand neu laden.

## Links in den Rechner
`#/rechner?item=Heavy%20Modular%20Frame&rate=4` öffnet den Rechner vorausgefüllt — so verlinkt auch die Lage-Seite
aus der Mangelware-Liste.
