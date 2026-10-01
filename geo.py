"""Netzgeometrie (Gleise, Rohre, Bänder), Maschinen und Kartenmarker aus FRM → /api/geo.

Ändert sich selten — mapd holt sie deshalb nur alle paar Minuten, nicht im 5-Sekunden-Takt.
Koordinaten in Metern als Ganzzahlen; Polylinien werden vereinfacht (Douglas-Peucker).
"""
import json, os, sys
import frm

HERE = os.path.dirname(os.path.abspath(__file__))
TOL = 2.0                                   # Meter: alles darunter sieht man auf der Karte nicht


def _rdp(pts, tol):
    """Douglas-Peucker, iterativ (Rekursion reicht bei 134 Punkten, aber so ist es robust)."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1
        n2 = dx * dx + dy * dy
        best, bi = -1.0, -1
        for i in range(a + 1, b):
            x, y = pts[i]
            if n2 == 0:
                d = (x - x1) ** 2 + (y - y1) ** 2
            else:
                t = ((x - x1) * dx + (y - y1) * dy) / n2
                t = 0.0 if t < 0 else 1.0 if t > 1 else t
                d = (x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2
            if d > best:
                best, bi = d, i
        if best > tol * tol:
            keep[bi] = True
            stack += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]


def _lines(rows, tol=TOL):
    out = []
    for r in rows:
        sp = r.get('SplineData') or []
        pts = [(round(p['x'] / 100.0, 1), round(p['y'] / 100.0, 1)) for p in sp]
        ded = [pts[0]] if pts else []
        for p in pts[1:]:
            if p != ded[-1]:
                ded.append(p)
        if len(ded) < 2:
            continue
        out.append([[round(x), round(y)] for x, y in _rdp(ded, tol)])
    return out


def _xy(o):
    l = o.get('location') or {}
    return [round(float(l.get('x') or 0) / 100), round(float(l.get('y') or 0) / 100)]


def build():
    machines = []
    for m in frm.get('getFactory'):
        prod = m.get('production') or []
        ing = m.get('ingredients') or []
        state = ('off' if not m.get('IsConfigured') else 'paused' if m.get('IsPaused')
                 else 'running' if m.get('IsProducing') else 'stopped')
        machines.append(dict(
            name=m.get('Name'), pos=_xy(m), recipe=m.get('Recipe') or None, state=state,
            pct=round(float(m.get('Productivity') or 0)),
            out=[dict(item=p.get('Name'), rate=round(float(p.get('CurrentProd') or 0), 1),
                      max=round(float(p.get('MaxProd') or 0), 1)) for p in prod],
            inp=[dict(item=i.get('Name'), rate=round(float(i.get('CurrentConsumed') or 0), 1))
                 for i in ing],
            fuse=bool((m.get('PowerInfo') or {}).get('FuseTriggered')),
            power=round(float((m.get('PowerInfo') or {}).get('PowerConsumed') or 0), 1)))
    gens = []
    for g in frm.get('getGenerators'):
        fuel = (g.get('FuelInventory') or [])
        gens.append(dict(name=g.get('Name'), pos=_xy(g),
                         prod=round(float(g.get('BaseProd') or 0), 1),
                         fuel=fuel[0].get('Name') if fuel else None))
    markers = [dict(name=m.get('Name'), pos=_xy(m), category=m.get('Category'),
                    type=m.get('MapMarkerType')) for m in frm.get('getMapMarkers')]
    import datetime
    return dict(at=datetime.datetime.now().isoformat(timespec='seconds'),
                rails=_lines(frm.get('getTrainRails')),
                pipes=_lines(frm.get('getPipes')),
                belts=_lines(frm.get('getBelts')),
                machines=machines, generators=gens, markers=markers)


if __name__ == '__main__':
    d = build()
    print('geo: %.1f MB · %d Gleise, %d Rohre, %d Bänder, %d Maschinen, %d Generatoren, %d Marker' % (
        len(json.dumps(d, separators=(',', ':'))) / 1e6, len(d['rails']), len(d['pipes']), len(d['belts']),
        len(d['machines']), len(d['generators']), len(d['markers'])))
