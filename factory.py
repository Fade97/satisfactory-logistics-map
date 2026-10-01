"""Factory from the save: machines with recipe and nominal rates, power grids, network geometry, resource nodes.

Provides the same as geo.py via FRM, but without the mod — plus what FRM does not know:
power grid per building, resource nodes with purity, builder, power lines.
Nominal rates come from gamedata/data1.0.json (SatisfactoryTools, MIT), node purity
from gamedata/resource_nodes.json (from satisfactory-savegame-prometheus-exporter, MIT).

    python3 factory.py [save.sav]      # short statistics
"""
import collections, json, math, os, sys
import sbp, sav, stations

EXTRACT = 'Extracting '                  # recipe name of extractors: 'Extracting Iron Ore'

HERE = os.path.dirname(os.path.abspath(__file__))
GD = json.load(open(os.path.join(HERE, 'gamedata', 'data1.0.json')))
NODES = json.load(open(os.path.join(HERE, 'gamedata', 'resource_nodes.json')))
ITEMS, RECIPES, BUILDINGS, GENS = GD['items'], GD['recipes'], GD['buildings'], GD['generators']
# node types the dataset names differently from the item
NODE_ITEM = {'Desc_LiquidOilWell_C': 'Desc_LiquidOil_C', 'Desc_Geyser_C': None}

PURITY = {0.5: 'impure', 1.0: 'normal', 2.0: 'pure'}
EXTRACTORS = {'Build_MinerMk1_C', 'Build_MinerMk2_C', 'Build_MinerMk3_C', 'Build_OilPump_C',
              'Build_WaterPump_C', 'Build_FrackingExtractor_C'}
BELT_SPEED = {'Mk1': 60, 'Mk2': 120, 'Mk3': 270, 'Mk4': 480, 'Mk5': 780, 'Mk6': 1200}
NEVER = 3e38                                   # mTimeSinceStartStopProducing if never toggled


def item(path):
    """Class name → English display name from the game data (fallback: stations.item_name)."""
    if not path:
        return None
    k = path.split('.')[-1]
    return ITEMS[k]['name'] if k in ITEMS else stations.item_name(path)


def is_fluid(path):
    k = path.split('.')[-1]
    return bool(ITEMS.get(k, {}).get('liquid'))


def building_name(cls):
    b = BUILDINGS.get(cls.replace('Build_', 'Desc_', 1))
    return b['name'] if b else cls.replace('Build_', '').rstrip('_C').replace('_', ' ')


class Save:
    """Index with class lookup and cached property dicts."""

    def __init__(self, path):
        self.path = path
        self.idx = sav.load_index(path)
        self.by = collections.defaultdict(list)
        for n, (h, _) in self.idx.items():
            self.by[sbp.short(h['cls'])].append(n)
        self._p = {}

    def props(self, n):
        if n not in self._p:
            ob = sav.obj(self.idx, n)[1] if n in self.idx else {}
            self._p[n] = {p['name']: p['value'] for p in ob.get('props', [])}
        return self._p[n]

    def raw_props(self, n):
        ob = sav.obj(self.idx, n)[1] if n in self.idx else {}
        return ob.get('props', [])

    def pos(self, n):
        return self.idx[n][0]['pos']

    def classes(self, pred):
        return [n for c, ns in self.by.items() if pred(c) for n in ns]

    def inventory(self, comp):
        """[(item path, amount)] of an FGInventoryComponent; fluids in m³."""
        out = collections.Counter()
        for st in self.props(comp).get('mInventoryStacks', []) if comp else []:
            d = {p['name']: p['value'] for p in st}
            it = (d.get('Item') or {}).get('item')
            n = d.get('NumItems', 0)
            if it and n:
                out[it] += n / 1000.0 if is_fluid(it) else n
        return list(out.items())


def _xy(p):                                      # cm → m, rounded
    return [round(p[0] / 100), round(p[1] / 100)]


def _circuits(S):
    """Component path → circuit ID (FGPowerCircuit.mComponents)."""
    comp = {}
    for n in S.by['FGPowerCircuit']:
        d = S.props(n)
        cid = d.get('mCircuitID')
        for _, path in d.get('mComponents', []):
            comp[path] = cid
    return comp


def _owner_circuit(circ, name):
    for suffix in ('.PowerInput', '.PowerConnection', '.PowerConnection1', '.SlidingShoe', '.FGPowerConnection'):
        if name + suffix in circ:
            return circ[name + suffix]
    return None


def _players(S):
    """PlayerInfoHandle bytes (BuiltBy) → player name, only if unambiguous.

    Mapping via BP_PlayerState_C.mPlatformPlayerInfoHandle → mOwnedPawn → mCachedPlayerName.
    Several PlayerStates in the save share the same handle (as of 2026-09-29: handle 0 belongs
    to two states) — such handles stay unknown rather than being assigned wrongly.
    """
    names = collections.defaultdict(set)
    for ps in S.by['BP_PlayerState_C']:
        d = S.props(ps)
        h = d.get('mPlatformPlayerInfoHandle')
        pawn = (d.get('mOwnedPawn') or ['', ''])[1]
        names[h].add(S.props(pawn).get('mCachedPlayerName') if pawn else None)
    return {h: next(iter(n)) for h, n in names.items() if h is not None and len(n) == 1 and None not in n}


def machine_state(d, rec, cls):
    """State + reason from save flags. The game measures productivity over 5-minute windows."""
    last_d = d.get('mLastProductivityMeasurementDuration') or 0
    last_p = d.get('mLastProductivityMeasurementProduceDuration') or 0
    cur_d = d.get('mCurrentProductivityMeasurementDuration') or 0
    cur_p = d.get('mCurrentProductivityMeasurementProduceDuration') or 0
    tot = last_d + cur_d
    pct = round(100 * (last_p + cur_p) / tot) if tot > 1 else 0
    if cls not in EXTRACTORS and not rec:
        return 'off', 0
    if d.get('mIsProductionPaused'):
        return 'paused', pct
    if pct >= 95:
        return 'running', pct
    if pct > 5:
        return 'partial', pct
    return 'stopped', pct


def _reason(S, name, d, rec):
    """Why is a machine stopped? Heuristic based on its inventories."""
    if not rec:
        return None
    r = RECIPES.get(rec)
    if not r:
        return None
    out_inv = dict(S.inventory((d.get('mOutputInventory') or ['', ''])[1]))
    in_inv = dict(S.inventory((d.get('mInputInventory') or ['', ''])[1]))
    for p in r['products']:
        st = ITEMS.get(p['item'], {}).get('stackSize', 100)
        have = sum(v for k, v in out_inv.items() if k.endswith(p['item']))
        cap = 50 if ITEMS.get(p['item'], {}).get('liquid') else st
        if have >= cap * 0.95:
            return 'Output full: ' + ITEMS[p['item']]['name']
    for i in r['ingredients']:
        have = sum(v for k, v in in_inv.items() if k.endswith(i['item']))
        need = i['amount']
        if have < need:
            return 'Missing: ' + ITEMS.get(i['item'], {}).get('name', i['item'])
    return None


def machines(S, circ, who):
    out = []
    kinds = set(RECIPES[r]['producedIn'][0] for r in RECIPES if RECIPES[r]['producedIn'])
    prod_cls = [c for c in S.by if c.startswith('Build_') and (c.replace('Build_', 'Desc_', 1) in kinds or c in EXTRACTORS)]
    for c in prod_cls:
        bdesc = BUILDINGS.get(c.replace('Build_', 'Desc_', 1), {})
        meta = bdesc.get('metadata', {})
        for n in S.by[c]:
            d = S.props(n)
            rec = (d.get('mCurrentRecipe') or ['', ''])[1].split('.')[-1] or None
            clock = float(d.get('mCurrentPotential') or 1.0)
            state, pct = machine_state(d, rec, c)
            qx, qy, qz, qw = S.idx[n][0]['rot']
            m = dict(id=sbp.short(n), cls=c, name=building_name(c), pos=_xy(S.pos(n)),
                     z=round(S.pos(n)[2] / 100), yaw=round(math.degrees(math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz)))), recipe=None, clock=round(clock, 3),
                     state=state, pct=pct, circuit=_owner_circuit(circ, n),
                     by=who.get(d.get('BuiltBy')), out=[], inp=[],
                     power=round(meta.get('powerConsumption', 0) * clock ** meta.get('powerConsumptionExponent', 1.321929), 1))
            if c in EXTRACTORS:
                res = (d.get('mExtractableResource') or ['', ''])[1]
                node = NODES.get(sbp.short(res).split(':')[-1]) or NODES.get(res.split('.', 1)[-1])
                mk = GD['miners'].get(c.replace('Build_', 'Desc_', 1))
                if c == 'Build_WaterPump_C':
                    it, per = 'Desc_Water_C', 120.0
                elif node and mk:
                    it = NODE_ITEM.get(node['item'], node['item'])
                    per = (mk['itemsPerCycle'] / (1000 if mk['allowLiquids'] else 1)) * 60 / mk['extractCycleTime'] * node['purity']
                else:
                    it, per = None, 0
                m['node'] = sbp.short(res) if res else None
                if node:
                    m['purity'] = PURITY.get(node['purity'])
                if it in ITEMS:
                    m['recipe'] = EXTRACT + ITEMS[it]['name']
                    m['out'] = [dict(item=ITEMS[it]['name'], max=round(per * clock, 2))]
            elif rec in RECIPES:
                r = RECIPES[rec]
                k = 60.0 / r['time'] * clock
                liq = lambda x: 1.0          # recipe amounts in the dataset are already m³ for fluids
                m['recipe'] = r['name']
                m['alt'] = bool(r.get('alternate'))
                m['out'] = [dict(item=ITEMS[p['item']]['name'], max=round(p['amount'] / liq(p['item']) * k, 2)) for p in r['products']]
                m['inp'] = [dict(item=ITEMS[i['item']]['name'], max=round(i['amount'] / liq(i['item']) * k, 2)) for i in r['ingredients']]
                if state in ('stopped', 'partial'):
                    m['why'] = _reason(S, n, d, rec)
            for x in m['out'] + m['inp']:
                x['rate'] = round(x['max'] * m['pct'] / 100.0, 2)
            since = d.get('mTimeSinceStartStopProducing')
            m['since'] = None if since is None or since > NEVER else round(since)
            out.append(m)
    return out


def generators(S, circ, who):
    out = []
    for c in [c for c in S.by if c.startswith('Build_Generator')]:
        g = GENS.get(c.replace('Build_', 'Desc_', 1)) or {}
        for n in S.by[c]:
            d = S.props(n)
            fuel = (d.get('mCurrentFuelClass') or ['', ''])[1]
            inv = S.inventory((d.get('mFuelInventory') or ['', ''])[1])
            clock = float(d.get('mCurrentPotential') or 1.0)
            cap = g.get('powerProduction', 20 if 'Biomass' in c else 0) * clock ** (1 / 1.3)  # simplified
            ev = ITEMS.get(fuel.split('.')[-1], {}).get('energyValue') if fuel else None
            # energyValue in MJ per item or per m³ → consumption/min = MW × 60 ÷ MJ
            per_min = (cap * 60 / ev) if ev else None
            state, pct = machine_state(d, 'gen', c)
            out.append(dict(id=sbp.short(n), cls=c, name=building_name(c) if 'Integrated' not in c else 'Biomass Burner (HUB)',
                            pos=_xy(S.pos(n)), circuit=_owner_circuit(circ, n),
                            cap=round(cap, 1), producing=bool(d.get('mIsProducing')) or pct > 50, pct=pct,
                            fuel=item(fuel) if fuel else None,
                            fuel_rate=round(per_min, 2) if per_min else None,
                            stock=[dict(item=item(i), amount=round(a, 1)) for i, a in inv],
                            by=who.get(d.get('BuiltBy'))))
    return out


def batteries(S, circ):
    out = []
    for n in S.by['Build_PowerStorageMk1_C']:
        d = S.props(n)
        out.append(dict(id=sbp.short(n), pos=_xy(S.pos(n)), circuit=_owner_circuit(circ, n),
                        stored=round(float(d.get('mPowerStore') or 0), 1), capacity=100.0))
    return out


def power_lines(S, circ):
    """Power lines as segments [x1,y1,x2,y2,circuit] in metres (from mWireInstances)."""
    out = []
    for n in S.by['Build_PowerLine_C'] + S.by.get('Build_XmassLightsLine_C', []):
        locs = [p['value'] for p in S.raw_props(n) if p['name'] == 'mWireInstances']
        pts = []
        for wi in locs[:1]:
            for inst in wi:
                pts += [q['value'] for q in inst if q['name'] == 'Locations']
        if len(pts) < 2:
            continue
        ob = sav.obj(S.idx, n)[1]
        cid = None
        try:                                     # trail: int32 0, (lvl, path) × 2 → connection components
            r = sbp.R(ob['trail']); r.i32(); r.s(); a = r.s()
            cid = circ.get(a)
        except Exception:
            pass
        out.append([round(pts[0][0] / 100), round(pts[0][1] / 100), round(pts[1][0] / 100), round(pts[1][1] / 100), cid])
    return out


def _spline(S, n):
    """World points (m) of the spline of a belt/pipe/rail."""
    h = S.idx[n][0]
    sp = S.props(n).get('mSplineData') or []
    x0, y0 = h['pos'][0], h['pos'][1]
    qx, qy, qz, qw = h['rot']
    yaw = math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))
    cs, sn = math.cos(yaw), math.sin(yaw)
    pts = []
    for pt in sp:
        loc = next(q['value'] for q in pt if q['name'] == 'Location')
        pts.append((round((x0 + cs * loc[0] - sn * loc[1]) / 100, 1), round((y0 + sn * loc[0] + cs * loc[1]) / 100, 1)))
    return pts


def lines(S, pred, with_ids=False):
    import geo
    out, ids = [], []
    for n in S.classes(pred):
        pts = _spline(S, n)
        if len(pts) >= 2:
            out.append([[round(x), round(y)] for x, y in geo._rdp(pts, geo.TOL)])
            ids.append(sbp.short(n))
    return (out, ids) if with_ids else out


def belt_items(S):
    """Belt ID → item currently on it (most common). Source: raw trail of the FGConveyorChainActor —
    it lists the belts of the chain and the item paths of the cargo. Empty belts are missing."""
    import re
    out = {}
    for c in [n for k, ns in S.by.items() if k.startswith('FGConveyorChainActor') for n in ns]:
        tr = sav.obj(S.idx, c)[1].get('trail', b'')
        its = collections.Counter(m.decode().split('.')[-1] for m in re.findall(rb'Desc_[A-Za-z0-9_]+\.Desc_[A-Za-z0-9_]+_C', tr))
        if not its:
            continue
        top = its.most_common(1)[0][0]
        name = ITEMS[top]['name'] if top in ITEMS else stations.item_name(top)
        for b in set(re.findall(rb'PersistentLevel\.(Build_Conveyor[A-Za-z0-9_]+)', tr)):
            out[b.decode()] = name
    return out


def pipe_items(S):
    """Pipe ID → fluid via the pipe network (FGPipeNetwork.mFluidDescriptor ↔ mPipeNetworkID of the connections)."""
    fluid = {}
    for n in S.by['FGPipeNetwork']:
        d = S.props(n)
        f = (d.get('mFluidDescriptor') or ['', ''])[1]
        if f and d.get('mPipeNetworkID') is not None:
            fluid[d['mPipeNetworkID']] = item(f)
    out = {}
    for c in S.by['FGPipeConnectionComponent']:
        nid = S.props(c).get('mPipeNetworkID')
        if nid in fluid:
            out[sbp.short(c.rsplit('.', 1)[0])] = fluid[nid]
    return out


def resource_nodes(S, extractors):
    used = {m['node']: m for m in extractors if m.get('node')}
    out = []
    for c in ('BP_ResourceNode_C', 'BP_ResourceNodeGeyser_C', 'BP_FrackingSatellite_C'):
        for n in S.by[c]:
            k = n.split('.', 1)[1]
            info = NODES.get(k) or {}
            m = used.get(sbp.short(n))
            it = NODE_ITEM.get(info.get('item'), info.get('item'))
            out.append(dict(id=sbp.short(n), pos=_xy(S.pos(n)),
                            item=ITEMS[it]['name'] if it in ITEMS else ('Geyser' if 'Geyser' in c else None),
                            purity=PURITY.get(info.get('purity')), kind='geyser' if 'Geyser' in c else 'well' if 'Fracking' in c else 'node',
                            used=bool(m), extractor=m['name'] if m else None, rate=m['out'][0]['max'] if m and m['out'] else None))
    return out


def circuits(mach, gens, bats):
    """Power grids: nominal machine consumption vs. generation from the save."""
    C = collections.defaultdict(lambda: dict(prod=0.0, cap=0.0, use=0.0, max_use=0.0, n_mach=0, n_gen=0, battery=0.0, battery_cap=0.0))
    for m in mach:
        c = C[m['circuit']]
        c['n_mach'] += 1
        c['max_use'] += m['power']
        c['use'] += m['power'] * (m['pct'] / 100.0 if m['state'] != 'off' else 0)
    for g in gens:
        c = C[g['circuit']]
        c['n_gen'] += 1
        c['cap'] += g['cap']
        c['prod'] += g['cap'] if g['producing'] else 0
    for b in bats:
        c = C[b['circuit']]
        c['battery'] += b['stored']; c['battery_cap'] += b['capacity']
    return [dict(id=k, **{a: round(b, 1) if isinstance(b, float) else b for a, b in v.items()})
            for k, v in sorted(C.items(), key=lambda kv: -kv[1]['cap']) if k is not None]


def progress(S):
    """Unlocked milestones/research and project phase."""
    sm = S.props(S.by['BP_SchematicManager_C'][0]) if S.by['BP_SchematicManager_C'] else {}
    sch = GD['schematics']
    names = []
    for _, p in sm.get('mPurchasedSchematics', []):
        k = p.split('.')[-1]
        if k in sch and sch[k].get('type') in ('EST_Milestone', 'EST_MAM', 'EST_Alternate', 'EST_HardDrive', 'EST_Tutorial'):
            names.append(sch[k]['name'])
    act = (sm.get('mActiveSchematic') or ['', ''])[1].split('.')[-1]
    gp = S.props(S.by['BP_GamePhaseManager_C'][0]) if S.by['BP_GamePhaseManager_C'] else {}
    phase = (gp.get('mCurrentGamePhase') or ['', ''])[1].split('.')[-1]
    tiers = collections.Counter(sch[k].get('tier') for _, p in sm.get('mPurchasedSchematics', [])
                                for k in [p.split('.')[-1]] if k in sch and sch[k].get('type') == 'EST_Milestone')
    return dict(schematics=names, n_schematics=len(names), active=sch.get(act, {}).get('name'),
                phase=phase.replace('GP_Project_Assembly_Phase_', 'Phase '), milestones_by_tier=dict(sorted(tiers.items())))


def _len_km(ls):
    return round(sum(math.hypot(b[0] - a[0], b[1] - a[1]) for l in ls for a, b in zip(l, l[1:])) / 1000, 2)


def header(path):
    """Play time (s) and session name from the uncompressed save header."""
    r = sbp.R(open(path, 'rb').read(4096))
    r.i32(); r.i32(); r.i32()
    r.s(); r.s(); r.s(); session = r.s()
    return dict(playtime=r.i32(), session=session)


STOP_CLS = ('TruckStation', 'TrainDocking', 'TrainStation', 'StorageContainer', 'IndustrialTank', 'CentralStorage',
            'ResourceSink', 'SpaceElevator', 'Hub', 'StorageIntegrated')


def machine_links(S, mids):
    """Machine pairs directly connected via belts/pipes/splitters/lifts.

    Storage, stations and sinks separate: beyond them begins logistics between factories.
    Transport parts (everything except machines and separators) are merged into networks via union-find;
    each machine is attached to the networks of its connections. Returns [(id_a, id_b)] with short IDs.
    """
    owner = lambda p: p.rsplit('.', 1)[0]
    stop, kind = {}, {}
    def k(n):                                     # 'm' machine, 's' separator, 't' transport
        if n not in kind:
            sid = sbp.short(n)
            c = sbp.short(S.idx[n][0]['cls']) if n in S.idx else ''
            kind[n] = 'm' if sid in mids else 's' if any(x in c for x in STOP_CLS) else 't'
        return kind[n]
    edges = []
    for cc in ('FGFactoryConnectionComponent', 'FGPipeConnectionComponent', 'FGPipeConnectionFactory'):
        for c in S.by[cc]:
            o = (S.props(c).get('mConnectedComponent') or ['', ''])[1]
            if o:
                a, b = owner(c), owner(o)
                if a != b:
                    edges.append((a, b))
    parent = {}
    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    touch = collections.defaultdict(set)          # transport network → attached machines
    direct = set()
    for a, b in edges:
        ka, kb = k(a), k(b)
        if 's' in (ka, kb):
            continue
        if ka == 't' and kb == 't':
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
        elif ka == 'm' and kb == 'm':
            direct.add(tuple(sorted((sbp.short(a), sbp.short(b)))))
    for a, b in edges:
        ka, kb = k(a), k(b)
        if ka == 'm' and kb == 't':
            touch[find(b)].add(sbp.short(a))
        elif kb == 'm' and ka == 't':
            touch[find(a)].add(sbp.short(b))
    out = set(direct)
    for ms in touch.values():
        ms = sorted(ms)
        if len(ms) > 400:                         # huge collector network: star instead of all pairs
            out.update((ms[0], x) for x in ms[1:])
            continue
        for i, x in enumerate(ms):
            for y in ms[i + 1:]:
                out.add((x, y))
    return sorted(out)


def _flow(S):
    """Per item, the polylines of the belts and pipes carrying it (for "item flow" on the map)."""
    bi, pi = belt_items(S), pipe_items(S)
    out = collections.defaultdict(list)
    for pred, m in ((lambda c: c.startswith('Build_ConveyorBelt') or c.startswith('Build_ConveyorLift'), bi),
                    (lambda c: c.startswith('Build_Pipeline') and 'Support' not in c and 'Junction' not in c
                     and 'Pump' not in c and 'FlowIndicator' not in c, pi)):
        ls, ids = lines(S, pred, with_ids=True)
        for l, i in zip(ls, ids):
            if i in m:
                out[m[i]].append(l)
    return dict(out)


COLLECTIBLES = {                              # class → (key, display label)
    'BP_WAT1_C': ('somersloop', 'Somersloop'), 'BP_WAT2_C': ('mercer', 'Mercer Sphere'),
    'BP_Crystal_C': ('slug1', 'Blue Power Slug'), 'BP_Crystal_mk2_C': ('slug2', 'Yellow Power Slug'),
    'BP_Crystal_mk3_C': ('slug3', 'Purple Power Slug'), 'BP_DropPod_C': ('droppod', 'Crash Site'),
}


def collectibles(S):
    """Collectibles not picked up yet: they exist as actors in the save, collected ones are missing there
    (they end up in the level's collected list). Crash sites remain — looted via mHasBeenLooted."""
    out = {k: [] for k, _ in COLLECTIBLES.values()}
    done = {k: 0 for k in out}
    for cls, (key, _) in COLLECTIBLES.items():
        for n in S.by.get(cls, []):
            p = S.pos(n)
            if key == 'droppod' and S.props(n).get('mHasBeenLooted'):
                done[key] += 1
                continue
            out[key].append([round(p[0] / 100), round(p[1] / 100), round(p[2] / 100)])
    # Total on the map (game version 1.0/1.1, world fully revealed, nothing collected — sat_sav_parse);
    # slugs are counted by the world itself: collected ones are missing, total = open + in the level's collected list
    total = dict(somersloop=106, mercer=298, droppod=len(S.by.get('BP_DropPod_C', [])))
    return dict(open=out, looted_pods=done['droppod'], total=total, labels={k: v for k, v in COLLECTIBLES.values()})


def storage(S):
    """Stock per container/tank: item, amount, fill level, position (for the overview and "storage full")."""
    CAP = {'Build_StorageContainerMk1_C': 24, 'Build_StorageContainerMk2_C': 48, 'Build_CentralStorage_C': 0,
           'Build_StorageIntegrated_C': 0}
    out = []
    for cls in ('Build_StorageContainerMk1_C', 'Build_StorageContainerMk2_C', 'Build_IndustrialTank_C', 'Build_PipeStorageTank_C'):
        for n in S.by.get(cls, []):
            d = S.props(n)
            p = S.pos(n)
            if 'Tank' in cls:
                amt = float(d.get('mFluidBox') or 0)
                cap = 2400.0 if 'Industrial' in cls else 400.0
                inv = [(None, amt)] if amt else []
                # tank fluid via the pipe network of its connections
                fl = None
                for k in ('ConnectionAny0', 'ConnectionAny1', 'PipelineConnection0', 'PipelineConnection1'):
                    nid = S.props(n + '.' + k).get('mPipeNetworkID') if n + '.' + k in S.idx else None
                    if nid is not None:
                        fl = _pipe_fluid(S).get(nid)
                        if fl:
                            break
                items = [dict(item=fl or '?', amount=round(amt, 1))] if amt else []
                fill = min(1.0, amt / cap) if cap else None
            else:
                inv = S.inventory((d.get('mStorageInventory') or ['', ''])[1])
                items = [dict(item=item(i), amount=round(a)) for i, a in sorted(inv, key=lambda x: -x[1])]
                slots = CAP.get(cls, 48)
                st = max((ITEMS.get(i.split('.')[-1], {}).get('stackSize', 100) for i, _ in inv), default=100)
                fill = min(1.0, sum(a for _, a in inv) / (slots * st)) if slots and inv else 0.0
            out.append(dict(id=sbp.short(n), cls=cls, pos=[round(p[0] / 100), round(p[1] / 100)], z=round(p[2] / 100),
                            items=items, fill=round(fill, 3) if fill is not None else None))
    return out


_PF = {}


def _pipe_fluid(S):
    if id(S) not in _PF:
        m = {}
        for n in S.by['FGPipeNetwork']:
            d = S.props(n)
            f = (d.get('mFluidDescriptor') or ['', ''])[1]
            if f and d.get('mPipeNetworkID') is not None:
                m[d['mPipeNetworkID']] = item(f)
        _PF.clear(); _PF[id(S)] = m
    return _PF[id(S)]


def sink(S):
    n = S.by.get('FGResourceSinkSubsystem', [])
    if not n:
        return None
    d = S.props(n[0])
    pts = d.get('mTotalPoints') or [0]
    return dict(points=int(pts[0]), coupons=int(d.get('mNumResourceSinkCoupons') or 0))


def build_from(S, path=None):
    circ = _circuits(S)
    who = _players(S)
    mach = machines(S, circ, who)
    gens = generators(S, circ, who)
    bats = batteries(S, circ)
    out = dict(
        machines=mach, generators=gens, batteries=bats,
        circuits=circuits(mach, gens, bats),
        powerlines=power_lines(S, circ),
        nodes=resource_nodes(S, [m for m in mach if m['cls'] in EXTRACTORS]),
        rails=lines(S, lambda c: c.startswith('Build_RailroadTrack')),
        pipes=lines(S, lambda c: c.startswith('Build_Pipeline') and 'Support' not in c and 'Junction' not in c and 'Pump' not in c and 'FlowIndicator' not in c),
        belts=lines(S, lambda c: c.startswith('Build_ConveyorBelt')),
        flow=_flow(S),
        players_known=sorted(set(who.values())),
        progress=progress(S),
        links=machine_links(S, {m['id'] for m in mach}),
        collectibles=collectibles(S), storage=storage(S), sink=sink(S),
    )
    out['rail_km'] = _len_km(out['rails'])
    out['belt_km'] = _len_km(out['belts'])
    if path or getattr(S, 'path', None):
        out.update(header(path or S.path))
    return out


def build(path):
    return build_from(Save(path), path)


if __name__ == '__main__':
    import time
    t = time.time()
    f = build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'saves', 'latest.sav'))
    st = collections.Counter(m['state'] for m in f['machines'])
    print('%.1fs · %d machines %s · %d generators · %d grids · %d power lines · %d nodes (%d used)' % (
        time.time() - t, len(f['machines']), dict(st), len(f['generators']), len(f['circuits']),
        len(f['powerlines']), len(f['nodes']), sum(n['used'] for n in f['nodes'])))
    print('rails %d, pipes %d, belts %d' % (len(f['rails']), len(f['pipes']), len(f['belts'])))
    for c in f['circuits'][:6]:
        print('  grid', c)
    print('  builders:', f['players_known'])
