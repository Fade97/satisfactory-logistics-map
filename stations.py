"""Liest Truck-/Zug-Bahnhoefe aus einem Satisfactory-.sav und liefert strukturierte Records."""
import re, struct
import sbp, sav

# ---------- kleine Helfer ----------
def text_prop(b):
    """FText aus den Rohbytes einer TextProperty (nur die im Save genutzten History-Typen)."""
    if not b: return ''
    r = sbp.R(b); r.i32()                      # flags
    ht = r.u8()
    if ht == 0xff:                             # None-History: optional invariant string
        if r.i32():
            return r.s()
        return ''
    if ht == 0:                                # Base: namespace, key, source string
        r.s(); r.s(); return r.s()
    if ht == 11:                               # StringTableEntry = unveraenderter Default-Name
        return ''
    return ''

ITEM_NAMES = {
    'Desc_OreIron': 'Iron Ore', 'Desc_OreCopper': 'Copper Ore', 'Desc_OreGold': 'Caterium Ore',
    'Desc_OreBauxite': 'Bauxite', 'Desc_OreUranium': 'Uranium', 'Desc_Stone': 'Limestone',
    'Desc_Coal': 'Coal', 'Desc_RawQuartz': 'Raw Quartz', 'Desc_Sulfur': 'Sulfur',
    'Desc_LiquidOil': 'Crude Oil', 'Desc_Water': 'Water', 'Desc_LiquidFuel': 'Fuel',
    'Desc_LiquidTurboFuel': 'Turbofuel', 'Desc_LiquidBiofuel': 'Liquid Biofuel',
    'Desc_HeavyOilResidue': 'Heavy Oil Residue', 'Desc_AluminaSolution': 'Alumina Solution',
    'Desc_SulfuricAcid': 'Sulfuric Acid', 'Desc_NitricAcid': 'Nitric Acid',
    'Desc_NitrogenGas': 'Nitrogen Gas', 'Desc_Rotor': 'Rotor', 'Desc_Cable': 'Cable',
    'Desc_Wire': 'Wire', 'Desc_IronPlateReinforced': 'Reinforced Iron Plate',
    'Desc_IronPlate': 'Iron Plate', 'Desc_IronRod': 'Iron Rod', 'Desc_IronScrew': 'Screw',
    'Desc_SteelPlate': 'Steel Beam', 'Desc_SteelPipe': 'Steel Pipe',
    'Desc_SteelPlateReinforced': 'Encased Industrial Beam', 'Desc_Cement': 'Concrete',
    'Desc_CopperSheet': 'Copper Sheet', 'Desc_CopperIngot': 'Copper Ingot',
    'Desc_IronIngot': 'Iron Ingot', 'Desc_SteelIngot': 'Steel Ingot',
    'Desc_GoldIngot': 'Caterium Ingot', 'Desc_AluminumIngot': 'Aluminum Ingot',
    'Desc_AluminumPlate': 'Alclad Aluminum Sheet', 'Desc_AluminumCasing': 'Aluminum Casing',
    'Desc_AluminumPlateReinforced': 'Heat Sink', 'Desc_HighSpeedWire': 'Quickwire',
    'Desc_CircuitBoard': 'Circuit Board', 'Desc_CircuitBoardHighSpeed': 'AI Limiter',
    'Desc_Computer': 'Computer', 'Desc_ComputerSuper': 'Supercomputer',
    'Desc_ModularFrame': 'Modular Frame', 'Desc_ModularFrameHeavy': 'Heavy Modular Frame',
    'Desc_ModularFrameLightweight': 'Radio Control Unit', 'Desc_Motor': 'Motor',
    'Desc_MotorLightweight': 'Turbo Motor', 'Desc_Stator': 'Stator',
    'Desc_Plastic': 'Plastic', 'Desc_Rubber': 'Rubber', 'Desc_PolymerResin': 'Polymer Resin',
    'Desc_PetroleumCoke': 'Petroleum Coke', 'Desc_CompactedCoal': 'Compacted Coal',
    'Desc_Silica': 'Silica', 'Desc_QuartzCrystal': 'Quartz Crystal',
    'Desc_Fabric': 'Fabric', 'Desc_Biofuel': 'Solid Biofuel', 'Desc_Gunpowder': 'Black Powder',
    'Desc_SpaceElevatorPart_1': 'Smart Plating', 'Desc_SpaceElevatorPart_2': 'Versatile Framework',
    'Desc_SpaceElevatorPart_3': 'Automated Wiring', 'Desc_SpaceElevatorPart_4': 'Modular Engine',
    'Desc_SpaceElevatorPart_5': 'Adaptive Control Unit', 'Desc_SpaceElevatorPart_6': 'Magnetic Field Generator',
    'Desc_SpaceElevatorPart_7': 'Assembly Director System', 'Desc_SpaceElevatorPart_8': 'Thermal Propulsion Rocket',
    'Desc_SpaceElevatorPart_9': 'Nuclear Pasta', 'Desc_CrystalOscillator': 'Crystal Oscillator',
    'Desc_HighSpeedConnector': 'High-Speed Connector', 'Desc_ElectromagneticControlRod': 'Electromagnetic Control Rod',
    'Desc_Battery': 'Battery', 'Desc_SAMIngot': 'Reanimated SAM', 'Desc_SAM': 'SAM',
    'Desc_PackagedOil': 'Packaged Oil', 'Desc_PackagedOilResidue': 'Packaged Heavy Oil Residue',
    'Desc_Fuel': 'Packaged Fuel', 'Desc_TurboFuel': 'Packaged Turbofuel',
    'Desc_PackagedWater': 'Packaged Water', 'Desc_PackagedBiofuel': 'Packaged Liquid Biofuel',
    'Desc_PackagedAlumina': 'Packaged Alumina Solution', 'Desc_PackagedSulfuricAcid': 'Packaged Sulfuric Acid',
    'Desc_PackagedNitricAcid': 'Packaged Nitric Acid', 'Desc_PackagedNitrogenGas': 'Packaged Nitrogen Gas',
    'Desc_FluidCanister': 'Empty Canister', 'Desc_GasTank': 'Empty Fluid Tank',
    'Desc_Filter': 'Gas Filter', 'Desc_HazmatFilter': 'Iodine-Infused Filter',
    'Desc_NuclearFuelRod': 'Uranium Fuel Rod', 'Desc_NuclearWaste': 'Uranium Waste',
    'Desc_UraniumCell': 'Encased Uranium Cell', 'Desc_NonFissibleUranium': 'Non-Fissile Uranium',
    'Desc_PlutoniumCell': 'Encased Plutonium Cell', 'Desc_PlutoniumPellet': 'Plutonium Pellet',
    'Desc_PlutoniumFuelRod': 'Plutonium Fuel Rod', 'Desc_PlutoniumWaste': 'Plutonium Waste',
    'Desc_CoolingSystem': 'Cooling System', 'Desc_MotorTurbo': 'Turbo Motor',
    'Desc_PressureConversionCube': 'Pressure Conversion Cube', 'Desc_CopperDust': 'Copper Powder',
    'Desc_AluminumScrap': 'Aluminum Scrap', 'Desc_GoldenNut': 'Golden Nut Statue',
}
FLUIDS = {'Crude Oil','Water','Fuel','Turbofuel','Liquid Biofuel','Heavy Oil Residue',
          'Alumina Solution','Sulfuric Acid','Nitric Acid','Nitrogen Gas','Rocket Fuel','Ionized Fuel'}

def item_name(path):
    """/Game/.../Desc_Wire.Desc_Wire_C -> 'Wire'"""
    if not path: return None
    key = path.split('.')[-1]
    key = key[:-2] if key.endswith('_C') else key
    if key in ITEM_NAMES: return ITEM_NAMES[key]
    base = re.sub(r'^(Desc_|BP_|Build_)', '', key)
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', base)

def props(ob):
    return {p['name']: p['value'] for p in ob['props']}

def inventory(idx, comp_path):
    """Liste (item, anzahl) aus einer FGInventoryComponent (Fluide in m3)."""
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
            if name in FLUIDS: n = round(n / 1000.0, 1)   # Fluid-Stacks zaehlen in Litern
            out[name] = out.get(name, 0) + n
    return sorted(out.items(), key=lambda kv: -kv[1])

VEHICLES = {'BP_Locomotive_C': 'Lok', 'BP_FreightWagon_C': 'Frachtwaggon', 'BP_Truck_C': 'Truck',
            'BP_Tractor_C': 'Traktor', 'BP_Explorer_C': 'Explorer', 'BP_Golfcart_C': 'Cyber-Wagen',
            'BP_GolfcartGold_C': 'Goldener Cyber-Wagen', 'FGPlayerHotbar': ''}


def players(idx):
    """Spielerfiguren aus dem Save: Name, Weltposition, gefahrenes Fahrzeug.

    Der Zustand 'gerade online' steht nicht im Save -- die Figur bleibt auch nach dem
    Abmelden stehen. Die Position ist also der Stand des jeweiligen Speicherzeitpunkts.
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

# ---------- Extraktion ----------
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
        st = d['mStation'][1]
        if st not in idx: continue
        sd = props(sav.obj(idx, st)[1])
        inv = inventory(idx, comp(idx, st, 'inventory'))
        # mIsInLoadMode fehlt = Default true = Fahrzeuge werden beladen
        load = bool(sd.get('mIsInLoadMode', True))
        # mVehicleTracking = jedes Fahrzeug, das hier andockt, mit Rundenzeit. Stationen, die dasselbe
        # Fahrzeug führen, liegen auf derselben Route — das sind die echten Gegenstellen.
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

    # Zug: Station -> Plattformkette ueber FGTrainPlatformConnection.mConnectedTo
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
        st = d['mStation'][1]
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

    # Zuege + Fahrplaene
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
    """Fahrzeugpositionen aus dem Save — Rückfall, wenn FRM keine Live-Daten liefert.

    Form wie frm.trains()/frm.trucks(), damit die Website beide Quellen gleich behandelt.
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
