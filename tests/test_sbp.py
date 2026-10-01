"""Blueprint tests: every committed .sbp must round-trip byte-exactly; planner blueprints (bpgen). Need no save file."""
import glob, os, sys
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import sbp  # noqa: E402

FILES = sorted(glob.glob(os.path.join(ROOT, 'gamedata', 'templates', '*.sbp'))
               + glob.glob(os.path.join(ROOT, 'blueprints', '**', '*.sbp'), recursive=True))


def test_files_found():
    assert FILES


@pytest.mark.parametrize('path', FILES, ids=lambda p: os.path.relpath(p, ROOT))
def test_roundtrip(path, tmp_path):
    ok_h, ok_b, bad, _ = sbp.roundtrip(path)
    assert ok_h and ok_b and not bad, bad
    H, B = sbp.load(path)
    assert all(o['obj'] is not None for o in B['objs'])
    out = tmp_path / 'out.sbp'
    sbp.save(str(out), H, B)
    assert out.read_bytes() == open(path, 'rb').read()


def test_strings_utf16_length():
    w = sbp.Writer(); w.s('Bahnhof Süd'); w.s('🚂 Zug')
    r = sbp.Reader(w.bytes())
    assert (r.s(), r.s()) == ('Bahnhof Süd', '🚂 Zug')
    assert r.eof()


def test_int8_signed_roundtrip():
    p = dict(name='X', type=sbp.T('Int8Property'), flags=0, value=-3)
    w = sbp.Writer(); sbp.write_props(w, [p]); data = w.bytes()
    props = sbp.parse_props(sbp.Reader(data))
    assert props[0]['value'] == -3
    w2 = sbp.Writer(); sbp.write_props(w2, props)
    assert w2.bytes() == data


# ---------------------------------------------------------------- planner blueprints (bpgen)
def test_blueprint_roundtrip(tmp_path, monkeypatch):
    import bpgen, sbp
    monkeypatch.setattr(bpgen, 'OUT', str(tmp_path))
    path, info = bpgen.build(dict(cls='Recipe_IronPlate_C', building='Constructor', machines=3, full_clock=100, clock=None))
    H, B = sbp.load(path)
    mach = [o for h, o in zip(B['headers'], B['objs']) if h['type'] == 1 and h['cls'].endswith('Build_ConstructorMk1_C')]
    assert len(mach) == 3
    for o in mach:
        rec = [p['value'][1] for p in o['obj']['props'] if p['name'] == 'mCurrentRecipe']
        assert rec and rec[0].endswith('Recipe_IronPlate_C')
    # byte-exact round trip and no dangling references to removed machines
    names = {h['name'] for h in B['headers']}
    for o in B['objs']:
        for p in o['obj']['props']:
            if p['name'] == 'mConnectedComponent' and p['value'][1]:
                assert p['value'][1] in names


def test_blueprint_rejects_unsupported():
    import bpgen
    with pytest.raises(bpgen.BpError):
        bpgen.build(dict(cls='Recipe_IngotSteel_C', building='Foundry', machines=2, full_clock=100, clock=None))
