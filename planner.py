"""Production planner: "I want X/min of Y" → recipe chain, machines, power, raw resources.

Linear program (scipy HiGHS), like the well-known community planners:
  variables   x_r ≥ 0   recipe runs per minute (recipe r runs x_r times per minute)
              s_i ≥ 0   raw resource i from nodes (extraction, /min)
              u_i ≥ 0   used surplus of the existing factory (/min, capped)
  balance per item:   Σ_r (out_ri − in_ri)·x_r + s_i + u_i ≥ target_i   (byproducts may be left over)
  objective:  min Σ s_i · weight_i + ε·Σ machines   — weight = scarcity on the map
Only unlocked recipes (from the save); individual recipes can be excluded.
"""
import collections, math
import numpy as np
from scipy.optimize import linprog

import gamedata
from gamedata import GD, ITEMS, RECIPES, BUILDINGS

# world supply per raw resource (/min, default values of the community planners) → weight rare resources higher
WORLD = {'Desc_OreIron_C': 92100, 'Desc_OreCopper_C': 36900, 'Desc_Stone_C': 69300, 'Desc_Coal_C': 42300,
         'Desc_OreGold_C': 15000, 'Desc_LiquidOil_C': 12600, 'Desc_RawQuartz_C': 13500, 'Desc_Sulfur_C': 10800,
         'Desc_OreBauxite_C': 12300, 'Desc_OreUranium_C': 2100, 'Desc_NitrogenGas_C': 12000, 'Desc_SAM_C': 10200,
         'Desc_Water_C': 9007199254740991}
RAW = set(WORLD)


def unlocked(S):
    """Class names of the unlocked machine recipes (standard + alternate) according to the save.

    Basic recipes (Iron Ingot, Iron Plate, Residual Plastic …) are not tied to any milestone in the dataset —
    they are available from the start or come as byproduct recipes. Hence: all non-alternate recipes without
    an unlocking schematic, plus everything currently set in a machine in the save.
    """
    sm = S.props(S.by['BP_SchematicManager_C'][0]) if S.by['BP_SchematicManager_C'] else {}
    granted = {r for sc in GD['schematics'].values() for r in sc['unlock'].get('recipes', [])}
    out = {r for r, R in RECIPES.items() if R['inMachine'] and R['producedIn'] and not R['alternate'] and r not in granted}
    for n in S.classes(lambda c: c.startswith('Build_')):
        if b'mCurrentRecipe' in S.idx[n][1]:
            r = (S.props(n).get('mCurrentRecipe') or ['', ''])[1].split('.')[-1]
            if r in RECIPES:
                out.add(r)
    for _, p in sm.get('mPurchasedSchematics', []):
        sc = GD['schematics'].get(p.split('.')[-1])
        for r in (sc or {}).get('unlock', {}).get('recipes', []):
            if r in RECIPES and RECIPES[r]['inMachine'] and RECIPES[r]['producedIn']:
                out.add(r)
    return out


def recipe_list(rec):
    """For the website: producible items and the unlocked recipes per item."""
    items = collections.defaultdict(list)
    for r in sorted(rec, key=lambda r: (RECIPES[r]['alternate'], RECIPES[r]['name'])):   # stable: standard first, then by name
        R = RECIPES[r]
        for p in R['products']:
            items[p['item']].append(dict(cls=r, name=R['name'], alt=R['alternate']))
    return sorted([dict(key=k, item=ITEMS[k]['name'], fluid=ITEMS[k]['liquid'], recipes=v)
                   for k, v in items.items() if k in ITEMS], key=lambda x: x['item'])


def item_key(name_or_key):
    if name_or_key in ITEMS:
        return name_or_key
    for k, v in ITEMS.items():
        if v['name'].lower() == str(name_or_key).lower():
            return k
    raise KeyError(name_or_key)


def _power(meta, clock):
    """MW of a machine at clock speed clock (1.0 = 100 %), exponent from the game data (1.32)."""
    return meta.get('powerConsumption', 0) * clock ** meta.get('powerConsumptionExponent', gamedata.POWER_EXPONENT)


def solve(targets, recipes, surplus=None, exclude=(), goal='raw', max_clock=1.0, sloop=False):
    """targets: {item_key: rate/min}; recipes: allowed recipe classes; surplus: {item_key: available rate}.

    goal:      'raw' few raw resources (weighted by scarcity) · 'machines' few machines · 'power' little power
    max_clock: highest clock speed per machine (1.0 … 2.5 with Power Shards) — fewer machines, more power each
    sloop:     Somersloops in all machines: double output for the same input, power ×4 (game values 1.0)
    """
    rs = [r for r in sorted(recipes) if r not in exclude and not RECIPES[r].get('forBuilding')]
    rs = [r for r in rs if 'Desc_Converter' not in RECIPES[r]['producedIn'][0]]   # avoid converter loops
    items = sorted({x['item'] for r in rs for x in RECIPES[r]['ingredients'] + RECIPES[r]['products']} | set(targets))
    ix = {k: i for i, k in enumerate(items)}
    raw = [k for k in items if k in RAW]
    sur = [k for k in items if surplus and surplus.get(k, 0) > 0.01]
    n_r, n_s, n_u = len(rs), len(raw), len(sur)
    boost = 2.0 if sloop else 1.0
    # A_ub · v ≤ b_ub  with  −balance ≤ −target
    A = np.zeros((len(items), n_r + n_s + n_u))
    for j, r in enumerate(rs):
        R = RECIPES[r]
        for p in R['products']:
            A[ix[p['item']], j] += p['amount'] * boost
        for i in R['ingredients']:
            A[ix[i['item']], j] -= i['amount']
    for j, k in enumerate(raw):
        A[ix[k], n_r + j] = 1
    for j, k in enumerate(sur):
        A[ix[k], n_r + n_s + j] = 1
    b = np.array([targets.get(k, 0.0) for k in items])

    # cost per recipe run/min: machines = runs ÷ (runs per machine at max clock), power = machines × MW
    per_m = np.array([60.0 / RECIPES[r]['time'] * max_clock for r in rs])
    mw = np.array([_power(BUILDINGS.get(RECIPES[r]['producedIn'][0], {}).get('metadata', {}), max_clock) * (4 if sloop else 1) for r in rs])
    wmax = max(v for k, v in WORLD.items() if k != 'Desc_Water_C')
    raw_w = np.array([(wmax / WORLD[k]) if k != 'Desc_Water_C' else 1e-3 for k in raw])
    if goal == 'machines':
        c_r, c_s = 1.0 / per_m, raw_w * 1e-4
    elif goal == 'power':
        c_r, c_s = mw / per_m, raw_w * 1e-3
    else:
        c_r, c_s = 1e-4 / per_m, raw_w
    c = np.concatenate([c_r, c_s, np.full(n_u, 1e-5)])   # surpluses almost free
    bounds = [(0, None)] * (n_r + n_s) + [(0, surplus[k]) for k in sur]
    res = linprog(c, A_ub=-A, b_ub=-b, bounds=bounds, method='highs')
    if not res.success:
        return dict(ok=False, error='Not possible with the allowed recipes' if res.status == 2 else res.message)
    x = res.x
    steps = []
    for j, r in enumerate(rs):
        if x[j] < 1e-7:
            continue
        R = RECIPES[r]
        n = x[j] / per_m[j]                               # machines at max clock
        bdesc = BUILDINGS.get(R['producedIn'][0], {})
        meta = bdesc.get('metadata', {})
        full, frac = int(math.floor(n + 1e-6)), n - math.floor(n + 1e-6)
        # full machines at max_clock, the last one at the remainder
        power = (full * _power(meta, max_clock) + (_power(meta, frac * max_clock) if frac > 1e-3 else 0)) * (4 if sloop else 1)
        steps.append(dict(recipe=R['name'], cls=r, alt=R['alternate'], building=bdesc.get('name', R['producedIn'][0]),
                          machines=round(n, 3), full=full, full_clock=round(max_clock * 100),
                          clock=round(frac * max_clock * 100, 1) if frac > 1e-3 else None,
                          power=round(power, 1),
                          out=[dict(item=ITEMS[p['item']]['name'], rate=round(p['amount'] * boost * x[j], 3)) for p in R['products']],
                          inp=[dict(item=ITEMS[i['item']]['name'], rate=round(i['amount'] * x[j], 3)) for i in R['ingredients']]))
    raws = [dict(item=ITEMS[k]['name'], key=k, rate=round(x[n_r + j], 3)) for j, k in enumerate(raw) if x[n_r + j] > 1e-6]
    used = [dict(item=ITEMS[k]['name'], rate=round(x[n_r + n_s + j], 3), available=round(surplus[k], 2))
            for j, k in enumerate(sur) if x[n_r + n_s + j] > 1e-6]
    bal = collections.defaultdict(float)
    for j, r in enumerate(rs):
        for p in RECIPES[r]['products']:
            bal[p['item']] += p['amount'] * boost * x[j]
        for i in RECIPES[r]['ingredients']:
            bal[i['item']] -= i['amount'] * x[j]
    by = [dict(item=ITEMS[k]['name'], rate=round(v - targets.get(k, 0), 3)) for k, v in bal.items()
          if v - targets.get(k, 0) > 0.01 and k not in RAW]
    n_mach = sum(math.ceil(s['machines'] - 1e-6) for s in steps)
    return dict(ok=True, steps=sorted(steps, key=lambda s: -s['machines']), raw=raws, surplus_used=used, byproducts=by,
                power=round(sum(s['power'] for s in steps), 1), machines=n_mach,
                shards=(n_mach * math.ceil((max_clock - 1) / .5 - 1e-9)) if max_clock > 1 else 0,
                sloops=n_mach if sloop else 0, goal=goal, max_clock=max_clock,
                targets=[dict(item=ITEMS[k]['name'], rate=v) for k, v in targets.items()])


if __name__ == '__main__':
    import sys, json, factory
    S = factory.Save('saves/latest.sav')
    rec = unlocked(S)
    what = sys.argv[1] if len(sys.argv) > 1 else 'Steel Beam'
    rate = float(sys.argv[2]) if len(sys.argv) > 2 else 60
    r = solve({item_key(what): rate}, rec)
    print(json.dumps(r, ensure_ascii=False, indent=1))
