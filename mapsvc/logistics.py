"""Logistik: Füllstände, Zugdurchsatz und Rundenzeiten, Fahrplan-Prüfung."""
import collections, math, time

from .core import ST, DB, paused


STACK = {v['name']: (v['stackSize'], v['liquid']) for v in __import__('factory').ITEMS.values()}
VEH_SLOTS = {'Truck': 48, 'Traktor': 25, 'Explorer': 24}


def fill_levels(data):
    """Füllstand je Station (0..1) und theoretischer Durchsatz je Truck-Fahrzeug.

    Truckstation 48 Slots, Frachtplattform 32 Slots, Flüssigplattform 2400 m³ (Wiki-Werte).
    Durchsatz = volle Ladung ÷ Rundenzeit — eine Obergrenze, denn wie voll ein Fahrzeug tatsächlich
    fährt, steht nicht im Save.
    """
    def cap(items, slots, fluid_cap):
        if not items:
            return None
        it = items[0]['item']
        st, liq = STACK.get(it, (100, False))
        c = fluid_cap if liq else slots * st
        return round(min(1.0, sum(i['amount'] for i in items) / c), 3) if c else None
    for s in data['trucks']:
        s['fill'] = cap(s['items'], 48, 0)
        it = s['items'][0]['item'] if s['items'] else None
        st, liq = STACK.get(it, (100, False)) if it else (0, False)
        for v in s.get('vehicles', []):
            load = VEH_SLOTS.get(v['type'], 48) * st
            v['per_min'] = round(load / (v['round'] / 60), 1) if v['round'] > 30 and load else None
    for s in data['trains']:
        for p in s['platforms']:
            p['fill'] = cap(p['items'], 32, 2400) if p['type'] != 'empty' else None


# ---------------------------------------------------------------- Zugdurchsatz
_cargo_prev = {}


_round_start = {}          # Zug → (Station beim Rundenbeginn, Zeitpunkt)


def train_rounds(live):
    """Rundenzeit je Zug messen: Ankunft (angedockt) am ersten Halt des Fahrplans bis zur nächsten Ankunft dort."""
    now = time.time()
    for t in live.get('trains', []):
        stops = t.get('stops') or []
        if not stops or not t.get('docked') or t.get('station') != stops[0]:
            continue
        prev = _round_start.get(t['name'])
        if prev and prev[1] == 'weg':                    # zwischendurch abgefahren → Runde beendet
            dt = now - prev[0]
            if 60 < dt < 4 * 3600:
                DB.put_series(now, {'round:' + t['name']: dt})
        if not prev or prev[1] == 'weg':
            _round_start[t['name']] = (now, 'da')
    for t in live.get('trains', []):                  # Abfahrt vom ersten Halt merken
        p = _round_start.get(t['name'])
        if p and p[1] == 'da' and not (t.get('docked') and t.get('station') == (t.get('stops') or [None])[0]):
            _round_start[t['name']] = (p[0], 'weg')


def train_transfers(live):
    """Tatsächlich umgeschlagene Ware je Bahnhof: Ladungsänderung eines angedockten Zugs zwischen zwei Abfragen.

    Zunahme = am Bahnhof beladen, Abnahme = entladen. Summiert als Zeitreihe `train:<Bahnhof>:<+|->:<Ware>`
    (Menge je Minute) — daraus rechnet die Logistik-Seite den echten Durchsatz der letzten Stunden.
    """
    if paused():
        return
    now = int(time.time())
    add = collections.Counter()
    for t in live.get('trains', []):
        cur, st = t.get('cargo') or {}, t.get('station')
        prev = _cargo_prev.get(t['name'])
        _cargo_prev[t['name']] = (cur, st, t.get('docked'))
        if not prev or not st or not t.get('docked') or prev[1] != st:
            continue
        for it in set(cur) | set(prev[0]):
            d = cur.get(it, 0) - prev[0].get(it, 0)
            if abs(d) >= 1:
                add['train:%s:%s:%s' % (st, '+' if d > 0 else '-', it)] += abs(d)
    if add:
        t = now // 60 * 60
        with DB.lock:
            for k, v in add.items():   # innerhalb der Minute aufsummieren
                DB.db.execute('INSERT INTO series_min VALUES (?,?,?) ON CONFLICT(key, t) DO UPDATE SET v = v + excluded.v', (k, t, v))


# ---------------------------------------------------------------- Fahrplan-Prüfung
def schedule_check():
    """Je Zug- und Truck-Route: Kapazität (Ladung je Runde ÷ Rundenzeit) gegen Bedarf der Ware in der Fabrik.

    Zug: Rundenzeit gemessen (Median der letzten Runden, sonst unbekannt), Ladung = Wagen × 32 Stapel bzw. 1600 m³.
    Truck: Rundenzeit aus dem Save (AverageTimeBetweenDocks), Ladung = 48 Stapel (Traktor 25).
    Bedarf = Verbrauch der Ware in der Warenbilanz; Auslastung = gemessener Durchsatz ÷ Kapazität, wo vorhanden.
    """
    import factory as F
    stack = {v['name']: (v['stackSize'], v['liquid']) for v in F.ITEMS.values()}
    machines = (ST.factory or {}).get('machines', [])
    st_pos = {s['name']: (s['pos'][0] / 100, s['pos'][1] / 100, s['mode'])
              for s in (ST.stations or {}).get('trucks', []) + (ST.stations or {}).get('trains', [])}

    def demand(item, unload_names, r=250.0):
        """Bedarf bei Volllast: Soll-Verbrauch der Maschinen im Umkreis der Entladestationen (Fabrik dahinter)."""
        pts = [st_pos[n][:2] for n in unload_names if n in st_pos]
        if not pts:
            return None
        tot = 0.0
        for mm in machines:
            i = next((x for x in mm['inp'] if x['item'] == item), None)
            if i and any((mm['pos'][0] - x) ** 2 + (mm['pos'][1] - y) ** 2 <= r * r for x, y in pts):
                tot += i['max']
        return tot or None
    out = []
    now = int(time.time())
    for t in (ST.live or {}).get('trains', []):
        with DB.lock:
            rs = [r[0] for r in DB.db.execute("SELECT v FROM series_min WHERE key=? AND t>=? ORDER BY t DESC LIMIT 5",
                                              ('round:' + t['name'], now - 48 * 3600))]
        rnd = sorted(rs)[len(rs) // 2] if rs else None
        items = sorted((t.get('cargo') or {}).items(), key=lambda kv: -kv[1])
        wag = t.get('wagons') or 0
        caps = []
        # Wagen je Ware aus der Ladung: Menge ÷ Wagenkapazität, aufgerundet; Rest der Wagen gleichmäßig verteilt
        need_w = {it: max(1, math.ceil(a / (1600 if stack.get(it, (100, False))[1] else 32 * stack.get(it, (100, False))[0]))) for it, a in items}
        spare = max(0, wag - sum(need_w.values()))
        for it, _ in items:
            st, liq = stack.get(it, (100, False))
            w = need_w[it] + (spare // max(1, len(items)))
            caps.append(dict(item=it, per_round=w * (1600 if liq else 32 * st)))
        with DB.lock:
            meas = dict(DB.db.execute("SELECT substr(key, length('train:') + 1), SUM(v) FROM series_min WHERE key LIKE 'train:%' AND t >= ? GROUP BY key",
                                      (now - 24 * 3600,)).fetchall())
        flows = []
        for c in caps:
            cap = c['per_round'] / (rnd / 60) if rnd else None
            moved = sum(v for k, v in meas.items() if k.endswith(':+:' + c['item']) and k.split(':')[0] in (t.get('stops') or [])) / (24 * 60)
            unload = [n for n in (t.get('stops') or []) if st_pos.get(n, (0, 0, 'load'))[2] in ('unload', 'mixed')]
            need = demand(c['item'], unload)
            flows.append(dict(item=c['item'], cap=round(cap, 1) if cap else None, moved=round(moved, 1) if moved else None,
                              need=round(need, 1) if need else None))
        out.append(dict(kind='zug', name=t['name'], stops=t.get('stops') or [], round=round(rnd) if rnd else None,
                        rounds_measured=len(rs), flows=flows, wagons=wag))
    for s in (ST.stations or {}).get('trucks', []):
        for v in s.get('vehicles', []):
            if s['mode'] != 'load' or not s['items'] or not v.get('round'):
                continue
            it = s['items'][0]['item']
            st, liq = stack.get(it, (100, False))
            slots = 25 if v['type'] == 'Traktor' else 48
            cap = slots * st / (v['round'] / 60)
            partners = [o['name'] for o in (ST.stations or {}).get('trucks', [])
                        if o['mode'] == 'unload' and any(x['id'] == v['id'] for x in o.get('vehicles', []))]
            need = demand(it, partners)
            name = next((x['name'] for x in (ST.live or {}).get('trucks', []) if x.get('id') == v['id']), v['type'] + ' ' + v['id'].split('_')[-1])
            out.append(dict(kind='truck', name=name, stops=[s['name']] + partners, round=v['round'], rounds_measured=None, wagons=None,
                            flows=[dict(item=it, cap=round(cap, 1), moved=None, need=round(need, 1) if need else None)]))
    # Bewertung: Kapazität < Bedarf → Engpass (sofern die Route die einzige Quelle ist, ist das echt; sonst Hinweis)
    for r in out:
        for f in r['flows']:
            f['verdict'] = ('unbekannt' if not f['cap'] else 'engpass' if f['need'] and f['cap'] < f['need'] * .9
                            else 'knapp' if f['need'] and f['cap'] < f['need'] * 1.1 else 'ok')
    return out
