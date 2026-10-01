"""Client for FicsIt Remote Monitoring (FRM) on the game server — optional.

Address via FRM_URL (e.g. http://gameserver:8080). Empty = off: the map then runs from the save only.

    python3 frm.py probe               # which endpoints respond?
    python3 frm.py live                # players/vehicles summarised
    python3 frm.py getPlayer           # raw response of an endpoint
"""
import datetime, json, os, sys, urllib.error, urllib.request

from gamedata import is_fluid

BASE = os.environ.get('FRM_URL', '').rstrip('/')
TIMEOUT = float(os.environ.get('FRM_TIMEOUT', '8'))
CMS_TO_KMH = 0.036                          # FRM speeds are cm/s


class FrmError(Exception):
    pass


def get(endpoint, timeout=None):
    if not BASE:
        raise FrmError('FRM not configured (FRM_URL empty)')
    try:
        with urllib.request.urlopen(BASE + '/' + endpoint.lstrip('/'), timeout=timeout or TIMEOUT) as r:
            return json.loads(r.read().decode('utf-8', 'replace'))
    except Exception as e:
        raise FrmError('%s: %s' % (endpoint, repr(e)[:120]))


def _xyz(o):
    l = o.get('location') or {}
    return [round(float(l.get('x') or 0), 1), round(float(l.get('y') or 0), 1), round(float(l.get('z') or 0), 1)]


def _first_item(o, field='Inventory'):
    for i in o.get(field) or []:
        if i.get('Amount'):
            return dict(item=i.get('Name'), amount=i.get('Amount'))
    return None


def players():
    return sorted([dict(name=p.get('Name') or '(unknown)', pos=_xyz(p),
                        online=bool(p.get('Online')), dead=bool(p.get('Dead')),
                        hp=round(float(p.get('PlayerHP') or 0)),
                        speed=round(float(p.get('Speed') or 0), 1), vehicle=None,
                        inventory=[dict(Name=i.get('Name'), Amount=i.get('Amount'))
                                   for i in (p.get('Inventory') or []) if i.get('Amount')][:20])
                   for p in get('getPlayer')], key=lambda p: p['name'])


def trains():
    out = []
    for t in get('getTrains'):
        out.append(dict(name=t.get('Name') or '(unnamed)', pos=_xyz(t),
                        status=t.get('Status'), station=t.get('TrainStation'),
                        speed=round(abs(float(t.get('ForwardSpeed') or 0)) * CMS_TO_KMH, 1),
                        derailed=bool(t.get('Derailed')),
                        payload=round(float(t.get('PayloadMass') or 0)),
                        max_payload=round(float(t.get('MaxPayloadMass') or 0)),
                        docked=t.get('Docking') == 'TDS_Docked',
                        cargo=_train_cargo(t),
                        wagons=sum(1 for v in t.get('Vehicles') or [] if 'Wagon' in (v.get('ClassName') or '')),
                        fluid_wagons=sum(1 for v in t.get('Vehicles') or [] if 'Wagon' in (v.get('ClassName') or '') and
                                         any(is_fluid(i.get('ClassName') or '') for i in v.get('Inventory') or [])),
                        stops=[s.get('StationName') for s in (t.get('TimeTable') or [])]))
    return sorted(out, key=lambda t: t['name'])


def _train_cargo(t):
    """Cargo of all wagons combined: {item: amount} (fluids in m³ as shown in game)."""
    out = {}
    for v in t.get('Vehicles') or []:
        for i in v.get('Inventory') or []:
            if i.get('Amount'):
                out[i['Name']] = out.get(i['Name'], 0) + i['Amount']
    return out


def trucks():
    out = []
    rows = [(v, 'Truck') for v in get('getTruck')] + [(v, 'Tractor') for v in get('getTractor')]
    for v, vtype in rows:
        out.append(dict(id=v.get('ID'), type=vtype, name=v.get('Name') or '(unnamed)', pos=_xyz(v),
                        speed=round(abs(float(v.get('ForwardSpeed') or 0)) * CMS_TO_KMH, 1),
                        autopilot=bool(v.get('Autopilot')), fuel=bool(v.get('HasFuel')),
                        cargo=_first_item(v)))
    return sorted(out, key=lambda t: t['name'])


def station_status():
    """Live state per truck station, key = object name from the save."""
    out = {}
    for s in get('getTruckStation'):
        out[s['ID']] = dict(activity=s.get('LoadMode'), status=s.get('StationStatus'),
                            rate=round(float(s.get('TransferRate') or 0), 2),
                            item=(_first_item(s) or {}).get('item'),
                            amount=(_first_item(s) or {}).get('amount'))
    for s in get('getTrainStation'):
        out[s['ID']] = dict(activity=None, status=None,
                            rate=round(float(s.get('TransferRate') or 0), 2),
                            inflow=round(float(s.get('InflowRate') or 0), 2),
                            outflow=round(float(s.get('OutflowRate') or 0), 2))
    return out


def live():
    s = get('getSessionInfo')
    return dict(at=datetime.datetime.now().isoformat(timespec='seconds'),
                paused=bool(s.get('IsPaused')),
                session=dict(name=s.get('SessionName'), day=s.get('PassedDays'),
                             clock='%02d:%02d' % (s.get('Hours') or 0, s.get('Minutes') or 0),
                             is_day=bool(s.get('IsDay'))),
                players=players(), trains=trains(), trucks=trucks(), stations=station_status())


PROBE = ['getSessionInfo', 'getPlayer', 'getTruckStation', 'getTrainStation', 'getTrains',
         'getTruck', 'getDroneStation', 'getPower', 'getModList']


def probe():
    ok = 0
    for e in PROBE:
        try:
            r = get(e, timeout=15)
            n = len(r) if isinstance(r, list) else 1
            print('  %-18s OK   %s' % (e, ('%d entries' % n) if isinstance(r, list) else 'object'))
            ok += 1
        except FrmError as err:
            print('  %-18s %s' % (e, err))
    print('%d/%d endpoints respond' % (ok, len(PROBE)))
    return 0 if ok == len(PROBE) else 1


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'probe'
    if cmd == 'probe':
        sys.exit(probe())
    if cmd == 'live':
        d = live()
        print('%s · %d players (%d online), %d trains, %d trucks%s' % (
            d['at'], len(d['players']), sum(p['online'] for p in d['players']),
            len(d['trains']), len(d['trucks']), ' · paused' if d['paused'] else ''))
    else:
        print(json.dumps(get(cmd), ensure_ascii=False)[:4000])
