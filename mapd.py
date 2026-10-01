#!/usr/bin/env python3
"""Logistics map — service: collects data, keeps history and events, serves website + API.

One instance, three ticks:
  live     every  5 s   FRM: players, vehicles, station status   → /api/live
  factory  every 60 s   FRM: machines, power, item balance       → /api/factory, history, events
  save     every 60 s   new save? (SAVE_SOURCE) → stations + factory from the save (fallback without FRM)

The source per area is included (`source`: frm | save), so the website can honestly show
how old a value is. Without FRM everything runs from the save (resolution: the game's autosave interval).
Settings via environment variables, see README and .env.example.

    python mapd.py [--port 8050] [--no-fetch]
"""
import argparse, os, threading, traceback

from mapsvc.core import ST, DB, log, DIST
from mapsvc import source
from mapsvc.collect import save_cycle, live_loop, factory_loop, save_loop, sink_loop
from mapsvc.http import H, Server
# backwards compatible for tests and tools that use mapd.<function>
from mapsvc.factory import balance, block_kind, clusters, publish_factory  # noqa: F401
from mapsvc.logistics import schedule_check  # noqa: F401


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=8050)
    ap.add_argument('--bind', default='0.0.0.0')
    ap.add_argument('--no-fetch', action='store_true', help='only read saves/latest.sav, do not fetch from the server')
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
