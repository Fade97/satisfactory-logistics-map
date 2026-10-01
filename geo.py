"""Network geometry (rails, pipes, belts) from FRM → /api/geo.

Changes rarely — so mapd fetches it only every few minutes, not on the 5-second tick.
Coordinates in metres as integers; polylines are simplified (Douglas-Peucker).
"""
import datetime, json

import frm

TOL = 2.0                                   # metres: anything below is invisible on the map


def simplify(pts, tol=TOL):
    """Douglas-Peucker polyline simplification, iterative. pts: [(x, y)] in metres."""
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
        out.append([[round(x), round(y)] for x, y in simplify(ded, tol)])
    return out


def build():
    return dict(at=datetime.datetime.now().isoformat(timespec='seconds'),
                rails=_lines(frm.get('getTrainRails')),
                pipes=_lines(frm.get('getPipes')),
                belts=_lines(frm.get('getBelts')))


if __name__ == '__main__':
    d = build()
    print('geo: %.1f MB · %d rails, %d pipes, %d belts' % (
        len(json.dumps(d, separators=(',', ':'))) / 1e6, len(d['rails']), len(d['pipes']), len(d['belts'])))
