"""Reads truck/train stations from a Satisfactory .sav and returns structured records."""
import sbp, sav
from gamedata import item_name, FLUID_NAMES

# ---------- small helpers ----------
# FText history types (only those used in the save)
HISTORY_BASE = 0                       # namespace, key, source string
HISTORY_STRING_TABLE = 11              # string table entry = unchanged default name
HISTORY_NONE = 0xff                    # optional culture-invariant string

def text_prop(b):
    """FText from the raw bytes of a TextProperty: int32 flags, uint8 history type, payload."""
    if not b: return ''
    r = sbp.Reader(b); r.i32()                 # flags
    ht = r.u8()
    if ht == HISTORY_NONE:
        return r.s() if r.i32() else ''
    if ht == HISTORY_BASE:
        r.s(); r.s(); return r.s()
    return ''                                  # HISTORY_STRING_TABLE and others: no user text

def props(ob):
    return {p['name']: p['value'] for p in ob.get('props', [])}   # unparseable objects: {err, raw}

def inventory(idx, comp_path):
    """List of (item, amount) from an FGInventoryComponent (fluids in m3)."""
    if not comp_path or comp_path not in idx: return []
    _, ob = sav.obj(idx, comp_path)
    if 'err' in ob: return []
    out = {}
    for st in props(ob).get('mInventoryStacks', []):
        d = {p['name']: p['value'] for p in st}
        it = d.get('Item', {}).get('item')
        n = d.get('NumItems', 0)
        if it and n:
            name = item_name(it)
            if name in FLUID_NAMES: n = round(n / 1000.0, 1)   # fluid stacks count in litres
            out[name] = out.get(name, 0) + n
    return sorted(out.items(), key=lambda kv: -kv[1])

VEHICLES = {'BP_Locomotive_C': 'Locomotive', 'BP_FreightWagon_C': 'Freight Car', 'BP_Truck_C': 'Truck',
            'BP_Tractor_C': 'Tractor', 'BP_Explorer_C': 'Explorer', 'BP_Golfcart_C': 'FICSIT Factory Cart',
            'BP_GolfcartGold_C': 'Golden Factory Cart', 'FGPlayerHotbar': ''}


def players(idx):
    """Player characters from the save: name, world position, driven vehicle.

    'Currently online' is not stored in the save -- the character stays in the world after
    logging out. The position is therefore the state at the time of saving.
    """
    out = []
    for n, (h, o) in idx.items():
        if sbp.short(h['cls']) != 'Char_Player_C':
            continue
        d = props(sav.obj(idx, n)[1])
        veh = d.get('mSavedDrivenVehicle', ['', ''])[1]
        vcls = sbp.short(idx[veh][0]['cls']) if veh in idx else None
        out.append(dict(name=d.get('mCachedPlayerName') or '(unknown)',
                        pos=[round(v, 1) for v in h['pos']],
                        vehicle=VEHICLES.get(vcls, vcls) if vcls else None))
    out.sort(key=lambda p: p['name'])
    return out


def comp(idx, actor_name, suffix):
    p = actor_name + '.' + suffix
    return p if p in idx else None

# ---------- extraction ----------
def extract(path, idx=None):
    idx = idx or sav.load_index(path)
    cls = {n: sbp.short(h['cls']) for n, (h, o) in idx.items()}

    def pos(n):
        h = idx[n][0]
        return [round(v, 1) for v in h['pos']]

    trucks = []
    for n, c in cls.items():
        if c != 'FGDockingStationIdentifier': continue
        d = props(sav.obj(idx, n)[1])
        st = d.get('mStation', ['', ''])[1]
        if st not in idx: continue
        sd = props(sav.obj(idx, st)[1])
        inv = inventory(idx, comp(idx, st, 'inventory'))
        # mIsInLoadMode missing = default true = vehicles are loaded
        load = bool(sd.get('mIsInLoadMode', True))
        # mVehicleTracking = every vehicle docking here, with its round-trip time. Stations listing the
        # same vehicle are on the same route — those are the real counterpart stations.
        vehicles = []
        for v in sd.get('mVehicleTracking', []):
            vd = {p['name']: p['value'] for p in v}
            ov = vd.get('OwnerVehicle', ['', ''])[1]
            if not ov:
                continue
            vid = sbp.short(ov)
            vehicles.append(dict(id=vid,
                                 type=VEHICLES.get(vid.rsplit('_', 1)[0], vid.rsplit('_', 1)[0]),
                                 last=round(float(vd.get('TimeSinceLastDocking') or 0)),
                                 round=round(float(vd.get('AverageTimeBetweenDocks') or 0))))
        trucks.append(dict(kind='truck', id=st, name=text_prop(d.get('mStationName')) or '(unnamed)',
                           pos=pos(st), mode='load' if load else 'unload',
                           items=[dict(item=i, amount=a) for i, a in inv],
                           vehicles=sorted(vehicles, key=lambda v: v['id'])))

    # train: station -> platform chain via FGTrainPlatformConnection.mConnectedTo
    def platform_chain(station):
        seen, chain = set(), []
        cur = comp(idx, station, 'PlatformConnection0')
        while cur:
            d = props(sav.obj(idx, cur)[1])
            nxt = d.get('mConnectedTo', ['', ''])[1]
            if not nxt or nxt not in idx: break
            owner = nxt.rsplit('.', 1)[0]
            if owner in seen: break
            seen.add(owner); chain.append(owner)
            other = owner + ('.PlatformConnection1' if nxt.endswith('0') else '.PlatformConnection0')
            cur = other if other in idx else None
        return chain

    trains = []
    for n, c in cls.items():
        if c != 'FGTrainStationIdentifier': continue
        d = props(sav.obj(idx, n)[1])
        st = d.get('mStation', ['', ''])[1]
        if st not in idx: continue
        plats = []
        for p in platform_chain(st):
            pc = cls.get(p, '')
            pd = props(sav.obj(idx, p)[1])
            if pc == 'Build_TrainPlatformEmpty_02_C' or 'DockingStation' not in pc:
                plats.append(dict(id=p, type='empty', mode=None, items=[]))
                continue
            inv = inventory(idx, pd.get('mInventory', ['', ''])[1])
            plats.append(dict(id=p, type='fluid' if 'Liquid' in pc else 'freight',
                              mode='load' if bool(pd.get('mIsInLoadMode', True)) else 'unload',
                              items=[dict(item=i, amount=a) for i, a in inv]))
        modes = {p['mode'] for p in plats if p['mode']}
        trains.append(dict(kind='train', id=st, ident=n,
                           name=text_prop(d.get('mStationName')) or '(unnamed)', pos=pos(st),
                           mode=('load' if modes == {'load'} else 'unload' if modes == {'unload'}
                                 else 'mixed' if modes else 'none'),
                           platforms=plats,
                           items=merge_items(plats)))

    # trains + timetables
    ident_to_station = {t['ident']: t['name'] for t in trains}
    routes = []
    for n, c in cls.items():
        if c != 'BP_Train_C': continue
        d = props(sav.obj(idx, n)[1])
        tt = d.get('TimeTable', ['', ''])[1]
        stops = []
        if tt in idx:
            for s in props(sav.obj(idx, tt)[1]).get('mStops', []):
                sd = {p['name']: p['value'] for p in s}
                ident = sd.get('Station', ['', ''])[1]
                stops.append(dict(ident=ident, name=ident_to_station.get(ident, sbp.short(ident))))
        routes.append(dict(name=text_prop(d.get('mTrainName')) or '(unnamed train)',
                           self_driving=bool(d.get('mIsSelfDrivingEnabled', False)), stops=stops))

    trucks.sort(key=lambda s: s['name'])
    trains.sort(key=lambda s: s['name'])
    routes.sort(key=lambda r: r['name'])
    return dict(trucks=trucks, trains=trains, routes=routes, players=players(idx), vehicles=save_vehicles(idx, cls))


def save_vehicles(idx, cls=None):
    """Vehicle positions from the save — fallback when FRM provides no live data.

    Same shape as frm.trains()/frm.trucks(), so the website treats both sources alike.
    """
    cls = cls or {n: sbp.short(h['cls']) for n, (h, o) in idx.items()}
    trucks, trains = [], []
    for n, c in cls.items():
        if c != 'FGWheeledVehicleIdentifier':
            continue
        d = props(sav.obj(idx, n)[1])
        v = d.get('mOwnerVehicle', ['', ''])[1]
        if v not in idx:
            continue
        vd = props(sav.obj(idx, v)[1])
        inv = inventory(idx, comp(idx, v, 'StorageInventory'))
        vid = sbp.short(v)
        trucks.append(dict(id=vid, type=VEHICLES.get(cls.get(v), cls.get(v)),
                           name=text_prop(d.get('mVehicleName')) or '(unnamed)',
                           pos=[round(x, 1) for x in idx[v][0]['pos']], speed=None,
                           autopilot=bool(d.get('mIsAutopilotEnabled')),
                           fuel=float(vd.get('mCurrentFuelAmount') or 0) > 0 or bool(inventory(idx, comp(idx, v, 'FuelInventory'))),
                           cargo=dict(item=inv[0][0], amount=inv[0][1]) if inv else None))
    for n, c in cls.items():
        if c != 'BP_Train_C':
            continue
        d = props(sav.obj(idx, n)[1])
        first = d.get('FirstVehicle', ['', ''])[1]
        if first not in idx:
            continue
        trains.append(dict(name=text_prop(d.get('mTrainName')) or '(unnamed train)',
                           pos=[round(x, 1) for x in idx[first][0]['pos']], status=None, station=None,
                           speed=None, derailed=False, payload=None))
    return dict(trucks=sorted(trucks, key=lambda t: t['name']), trains=sorted(trains, key=lambda t: t['name']))

def merge_items(plats):
    out = {}
    for p in plats:
        for it in p['items']:
            out[it['item']] = out.get(it['item'], 0) + it['amount']
    return [dict(item=i, amount=a) for i, a in sorted(out.items(), key=lambda kv: -kv[1])]
