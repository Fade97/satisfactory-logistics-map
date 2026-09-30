"""Anbindung des Produktionsrechners an den Dienst (/api/plan)."""
import threading

from .core import ST
from .factory import balance


# ================================================================ Produktionsrechner
PLAN_LOCK = threading.Semaphore(2)


def plan(b):
    """POST /api/plan {targets:[{item,rate}], exclude:[recipe], use_surplus:bool, only_unlocked:bool}"""
    import planner
    try:
        targets = {planner.item_key(t['item']): float(t['rate']) for t in (b.get('targets') or [])[:8]
                   if 0 < float(t['rate']) <= 100000}
    except (KeyError, ValueError, TypeError):
        return dict(ok=False, error='Unknown item or invalid amount')
    if not targets:
        return dict(ok=False, error='Add at least one target')
    rec = getattr(ST, 'unlocked', None) or set()
    if not b.get('only_unlocked', True):
        rec = {r for r, R in planner.RECIPES.items() if R['inMachine'] and R['producedIn']}
    surplus = None
    if b.get('use_surplus', True) and ST.factory:
        surplus = {}
        for x in balance(ST.factory['machines'], ST.factory['generators']):
            net = x['prod'] - x['cons']
            if net > 0.5:
                try:
                    surplus[planner.item_key(x['item'])] = round(net * 0.9, 2)    # 10 % Luft lassen
                except KeyError:
                    pass
    if not PLAN_LOCK.acquire(timeout=10):
        return dict(ok=False, error='Planner is busy, try again in a moment')
    try:
        goal = b.get('goal') if b.get('goal') in ('raw', 'machines', 'power') else 'raw'
        clock = min(2.5, max(0.01, float(b.get('max_clock') or 1.0)))
        # Rezeptwahl je Ware: {item_name: [erlaubte Rezeptklassen]} → alle anderen Rezepte dieser Ware ausschließen
        excl = set(b.get('exclude') or [])
        for item_name, allowed in (b.get('allow') or {}).items():
            try:
                k = planner.item_key(item_name)
            except KeyError:
                continue
            for r in rec:
                if any(p['item'] == k for p in planner.RECIPES[r]['products']) and r not in set(allowed):
                    excl.add(r)
        return planner.solve(targets, rec, surplus, exclude=excl, goal=goal, max_clock=clock, sloop=bool(b.get('sloop')))
    finally:
        PLAN_LOCK.release()
