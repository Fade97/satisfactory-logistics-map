"""Logistics: fill levels, train throughput and round times, schedule check."""
import collections, math, time

from gamedata import ITEMS
from .core import ST, DB, paused


STACK = {v['name']: (v['stackSize'], v['liquid']) for v in ITEMS.values()}     # item name → (stack size, fluid?)
DEFAULT_STACK = (100, False)
VEH_SLOTS = {'Truck': 48, 'Tractor': 25, 'Explorer': 24}     # keys = vehicle type values from stations.py/frm.py
TRUCK_SLOTS = 48                    # truck station (and default vehicle)
PLATFORM_SLOTS, FLUID_PLATFORM = 32, 2400      # freight platform / fluid platform (m³)
WAGON_SLOTS, FLUID_WAGON = 32, 1600            # freight wagon / fluid wagon (m³)
DEMAND_RADIUS = 250.0               # m around the unloading stations
ROUND_MIN, ROUND_MAX = 60, 4 * 3600             # s: plausible train round times


def fill_levels(data):
    """Fill level per station (0..1) and theoretical throughput per truck vehicle.

    Truck station 48 slots, freight platform 32 slots, fluid platform 2400 m³ (wiki values, constants above).
    Throughput = full load ÷ round time — an upper bound, since how full a vehicle actually
    travels is not in the save.
    """
    def cap(items, slots, fluid_cap):
        if not items:
            return None
        it = items[0]['item']
        st, liq = STACK.get(it, DEFAULT_STACK)
        c = fluid_cap if liq else slots * st
        return round(min(1.0, sum(i['amount'] for i in items) / c), 3) if c else None
    for s in data['trucks']:
        s['fill'] = cap(s['items'], TRUCK_SLOTS, 0)
        it = s['items'][0]['item'] if s['items'] else None
        st, liq = STACK.get(it, DEFAULT_STACK) if it else (0, False)
        for v in s.get('vehicles', []):
            load = VEH_SLOTS.get(v['type'], TRUCK_SLOTS) * st
            v['per_min'] = round(load / (v['round'] / 60), 1) if v['round'] > 30 and load else None
    for s in data['trains']:
        for p in s['platforms']:
            p['fill'] = cap(p['items'], PLATFORM_SLOTS, FLUID_PLATFORM) if p['type'] != 'empty' else None


def wagon_cap(item):
    st, liq = STACK.get(item, DEFAULT_STACK)
    return FLUID_WAGON if liq else WAGON_SLOTS * st


# ---------------------------------------------------------------- train throughput
_cargo_prev = {}           # train → (cargo, station, docked) at the previous poll
_round_start = {}          # train → (round start time, 'docked' | 'away')


def train_rounds(live):
    """Measure round time per train: arrival (docked) at the first stop of the timetable until the next arrival there."""
    now = time.time()
    for t in live.get('trains', []):
        stops = t.get('stops') or []
        if not stops or not t.get('docked') or t.get('station') != stops[0]:
            continue
        prev = _round_start.get(t['name'])
        if prev and prev[1] == 'away':                   # left in between → round complete
            dt = now - prev[0]
            if ROUND_MIN < dt < ROUND_MAX:
                DB.put_series(now, {'round:' + t['name']: dt})
        if not prev or prev[1] == 'away':
            _round_start[t['name']] = (now, 'docked')
    for t in live.get('trains', []):                  # note departure from the first stop
        p = _round_start.get(t['name'])
        if p and p[1] == 'docked' and not (t.get('docked') and t.get('station') == (t.get('stops') or [None])[0]):
            _round_start[t['name']] = (p[0], 'away')


def train_transfers(live):
    """Items actually transferred per station: cargo change of a docked train between two polls.

    Increase = loaded at the station, decrease = unloaded. Summed as time series `train:<station>:<+|->:<item>`
    (amount per minute) — the logistics page derives the real throughput of the last hours from it.
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
        DB.series_add(now, add)                           # accumulate within the minute


# ---------------------------------------------------------------- schedule check
def schedule_check():
    """Per train and truck route: capacity (load per round ÷ round time) against the factory's demand for the item.

    Train: round time measured (median of the last rounds, otherwise unknown), load = wagons × 32 stacks or 1600 m³.
    Truck: round time from the save (AverageTimeBetweenDocks), load = VEH_SLOTS stacks (truck 48, tractor 25, explorer 24).
    Demand = consumption of the item in the item balance; utilisation = measured throughput ÷ capacity, where available.
    """
    machines = (ST.factory or {}).get('machines', [])
    st_pos = {s['name']: (s['pos'][0] / 100, s['pos'][1] / 100, s['mode'])
              for s in (ST.stations or {}).get('trucks', []) + (ST.stations or {}).get('trains', [])}

    def demand(item, unload_names, r=DEMAND_RADIUS):
        """Demand at full load: target consumption of machines around the unloading stations (the factory behind them)."""
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
    # items moved per station in the last 24 h: '<station>:<+|->:<item>' → amount
    meas = {k[len('train:'):]: v for k, v in DB.train_totals(now - 24 * 3600)}
    for t in (ST.live or {}).get('trains', []):
        rs = DB.series_last('round:' + t['name'], now - 48 * 3600, 5)
        rnd = sorted(rs)[len(rs) // 2] if rs else None
        items = sorted((t.get('cargo') or {}).items(), key=lambda kv: -kv[1])
        wag = t.get('wagons') or 0
        caps = []
        # wagons per item from the cargo: amount ÷ wagon capacity, rounded up; remaining wagons split evenly
        need_w = {it: max(1, math.ceil(a / wagon_cap(it))) for it, a in items}
        spare = max(0, wag - sum(need_w.values()))
        for it, _ in items:
            w = need_w[it] + (spare // max(1, len(items)))
            caps.append(dict(item=it, per_round=w * wagon_cap(it)))
        flows = []
        for c in caps:
            cap = c['per_round'] / (rnd / 60) if rnd else None
            moved = sum(v for k, v in meas.items() if k.endswith(':+:' + c['item']) and k.split(':')[0] in (t.get('stops') or [])) / (24 * 60)
            unload = [n for n in (t.get('stops') or []) if st_pos.get(n, (0, 0, 'load'))[2] in ('unload', 'mixed')]
            need = demand(c['item'], unload)
            flows.append(dict(item=c['item'], cap=round(cap, 1) if cap else None, moved=round(moved, 1) if moved else None,
                              need=round(need, 1) if need else None))
        out.append(dict(kind='train',                   # value matched by the frontend
                        name=t['name'], stops=t.get('stops') or [], round=round(rnd) if rnd else None,
                        rounds_measured=len(rs), flows=flows, wagons=wag))
    for s in (ST.stations or {}).get('trucks', []):
        for v in s.get('vehicles', []):
            if s['mode'] != 'load' or not s['items'] or not v.get('round'):
                continue
            it = s['items'][0]['item']
            st, liq = STACK.get(it, DEFAULT_STACK)
            cap = VEH_SLOTS.get(v['type'], TRUCK_SLOTS) * st / (v['round'] / 60)
            partners = [o['name'] for o in (ST.stations or {}).get('trucks', [])
                        if o['mode'] == 'unload' and any(x['id'] == v['id'] for x in o.get('vehicles', []))]
            need = demand(it, partners)
            name = next((x['name'] for x in (ST.live or {}).get('trucks', []) if x.get('id') == v['id']), v['type'] + ' ' + v['id'].split('_')[-1])
            out.append(dict(kind='truck', name=name, stops=[s['name']] + partners, round=v['round'], rounds_measured=None, wagons=None,
                            flows=[dict(item=it, cap=round(cap, 1), moved=None, need=round(need, 1) if need else None)]))
    # verdict: capacity < demand → bottleneck (real if the route is the only source; otherwise a hint)
    for r in out:
        for f in r['flows']:
            f['verdict'] = ('unknown' if not f['cap'] else 'bottleneck' if f['need'] and f['cap'] < f['need'] * .9
                            else 'tight' if f['need'] and f['cap'] < f['need'] * 1.1 else 'ok')
    return out
