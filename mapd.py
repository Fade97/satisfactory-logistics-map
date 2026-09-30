#!/usr/bin/env python3
"""Logistikkarte — Dienst: sammelt Daten, führt Verlauf und Ereignisse, liefert Website + API.

Eine Instanz, drei Takte:
  live   alle  5 s   FRM: Spieler, Fahrzeuge, Stationsstatus  → /api/live
  werk   alle 60 s   FRM: Maschinen, Strom, Warenbilanz        → /api/factory, Verlauf, Ereignisse
  save   alle 60 s   neues Save? (SAVE_SOURCE) → Stationen + Fabrik aus dem Save (Rückfall ohne FRM)

Quelle je Bereich wird mitgeliefert (`source`: frm | save), damit die Website ehrlich anzeigen
kann, wie alt ein Wert ist. Ohne FRM läuft alles aus dem Save (Auflösung: Autosave-Takt des Spiels).
Einstellungen per Umgebungsvariablen, siehe README und .env.example.

    python mapd.py [--port 8050] [--no-fetch]
"""
import argparse, os, threading, traceback

from mapsvc.core import ST, DB, log, DIST
from mapsvc import source
from mapsvc.collect import save_cycle, live_loop, factory_loop, save_loop, sink_loop
from mapsvc.http import H, Server
# Rückwärtskompatibel für Tests und Werkzeuge, die mapd.<funktion> nutzen
from mapsvc.factory import balance, block_kind, clusters, publish_factory  # noqa: F401
from mapsvc.logistics import schedule_check  # noqa: F401


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=8050)
    ap.add_argument('--bind', default='0.0.0.0')
    ap.add_argument('--no-fetch', action='store_true', help='nur saves/latest.sav lesen, nicht vom Server holen')
    a = ap.parse_args()
    log('Save source:', source.describe(), '· FRM:', __import__('frm').BASE or 'off')
    try:
        save_cycle(a.no_fetch)
    except source.SourceError as e:
        ST.save_error = str(e)
        log('first save fetch failed:', e)
    except Exception:
        log('first save run failed:\n' + traceback.format_exc()[-800:])
    for fn, args in ((live_loop, ()), (factory_loop, ()), (save_loop, (a.no_fetch,)), (sink_loop, ())):
        threading.Thread(target=fn, args=args, daemon=True).start()
    if not os.path.isdir(DIST):
        log('Warning: frontend/dist missing — build it first (cd frontend && pnpm install && pnpm run build)')
    log('Logistics map on http://%s:%d' % (a.bind, a.port))
    Server((a.bind, a.port), H).serve_forever()


if __name__ == '__main__':
    main()
