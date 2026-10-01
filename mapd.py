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

import frm
from mapsvc.core import ST, log, DIST
from mapsvc import source
from mapsvc.collect import save_cycle, live_loop, factory_loop, save_loop, sink_loop
from mapsvc.http import RequestHandler, Server


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=8050)
    ap.add_argument('--bind', default='0.0.0.0')
    ap.add_argument('--no-fetch', action='store_true', help='only read saves/latest.sav, do not fetch from the server')
    args = ap.parse_args()
    log('Save source:', source.describe(), '· FRM:', frm.BASE or 'off')
    try:
        save_cycle(args.no_fetch)
    except source.SourceError as e:
        ST.save_error = str(e)
        log('first save fetch failed:', e)
    except Exception:
        log('first save run failed:\n' + traceback.format_exc()[-800:])
    for fn, fn_args in ((live_loop, ()), (factory_loop, ()), (save_loop, (args.no_fetch,)), (sink_loop, ())):
        threading.Thread(target=fn, args=fn_args, daemon=True).start()
    if not os.path.isdir(DIST):
        log('Warning: frontend/dist missing — build it first (cd frontend && pnpm install && pnpm run build)')
    log('Logistics map on http://%s:%d' % (args.bind, args.port))
    Server((args.bind, args.port), RequestHandler).serve_forever()


if __name__ == '__main__':
    main()
