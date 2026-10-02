"""Save body layout: worlds migrated from older game versions mix level and object versions (issue #1). Needs no save."""
import os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import sav, sbp  # noqa: E402

SV = 60
CELLS = 100                            # grid cells; real saves have thousands


def version_data(w):
    w.u32(0); w.i32(522); w.i32(1017); w.i32(3)
    w.raw(struct.pack('<HHH', 5, 3, 2)); w.u32(502094); w.s('++FactoryGame+rel-main'); w.i32(1); w.raw(b'\x01' * 16); w.i32(7)


def header(name):
    return dict(type=0, cls='/Script/FactoryGame.FGTest', root='Persistent_Level', name=name, flags=0, outer='')


def level(w, name, version, objs, persistent=False):
    """objs: [(name, data, object version, with version data)]; version = level save version."""
    if not persistent:
        w.s(name)
    toc = sbp.Writer(); toc.i32(len(objs))
    for n, *_ in objs:
        sbp.write_object_header(toc, header(n))
    toc = toc.o.getvalue()
    data = sbp.Writer(); data.i32(len(objs))
    for n, d, ov, vd in objs:
        if version >= sav.V_WORLD_PARTITION:
            data.i32(ov); data.i32(0)
        data.i32(len(d)); data.raw(d)
        if ov >= sav.V_VERSION_DATA:
            data.i32(1 if vd else 0)
            if vd:
                version_data(data)
    data = data.o.getvalue()
    w.i32(len(toc)); w.i32(0); w.raw(toc)
    w.i32(len(data)); w.i32(0); w.raw(data)
    if persistent:
        w.i32(1); w.s('Persistent_Level'); w.i32(1); w.s('Persistent_Level'); w.s('Persistent_Level:PersistentLevel.Gone')
    else:
        w.i32(version)
        w.i32(1); w.s(name); w.s(name + ':PersistentLevel.Picked')     # collected
        w.i32(1 if version >= sav.V_VERSION_DATA else 0)
        if version >= sav.V_VERSION_DATA:
            version_data(w)


def body(levels):
    w = sbp.Writer()
    w.i32(0); w.i32(0)
    version_data(w)
    w.i32(1); w.s('MainGrid'); w.i32(51200); w.u32(1); w.u32(CELLS)
    for i in range(CELLS):
        w.s('MainGrid_Cell_%d' % i); w.u32(i)
    w.i32(len(levels) - 1)
    for i, l in enumerate(levels):
        level(w, *l, persistent=i == len(levels) - 1)
    w.i32(0)
    return w.o.getvalue()


def test_mixed_level_and_object_versions():
    b = body([
        ('Cell_new', SV, [('Cell_new:A', b'aa', SV, False), ('Cell_new:B', b'bbb', SV, True)]),
        ('Cell_old', 46, [('Cell_old:C', b'c', 46, False), ('Cell_old:D', b'dddd', 46, False)]),   # migrated: no trailing int
        ('Cell_mid', SV, [('Cell_mid:E', b'e', 50, False)]),                                        # old object in a new level
        ('', SV, [('P:F', b'ffffff', SV, False), ('P:G', b'g', 46, False)]),
    ])
    levels, end = sav.parse_levels(b, SV)
    assert end == len(b)
    assert [l['name'] for l in levels] == ['Cell_new', 'Cell_old', 'Cell_mid', '']
    assert [l['version'] for l in levels] == [SV, 46, SV, SV]
    assert all(l['error'] is None for l in levels)
    assert [o for l in levels for o in l['objs']] == [b'aa', b'bbb', b'c', b'dddd', b'e', b'ffffff', b'g']
    assert levels[1]['coll'] == [('Cell_old', 'Cell_old:PersistentLevel.Picked')]


def test_bad_level_does_not_break_the_rest():
    b = bytearray(body([
        ('Cell_bad', SV, [('Cell_bad:A', b'aaaa', SV, False)]),
        ('', SV, [('P:F', b'ff', SV, False)]),
    ]))
    i = b.index(b'aaaa')
    b[i - 4:i] = struct.pack('<i', 2)                      # wrong object size inside the first level
    levels, end = sav.parse_levels(bytes(b), SV)
    assert end == len(b)
    assert levels[0]['error'] and levels[0]['objs'] == []
    assert levels[1]['error'] is None and levels[1]['objs'] == [b'ff']
