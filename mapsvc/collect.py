"""Loops: save (60 s), FRM factory (60 s), live (5 s), sink (60 s)."""
import datetime, os, time, traceback

import frm
import geo
import lightweight
import stations
import factory
from factory import EXTRACT
from . import source
from .core import ST, DB, log, paused, frm_status, status_obj, SAVES, LIVE_EVERY, FACTORY_EVERY, SAVE_EVERY
from .production import publish_factory
from .events import live_events, changelog, growth, storage_events
from .logistics import fill_levels


# World extent of the game map (frontend/public/map.jpg) in cm — standard bounds of the Satisfactory map render,
# verified against the resource nodes: all 490 lie on land
MAP = dict(west=-324698.832031, east=425301.832031, north=-375000.0, south=375000.0, image='map.jpg')

SINK_EVERY = 60             # s: AWESOME Sink poll
GEO_EVERY = 900             # s: network geometry from FRM (changes rarely, large)
FRAME_EVERY = 60            # s: time-travel frame
RUNNING_PCT = 95            # productivity from which a producing machine counts as 'running' (below: 'partial')

_warned = set()


def _log_once(key, *a):
    if key not in _warned:
        _warned.add(key)
        log(*a)


# ================================================================ save cycle
def save_cycle(no_fetch=False):
    if no_fetch:
        path = os.path.join(SAVES, 'latest.sav'); changed = ST.stations is None
        with open(os.path.join(SAVES, 'latest.stamp')) as f:
            label = f.read().split('|')[0].rsplit('/', 1)[-1]
        mtime = os.path.getmtime(path)
    else:
        path, label, mtime, changed = source.fetch_latest()
    if not changed and ST.stations is not None:
        return
    t0 = time.time()
    S = factory.Save(path)
    data = stations.extract(path, S.idx)
    fac = factory.build_from(S)
    saved_at = datetime.datetime.fromtimestamp(mtime).isoformat(timespec='seconds')
    ST.save_meta = dict(file=label, saved_at=saved_at, mtime=int(mtime), parsed_in=round(time.time() - t0, 1),
                        playtime=fac.get('playtime'), session=fac.get('session'))
    fill_levels(data)
    ST.stations = data
    try:
        import planner          # lazy: pulls in numpy/scipy
        ST.unlocked = planner.unlocked(S)
        ST.put('recipes', planner.recipe_list(ST.unlocked))
    except Exception as e:
        log('Recipes:', repr(e)[:120])
    data['map'] = MAP
    data['source'] = dict(save=label, saved_at=saved_at, rendered_at=datetime.datetime.now().isoformat(timespec='seconds'),
                          label='Save %s · saved %s' % (label, datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')))
    ST.put('stations', data)
    ST.put('nodes', fac['nodes'])
    ST.put('flow', fac.get('flow') or {})
    ST.put('collectibles', fac.get('collectibles') or {})
    try:                                               # detail layer: foundations + walls (lightweight buildables)
        ST.put('detail', lightweight.detail_binary(S))
    except Exception as e:
        log('Detail layer:', repr(e)[:120])
    ST.put('storage', fac.get('storage') or [])
    if fac.get('sink') and not paused():
        DB.put_series(mtime, {'sink:points': fac['sink']['points'], 'sink:coupons': fac['sink']['coupons']})
    ST.put('powerlines', fac['powerlines'])
    ST.put('progress', fac['progress'])
    if not ST.frm_ok or ST.geo is None:          # network geometry from the save while FRM is missing
        ST.geo = dict(at=saved_at, source='save', rails=fac['rails'], pipes=fac['pipes'], belts=fac['belts'])
        ST.put('geo', ST.geo)
    if not ST.frm_ok or ST.factory is None:
        publish_factory(fac, 'save', mtime)
    storage_events(fac.get('storage') or [])     # after publishing: needs the machines' block reason
    changelog(fac, mtime)
    growth(fac, mtime)
    log('Save %s read (%.1fs): %d machines, %d stations' % (label, time.time() - t0, len(fac['machines']),
                                                                 len(data['trucks']) + len(data['trains'])))


# ================================================================ loops
def live_loop():
    while True:
        t = time.time()
        try:
            live = frm.live()
        except Exception as e:
            live = None
            frm_status(False, e)
            if ST.stations:                         # fallback: vehicles and players as of the save
                v = ST.stations.get('vehicles', {})
                ST.put('live', dict(at=ST.save_meta['saved_at'], source='save', paused=None, session=None,
                                    players=[dict(p, online=None, dead=False, hp=None, speed=None) for p in ST.stations['players']],
                                    trains=v.get('trains', []), trucks=v.get('trucks', []), stations={}))
        if live is not None:
            try:                                    # a bug here is ours, not an FRM outage — log it, keep FRM status
                frm_status(True)
                live['source'] = 'frm'
                ST.live = live
                ST.put('live', live)
                DB.trail_add(t, live['players'])
                record_frame(t, live)
                live_events(live)
            except Exception:
                log('Live recording failed:\n' + traceback.format_exc()[-800:])
        ST.put('status', status_obj())
        time.sleep(max(1, LIVE_EVERY - (time.time() - t)))


_last_frame = 0     # time of the last recorded frame


def record_frame(t, live):
    """Time travel: once per minute record everything that moves + factory state (not while paused)."""
    global _last_frame
    if t - _last_frame < FRAME_EVERY or paused():
        return
    _last_frame = t
    pos_m = lambda v: [round(v['pos'][0] / 100), round(v['pos'][1] / 100)]     # cm → m
    fac = ST.factory or {}
    DB.frame_put(t, dict(
        p=[[x['name'], *pos_m(x), 1 if x.get('online') else 0] for x in live.get('players', [])],
        tr=[[x['name'], *pos_m(x), round(x.get('speed') or 0), 1 if x.get('docked') else 0] for x in live.get('trains', [])],
        tk=[[x.get('id') or x['name'], *pos_m(x), round(x.get('speed') or 0)] for x in live.get('trucks', [])],
        # per factory: share running / starved of input (0–100)
        f=[[f['key'], round(100 * ((f['states'].get('running', 0) + f['states'].get('partial', 0)) / max(1, f['n']))),
            round(100 * f.get('starved', 0) / max(1, f['n']))] for f in fac.get('factories', [])],
        pw=[[c['id'], round(c['use']), round(c['cap'])] for c in fac.get('circuits', []) if c.get('cap')],
    ))


def factory_loop():
    last_geo = 0
    while True:
        t = time.time()
        if ST.frm_ok:                               # without FRM the save state stays until the next autosave
            try:
                fac = frm_factory()
                publish_factory(fac, 'frm', t)
                if t - last_geo > GEO_EVERY:
                    g = geo.build(); g['source'] = 'frm'
                    ST.geo = g; ST.put('geo', dict(at=g['at'], source='frm', rails=g['rails'], pipes=g['pipes'], belts=g['belts']))
                    last_geo = t
            except Exception as e:
                log('FRM factory failed:', repr(e)[:160])
        try:
            DB.compact(t)
        except Exception as e:
            log('compact:', e)
        time.sleep(max(5, FACTORY_EVERY - (time.time() - t)))


def save_loop(no_fetch):
    while True:
        try:
            save_cycle(no_fetch)
            ST.save_error = None
        except source.SourceError as e:
            ST.save_error = str(e)
            log('Save fetch:', e)
        except Exception as e:
            ST.save_error = 'Save not readable: ' + repr(e)[:200]
            log('Save run failed:\n' + traceback.format_exc()[-800:])
        time.sleep(SAVE_EVERY)


# ================================================================ FRM factory
def frm_factory():
    """Machines/power from FRM in the same shape as factory.build — the save fills in what FRM lacks."""
    save_fac = ST.save_factory or {}
    base = {m['id']: m for m in save_fac.get('machines', [])}      # builder, reason, since when: only in the save
    # getFactory only covers production machines; miners, pumps and fracking extractors are in getExtractor
    try:
        extractors = frm.get('getExtractor')
    except frm.FrmError as e:
        _log_once('getExtractor', 'FRM getExtractor unavailable, extractors from the save:', e)
        extractors = None
    rows = [(m, False) for m in frm.get('getFactory')] + [(m, True) for m in (extractors or [])]
    mach = [_frm_machine(m, is_ex, base.get(m.get('ID'), {})) for m, is_ex in rows]
    if extractors is None:
        mach += [x for x in save_fac.get('machines', []) if (x.get('recipe') or '').startswith(EXTRACT)]
    return dict(machines=mach, generators=_frm_generators(save_fac), circuits=_frm_circuits(mach), batteries=[])


def _frm_state(m, pct):
    return ('off' if not m.get('IsConfigured') else 'paused' if m.get('IsPaused')
            else 'running' if m.get('IsProducing') and pct >= RUNNING_PCT
            else 'partial' if m.get('IsProducing') else 'stopped')


def _frm_machine(m, is_ex, b):
    """One FRM machine (getFactory/getExtractor row); `b` = the same machine from the save, if known."""
    prod, ing = m.get('production') or [], m.get('ingredients') or []
    pi = m.get('PowerInfo') or {}
    loc = m['location']
    pct = m.get('Productivity')
    if pct is None and prod:                      # extractor: utilisation is reported per product
        pct = prod[0].get('ProdPercent')
    pct = float(pct or 0)
    state = _frm_state(m, pct)
    recipe = m.get('Recipe') or None
    if is_ex:                                     # names as in the save path so filters/nodes match
        recipe = EXTRACT + (prod[0].get('Name') if prod else (recipe or '?'))
    return dict(id=m.get('ID'), cls=m.get('ClassName'), name=m.get('Name'), pos=[round(loc['x'] / 100), round(loc['y'] / 100)],
                z=round(loc['z'] / 100), recipe=recipe, clock=round(float(m.get('ManuSpeed') or 100) / 100, 3),
                node=b.get('node'), purity=b.get('purity'), yaw=b.get('yaw', round(float(loc.get('rotation') or 0))),
                state=state, pct=round(pct), circuit=pi.get('CircuitGroupID'),
                by=b.get('by'), why=b.get('why') if state == 'stopped' else None, since=b.get('since'),
                fuse=bool(pi.get('FuseTriggered')), power=round(float(pi.get('PowerConsumed') or 0), 1),
                out=[dict(item=p.get('Name'), rate=round(float(p.get('CurrentProd') or 0), 2), max=round(float(p.get('MaxProd') or 0), 2)) for p in prod],
                inp=[dict(item=i.get('Name'), rate=round(float(i.get('CurrentConsumed') or 0), 2), max=round(float(i.get('MaxConsumed') or 0), 2)) for i in ing])


def _frm_circuits(mach):
    circ = []
    for c in frm.get('getPower'):
        circ.append(dict(id=c.get('CircuitGroupID'), prod=round(float(c.get('PowerProduction') or 0), 1),
                         cap=round(float(c.get('PowerCapacity') or 0), 1), use=round(float(c.get('PowerConsumed') or 0), 1),
                         max_use=round(float(c.get('PowerMaxConsumed') or 0), 1),
                         battery=round(float(c.get('BatteryPercent') or 0), 1), battery_cap=round(float(c.get('BatteryCapacity') or 0), 1),
                         battery_empty=c.get('BatteryTimeEmpty'), battery_full=c.get('BatteryTimeFull'),
                         fuse=bool(c.get('FuseTriggered')),
                         n_mach=sum(1 for m in mach if m['circuit'] == c.get('CircuitGroupID'))))
    return circ


def _frm_generators(save_fac):
    """FRM knows output and grid; fuel stock and builder come from the save."""
    sg = {g['id']: g for g in save_fac.get('generators', [])}
    gens = []
    try:
        rows = frm.get('getGenerators')
    except frm.FrmError as e:
        _log_once('getGenerators', 'FRM getGenerators unavailable, generators from the save:', e)
        rows = []
    seen = set()
    for g in rows:
        old = sg.get(g.get('ID'), {})
        loc = g.get('location') or {}
        pos = [round(loc['x'] / 100), round(loc['y'] / 100)] if 'x' in loc else old.get('pos')
        if not pos:
            continue
        seen.add(g.get('ID'))
        prod = float(g.get('RegulatedDemandProd') or g.get('ProdPowerComsumption') or 0)
        gens.append(dict(old, id=g.get('ID'), cls=g.get('ClassName') or old.get('cls'), name=g.get('Name') or old.get('name'), pos=pos,
                         circuit=g.get('CircuitID', (g.get('PowerInfo') or {}).get('CircuitGroupID', old.get('circuit'))),
                         cap=round(float(g.get('PowerProductionPotential') or g.get('BaseProd') or old.get('cap') or 0), 1),
                         prod=round(prod, 1), producing=prod > 0 or bool(g.get('IsFullBlast'))))
    gens += [g for k, g in sg.items() if k not in seen and not rows]     # FRM without generators → save state
    return gens


# ================================================================ sink
def sink_loop():
    """AWESOME Sink live (FRM): points per minute as a time series, current state for the website."""
    while True:
        try:
            if ST.frm_ok:
                s = frm.get('getResourceSink')[0]
                g = s.get('GraphPoints') or []
                d = dict(source='frm', points=int(s.get('TotalPoints') or 0), coupons=int(s.get('NumCoupon') or 0),
                         to_coupon=int(s.get('PointsToCoupon') or 0), pct=float(s.get('Percent') or 0),
                         per_min=g[-1] if g else None, graph=g)
                ST.put('sink', d)
                if not paused():
                    DB.put_series(time.time(), {'sink:points': d['points'], 'sink:per_min': d['per_min'] or 0, 'sink:coupons': d['coupons']})
            elif ST.save_factory and ST.save_factory.get('sink'):
                ST.put('sink', dict(source='save', **ST.save_factory['sink']))
        except Exception as e:
            log('Sink:', repr(e)[:120])
        time.sleep(SINK_EVERY)
