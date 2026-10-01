"""Ereignisse (Flanke, Hysterese, 2-h-Sperre), Änderungsprotokoll, Wachstum, Lager-Warnungen."""
import collections, json, os, re, time

from .core import ST, DB, paused


# ---------------------------------------------------------------- Ältere deutsche Ereignistexte → Englisch (einmalig)
TEXTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend', 'src', 'lib', 'i18n', 'server-texts.json')


def _de_to_en():
    rules = []
    for en, de in json.load(open(TEXTS)):
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
    """Ereignisse aus der Zeit vor der Umstellung auf englische Backend-Texte übersetzen — einmal je Datenbank."""
    if DB.kv_get('texts_en', False) or not os.path.exists(TEXTS):
        return
    conv = _de_to_en()
    with DB.lock:
        rows = DB.db.execute('SELECT id, text FROM events').fetchall()
        n = 0
        for i, t in rows:
            e = conv(t or '')
            if e != t:
                DB.db.execute('UPDATE events SET text = ? WHERE id = ?', (e, i)); n += 1
        DB.db.commit()
    DB.kv_put('texts_en', True)
    if n:
        print('Event texts migrated to English:', n, flush=True)


migrate_texts()


# ---------------------------------------------------------------- Ereignisse
_seen = {k: set(v) for k, v in DB.kv_get('seen', {}).items()}


def _edge(kind, key, active, level, text, x=None, y=None, clear=None):
    """Nur beim Wechsel melden (Flanke), nicht jede Minute erneut — auch nicht nach einem Neustart.

    `clear` (optional) ist eine strengere Bedingung fürs Zurücksetzen (Hysterese): Eine Fabrik, die um die
    Warnschwelle pendelt, meldet sich sonst alle paar Minuten neu. Zusätzlich frühestens nach 2 h erneut.
    """
    s = _seen.setdefault(kind, set())
    if active and key not in s:
        last = _last.get((kind, key), 0)
        s.add(key)
        if time.time() - last > 7200:
            DB.event(kind, level, text, ref=str(key), x=x, y=y)
            _last[(kind, key)] = time.time()
        DB.kv_put('seen', {k: sorted(v, key=str) for k, v in _seen.items()})
    elif not active and key in s and (clear is None or clear):
        s.discard(key)
        DB.kv_put('seen', {k: sorted(v, key=str) for k, v in _seen.items()})


_last = {}


def factory_events(fac, t):
    for c in fac['circuits']:
        _edge('fuse', c['id'], c.get('fuse'), 'error', 'Fuse tripped in grid %s' % c['id'])
        if c.get('battery_cap'):
            _edge('battery', c['id'], c['battery'] < 0.2 * c['battery_cap'] and c['use'] > c['prod'], 'warn',
                  'Battery in grid %s below 20 %%' % c['id'])
    nop = [x for x in fac['machines'] if x.get('nopower')]
    _edge('nopower', 'all', bool(nop), 'warn', '%d machines not connected to power' % len(nop),
          *(nop[0]['pos'] if nop else (None, None)))
    for f in fac['factories']:
        if f.get('status') != 'active':          # im Aufbau / stillgelegt / Puffer: keine Warnungen
            _edge('stall', f['key'], False, 'warn', '')
            continue
        bad = f['starved'] / max(1, f['n'])
        _edge('stall', f['key'], bad > .3 and f['starved'] >= 4, 'warn', '%s: %d of %d machines missing input' % (
            f['name'], f['starved'], f['n']), *f['center'], clear=bad < .15)


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
    from .logistics import train_transfers, train_rounds
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


# ---------------------------------------------------------------- Änderungsprotokoll + Wachstum
def changelog(fac, t):
    """Vergleicht Gebäude-IDs mit dem letzten Save-Stand: neu / abgerissen, je Typ und Erbauer."""
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
        DB.event('build', lvl, '%s %s%s' % (', '.join('%d× %s' % (n, k) for k, n in cnt.most_common(4)), label,
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


# ---------------------------------------------------------------- Lager + Sink
def storage_events(st):
    """„Lager voll“: nur Container, an denen eine Fabrik hängt, die dadurch staut (Maschinen mit vollem Ausgang
    in 60 m) — ein volles Endlager ohne Zulauf ist gewollt. Eine Meldung je Container, Hysterese über _edge."""
    fac = ST.factory or {}
    full_out = [m for m in fac.get('machines', []) if m.get('block') == 'full']
    for c in st:
        if c['fill'] is None or 'Tank' in c['cls']:
            continue
        near = sum(1 for m in full_out if (m['pos'][0] - c['pos'][0]) ** 2 + (m['pos'][1] - c['pos'][1]) ** 2 < 3600)
        it = c['items'][0]['item'] if c['items'] else '?'
        _edge('full', c['id'], c['fill'] > .98 and near >= 2, 'warn', 'Storage full (%s), %d machines backed up' % (it, near),
              c['pos'][0], c['pos'][1], clear=c['fill'] < .9)


