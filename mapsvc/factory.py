"""Factory: item balance, block reason, publishing + history, factory clusters."""
import collections

from factory import EXTRACT
from .core import ST, DB, paused


# ================================================================ factory (FRM or save) → balance, power, history
def balance(machines, generators=()):
    """Balance per item: actual (current rate) and target (maximum at 100 % uptime).

    Power plants count as consumers of their fuel — otherwise Fuel would look like a surplus
    even though almost all of it is burned.
    """
    B = collections.defaultdict(lambda: dict(prod=0.0, cons=0.0, prod_max=0.0, cons_max=0.0, n_prod=0, n_cons=0))
    for g in generators:
        # HUB biomass burners are filled by hand — not part of the factory balance
        if 'Integrated' in (g.get('cls') or ''):
            continue
        if g.get('fuel') and g.get('fuel_rate'):
            b = B[g['fuel']]; b['cons_max'] += g['fuel_rate']; b['n_cons'] += 1
            if g.get('producing'):
                b['cons'] += g['fuel_rate']
    for m in machines:
        for o in m.get('out', []):
            b = B[o['item']]; b['prod'] += o.get('rate') or 0; b['prod_max'] += o.get('max') or 0; b['n_prod'] += 1
        for i in m.get('inp', []):
            b = B[i['item']]; b['cons'] += i.get('rate') or 0; b['cons_max'] += i.get('max') or 0; b['n_cons'] += 1
    return [dict(item=k, **{a: round(v, 2) if isinstance(v, float) else v for a, v in b.items()})
            for k, b in sorted(B.items())]


def block_kind(m):
    """Classify a stopped machine: 'full' = output full (buffer, intended), 'starved' = input missing.

    The German prefixes ('Ausgang voll', 'fehlt') match reasons stored before the switch to English texts.
    """
    if m['state'] not in ('stopped', 'partial'):
        return None
    w = m.get('why') or ''
    return ('full' if w.startswith(('Output full', 'Ausgang voll')) else 'starved' if w.startswith(('Missing', 'fehlt'))
            else 'unknown')


def publish_factory(fac, source, t):
    ST.factory, ST.factory_source = fac, source
    for m in fac['machines']:
        m['block'] = block_kind(m)
        m['nopower'] = m.get('circuit') in (None, -1) and m['cls'] not in ('Build_GeneratorFuel_C',)
        if m['nopower'] and m['state'] in ('stopped', 'partial', 'off'):
            m['why'] = 'No power — not connected to a power grid'
            m['block'] = 'starved'
    # hide empty grids (FRM reports all 75 circuit groups)
    fac['circuits'] = [c for c in fac['circuits'] if c.get('cap') or c.get('n_mach') or c.get('use')]
    if source == 'save':
        ST.save_factory = fac
    for g in fac['generators']:                   # fuel runtime left in the building buffer
        if g.get('fuel_rate') and g.get('stock') and g.get('producing'):
            g['fuel_minutes'] = round(sum(s['amount'] or 0 for s in g['stock'] if s['item'] == g.get('fuel')) / g['fuel_rate'])
    bal = balance(fac['machines'], fac['generators'])
    out = dict(source=source, at=int(t), machines=fac['machines'], generators=fac['generators'],
               batteries=fac.get('batteries', []), circuits=fac['circuits'], balance=bal,
               factories=clusters(fac['machines'], (getattr(ST, 'save_factory', None) or {}).get('links') or fac.get('links')))
    ST.put('factory', out)
    record(out, t)
    from .events import factory_events      # late import: events needs factory.balance
    factory_events(out, t)


def record(fac, t):
    if paused():
        return
    v = {}
    for b in fac['balance']:
        v['prod:' + b['item']] = b['prod']; v['cons:' + b['item']] = b['cons']
    for c in fac['circuits']:
        k = 'power:%s:' % c['id']
        v[k + 'prod'] = c['prod']; v[k + 'use'] = c['use']; v[k + 'cap'] = c['cap']
        if c.get('battery_cap'):
            v[k + 'battery'] = c['battery']
    st = collections.Counter(m['state'] for m in fac['machines'])
    for s in ('running', 'partial', 'stopped', 'paused', 'off'):
        v['machines:' + s] = st.get(s, 0)
    DB.put_series(t, v)


# ---------------------------------------------------------------- factory clusters
def clusters(machines, links=None, eps=60.0):
    """Group machines into factories.

    With belt connections from the save (`links`): machines are connected if a belt/pipe joins them with no
    storage in between; if two machines are more than 10 m apart vertically, the link only counts when one
    actually supplies the other (otherwise manifold belts across floors merge everything).
    Without `links` (FRM only): proximity (single linkage, eps metres) as a fallback.
    Key = smallest machine ID in the group — stays stable so renames persist.
    """
    pts = [m for m in machines if m['state'] != 'off' or m.get('recipe')]
    idx = {m['id']: i for i, m in enumerate(pts)}
    parent = list(range(len(pts)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj
    if links:
        for a, b in links:
            if a not in idx or b not in idx:
                continue
            ma, mb = pts[idx[a]], pts[idx[b]]
            if abs((ma.get('z') or 0) - (mb.get('z') or 0)) > 10:
                oa = {o['item'] for o in ma['out']}; ia = {i['item'] for i in ma['inp']}
                ob = {o['item'] for o in mb['out']}; ib = {i['item'] for i in mb['inp']}
                if not (oa & ib or ob & ia):
                    continue
            union(idx[a], idx[b])
        # attach unconnected single machines to the nearest group within 30 m (water pumps, hand-fed machines)
        eps = 30.0
    grid = collections.defaultdict(list)
    for i, m in enumerate(pts):
        grid[(int(m['pos'][0] // eps), int(m['pos'][1] // eps))].append(i)
    sizes = collections.Counter(find(i) for i in range(len(pts)))
    for (gx, gy), ids in grid.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((gx + dx, gy + dy), ()):
                    for i in ids:
                        if i >= j:
                            continue
                        if links and sizes[find(i)] > 1 and sizes[find(j)] > 1:
                            continue            # do not merge two real belt groups by proximity
                        a, b = pts[i]['pos'], pts[j]['pos']
                        if (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 <= eps * eps:
                            union(i, j)
                            sizes = collections.Counter(find(k) for k in range(len(pts))) if links else sizes
    groups = collections.defaultdict(list)
    for i in range(len(pts)):
        groups[find(i)].append(pts[i])
    names = DB.factory_names()
    out = []
    for g in groups.values():
        if len(g) < 3:
            continue
        key = min(m['id'] for m in g)
        prod, cons, pmax, cmax = (collections.Counter() for _ in range(4))
        for m in g:
            for o in m['out']:
                prod[o['item']] += o['rate']; pmax[o['item']] += o['max']
            for i in m['inp']:
                cons[i['item']] += i['rate']; cmax[i['item']] += i['max']
        net_out = {k: v - cons.get(k, 0) for k, v in prod.items() if v - cons.get(k, 0) > 0.05}
        net_in = {k: v - prod.get(k, 0) for k, v in cons.items() if v - prod.get(k, 0) > 0.05}
        # name from the target (max), not the actual rate — otherwise a stopped factory gets a random name
        target = {k: v - cmax.get(k, 0) for k, v in pmax.items() if v - cmax.get(k, 0) > 0.05}
        # raw resources (from extractors) only as the name if the group makes nothing else
        raw = {o['item'] for m in g if (m.get('recipe') or '').startswith(EXTRACT) for o in m['out']}
        made = {k: v for k, v in target.items() if k not in raw} or target
        # weighting by quantity would always put Screws first — weight by number of machines producing it
        nmach = collections.Counter(o['item'] for m in g for o in m['out'][:1])
        main = max(made, key=lambda k: (nmach.get(k, 0), made[k])) if made else (g[0].get('recipe') or g[0]['name'])
        xs, ys = [m['pos'][0] for m in g], [m['pos'][1] for m in g]
        st = collections.Counter(m['state'] for m in g)
        blk = collections.Counter(m.get('block') for m in g if m['state'] == 'stopped')
        auto = main + (' Mining' if all(m['recipe'] and m['recipe'].startswith(EXTRACT) for m in g) else ' Factory')
        nm = names.get(key)
        out.append(dict(key=key, name=(nm or {}).get('name') or auto, auto=auto, renamed=bool(nm and nm.get('name')),
                        status=(nm or {}).get('status') or 'active',
                        n=len(g), ids=[m['id'] for m in g], box=[min(xs), min(ys), max(xs), max(ys)],
                        center=[round(sum(xs) / len(xs)), round(sum(ys) / len(ys))],
                        states=dict(st), starved=blk.get('starved', 0), full=blk.get('full', 0), power=round(sum(m['power'] for m in g), 1),
                        out=sorted([dict(item=k, rate=round(v, 1)) for k, v in net_out.items()], key=lambda x: -x['rate'])[:8],
                        inp=sorted([dict(item=k, rate=round(v, 1)) for k, v in net_in.items()], key=lambda x: -x['rate'])[:8]))
    out.sort(key=lambda f: -f['n'])
    # number identical auto names (west to east) so they can be told apart
    same = collections.defaultdict(list)
    for f in out:
        same[f['auto']].append(f)
    for fs in same.values():
        if len(fs) > 1:
            for i, f in enumerate(sorted(fs, key=lambda f: f['center'][0]), 1):
                f['auto'] = '%s %d' % (f['auto'], i)
                if not f['renamed']:
                    f['name'] = f['auto']
    return out
