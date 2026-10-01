"""Backend tests against a fixed save (tests/fixtures/sample.sav, copy from 2026-09-30, not in the repo).

    .venv/bin/python -m pytest tests -q
If the fixture is missing: `cp saves/latest.sav tests/fixtures/sample.sav` — the exact numbers below then no
longer hold; the structural tests still do.
"""
import os, sys
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
SAMPLE = os.path.join(HERE, 'fixtures', 'sample.sav')
pytestmark = pytest.mark.skipif(not os.path.exists(SAMPLE), reason='fixture missing')

import factory, stations, planner   # noqa: E402


@pytest.fixture(scope='module')
def S():
    return factory.Save(SAMPLE)


@pytest.fixture(scope='module')
def fac(S):
    return factory.build_from(S, SAMPLE)


# ---------------------------------------------------------------- reading the save
def test_counts(fac):
    assert len(fac['machines']) == 1131
    assert len(fac['generators']) == 85
    assert len(fac['nodes']) == 608
    assert fac['progress']['n_schematics'] == 121


def test_stations(S):
    d = stations.extract(SAMPLE, S.idx)
    assert (len(d['trucks']), len(d['trains']), len(d['routes'])) == (104, 17, 6)
    # direction: if mIsInLoadMode is missing, "load" applies
    assert {s['mode'] for s in d['trucks']} <= {'load', 'unload'}
    assert all(p['mode'] in (None, 'load', 'unload') for s in d['trains'] for p in s['platforms'])


def test_machine_fields(fac):
    for m in fac['machines']:
        assert m['state'] in ('running', 'partial', 'stopped', 'paused', 'off')
        assert 0 <= m['pct'] <= 100
        for x in m['out'] + m['inp']:
            assert x['rate'] <= x['max'] + 1e-6, (m['id'], x)


def test_extractors_have_output(fac):
    ex = [m for m in fac['machines'] if (m.get('recipe') or '').startswith(factory.EXTRACT)]
    assert len(ex) >= 100
    # ores from nodes: purity known, amount > 0 (water pumps have no node)
    ores = [m for m in ex if m['cls'] == 'Build_MinerMk2_C']
    assert ores and all(m['out'] and m['out'][0]['max'] > 0 and m.get('purity') for m in ores)


def test_fluid_units(fac):
    """Fluid recipes are in m³ in the dataset — fuel refinery: 60 Crude Oil → 40 Fuel per minute."""
    fuel = [m for m in fac['machines'] if m.get('recipe') == 'Fuel']
    assert fuel
    m = fuel[0]
    assert abs(m['inp'][0]['max'] / m['clock'] - 60) < 1e-6
    assert abs(m['out'][0]['max'] / m['clock'] - 40) < 1e-6


def test_power_circuits(fac):
    big = max(fac['circuits'], key=lambda c: c['cap'])
    assert big['cap'] > 10000 and big['n_mach'] > 1000
    assert all(c['use'] <= c['max_use'] + 1e-6 for c in fac['circuits'])


def test_belt_flow(fac):
    """Belt contents from the ConveyorChain trails: the large flows must be present."""
    for it in ('Iron Ore', 'Copper Ore', 'Fuel', 'Water'):
        assert len(fac['flow'].get(it, [])) > 50, it


def test_machine_links(fac):
    links = fac['links']
    assert len(links) > 10000
    ids = {m['id'] for m in fac['machines']}
    assert all(a in ids and b in ids and a < b for a, b in links[:500])


def test_header(fac):
    assert fac['session']
    assert fac['playtime'] > 1_000_000


# ---------------------------------------------------------------- planner
@pytest.fixture(scope='module')
def rec(S):
    return planner.unlocked(S)


def test_unlocked_contains_basics(rec):
    for r in ('Recipe_IngotIron_C', 'Recipe_IronPlate_C', 'Recipe_IngotSteel_C', 'Recipe_ResidualPlastic_C'):
        assert r in rec


def test_plan_iron_plate(rec):
    r = planner.solve({planner.item_key('Iron Plate'): 60}, rec)
    assert r['ok']
    # standard route: 90 Iron Ore → 90 Ingot → 60 Plate (alternates may need less)
    ore = next(x['rate'] for x in r['raw'] if x['item'] == 'Iron Ore')
    assert 0 < ore <= 90 + 1e-6


def test_plan_balance_closes(rec):
    """Every intermediate item is produced at least as much as it is consumed."""
    r = planner.solve({planner.item_key('Heavy Modular Frame'): 5}, rec)
    assert r['ok']
    bal = {}
    for s in r['steps']:
        for o in s['out']:
            bal[o['item']] = bal.get(o['item'], 0) + o['rate']
        for i in s['inp']:
            bal[i['item']] = bal.get(i['item'], 0) - i['rate']
    for x in r['raw'] + r['surplus_used']:
        bal[x['item']] = bal.get(x['item'], 0) + x['rate']
    bal['Heavy Modular Frame'] -= 5
    assert min(bal.values()) > -1e-3, {k: v for k, v in bal.items() if v < -1e-3}


def test_plan_goals_and_boosts(rec):
    t = {planner.item_key('Heavy Modular Frame'): 5}
    raw = planner.solve(t, rec, goal='raw')
    mach = planner.solve(t, rec, goal='machines')
    fast = planner.solve(t, rec, goal='raw', max_clock=2.5)
    sl = planner.solve(t, rec, goal='raw', sloop=True)
    assert mach['machines'] <= raw['machines']
    assert fast['machines'] < raw['machines'] and fast['shards'] > 0
    ore = lambda r: sum(x['rate'] for x in r['raw'] if x['item'] == 'Iron Ore')
    assert ore(sl) < ore(raw) / 2


def test_plan_exclude(rec):
    t = {planner.item_key('Steel Beam'): 60}
    r = planner.solve(t, rec)
    used = {s['cls'] for s in r['steps']}
    r2 = planner.solve(t, rec, exclude=used & {x for x in rec if 'Beam' in x})
    assert r2['ok'] and not ({s['cls'] for s in r2['steps']} & used & {x for x in rec if 'Beam' in x})


def test_plan_unknown_item():
    with pytest.raises(KeyError):
        planner.item_key('Unobtainium')


# ---------------------------------------------------------------- service logic
def test_clusters_by_belts(fac):
    from mapsvc import production
    for m in fac['machines']:
        m['block'] = production.block_kind(m)
    cl = production.clusters(fac['machines'], fac['links'])
    assert 20 <= len(cl) <= 80
    names = [c['name'] for c in cl]
    assert len(names) == len(set(names)), 'automatic names must be unique'
    assert sum(c['n'] for c in cl) <= len(fac['machines'])


def test_balance_counts_generators(fac):
    from mapsvc import production
    b = {x['item']: x for x in production.balance(fac['machines'], fac['generators'])}
    assert b['Fuel']['cons'] > 1000, 'power plants must consume Fuel'


def test_compact_train_series_keeps_totals(tmp_path):
    """train:* minutes only exist when something moved — the hourly value must be the mean over the whole hour."""
    import store
    db = store.Store(str(tmp_path / 't.db'))
    h = 1_000_000 // 3600 * 3600
    for i, v in enumerate((60, 60, 30)):
        db.put_series(h + 60 * i, {'train:A:+:Iron Plate': v, 'power:1:use': v})
    db.compact(h + 3600 + 30)
    rows = dict(((k, t), v) for k, t, v in db.db.execute('SELECT key, t, v FROM series_hour'))
    assert rows[('train:A:+:Iron Plate', h)] * 60 == 150         # SUM(hour) * 60 = items moved
    assert rows[('power:1:use', h)] == 50                        # other series: average


def test_frm_status_back_only_after_loss():
    from mapsvc.core import ST, DB, frm_status
    saved = ST.frm_ok, ST.frm_since, ST.save_meta
    try:
        ST.frm_ok, ST.frm_since, ST.save_meta = False, None, dict(file='x')
        n = lambda: sum(1 for e in DB.events(limit=500) if e['ref'] == 'frm')
        before = n()
        frm_status(True)                                         # first contact: no "back" event
        assert n() == before
        frm_status(False, 'down')
        frm_status(True)
        assert n() == before + 2                                 # lost + back
    finally:
        ST.frm_ok, ST.frm_since, ST.save_meta = saved


# ---------------------------------------------------------------- round 5: collectibles, storage, blueprints
def test_collectibles(S):
    c = factory.collectibles(S)
    assert c['total']['somersloop'] == 106
    assert 0 < len(c['open']['somersloop']) <= 106
    assert all(len(p) == 3 for p in c['open']['mercer'])


def test_storage(S):
    st = factory.storage(S)
    assert len(st) > 300
    assert all(x['fill'] is None or 0 <= x['fill'] <= 1 for x in st)
    tanks = [x for x in st if 'Tank' in x['cls'] and x['items']]
    assert tanks and all(t['items'][0]['item'] != '?' for t in tanks), 'determine tank contents via the pipe network'


def test_lightweight(S):
    import lightweight
    res = lightweight.parse(S)
    assert sum(len(i) for _, i in res) > 50000
    d = lightweight.detail(S)
    assert len(d['tiles']) > 10000 and len(d['walls']) > 5000
    b = lightweight.detail_binary(S)
    import struct
    nt, nw = struct.unpack_from('<ii', b)
    assert len(b) == 8 + 6 * nt + nt + (nt % 2) + 10 * nw
