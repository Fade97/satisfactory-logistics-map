"""Blueprints from the production planner: one blueprint per recipe step with N machines, recipe and clock set.

Approach: rewire nothing. The template is a complete player blueprint proven in the game
(gamedata/templates/*.sbp) with K machines in rows of two:
    splitter ─ machine ─ merger ─ machine ─ splitter
If the plan needs n ≤ K machines, the surplus machines are removed (from the back, row by row).
Their feeder belts stay in place and end open — the game simply distributes less.
All remaining machines get the recipe; full machines run at `full_clock`, the last one at `clock`.

Constructor and Smelter only (one input and one output each). The generator rejects everything else.
Status: EXPERIMENTAL — not tested in the game. Output goes to OUT (data/blueprints/), not to the server automatically.
"""
import copy, json, math, os, re
import sbp, gen

HERE = os.path.dirname(os.path.abspath(__file__))
RPATH = json.load(open(os.path.join(HERE, 'gamedata', 'recipe_paths.json')))
TEMPLATES = {'Build_ConstructorMk1_C': '8x Constructor T5', 'Build_SmelterMk1_C': '10x Smelter T5'}
BUILD = {'Desc_ConstructorMk1_C': 'Build_ConstructorMk1_C', 'Desc_SmelterMk1_C': 'Build_SmelterMk1_C'}
OUT = os.path.join(os.environ.get('MAP_DATA', os.path.join(HERE, 'data')), 'blueprints')


class BpError(Exception):
    pass


def supported(recipe_cls):
    import planner
    R = planner.RECIPES.get(recipe_cls)
    return bool(R and BUILD.get(R['producedIn'][0]) in TEMPLATES and recipe_cls in RPATH)


def build(step):
    """step = planner step (cls, building, machines, full_clock, clock). Returns (path, info)."""
    import planner
    recipe = step['cls']
    R = planner.RECIPES[recipe]
    bcls = BUILD.get(R['producedIn'][0])
    if bcls not in TEMPLATES:
        raise BpError('No template for %s yet — only Constructor and Smelter so far.' % step['building'])
    if recipe not in RPATH:
        raise BpError('Asset path of recipe %s unknown.' % R['name'])
    tpl = os.path.join(HERE, 'gamedata', 'templates', TEMPLATES[bcls] + '.sbp')
    H, B = sbp.load(tpl)
    machines = [h for h in B['headers'] if h['type'] == 1 and h['cls'].endswith(bcls)]
    # order: row by row (y), left to right within a row — removal starts from the back
    machines.sort(key=lambda h: (round(h['pos'][1]), h['pos'][0]))
    n = math.ceil(step['machines'] - 1e-6)
    if n > len(machines):
        raise BpError('%d machines needed, the template has %d. Place several blueprints side by side (%d each).'
                      % (n, len(machines), len(machines)))
    drop = {h['name'] for h in machines[n:]}
    keep = [h['name'] for h in machines[:n]]
    # drop the objects of removed machines (actor + components), clear references to them
    gone = lambda path: any(path.startswith(d + '.') or path == d for d in drop)
    # Power lines keep their two endpoints in the raw trail (not as a property): remove lines to a
    # removed machine as well, otherwise half a cable is left dangling in the blueprint
    for h, o in zip(B['headers'], B['objs']):
        if h['type'] == 1 and h['cls'].endswith('Build_PowerLine_C') and o['obj']:
            t = o['obj']['trail']
            if any(d.encode() in t for d in drop):
                drop.add(h['name'])
    hs, os_ = [], []
    for h, o in zip(B['headers'], B['objs']):
        owner = h['name'] if h['type'] == 1 else h['outer']
        if owner in drop:
            continue
        hs.append(h); os_.append(o)
    for h, o in zip(hs, os_):
        for p in (o['obj'] or {}).get('props', []):
            if p['name'] == 'mConnectedComponent' and p['value'][1] and gone(p['value'][1]):
                p['value'] = ['', '']
            if p['name'] == 'mWires':                       # power cable to the removed machine
                p['value'] = [w for w in p['value'] if not gone(w[1])]
    clock_full = step['full_clock'] / 100.0
    clock_last = (step['clock'] / 100.0) if step.get('clock') else clock_full
    for h, o in zip(hs, os_):
        if h['type'] == 1 and h['name'] in keep:
            _set_machine(o['obj'], RPATH[recipe], clock_last if h['name'] == keep[-1] else clock_full)
    H2 = dict(H)
    H2['recipes'] = [r for r in H['recipes']]            # the template's building recipes stay valid
    os.makedirs(OUT, exist_ok=True)
    label = '%s %dx%s' % (R['name'], n, (' %d%%' % step['full_clock']) if step['full_clock'] != 100 else '')
    fn = re.sub(r'[^\w .,%+-]', '', label).strip()[:60]
    path = os.path.join(OUT, fn + '.sbp')
    sbp.save(path, H2, dict(B, headers=hs, objs=os_))
    gen.write_cfg(path + 'cfg', 'Planner: %s, %d machines. Experimental — test before use.' % (R['name'], n), src=tpl + 'cfg')
    # cross-check: re-read; everything must parse and write back byte-exactly
    H3, B3 = sbp.load(path)
    bad = sum(1 for o in B3['objs'] if o.get('obj') is None)
    if bad:
        raise BpError('Generated blueprint has %d unreadable objects' % bad)
    # no object may still point at something removed (properties and raw trails, checked byte-exactly)
    for o in B3['objs']:
        if any(d.encode() + b'.' in o['data'] or d.encode() + b'\x00' in o['data'] for d in drop):
            raise BpError('Reference to a removed object left — blueprint discarded')
    return path, dict(file=os.path.basename(path), machines=n, template=TEMPLATES[bcls], objects=len(hs))


def _set_machine(obj, recipe_path, clock):
    props = [p for p in obj['props'] if p['name'] not in ('mCurrentRecipe', 'mCurrentPotential', 'mPendingPotential')]
    props.insert(0, gen.P_obj('mCurrentRecipe', ['', recipe_path]))
    if abs(clock - 1.0) > 1e-4:
        props.insert(1, gen.P_float('mCurrentPotential', clock))
        props.insert(2, gen.P_float('mPendingPotential', clock))
    obj['props'] = props


if __name__ == '__main__':
    import sys, factory, planner
    S = factory.Save(os.path.join(HERE, 'saves', 'latest.sav'))
    r = planner.solve({planner.item_key(sys.argv[1] if len(sys.argv) > 1 else 'Iron Plate'): float(sys.argv[2]) if len(sys.argv) > 2 else 60},
                      planner.unlocked(S))
    for s in r['steps']:
        try:
            print(build(s))
        except BpError as e:
            print('skipped:', e)
