"""Loops: save (60 s), FRM factory (60 s), live (5 s), sink (60 s)."""
import datetime, os, time, traceback

import frm
from . import source
from factory import EXTRACT
from .core import ST, DB, log, paused, frm_status, status_obj, SAVES, LIVE_EVERY, FACTORY_EVERY, SAVE_EVERY
from .factory import publish_factory
from .events import live_events, changelog, growth, storage_events
from .logistics import fill_levels


# World extent of the game map (frontend/public/map.jpg) in cm — standard bounds of the Satisfactory map render,
# verified against the resource nodes: all 490 lie on land
MAP = dict(west=-324698.832031, east=425301.832031, north=-375000.0, south=375000.0, image='map.jpg')


# ================================================================ save cycle
def save_cycle(no_fetch=False):
    import stations, factory
    if no_fetch:
        path = os.path.join(SAVES, 'latest.sav'); changed = ST.stations is None
        label = open(os.path.join(SAVES, 'latest.stamp')).read().split('|')[0].rsplit('/', 1)[-1]
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
        import planner
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
        import lightweight
        ST.put('detail', lightweight.detail_binary(S))
    except Exception as e:
        log('Detail layer:', repr(e)[:120])
    ST.put('storage', fac.get('storage') or [])
    if fac.get('sink') and not paused():
        DB.put_series(mtime, {'sink:points': fac['sink']['points'], 'sink:coupons': fac['sink']['coupons']})
    storage_events(fac.get('storage') or [])
    ST.put('powerlines', fac['powerlines'])
    ST.put('progress', fac['progress'])
    if not ST.frm_ok or ST.geo is None:          # network geometry from the save while FRM is missing
        ST.geo = dict(at=saved_at, source='save', rails=fac['rails'], pipes=fac['pipes'], belts=fac['belts'])
        ST.put('geo', ST.geo)
    if not ST.frm_ok or ST.factory is None:
        publish_factory(fac, 'save', mtime)
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
            frm_status(True)
            live['source'] = 'frm'
            ST.live = live
            ST.put('live', live)
            DB.trail_add(t, live['players'])
            record_frame(t, live)
            live_events(live)
        except Exception as e:
            frm_status(False, e)
            if ST.stations:                         # fallback: vehicles and players as of the save
                v = ST.stations.get('vehicles', {})
                ST.put('live', dict(at=ST.save_meta['saved_at'], source='save', paused=None, session=None,
                                    players=[dict(p, online=None, dead=False, hp=None, speed=None) for p in ST.stations['players']],
                                    trains=v.get('trains', []), trucks=v.get('trucks', []), stations={}))
        ST.put('status', status_obj())
        time.sleep(max(1, LIVE_EVERY - (time.time() - t)))


_last_frame = [0]


def record_frame(t, live):
    """Time travel: once per minute record everything that moves + factory state (not while paused)."""
    if t - _last_frame[0] < 60 or paused():
        return
    _last_frame[0] = t
    P = lambda v: [round(v['pos'][0] / 100), round(v['pos'][1] / 100)]
    fac = ST.factory or {}
    DB.frame_put(t, dict(
        p=[[x['name'], *P(x), 1 if x.get('online') else 0] for x in live.get('players', [])],
        tr=[[x['name'], *P(x), round(x.get('speed') or 0), 1 if x.get('docked') else 0] for x in live.get('trains', [])],
        tk=[[x.get('id') or x['name'], *P(x), round(x.get('speed') or 0)] for x in live.get('trucks', [])],
        # per factory: share running / starved of input (0–100)
        f=[[f['key'], round(100 * ((f['states'].get('running', 0) + f['states'].get('partial', 0)) / max(1, f['n']))),
            round(100 * f.get('starved', 0) / max(1, f['n']))] for f in fac.get('factories', [])],
        pw=[[c['id'], round(c['use']), round(c['cap'])] for c in fac.get('circuits', []) if c.get('cap')],
    ))


def factory_loop():
    import geo
    last_geo = 0
    while True:
        t = time.time()
        if ST.frm_ok:
            try:
                fac = frm_factory()
                publish_factory(fac, 'frm', t)
                if t - last_geo > 900:
                    g = geo.build(); g['source'] = 'frm'
                    ST.geo = g; ST.put('geo', dict(at=g['at'], source='frm', rails=g['rails'], pipes=g['pipes'], belts=g['belts']))
                    last_geo = t
            except Exception as e:
                log('FRM factory failed:', repr(e)[:160])
        elif ST.factory is not None and ST.factory_source == 'save':
            pass                                    # keep the save state; refreshed with the next autosave
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
        except (SystemExit, source.SourceError) as e:
            ST.save_error = str(e)
            log('Save fetch:', e)
        except Exception as e:
            ST.save_error = 'Save not readable: ' + repr(e)[:200]
            log('Save run failed:\n' + traceback.format_exc()[-800:])
        time.sleep(SAVE_EVERY)


def frm_factory():
    """Machines/power from FRM in the same shape as factory.build — the save fills in what FRM lacks."""
    save_fac = getattr(ST, 'save_factory', None) or {}
    base = {m['id']: m for m in save_fac.get('machines', [])}      # builder, reason, since when: only in the save
    mach = []
    # getFactory only covers production machines; miners, pumps and fracking extractors are in getExtractor
    try:
        extractors = frm.get('getExtractor')
    except frm.FrmError:
        extractors = None
    rows = [(m, False) for m in frm.get('getFactory')] + [(m, True) for m in (extractors or [])]
    for m, is_ex in rows:
        mid = m.get('ID')
        prod, ing = m.get('production') or [], m.get('ingredients') or []
        pi = m.get('PowerInfo') or {}
        pct = m.get('Productivity')
        if pct is None and prod:                      # extractor: utilisation is reported per product
            pct = prod[0].get('ProdPercent')
        pct = float(pct or 0)
        state = ('off' if not m.get('IsConfigured') else 'paused' if m.get('IsPaused')
                 else 'running' if m.get('IsProducing') and pct >= 95
                 else 'partial' if m.get('IsProducing') else 'stopped')
        b = base.get(mid, {})
        recipe = m.get('Recipe') or None
        if is_ex:                                     # names as in the save path so filters/nodes match
            recipe = EXTRACT + (prod[0].get('Name') if prod else (recipe or '?'))
        mach.append(dict(id=mid, cls=m.get('ClassName'), name=m.get('Name'), pos=[round(m['location']['x'] / 100), round(m['location']['y'] / 100)],
                         z=round(m['location']['z'] / 100), recipe=recipe, clock=round(float(m.get('ManuSpeed') or 100) / 100, 3),
                         node=b.get('node'), purity=b.get('purity'), yaw=b.get('yaw', round(float(m['location'].get('rotation') or 0))),
                         state=state, pct=round(pct), circuit=pi.get('CircuitGroupID'),
                         by=b.get('by'), why=b.get('why') if state == 'stopped' else None, since=b.get('since'),
                         fuse=bool(pi.get('FuseTriggered')), power=round(float(pi.get('PowerConsumed') or 0), 1),
                         out=[dict(item=p.get('Name'), rate=round(float(p.get('CurrentProd') or 0), 2), max=round(float(p.get('MaxProd') or 0), 2)) for p in prod],
                         inp=[dict(item=i.get('Name'), rate=round(float(i.get('CurrentConsumed') or 0), 2), max=round(float(i.get('MaxConsumed') or 0), 2)) for i in ing]))
    if extractors is None:
        mach += [x for x in save_fac.get('machines', []) if (x.get('recipe') or '').startswith(EXTRACT)]
    circ = []
    for c in frm.get('getPower'):
        circ.append(dict(id=c.get('CircuitGroupID'), prod=round(float(c.get('PowerProduction') or 0), 1),
                         cap=round(float(c.get('PowerCapacity') or 0), 1), use=round(float(c.get('PowerConsumed') or 0), 1),
                         max_use=round(float(c.get('PowerMaxConsumed') or 0), 1),
                         battery=round(float(c.get('BatteryPercent') or 0), 1), battery_cap=round(float(c.get('BatteryCapacity') or 0), 1),
                         battery_empty=c.get('BatteryTimeEmpty'), battery_full=c.get('BatteryTimeFull'),
                         fuse=bool(c.get('FuseTriggered')),
                         n_mach=sum(1 for m in mach if m['circuit'] == c.get('CircuitGroupID'))))
    # generators: FRM knows output and grid; fuel stock and builder come from the save
    sg = {g['id']: g for g in save_fac.get('generators', [])}
    gens = []
    try:
        rows = frm.get('getGenerators')
    except Exception:
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
    return dict(machines=mach, generators=gens, circuits=circ, batteries=[])

def sink_loop():
    """AWESOME Sink live (FRM): points per minute as a time series, current state for the website."""
    while True:
        if ST.frm_ok:
            try:
                s = frm.get('getResourceSink')[0]
                g = s.get('GraphPoints') or []
                d = dict(source='frm', points=int(s.get('TotalPoints') or 0), coupons=int(s.get('NumCoupon') or 0),
                         to_coupon=int(s.get('PointsToCoupon') or 0), pct=float(s.get('Percent') or 0),
                         per_min=g[-1] if g else None, graph=g)
                ST.put('sink', d)
                if not paused():
                    DB.put_series(time.time(), {'sink:points': d['points'], 'sink:per_min': d['per_min'] or 0, 'sink:coupons': d['coupons']})
            except Exception as e:
                log('Sink:', repr(e)[:120])
        elif ST.save_factory and ST.save_factory.get('sink'):
            ST.put('sink', dict(source='save', **ST.save_factory['sink']))
        time.sleep(60)
