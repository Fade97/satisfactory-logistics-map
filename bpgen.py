"""Blueprints aus dem Rechner: je Rezeptschritt ein Blueprint mit N Maschinen, Rezept und Takt gesetzt.

Ansatz: nichts neu verdrahten. Vorlage ist ein vollständiges, im Spiel bewährtes Spieler-Blueprint
(gamedata/templates/*.sbp) mit K Maschinen in Zeilen zu je zwei:
    Splitter ─ Maschine ─ Merger ─ Maschine ─ Splitter
Braucht der Plan n ≤ K Maschinen, werden überzählige Maschinen entfernt (von hinten, Zeile für Zeile).
Ihre Zuleitungsbänder bleiben liegen und enden offen — das Spiel verteilt dann eben weniger.
Allen übrigen Maschinen wird das Rezept gesetzt; volle Maschinen laufen auf `full_clock`, die letzte auf `clock`.

Nur Constructor und Smelter (je ein Ein- und Ausgang). Alles andere lehnt der Generator ab.
Status: EXPERIMENTELL — nicht im Spiel geprüft. Ausgabe in out/rechner/, nicht automatisch auf den Server.
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
    """step = Rechner-Schritt (cls, building, machines, full_clock, clock). Liefert (Pfad, Info)."""
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
    # Reihenfolge: Zeile für Zeile (y), in der Zeile links nach rechts — entfernt wird von hinten
    machines.sort(key=lambda h: (round(h['pos'][1]), h['pos'][0]))
    n = math.ceil(step['machines'] - 1e-6)
    if n > len(machines):
        raise BpError('%d machines needed, the template has %d. Place several blueprints side by side (%d each).'
                      % (n, len(machines), len(machines)))
    drop = {h['name'] for h in machines[n:]}
    keep = [h['name'] for h in machines[:n]]
    # Objekte der entfernten Maschinen (Actor + Komponenten) weglassen, Verweise darauf lösen
    gone = lambda path: any(path.startswith(d + '.') or path == d for d in drop)
    # Stromleitungen führen ihre beiden Endpunkte im Rohtrail (nicht als Property): Leitungen zu einer
    # entfernten Maschine mit entfernen, sonst hängt ein halbes Kabel im Blueprint
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
            if p['name'] == 'mWires':                       # Stromkabel zur entfernten Maschine
                p['value'] = [w for w in p['value'] if not gone(w[1])]
    clock_full = step['full_clock'] / 100.0
    clock_last = (step['clock'] / 100.0) if step.get('clock') else clock_full
    for h, o in zip(hs, os_):
        if h['type'] == 1 and h['name'] in keep:
            _set_machine(o['obj'], RPATH[recipe], clock_last if h['name'] == keep[-1] else clock_full)
    H2 = dict(H)
    H2['recipes'] = [r for r in H['recipes']]            # Gebäuderezepte der Vorlage bleiben gültig
    os.makedirs(OUT, exist_ok=True)
    label = '%s %dx%s' % (R['name'], n, (' %d%%' % step['full_clock']) if step['full_clock'] != 100 else '')
    fn = re.sub(r'[^\w äöüÄÖÜß.,%+-]', '', label).strip()[:60]
    path = os.path.join(OUT, fn + '.sbp')
    sbp.save(path, H2, dict(B, headers=hs, objs=os_))
    gen.write_cfg(path + 'cfg', 'Rechner: %s, %d Maschinen. Experimentell — erst testen.' % (R['name'], n), src=tpl + 'cfg')
    # Gegenprobe: neu einlesen, alles muss sich parsen und byte-genau zurückschreiben lassen
    H3, B3 = sbp.load(path)
    bad = sum(1 for o in B3['objs'] if o.get('obj') is None)
    if bad:
        raise BpError('Generated blueprint has %d unreadable objects' % bad)
    # kein Objekt darf mehr auf etwas Entferntes zeigen (Properties und Rohtrails, byte-genau geprüft)
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
            print('übersprungen:', e)
