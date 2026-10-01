"""Generator for the rail blueprint set (corridor: 2 tracks + hypertube, junctions, stations).

All geometry is defined globally in cm and then cut into 40 m designer boxes (5x5x5).
Conventions:
  - Corridor 24 m wide, symmetrical: foundation rows y=-800/0/800, track B (y=-800, runs +x),
    track A (y=+800, runs -x) -> right-hand traffic. Hypertube in the middle (y=0) at 1.75 m.
  - Track objects are always a single Hermite segment (2 points). TrackConnection0 = start, 1 = end.
  - Signals/switches are derived automatically from nodes (coinciding track ends).

    python3 tools/railset_gen.py        # BP_SRC = folder with TEMPLATE, BP_OUT = output folder
"""
import math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import sbp  # noqa: E402
from sbp import T, P_obj, P_objarr, P_float, P_int, P_bool, P_byte, P_struct, P_vec  # noqa: E402,F401

# folder with your own blueprints used as templates (needs TEMPLATE); relative paths = relative to the repo root
SRC = os.path.join(ROOT, os.environ.get('BP_SRC', 'extracted/blueprints'))
TEMPLATE = 'Asphalt + Schiene - Gerade'   # name of the player's own in-game blueprint used as header/.sbpcfg template
OUT = os.path.join(ROOT, os.environ.get('BP_OUT', 'blueprints/rail-set'))
LVL = "Persistent_Level"
PL = "Persistent_Level:PersistentLevel."
BOX = 2000.0
FOUND_Z = 49.984073638916016
TOP_Z = 99.98407745361328
TUBE_H = 175.0
TUBE_Z = TOP_Z + TUBE_H
BRIDGE_H = 700.0          # tube bridge over the tracks (locomotive 6 m high, tube radius 0.75 m)
BRIDGE_H2 = 850.0         # second bridge above it (X-crossing)
B_Y, A_Y, TUBE_Y = -800.0, 800.0, 0.0
K_ARC = 4.0 / 3.0 * math.tan(math.pi / 8) * 3.0   # Hermite tangent length/R for a quarter circle (=1.657)

# ---------------- classes / recipes ----------------
C = dict(
    found='/Game/FactoryGame/Buildable/Building/Foundation/AsphaltSet/Build_Foundation_Asphalt_8x1.Build_Foundation_Asphalt_8x1_C',
    track='/Game/FactoryGame/Buildable/Factory/Train/Track/Build_RailroadTrack.Build_RailroadTrack_C',
    itrack='/Game/FactoryGame/Buildable/Factory/Train/Track/Build_RailroadTrackIntegrated.Build_RailroadTrackIntegrated_C',
    tube='/Game/FactoryGame/Buildable/Factory/PipeHyper/Build_PipeHyper.Build_PipeHyper_C',
    support='/Game/FactoryGame/Buildable/Factory/PipeHyperSupport/Build_PipeHyperSupport.Build_PipeHyperSupport_C',
    railing='/Game/FactoryGame/Buildable/Building/Fence/Build_Railing_01.Build_Railing_01_C',
    bsig='/Game/FactoryGame/Buildable/Factory/Train/Signal/Build_RailroadBlockSignal.Build_RailroadBlockSignal_C',
    psig='/Game/FactoryGame/Buildable/Factory/Train/Signal/Build_RailroadPathSignal.Build_RailroadPathSignal_C',
    switch='/Game/FactoryGame/Buildable/Factory/Train/SwitchControl/Build_RailroadSwitchControl.Build_RailroadSwitchControl_C',
    station='/Game/FactoryGame/Buildable/Factory/Train/Station/Build_TrainStation.Build_TrainStation_C',
    dock='/Game/FactoryGame/Buildable/Factory/Train/Station/Build_TrainDockingStation.Build_TrainDockingStation_C',
    dockliq='/Game/FactoryGame/Buildable/Factory/Train/Station/Build_TrainDockingStationLiquid.Build_TrainDockingStationLiquid_C',
    beam='/Game/FactoryGame/Prototype/Buildable/Beams/Build_Beam_H.Build_Beam_H_C',
    light='/Game/FactoryGame/Buildable/Factory/StreetLight/Build_StreetLight.Build_StreetLight_C',
    wire='/Game/FactoryGame/Buildable/Factory/PowerLine/Build_PowerLine.Build_PowerLine_C',
)
RECIPE = dict(
    found='/Game/FactoryGame/Buildable/Building/Foundation/AsphaltSet/Recipe_Foundation_Asphalt_8x1.Recipe_Foundation_Asphalt_8x1_C',
    track='/Game/FactoryGame/Recipes/Buildings/Recipe_RailroadTrack.Recipe_RailroadTrack_C',
    itrack='/Game/FactoryGame/Recipes/Buildings/Recipe_RailroadTrackIntegrated.Recipe_RailroadTrackIntegrated_C',
    tube='/Game/FactoryGame/Recipes/Buildings/Recipe_PipeHyper.Recipe_PipeHyper_C',
    support='/Game/FactoryGame/Recipes/Buildings/Recipe_PipeHyperSupport.Recipe_PipeHyperSupport_C',
    railing='/Game/FactoryGame/Recipes/Buildings/Fence/Recipe_Railing_01.Recipe_Railing_01_C',
    bsig='/Game/FactoryGame/Buildable/Factory/Train/Signal/Recipe_RailroadBlockSignal.Recipe_RailroadBlockSignal_C',
    psig='/Game/FactoryGame/Buildable/Factory/Train/Signal/Recipe_RailroadPathSignal.Recipe_RailroadPathSignal_C',
    switch='/Game/FactoryGame/Recipes/Buildings/Recipe_RailroadSwitchControl.Recipe_RailroadSwitchControl_C',
    station='/Game/FactoryGame/Buildable/Factory/Train/Station/Recipe_TrainStation.Recipe_TrainStation_C',
    dock='/Game/FactoryGame/Buildable/Factory/Train/Station/Recipe_TrainDockingStation.Recipe_TrainDockingStation_C',
    dockliq='/Game/FactoryGame/Buildable/Factory/Train/Station/Recipe_TrainDockingStationLiquid.Recipe_TrainDockingStationLiquid_C',
    beam='/Game/FactoryGame/Prototype/Buildable/Beams/Recipe_Beam_H.Recipe_Beam_H_C',
    light='/Game/FactoryGame/Recipes/Buildings/Recipe_StreetLight.Recipe_StreetLight_C',
    wire='/Game/FactoryGame/Recipes/Buildings/Recipe_PowerLine.Recipe_PowerLine_C',
)
COMP = dict(
    trackconn=('/Script/FactoryGame.FGRailroadTrackConnectionComponent', 262152),
    hyperconn=('/Script/FactoryGame.FGPipeConnectionComponentHyper', 262152),
    platconn=('/Script/FactoryGame.FGTrainPlatformConnection', 262152),
    powerinfo=('/Script/FactoryGame.FGPowerInfoComponent', 262152),
    inventory=('/Script/FactoryGame.FGInventoryComponent', 262152),
    legs=('/Script/FactoryGame.FGFactoryLegsComponent', 2097152),
    factconn=('/Script/FactoryGame.FGFactoryConnectionComponent', 2097152),
    pipeconn=('/Script/FactoryGame.FGPipeConnectionFactory', 2097152),
    powerconn=('/Script/FactoryGame.FGPowerConnectionComponent', 2097152),
)
SWATCH_CONCRETE = '/Game/FactoryGame/Buildable/-Shared/Customization/Swatches/SwatchDesc_Concrete.SwatchDesc_Concrete_C'
SWATCH_SLOT2 = '/Game/FactoryGame/Buildable/-Shared/Customization/Swatches/SwatchDesc_Slot2.SwatchDesc_Slot2_C'

def desc(part): return f'/Game/FactoryGame/Resource/Parts/{part}/Desc_{part}.Desc_{part}_C'
COST = {   # per object: {part: amount}; track/tube are computed from their length
    'found': {'Cement': 7},
    'support': {'IronPlate': 2, 'Cement': 2},
    'railing': {'IronRod': 2},
    'light': {'HighSpeedWire': 10, 'Wire': 4, 'IronRod': 4},
    'wire': {'Cable': 3},
    'beam': {},
    'bsig': {'SteelPipe': 2, 'Computer': 1},
    'psig': {'SteelPipe': 2, 'Computer': 1},
    'switch': {},
    'station': {'SteelPlateReinforced': 10, 'Plastic': 50, 'Cement': 50, 'Wire': 200},
    'dock': {'ModularFrameHeavy': 6, 'Computer': 2, 'Cement': 50, 'Cable': 25, 'Motor': 5},
    'dockliq': {'ModularFrameHeavy': 6, 'Computer': 2, 'Cement': 50, 'Cable': 25, 'Motor': 5},
    'itrack': {},
}

# ---------------- property helpers (generic ones live in sbp) ----------------
def P_splinedata(pts):
    """pts: list of (loc, arrive, leave)"""
    return dict(name='mSplineData', type=T('ArrayProperty', T('StructProperty', T('SplinePointData', T('/Script/Engine')))), flags=0,
                value=[[P_vec('Location', l), P_vec('ArriveTangent', a), P_vec('LeaveTangent', b)] for l, a, b in pts])
def generic_props(recipe, swatch, colorslot):
    return [dict(name='BuiltBy', type=T('StructProperty', T('PlayerInfoHandle', T('/Script/FactoryGame'))), flags=sbp.TAG_BINARY, value=b'\x06\x00\x00\x00\x00'),
            P_byte('mColorSlot', colorslot),
            P_struct('mCustomizationData', 'FactoryCustomizationData', '/Script/FactoryGame', [P_obj('SwatchDesc', ['', swatch])]),
            P_obj('mBuiltWithRecipe', ['', recipe])]

def quat_yaw(deg):
    r = math.radians(deg) / 2
    return [0.0, 0.0, math.sin(r), math.cos(r)]

# ---------------- geometry ----------------
def v(a, b): return [a[0] + b[0], a[1] + b[1], (a[2] if len(a) > 2 else 0) + (b[2] if len(b) > 2 else 0)]
def sub(a, b): return [a[0] - b[0], a[1] - b[1], (a[2] if len(a) > 2 else 0) - (b[2] if len(b) > 2 else 0)]
def mul(a, s): return [a[0] * s, a[1] * s, (a[2] if len(a) > 2 else 0) * s]
def norm(a):
    l = math.sqrt(sum(x * x for x in a)); return [x / l for x in a]
def p3(a): return [float(a[0]), float(a[1]), float(a[2]) if len(a) > 2 else 0.0]

class Seg:
    """Hermite segment P0 -> P1 (global, 3D), tangents T0/T1. kind: 'track' | 'itrack' | 'tube'"""
    def __init__(self, P0, T0, P1, T1, kind='track', tag=None):
        self.P0, self.T0, self.P1, self.T1, self.kind, self.tag = p3(P0), p3(T0), p3(P1), p3(T1), kind, tag
    def bezier(self):
        return [self.P0, v(self.P0, mul(self.T0, 1 / 3)), sub(self.P1, mul(self.T1, 1 / 3)), self.P1]
    def point(self, t):
        b = self.bezier(); u = 1 - t
        return [u**3 * b[0][i] + 3 * u * u * t * b[1][i] + 3 * u * t * t * b[2][i] + t**3 * b[3][i] for i in range(3)]
    def split(self, t):
        b = self.bezier()
        def lerp(p, q): return [p[i] + (q[i] - p[i]) * t for i in range(3)]
        b01, b12, b23 = lerp(b[0], b[1]), lerp(b[1], b[2]), lerp(b[2], b[3])
        b012, b123 = lerp(b01, b12), lerp(b12, b23); m = lerp(b012, b123)
        s1 = Seg(b[0], mul(sub(b01, b[0]), 3), m, mul(sub(m, b012), 3), self.kind, self.tag)
        s2 = Seg(m, mul(sub(b123, m), 3), b[3], mul(sub(b[3], b23), 3), self.kind, self.tag)
        return s1, s2
    def split_at_axis(self, axis, val):
        """splits at the intersection with axis==val (if it is a real interior intersection), otherwise None"""
        a0, a1 = self.P0[axis], self.P1[axis]
        if (a0 - val) * (a1 - val) >= -1e-6: return None
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if (self.point(mid)[axis] - val) * (a0 - val) > 0: lo = mid
            else: hi = mid
        s1, s2 = self.split((lo + hi) / 2)
        s1.P1[axis] = val; s2.P0[axis] = val
        return s1, s2

def straight(P0, P1, kind='track', tmag=None, tag=None):
    d = sub(P1, P0); L = math.sqrt(sum(x * x for x in d))
    t = mul(norm(d), tmag if tmag else L)
    return Seg(P0, t, P1, t, kind, tag)

def arc(P0, d0, turn, R, kind='track'):
    """Quarter circle from P0 in direction d0 (unit vector, 2D), turn=+1 left / -1 right."""
    d0 = norm(p3(d0)); n = [-d0[1] * turn, d0[0] * turn, 0.0]     # normal towards the inside of the curve
    P1 = v(v(P0, mul(d0, R)), mul(n, R)); d1 = n
    return Seg(P0, mul(d0, K_ARC * R), P1, mul(d1, K_ARC * R), kind)

def tube_profile(axis, other, pts_zx, z0=TUBE_Z):
    """Multi-point tube along axis ('x'|'y'); pts_zx: list of (coord, z). Horizontal tangents (S-ramps)."""
    segs = []
    for (a0, za), (a1, zb) in zip(pts_zx, pts_zx[1:]):
        P0 = [a0, other, za] if axis == 'x' else [other, a0, za]
        P1 = [a1, other, zb] if axis == 'x' else [other, a1, zb]
        d = [1, 0, 0] if axis == 'x' else [0, 1, 0]
        L = abs(a1 - a0)
        segs.append(Seg(P0, mul(d, L), P1, mul(d, L), 'tube'))
    return segs

# ---------------- piece definition ----------------
class Piece:
    def __init__(self, name, desc, boxes):
        self.name, self.desc, self.boxes = name, desc, boxes   # boxes: [(cx, cy, suffix)]
        self.segs = []; self.founds = []; self.supports = []; self.railings = []; self.signals = []; self.platforms = []
        self.beams = []; self.lamps = []
    def lamp(self, x, y, yaw=0.0):
        """Tube support + 2 street lights (1.5 m on either side) + cable; yaw = tube direction"""
        self.supports.append((x, y, TUBE_H, yaw)); self.lamps.append((x, y, yaw))
    def beam(self, x0, y0, x1, y1): self.beams.append((x0, y0, x1, y1))
    def track(self, *segs):
        for s in segs: self.segs.append(s)
    def corridor_x(self, x0, x1, nodes_b=(), nodes_a=()):
        """straight corridor along x: track B (+x) and A (-x), tube, foundations, supports"""
        xb = sorted(set([x0, x1] + list(nodes_b))); xa = sorted(set([x0, x1] + list(nodes_a)), reverse=True)
        for p, q in zip(xb, xb[1:]): self.segs.append(straight([p, B_Y, TOP_Z], [q, B_Y, TOP_Z]))
        for p, q in zip(xa, xa[1:]): self.segs.append(straight([p, A_Y, TOP_Z], [q, A_Y, TOP_Z]))
        for x in frange(x0 + 400, x1, 800):
            for y in (-800, 0, 800): self.founds.append((x, y))
    def tube_x(self, x0, x1, y=TUBE_Y): self.segs.append(straight([x0, y, TUBE_Z], [x1, y, TUBE_Z], 'tube', tmag=abs(x1 - x0) / 2))
    def tube_y(self, y0, y1, x=TUBE_Y): self.segs.append(straight([x, y0, TUBE_Z], [x, y1, TUBE_Z], 'tube', tmag=abs(y1 - y0) / 2))
    def railings_x(self, x0, x1, y, facing):
        for x in frange(x0 + 200, x1, 400): self.railings.append((x, y, -90.0))   # as placed by the player in the game
    def railings_y(self, y0, y1, x, facing):
        for y in frange(y0 + 200, y1, 400): self.railings.append((x, y, 0.0))
    def signal(self, x, y, travel, kind): self.signals.append((x, y, norm(p3(travel)), kind))

def frange(a, b, step):
    out = []; x = a
    while x < b - 1e-6: out.append(x); x += step
    return out

# ---------------- blueprint building ----------------
class Builder:
    def __init__(self):
        self.headers = []; self.objs = []; self.comp_headers = []; self.comp_objs = []
        self.n = 2140000000; self.cost = {}; self.recipes = []
    def nid(self): self.n += 1; return self.n
    def addcost(self, kind, mult=1):
        for k, a in COST.get(kind, {}).items(): self.cost[k] = self.cost.get(k, 0) + a * mult
        if kind in RECIPE and RECIPE[kind] not in self.recipes: self.recipes.append(RECIPE[kind])
    def actor(self, cls, name, pos, rot, props, comps):
        """comps: list of (compname, (cls, flags), props)"""
        self.headers.append(dict(type=1, cls=cls, root=LVL, name=PL + name, flags=8, needTransform=1, rot=list(rot), pos=[float(x) for x in pos], scale=[1.0, 1.0, 1.0], placed=0))
        self.objs.append(dict(obj=dict(parent=[LVL, PL + 'BuildableSubsystem'], components=[[LVL, PL + name + '.' + c[0]] for c in comps], pre=0, props=props, trail=b'\x00\x00\x00\x00')))
        for cn, (ccls, cfl), cprops in comps:
            self.comp_headers.append(dict(type=0, cls=ccls, root=LVL, name=PL + name + '.' + cn, flags=cfl, outer=PL + name))
            self.comp_objs.append(dict(obj=dict(pre=0, props=cprops, trail=b'\x00' * 8)))
    def body(self): return dict(headers=self.headers + self.comp_headers, objs=self.objs + self.comp_objs, rest=b'')

def ref(name): return [LVL, PL + name]

class Box:
    """One 40 m designer box of a piece: centre (cx, cy); objects are stored relative to it (off)."""
    def __init__(self, cx, cy): self.cx, self.cy, self.off = cx, cy, [cx, cy, 0.0]
    def inside(self, x, y): return (self.cx - BOX - 1 <= x <= self.cx + BOX + 1) and (self.cy - BOX - 1 <= y <= self.cy + BOX + 1)

def build_box(piece, cx, cy, suffix, H_tpl):
    """Cut one box out of the piece and write it as .sbp/.sbpcfg. The order of the steps fixes the object IDs."""
    b = Builder(); box = Box(cx, cy)
    segs = _clip(piece, box)
    tracks, names, nodes = _place_tracks(b, box, segs)
    _place_signals(b, box, piece, nodes)
    _place_platforms(b, box, piece, tracks, names)
    _place_tubes(b, box, segs)
    _place_supports_foundations_railings(b, box, piece)
    _place_beams(b, box, piece)
    _place_lamps(b, box, piece)
    return _write_box(b, piece, suffix, H_tpl)

def _clip(piece, box):
    cx, cy, inside = box.cx, box.cy, box.inside
    # --- cut segments at the box edges, keep only the inner ones
    segs = list(piece.segs)
    for axis, vals in ((0, (cx - BOX, cx + BOX)), (1, (cy - BOX, cy + BOX))):
        for val in vals:
            out = []
            for s in segs:
                r = s.split_at_axis(axis, val)
                out.extend(r if r else [s])
            segs = out
    segs = [s for s in segs if inside(*s.point(0.5)[:2])]
    return segs

def _place_tracks(b, box, segs):
    """Track objects, then nodes (coinciding ends): connections and switches."""
    cx, cy, off = box.cx, box.cy, box.off
    # --- tracks -> objects, collect ends
    ends = []   # (node_key, compref, outward_dir, segindex)
    tracks = [s for s in segs if s.kind in ('track', 'itrack')]
    names = []
    for s in tracks:
        kind = s.kind
        name = ('Build_RailroadTrackIntegrated_C_' if kind == 'itrack' else 'Build_RailroadTrack_C_') + str(b.nid())
        names.append(name)
        loc = sub(s.P1, s.P0)
        props = [P_splinedata([([0, 0, 0], s.T0, s.T0), (loc, s.T1, s.T1)]), P_int('mTrackGraphID', 0)] + generic_props(RECIPE[kind], SWATCH_SLOT2, 2)
        b.actor(C[kind], name, sub(s.P0, off), [0, 0, 0, 1], props,
                [('TrackConnection1', COMP['trackconn'], []), ('TrackConnection0', COMP['trackconn'], [])])
        ends.append((key(s.P0), name + '.TrackConnection0', mul(norm(s.T0), -1), s))
        ends.append((key(s.P1), name + '.TrackConnection1', norm(s.T1), s))
        L = math.dist(s.P0, s.P1) / 100
        if kind == 'track':
            n = max(1, round(L / 12)); b.cost['SteelPlate'] = b.cost.get('SteelPlate', 0) + n; b.cost['SteelPipe'] = b.cost.get('SteelPipe', 0) + n
        b.addcost(kind)
    # --- nodes: connections + switches
    nodes = {}
    on_edge = lambda k: abs(abs(k[0] - cx) - BOX) < 2 or abs(abs(k[1] - cy) - BOX) < 2
    for e in ends:
        if not on_edge(e[0]): nodes.setdefault(e[0], []).append(e)   # the game connects ends on the box edge when placing
    conn = {e[1]: [] for e in ends}
    for k, es in nodes.items():
        if len(es) == 2:
            conn[es[0][1]].append(es[1][1]); conn[es[1][1]].append(es[0][1])
        elif len(es) == 3:
            best = None
            for i in range(3):
                j, l = [x for x in range(3) if x != i]
                d = sum(es[j][2][m] * es[l][2][m] for m in range(3))
                if best is None or d > best[0]: best = (d, i)
            trunk = es[best[1]]; branches = [e for e in es if e is not trunk]
            for br in branches: conn[trunk[1]].append(br[1]); conn[br[1]].append(trunk[1])
            name = 'Build_RailroadSwitchControl_C_' + str(b.nid())
            yaw = math.degrees(math.atan2(trunk[2][1], trunk[2][0]))
            props = [P_objarr('mControlledConnections', [ref(trunk[1])]),
                     P_struct('mSwitchData', 'SwitchData', '/Script/FactoryGame', [])] + generic_props(RECIPE['switch'], SWATCH_SLOT2, 2)
            b.actor(C['switch'], name, sub(trunk[3].P1 if trunk[1].endswith('1') else trunk[3].P0, off), quat_yaw(yaw), props, [])
            b.addcost('switch')
        elif len(es) > 3: raise Exception('node with >3 track ends at ' + str(k))
    for h, o in zip(b.comp_headers, b.comp_objs):
        cn = h['name'][len(PL):]
        if cn in conn and conn[cn]: o['obj']['props'] = [P_objarr('mConnectedComponents', [ref(x) for x in conn[cn]])]
    return tracks, names, nodes

def _place_signals(b, box, piece, nodes):
    off, inside = box.off, box.inside
    # --- signals
    for x, y, travel, kind in piece.signals:
        if not inside(x, y): continue
        es = nodes.get(key([x, y, TOP_Z]), [])
        guarded = [e[1] for e in es if sum(e[2][m] * travel[m] for m in range(3)) > 0.5]
        observed = [e[1] for e in es if sum(e[2][m] * travel[m] for m in range(3)) < -0.5]
        assert guarded and observed, ('signal without track node', piece.name, x, y)
        name = ('Build_RailroadBlockSignal_C_' if kind == 'block' else 'Build_RailroadPathSignal_C_') + str(b.nid())
        props = [P_objarr('mGuardedConnections', [ref(g) for g in guarded]), P_objarr('mObservedConnections', [ref(o) for o in observed]),
                 P_bool('mIsBiDirectional', True)] + generic_props(RECIPE['bsig' if kind == 'block' else 'psig'], SWATCH_SLOT2, 2)
        b.actor(C['bsig' if kind == 'block' else 'psig'], name, sub([x, y, TOP_Z], off), quat_yaw(math.degrees(math.atan2(travel[1], travel[0]))), props, [])
        b.addcost('bsig' if kind == 'block' else 'psig')

def _place_platforms(b, box, piece, tracks, names):
    off, inside = box.off, box.inside
    # --- platforms (station / freight platform): objects + platform connections
    plat_ends = {}   # node_key -> (platname, 'PlatformConnection0/1')
    for x, y, yaw, kind, seg in piece.platforms:
        if not inside(x, y): continue
        tname = None
        for nm, s in zip(names, tracks):
            if s.kind == 'itrack' and s.tag is seg.tag: tname = nm
        assert tname, 'integrated track missing'
        name = {'station': 'Build_TrainStation_C_', 'dock': 'Build_TrainDockingStation_C_', 'dockliq': 'Build_TrainDockingStationLiquid_C_'}[kind] + str(b.nid())
        pc0 = [P_obj('mRailroadTrackConnection', ref(tname + '.TrackConnection0'))]
        pc1 = [P_obj('mRailroadTrackConnection', ref(tname + '.TrackConnection1'))]
        plat_ends[key(seg.P0)] = plat_ends.get(key(seg.P0), []) + [(name, 'PlatformConnection0', pc0)]
        plat_ends[key(seg.P1)] = plat_ends.get(key(seg.P1), []) + [(name, 'PlatformConnection1', pc1)]
        common = [P_obj('mRailroadTrack', ref(tname)), P_obj('mPowerInfo', ref(name + '.powerInfo')),
                  P_float('mTimeSinceStartStopProducing', 3.3999999521443642e+38), P_obj('mInventoryPotential', ['', ''])]
        if kind == 'station':
            props = common + generic_props(RECIPE['station'], SWATCH_SLOT2, 2)
            comps = [('FGFactoryLegs', COMP['legs'], []), ('InventoryPotential', COMP['inventory'], []), ('powerInfo', COMP['powerinfo'], []),
                     ('PlatformConnection0', COMP['platconn'], pc0), ('PlatformConnection1', COMP['platconn'], pc1), ('PowerConnection', COMP['powerconn'], [])]
        elif kind == 'dock':
            props = [P_obj('mInventory', ref(name + '.inventory'))] + common + generic_props(RECIPE['dock'], SWATCH_SLOT2, 2)
            comps = [('FGFactoryLegs', COMP['legs'], []), ('InventoryPotential', COMP['inventory'], []), ('powerInfo', COMP['powerinfo'], []),
                     ('PlatformConnection0', COMP['platconn'], pc0), ('PlatformConnection1', COMP['platconn'], pc1), ('inventory', COMP['inventory'], []),
                     ('Input0', COMP['factconn'], []), ('Output0', COMP['factconn'], []), ('Input1', COMP['factconn'], []), ('Output1', COMP['factconn'], []),
                     ('FGPowerConnection', COMP['powerconn'], [])]
        else:
            props = [P_obj('mInventory', ref(name + '.inventory'))] + common + generic_props(RECIPE['dockliq'], SWATCH_SLOT2, 2)
            comps = [('PipeFactoryInput1', COMP['pipeconn'], []), ('InventoryPotential', COMP['inventory'], []), ('powerInfo', COMP['powerinfo'], []),
                     ('PlatformConnection0', COMP['platconn'], pc0), ('PlatformConnection1', COMP['platconn'], pc1), ('inventory', COMP['inventory'], []),
                     ('PipeFactoryInput0', COMP['pipeconn'], []), ('PipeFactoryOutput1', COMP['pipeconn'], []), ('PipeFactoryOutput0', COMP['pipeconn'], []),
                     ('FGPowerConnection', COMP['powerconn'], []), ('FGFactoryLegs', COMP['legs'], [])]
        b.actor(C[kind], name, sub([x, y, TOP_Z], off), quat_yaw(yaw), props, comps)
        b.addcost(kind)
    for k, es in plat_ends.items():
        if len(es) == 2:
            es[0][2].append(P_obj('mConnectedTo', ref(es[1][0] + '.' + es[1][1])))
            es[1][2].append(P_obj('mConnectedTo', ref(es[0][0] + '.' + es[0][1])))

def _place_tubes(b, box, segs):
    off = box.off
    # --- hypertube: chain connected segments into one multi-point spline
    tubes = [s for s in segs if s.kind == 'tube']
    chains = []
    while tubes:
        ch = [tubes.pop(0)]
        changed = True
        while changed:
            changed = False
            for t in list(tubes):
                if key(t.P0) == key(ch[-1].P1): ch.append(t); tubes.remove(t); changed = True
                elif key(t.P1) == key(ch[0].P0): ch.insert(0, t); tubes.remove(t); changed = True
        chains.append(ch)
    for ch in chains:
        name = 'Build_PipeHyper_C_' + str(b.nid())
        P0 = ch[0].P0
        pts = [([0, 0, 0], norm(ch[0].T0), ch[0].T0)]
        for i, s in enumerate(ch):
            leave = ch[i + 1].T0 if i + 1 < len(ch) else norm(s.T1)
            pts.append((sub(s.P1, P0), s.T1, leave))
        props = [P_splinedata(pts), P_objarr('mSnappedPassthroughs', [['', ''], ['', '']])] + generic_props(RECIPE['tube'], SWATCH_SLOT2, 2)
        b.actor(C['tube'], name, sub(P0, off), [0, 0, 0, 1], props,
                [('PipeHyperConnection1', COMP['hyperconn'], []), ('PipeHyperConnection0', COMP['hyperconn'], [])])
        L = sum(math.dist(s.P0, s.P1) for s in ch) / 100; n = max(1, round(L / 2))
        b.cost['CopperSheet'] = b.cost.get('CopperSheet', 0) + n; b.cost['SteelPipe'] = b.cost.get('SteelPipe', 0) + n
        b.addcost('tube')

def _place_supports_foundations_railings(b, box, piece):
    off, inside = box.off, box.inside
    # --- supports, foundations, railings
    for x, y, h, yaw in piece.supports:
        if not inside(x, y): continue
        b.actor(C['support'], 'Build_PipeHyperSupport_C_' + str(b.nid()), sub([x, y, TOP_Z], off), quat_yaw(yaw),
                [P_float('mHeight', h)] + generic_props(RECIPE['support'], SWATCH_SLOT2, 2), [('SnapOnly0', COMP['hyperconn'], [])])
        b.addcost('support')
    for x, y in piece.founds:
        if not inside(x, y): continue
        b.actor(C['found'], 'Build_Foundation_Asphalt_8x1_C_' + str(b.nid()), sub([x, y, FOUND_Z], off), [0, 0, 0, 1],
                generic_props(RECIPE['found'], SWATCH_CONCRETE, 18), [])
        b.addcost('found')
    for x, y, yaw in piece.railings:
        if not inside(x, y): continue
        b.actor(C['railing'], 'Build_Railing_01_C_' + str(b.nid()), sub([x, y, TOP_Z], off), quat_yaw(yaw),
                generic_props(RECIPE['railing'], SWATCH_SLOT2, 2), [])
        b.addcost('railing')

def _place_beams(b, box, piece):
    cx, cy, off, inside = box.cx, box.cy, box.off, box.inside
    # --- H-beams on the outer edges (origin at the start, runs in yaw direction)
    for x0, y0, x1, y1 in piece.beams:
        # clip to the box edges
        ax = 0 if abs(x1 - x0) > abs(y1 - y0) else 1
        lo, hi = (cx - BOX, cx + BOX) if ax == 0 else (cy - BOX, cy + BOX)
        a, bb = sorted([(x0, y0)[ax], (x1, y1)[ax]]); a, bb = max(a, lo), min(bb, hi)
        if bb - a < 100 or not inside(*((a + bb) / 2, y0) if ax == 0 else (x0, (a + bb) / 2)): continue
        p0 = [a, y0, FOUND_Z] if ax == 0 else [x0, a, FOUND_Z]
        b.actor(C['beam'], 'Build_Beam_H_C_' + str(b.nid()), sub(p0, off), quat_yaw(0 if ax == 0 else 90),
                [P_float('mLength', bb - a)] + generic_props(RECIPE['beam'], SWATCH_SLOT2, 2), [])
        b.cost['SteelPlate'] = b.cost.get('SteelPlate', 0) + max(1, round((bb - a) / 400)); b.addcost('beam')

def _place_lamps(b, box, piece):
    off, inside = box.off, box.inside
    # --- pair of street lights + cable (modelled on the straight piece adjusted in the game)
    for x, y, yaw in piece.lamps:
        if not inside(x, y): continue
        r = math.radians(yaw); nx, ny = -math.sin(r), math.cos(r)      # normal to the tube direction
        names = []
        for side in (-1, 1):
            lx, ly = x + side * 150 * nx, y + side * 150 * ny
            nm = 'Build_StreetLight_C_' + str(b.nid()); names.append((nm, [lx, ly, TOP_Z]))
            b.actor(C['light'], nm, sub([lx, ly, TOP_Z], off), quat_yaw(yaw + (180 if side < 0 else 0)),
                    generic_props(RECIPE['light'], SWATCH_SLOT2, 2),
                    [('FGPowerConnection', COMP['powerconn'], [P_objarr('mWires', [ref('WIRE')])]), ('powerInfo', COMP['powerinfo'], [P_float('mTargetConsumption', 1.0)])])
            b.addcost('light')
        wn = 'Build_PowerLine_C_' + str(b.nid())
        for h, o in zip(b.comp_headers, b.comp_objs):
            for p in o['obj']['props']:
                if p['name'] == 'mWires': p['value'] = [[LVL, PL + wn] if v2[1] == PL + 'WIRE' else v2 for v2 in p['value']]
        locs = [v(v(pos, mul([nx, ny, 0], -side * 126.7)), [0, 0, 949.4]) for side, (nm, pos) in zip((-1, 1), names)]
        mid = mul(v(locs[0], locs[1]), 0.5)
        wire_props = [dict(name='mWireInstances', type=T('ArrayProperty', T('StructProperty', T('WireInstance', T('/Script/FactoryGame')))), flags=0,
                           value=[[dict(name='Locations', type=T('StructProperty', T('Vector', T('/Script/CoreUObject'))), flags=sbp.TAG_BINARY, value=sub(locs[0], off)),
                                   dict(name='Locations', type=T('StructProperty', T('Vector', T('/Script/CoreUObject'))), flags=sbp.TAG_BINARY | sbp.TAG_HAS_INDEX, index=1, value=sub(locs[1], off))]]),
                      P_float('mCachedLength', math.dist(locs[0], locs[1]))] + generic_props(RECIPE['wire'], SWATCH_SLOT2, 2)
        w = sbp.Writer(); w.raw(b'\x00\x00\x00\x00')
        for nm, pos in names: w.s(LVL); w.s(PL + nm + '.FGPowerConnection')
        b.actor(C['wire'], wn, sub(mid, off), quat_yaw(yaw + 90), wire_props, [])
        b.objs[-1]['obj']['trail'] = w.bytes()
        b.addcost('wire')

def _write_box(b, piece, suffix, H_tpl):
    # --- header + files
    cost = [['', desc(k), a] for k, a in b.cost.items() if a > 0]
    H = dict(hv=H_tpl['hv'], sv=H_tpl['sv'], bv=H_tpl['bv'], dims=[5, 5, 5], cost=cost, recipes=[['', r] for r in b.recipes], tail=H_tpl['tail'])
    fname = piece.name + (' ' + suffix if suffix else '')
    os.makedirs(OUT, exist_ok=True)
    sbp.save(f'{OUT}/{fname}.sbp', H, b.body())
    write_cfg(f'{OUT}/{fname}.sbpcfg', piece.desc)
    return fname, len(b.headers), b.cost


def key(p): return (round(p[0]), round(p[1]))

def write_cfg(path, text, src=None):
    """Write a description (.sbpcfg) modelled on an existing file — default: the rail template."""
    sbp.write_cfg(path, text, src or f'{SRC}/{TEMPLATE}.sbpcfg')

# ---------------- pieces ----------------
def corridor_deco(p, x0, x1):
    """railings (both edges) + H-beams along a corridor in x"""
    p.railings_x(x0, x1, 1200, +1); p.railings_x(x0, x1, -1200, -1)
    p.beam(x0, -1200, x1, -1200); p.beam(x0, 1200, x1, 1200)

def pieces():
    P = []
    # 01 straight (reference = the player's version adjusted in the game)
    p = Piece('Rail 01 Straight', 'Corridor 24 m: track B (y=-8 m, runs +x), track A (y=+8 m, runs -x), hypertube in the middle at 1.75 m, railings + H-beams outside, street lights in the middle. Right-hand traffic.', [(0, 0, '')])
    p.corridor_x(-2000, 2000); p.tube_x(-2000, 2000); corridor_deco(p, -2000, 2000); p.lamp(0, 0)
    P.append(p)
    # 02 straight + block signals
    p = Piece('Rail 02 Straight Block Signals', 'Like Straight, plus one block signal per track 4 m behind the entry. Use every 2-3 pieces.', [(0, 0, '')])
    p.corridor_x(-2000, 2000, nodes_b=(-1600,), nodes_a=(1600,)); p.tube_x(-2000, 2000); corridor_deco(p, -2000, 2000); p.lamp(0, 0)
    p.signal(-1600, B_Y, [1, 0, 0], 'block'); p.signal(1600, A_Y, [-1, 0, 0], 'block')
    P.append(p)
    # 03 junction approach (the junction is at the +x end)
    p = Piece('Rail 03 Junction Approach', 'Place directly in front of a junction (junction at the +x end, otherwise rotate by 180 degrees): path signal for the incoming track, block signal for the outgoing one.', [(0, 0, '')])
    p.corridor_x(-2000, 2000, nodes_b=(1600,), nodes_a=(1600,)); p.tube_x(-2000, 2000); corridor_deco(p, -2000, 2000); p.lamp(0, 0)
    p.signal(1600, B_Y, [1, 0, 0], 'path'); p.signal(1600, A_Y, [-1, 0, 0], 'block')
    P.append(p)
    # 05 curve 90 degrees: centre (-4000, 4000) = corner of the boxes, centre line R 60 m; boxes: bottom left (entry from -x),
    #    bottom right (middle), top right (exit towards +y). The top left box only holds the inner edge.
    p = Piece('Rail 05 Curve 90', 'Curve 90 degrees (centre line R 60 m, tracks R 52/68 m) made of 3 parts: "Bottom Left" (corridor comes from -x), "Bottom Right", "Top Right" (corridor leaves towards +y), plus "Top Left" (inner edge only). Usable as a right or left curve (the corridor is symmetrical).',
              [(-2000, -2000, 'Bottom Left'), (2000, -2000, 'Bottom Right'), (2000, 2000, 'Top Right'), (-2000, 2000, 'Top Left')])
    Rm = 6000.0; ctr = [-4000.0, 4000.0]
    def polar(r, deg): a = math.radians(deg); return [ctr[0] + r * math.cos(a), ctr[1] + r * math.sin(a), TOP_Z]
    p.track(arc(polar(Rm + 800, -90), [1, 0], +1, Rm + 800))          # B (outer): +x -> +y
    p.track(arc(polar(Rm - 800, 0), [0, -1], -1, Rm - 800))            # A (inner): -y -> -x
    tube = arc(polar(Rm, -90), [1, 0], +1, Rm, 'tube'); tube.P0[2] = tube.P1[2] = TUBE_Z; p.segs.append(tube)
    for x in frange(-4000 + 400, 4000, 800):
        for y in frange(-4000 + 400, 4000, 800):
            r = math.dist((x, y), ctr); deg = math.degrees(math.atan2(y - ctr[1], x - ctr[0]))
            if Rm - 1200 - 300 <= r <= Rm + 1200 + 300 and -93 <= deg <= 3: p.founds.append((x, y))
    for deg in (-80, -45, -10):                                       # one street light per box, tube direction = tangent
        q = polar(Rm, deg); p.lamp(q[0], q[1], deg + 90)
    for r in (Rm + 1200, Rm - 1200):                                  # railings along the arc edges, 4 m pieces
        n = int(r * math.pi / 2 / 400)
        for k in range(n):
            deg = -90 + (k + 0.5) * 90 / n; q = polar(r, deg); p.railings.append((q[0], q[1], deg))
    P.append(p)
    # 10 T-junction (branch towards -y), 3 boxes: top left (-2000,0), top right (2000,0), bottom (c,-4000)
    c = 400.0; R = 2000.0
    p = Piece('Rail 10 T-Junction', 'T-junction made of 3 parts: "Top Left" + "Top Right" side by side, "Bottom" below (branch corridor 4 m right of the centre, align with the foundations). The branch points towards -y. Put a "Junction Approach" at all 3 ends. The tube runs as a bridge over the curves, the branch tube ends blind.',
              [(-2000, 0, 'Top Left'), (2000, 0, 'Top Right'), (c, -4000, 'Bottom')])
    xo, xi = c - 800, c + 800
    p.corridor_x(-4000, 4000, nodes_b=(xo - R, 0, xi + R), nodes_a=(xo + R, 0, xi - R))
    for x in frange(-4000 + 400, 4000, 800):
        if xo - R - 400 <= x <= xi + R + 400: p.founds.append((x, -1600))
    p.track(arc([xo - R, B_Y, TOP_Z], [1, 0], -1, R))
    p.track(arc([xi, B_Y - R, TOP_Z], [0, 1], -1, R))
    p.track(arc([xo + R, A_Y, TOP_Z], [-1, 0], +1, R))
    p.track(arc([xi, A_Y - R, TOP_Z], [0, 1], +1, R))
    for a, bb in ((A_Y - R, -2000), (-2000, B_Y - R), (B_Y - R, -6000)): p.track(straight([xo, a, TOP_Z], [xo, bb, TOP_Z]))
    for a, bb in ((-6000, B_Y - R), (B_Y - R, -2000), (-2000, A_Y - R)): p.track(straight([xi, a, TOP_Z], [xi, bb, TOP_Z]))
    for y in frange(-6000 + 400, -2000, 800):
        for x in (xo, c, xi): p.founds.append((x, y))
    for s_ in tube_profile('x', TUBE_Y, [(-4000, TUBE_Z), (c - 1900, TUBE_Z), (c - 1100, TOP_Z + BRIDGE_H), (c + 1100, TOP_Z + BRIDGE_H), (c + 1900, TUBE_Z), (4000, TUBE_Z)]): p.segs.append(s_)
    p.tube_y(-6000, -2000, x=c)
    p.lamp(-2000, 0); p.lamp(3200, 0); p.lamp(c, -4000, 90)
    p.railings_x(-4000, 4000, 1200, +1); p.beam(-4000, 1200, 4000, 1200)
    p.railings_y(-6000, -2000, c - 1200, -1); p.railings_y(-6000, -2000, c + 1200, +1); p.beam(c - 1200, -6000, c - 1200, -2000); p.beam(c + 1200, -6000, c + 1200, -2000)
    P.append(p)
    # 20 X-crossing
    p = Piece('Rail 20 X-Crossing', 'Flat crossing of two corridors without turning. Both hypertubes as bridges (lengthwise 7 m, crosswise 8.5 m high). Put a "Junction Approach" at all 4 ends.', [(0, 0, '')])
    p.corridor_x(-2000, 2000)
    for x in (-800, 800):
        for y in (-1600, 1600): p.founds.append((x, y))
    for y in (-1600, 1600): p.founds.append((0, y))
    p.track(straight([-800, 2000, TOP_Z], [-800, -2000, TOP_Z]), straight([800, -2000, TOP_Z], [800, 2000, TOP_Z]))
    p.supports = [(x, 0, TUBE_H, 0) for x in (-1950, 1950)] + [(0, y, TUBE_H, 90) for y in (-1950, 1950)]
    for s_ in tube_profile('x', TUBE_Y, [(-2000, TUBE_Z), (-1900, TUBE_Z), (-1100, TOP_Z + BRIDGE_H), (1100, TOP_Z + BRIDGE_H), (1900, TUBE_Z), (2000, TUBE_Z)]): p.segs.append(s_)
    for s_ in tube_profile('y', TUBE_Y, [(-2000, TUBE_Z), (-1900, TUBE_Z), (-1100, TOP_Z + BRIDGE_H2), (1100, TOP_Z + BRIDGE_H2), (1900, TUBE_Z), (2000, TUBE_Z)]): p.segs.append(s_)
    P.append(p)
    # 30/31 stations
    for kind, nm, dsc in (('dock', 'Rail 30 Freight Station', 'Station with 1 freight platform on its own track (y=0), direction of travel +x: the train comes from -x, platform x=-16..0 m, station x=0..16 m. Container side -y. Block signals at both ends. Connect power!'),
                          ('dockliq', 'Rail 31 Fluid Station', 'Station with 1 fluid platform on its own track (y=0), direction of travel +x. Pipe connections -y. Block signals at both ends. Connect power!')):
        p = Piece(nm, dsc, [(0, 0, '')])
        for x in frange(-2000 + 400, 2000, 800):
            for y in frange(-2000 + 400, 2000, 800): p.founds.append((x, y))
        p.track(straight([-2000, 0, TOP_Z], [-1600, 0, TOP_Z]), straight([1600, 0, TOP_Z], [2000, 0, TOP_Z]))
        td = straight([-1600, 0, TOP_Z], [0, 0, TOP_Z], 'itrack', tmag=1200, tag=object()); ts = straight([0, 0, TOP_Z], [1600, 0, TOP_Z], 'itrack', tmag=1200, tag=object())
        p.track(td, ts)
        p.platforms.append((-800, 0, 180.0, kind, td)); p.platforms.append((800, 0, 180.0, 'station', ts))
        p.signal(-1600, 0, [1, 0, 0], 'block'); p.signal(1600, 0, [1, 0, 0], 'block')
        p.railings_x(-2000, 2000, 2000, +1); p.railings_x(-2000, 2000, -2000, -1); p.beam(-2000, -2000, 2000, -2000); p.beam(-2000, 2000, 2000, 2000)
        P.append(p)
    return P

if __name__ == '__main__':
    H_tpl, _ = sbp.load(f'{SRC}/{TEMPLATE}.sbp')
    for p in pieces():
        for cx, cy, suffix in p.boxes:
            fname, n, cost = build_box(p, cx, cy, suffix, H_tpl)
            print(f'{fname}: {n} actors, cost {cost}')
