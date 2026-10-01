"""Events (edge detection, hysteresis, cooldown), change log, growth, storage warnings."""
import collections, json, os, re, threading, time

from .core import ST, DB, paused
from .logistics import train_transfers, train_rounds

EVENT_COOLDOWN = 2 * 3600       # s: report the same edge again after this at the earliest
BATTERY_LOW = 0.2               # share of battery capacity
STALL_ON, STALL_OFF, STALL_MIN = .3, .15, 4     # share of starved machines: warn above / clear below; min. machines
STORAGE_FULL, STORAGE_CLEAR = .98, .9           # container fill: warn above / clear below
BACKUP_RADIUS = 60              # m: machines with full output this close count as backed up by a container


# ---------------------------------------------------------------- legacy German event texts → English (one-off)
TEXTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend', 'src', 'lib', 'i18n', 'server-texts.json')


def _de_to_en():
    rules = []
    with open(TEXTS) as f:
        pairs = json.load(f)
    for en, de in pairs:
        rx = re.compile('^' + re.sub(r'\\\{(\d)\\\}', '(.+?)', re.escape(de)) + '$', re.S)
        rules.append((rx, [int(n) for n in re.findall(r'\{(\d)\}', de)], en))

    def conv(t, depth=0):
        for rx, order, en in rules:
            m = rx.match(t)
            if m and depth < 4:
                val = {n: conv(m.group(i + 1), depth + 1) for i, n in enumerate(order)}
                return re.sub(r'\{(\d)\}', lambda g: val.get(int(g.group(1)), ''), en)
        return t
    return conv


def migrate_texts():
    """Translate events from before the switch to English backend texts — once per database."""
    if DB.kv_get('texts_en', False) or not os.path.exists(TEXTS):
        return
    n = DB.rewrite_event_texts(_de_to_en())
    DB.kv_put('texts_en', True)
    if n:
        print('Event texts migrated to English:', n, flush=True)


migrate_texts()


# ---------------------------------------------------------------- events
# edge state, shared by the live/factory/save loops and HTTP (factory rename) — guarded by _edge_lock
_seen = {k: set(v) for k, v in DB.kv_get('seen', {}).items()}      # (kind → keys) currently active, persisted
_last = {}                                                          # (kind, key) → time of the last report
_edge_lock = threading.Lock()


def _edge(kind, key, active, level, text, x=None, y=None, clear=None):
    """Report only on a change (edge), not again every minute — not even after a restart.

    `clear` (optional) is a stricter condition for resetting (hysteresis): otherwise a factory oscillating
    around the warning threshold would report again every few minutes. Additionally, re-report after EVENT_COOLDOWN at the earliest.
    """
    with _edge_lock:
        s = _seen.setdefault(kind, set())
        if active and key not in s:
            last = _last.get((kind, key), 0)
            s.add(key)
            if time.time() - last > EVENT_COOLDOWN:
                DB.event(kind, level, text, ref=str(key), x=x, y=y)
                _last[(kind, key)] = time.time()
            DB.kv_put('seen', {k: sorted(v, key=str) for k, v in _seen.items()})
        elif not active and key in s and (clear is None or clear):
            s.discard(key)
            DB.kv_put('seen', {k: sorted(v, key=str) for k, v in _seen.items()})


def factory_events(fac, t):
    for c in fac['circuits']:
        _edge('fuse', c['id'], c.get('fuse'), 'error', 'Fuse tripped in grid %s' % c['id'])
        if c.get('battery_cap'):
            _edge('battery', c['id'], c['battery'] < BATTERY_LOW * c['battery_cap'] and c['use'] > c['prod'], 'warn',
                  'Battery in grid %s below 20 %%' % c['id'])
    nop = [x for x in fac['machines'] if x.get('nopower')]
    _edge('nopower', 'all', bool(nop), 'warn', '%d machines not connected to power' % len(nop),
          *(nop[0]['pos'] if nop else (None, None)))
    for f in fac['factories']:
        if f.get('status') != 'active':          # building / decommissioned / buffer: no warnings
            _edge('stall', f['key'], False, 'warn', '')
            continue
        bad = f['starved'] / max(1, f['n'])
        _edge('stall', f['key'], bad > STALL_ON and f['starved'] >= STALL_MIN, 'warn', '%s: %d of %d machines missing input' % (
            f['name'], f['starved'], f['n']), *f['center'], clear=bad < STALL_OFF)


def live_events(live):
    prev = ST.prev_live
    if prev:
        was = {p['name']: p for p in prev.get('players', [])}
        for p in live.get('players', []):
            o = was.get(p['name'])
            x, y = p['pos'][0] / 100, p['pos'][1] / 100
            if o and p['online'] and not o['online']:
                DB.event('player', 'info', '%s is online' % p['name'], ref='player:' + p['name'], x=x, y=y)
            elif o and not p['online'] and o['online']:
                DB.event('player', 'info', '%s is offline' % p['name'], ref='player:' + p['name'], x=x, y=y)
            if o and p['dead'] and not o['dead']:
                DB.event('player', 'warn', '%s died' % p['name'], ref='player:' + p['name'], x=x, y=y)
    train_transfers(live)
    train_rounds(live)
    for v in live.get('trains', []):
        _edge('derail', v['name'], v.get('derailed'), 'error', 'Train %s derailed' % v['name'], v['pos'][0] / 100, v['pos'][1] / 100)
    for v in live.get('trucks', []):
        _edge('nofuel', v.get('id') or v['name'], v.get('fuel') is False and v.get('autopilot'), 'warn',
              '%s %s out of fuel' % (v.get('type', 'Truck'), v['name']), v['pos'][0] / 100, v['pos'][1] / 100)
    ss = live.get('stations') or {}
    if ST.stations:
        for s in ST.stations['trucks']:
            lv = ss.get(s['id'].split('.')[-1])
            if lv and lv.get('status') == 'Error':
                _edge('empty', s['id'], True, 'warn', 'Station %s reports an error' % s['name'], s['pos'][0] / 100, s['pos'][1] / 100)
            else:
                _edge('empty', s['id'], False, 'warn', '')
    ST.prev_live = live


# ---------------------------------------------------------------- change log + growth
def changelog(fac, t):
    """Compare building IDs with the previous save: built / removed, per type and builder."""
    cur = {m['id']: [m['name'], m['pos'][0], m['pos'][1], m.get('by')] for m in fac['machines'] + fac['generators']}
    old_t, old = DB.snapshot_get('buildings')
    DB.snapshot_put('buildings', t, cur)
    if old is None or old_t >= t:
        return
    new = [cur[k] for k in cur.keys() - old.keys()]
    gone = [old[k] for k in old.keys() - cur.keys()]
    for label, rows, lvl in (('built', new, 'info'), ('removed', gone, 'info')):
        if not rows:
            continue
        cnt = collections.Counter(r[0] for r in rows)
        who = sorted({r[3] for r in rows if r[3]})
        x = sum(r[1] for r in rows) / len(rows); y = sum(r[2] for r in rows) / len(rows)
        top = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:4]      # ties by name → stable text
        DB.event('build', lvl, '%s %s%s' % (', '.join('%d× %s' % (n, k) for k, n in top), label,
                                              ' (%s)' % ', '.join(who) if who else ''), ref='build', x=x, y=y, t=t)


def growth(fac, t):
    if paused():
        return
    v = {'count:machines': len(fac['machines']), 'count:generators': len(fac['generators']),
         'count:rail_km': fac.get('rail_km'), 'count:belt_km': fac.get('belt_km'),
         'count:schematics': fac['progress'].get('n_schematics'), 'count:playtime_h': (fac.get('playtime') or 0) / 3600}
    DB.put_series(t, v)
    prev = DB.kv_get('schematics', [])
    cur = fac['progress'].get('schematics', [])
    if prev:
        for s in [s for s in cur if s not in prev][:10]:
            DB.event('progress', 'info', 'Unlocked: ' + s, ref='progress', t=t)
    DB.kv_put('schematics', cur)


# ---------------------------------------------------------------- storage + sink
def storage_events(st):
    """'Storage full' warning: only containers with a factory attached that backs up because of it (machines with full
    output within BACKUP_RADIUS) — a full end-of-line storage with no inflow is intended. One report per container, hysteresis via _edge."""
    fac = ST.factory or {}
    full_out = [m for m in fac.get('machines', []) if m.get('block') == 'full']
    for c in st:
        if c['fill'] is None or 'Tank' in c['cls']:
            continue
        near = sum(1 for m in full_out if (m['pos'][0] - c['pos'][0]) ** 2 + (m['pos'][1] - c['pos'][1]) ** 2 < BACKUP_RADIUS ** 2)
        it = c['items'][0]['item'] if c['items'] else '?'
        _edge('full', c['id'], c['fill'] > STORAGE_FULL and near >= 2, 'warn', 'Storage full (%s), %d machines backed up' % (it, near),
              c['pos'][0], c['pos'][1], clear=c['fill'] < STORAGE_CLEAR)


