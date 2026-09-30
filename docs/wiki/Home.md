<p align="center"><img src="https://raw.githubusercontent.com/Fade97/satisfactory-logistikkarte/main/docs/logo/banner.png" alt="Satisfactory-Logistikkarte" width="640"></p>

# Satisfactory-Logistikkarte — Wiki

Die Logistikkarte ist eine Web-App für **deinen eigenen Satisfactory-Dedicated-Server**. Sie liest den Spielstand
(und optional Live-Daten) und zeigt Fabriken, Züge, Förderbänder, Stromnetze und Engpässe — am PC, auf dem zweiten
Monitor oder am Handy. Mitspieler brauchen nur einen Browser.

![Lage-Übersicht](https://raw.githubusercontent.com/Fade97/satisfactory-logistikkarte/main/docs/bilder/lage.png)

## Schnellstart
1. [Installation mit Docker](Installation-mit-Docker) — in 5 Minuten lauffähig
2. [Save-Quelle einrichten](Save-Quelle-einrichten) — woher die Karte den Spielstand bekommt
3. Optional: [Live-Daten mit FRM](Live-Daten-mit-FRM) — Positionen alle 5 Sekunden statt alle 5 Minuten
4. Optional: [Öffentlich erreichbar machen](Oeffentlich-erreichbar-machen) — für Mitspieler über das Internet

## Seiten dieses Wikis
| Thema | Seiten |
|---|---|
| Einrichten | [Installation mit Docker](Installation-mit-Docker) · [Installation ohne Docker](Installation-ohne-Docker) · [Save-Quelle einrichten](Save-Quelle-einrichten) · [Live-Daten mit FRM](Live-Daten-mit-FRM) · [Öffentlich erreichbar machen](Oeffentlich-erreichbar-machen) · [Konfiguration](Konfiguration) |
| Benutzen | [Bedienung im Überblick](Bedienung) · [Die Karte](Karte) · [Produktionsrechner](Produktionsrechner) · [How-tos](How-tos) |
| Betreiben | [Aktualisieren und Sichern](Aktualisieren-und-Sichern) · [Fehlerbehebung](Fehlerbehebung) |
| Für Entwickler | [API](API) · [Entwicklung](Entwicklung) |

## Was du brauchst
- Einen Satisfactory **Dedicated Server** (Version 1.0 oder neuer; getestet mit Build 502094 „anniversary-2026“, Save-Version 60)
- Einen Rechner, auf dem die Karte läuft: Linux-Server, NAS, Windows oder macOS mit Docker Desktop (ARM-Geräte wie ein Raspberry Pi sollten gehen, sind aber ungetestet).
  Die Karte braucht ca. 1 GB RAM bei großen Fabriken (1000+ Maschinen) und kaum CPU.
- Zugriff auf die Saves: Admin-Passwort des Servers **oder** SFTP/FTP **oder** den Save-Ordner direkt

## Was die Karte nicht tut
- Sie **schreibt nie** in den Spielstand und ändert nichts am Server. Notizen und Fabriknamen liegen nur in der Karte.
- Sie ersetzt keine Satisfactory-Calculator-Karte zum Bearbeiten von Saves.
