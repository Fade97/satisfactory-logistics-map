"""Produktionsrechner: „Ich will X/min von Y“ → Rezeptkette, Maschinen, Strom, Rohstoffe.

Lineares Programm (scipy HiGHS), wie die bekannten Community-Planer:
  Variablen   x_r ≥ 0   Rezeptläufe je Minute (Rezept r läuft x_r-mal pro Minute)
              s_i ≥ 0   Rohstoff i aus Knoten (Extraktion, /min)
              u_i ≥ 0   genutzter Überschuss der bestehenden Fabrik (/min, gedeckelt)
  Bilanz je Ware:   Σ_r (out_ri − in_ri)·x_r + s_i + u_i ≥ Ziel_i   (Nebenprodukte dürfen übrig bleiben)
  Ziel:       min Σ s_i · Gewicht_i + ε·Σ Maschinen   — Gewicht = Knappheit auf der Karte
Nur freigeschaltete Rezepte (aus dem Save), einzelne abwählbar.
"""
import collections, math
import numpy as np
from scipy.optimize import linprog

import factory

GD = factory.GD
ITEMS, RECIPES, BUILDINGS = GD['items'], GD['recipes'], GD['buildings']

# Weltvorrat je Rohstoff (/min, Standardwerte der Community-Planer) → seltene Rohstoffe teurer gewichten
WORLD = {'Desc_OreIron_C': 92100, 'Desc_OreCopper_C': 36900, 'Desc_Stone_C': 69300, 'Desc_Coal_C': 42300,
         'Desc_OreGold_C': 15000, 'Desc_LiquidOil_C': 12600, 'Desc_RawQuartz_C': 13500, 'Desc_Sulfur_C': 10800,
         'Desc_OreBauxite_C': 12300, 'Desc_OreUranium_C': 2100, 'Desc_NitrogenGas_C': 12000, 'Desc_SAM_C': 10200,
         'Desc_Water_C': 9007199254740991}
RAW = set(WORLD)


def unlocked(S):
    """Klassennamen der freigeschalteten Maschinenrezepte (Standard + Alternativ) laut Save.

    Grundrezepte (Iron Ingot, Iron Plate, Residual Plastic …) hängen an keinem Meilenstein im Datensatz —
    sie gehören zum Start bzw. entstehen als Nebenprodukt-Rezept. Deshalb: alle Nicht-Alternativrezepte ohne
    freischaltendes Schematic plus alles, was im Save gerade in einer Maschine eingestellt ist.
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
    """Für die Website: produzierbare Waren und die freigeschalteten Rezepte je Ware."""
    items = collections.defaultdict(list)
    for r in rec:
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
    """MW einer Maschine bei Taktrate clock (1.0 = 100 %), Exponent aus den Spieldaten (1,32)."""
    return meta.get('powerConsumption', 0) * clock ** meta.get('powerConsumptionExponent', 1.321929)


def solve(targets, recipes, surplus=None, exclude=(), goal='raw', max_clock=1.0, sloop=False):
    """targets: {item_key: rate/min}; recipes: erlaubte Rezeptklassen; surplus: {item_key: verfügbare Rate}.

    goal:      'raw' wenig Rohstoffe (nach Knappheit gewichtet) · 'machines' wenig Maschinen · 'power' wenig Strom
    max_clock: höchste Taktrate je Maschine (1,0 … 2,5 mit Power Shards) — weniger Maschinen, mehr Strom je Stück
    sloop:     Somersloops in allen Maschinen: doppelte Ausgabe bei gleichem Input, Strom ×4 (Spielwerte 1.0)
    """
    rs = [r for r in sorted(recipes) if r not in exclude and not RECIPES[r].get('forBuilding')]
    rs = [r for r in rs if 'Desc_' + 'Converter' not in RECIPES[r]['producedIn'][0]]   # Konverter-Kreisläufe meiden
    items = sorted({x['item'] for r in rs for x in RECIPES[r]['ingredients'] + RECIPES[r]['products']} | set(targets))
    ix = {k: i for i, k in enumerate(items)}
    raw = [k for k in items if k in RAW]
    sur = [k for k in items if surplus and surplus.get(k, 0) > 0.01]
    n_r, n_s, n_u = len(rs), len(raw), len(sur)
    boost = 2.0 if sloop else 1.0
    # A_ub · v ≤ b_ub  mit  −Bilanz ≤ −Ziel
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

    # Kosten je Rezeptlauf/min: Maschinen = Läufe ÷ (Läufe je Maschine bei max. Takt), Strom = Maschinen × MW
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
    c = np.concatenate([c_r, c_s, np.full(n_u, 1e-5)])   # Überschüsse fast kostenlos
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
        n = x[j] / per_m[j]                               # Maschinen bei max. Takt
        bdesc = BUILDINGS.get(R['producedIn'][0], {})
        meta = bdesc.get('metadata', {})
        full, frac = int(math.floor(n + 1e-6)), n - math.floor(n + 1e-6)
        # volle Maschinen auf max_clock, die letzte auf den Rest
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
    import sys, json
    S = factory.Save('saves/latest.sav')
    rec = unlocked(S)
    what = sys.argv[1] if len(sys.argv) > 1 else 'Steel Beam'
    rate = float(sys.argv[2]) if len(sys.argv) > 2 else 60
    r = solve({item_key(what): rate}, rec)
    print(json.dumps(r, ensure_ascii=False, indent=1))
