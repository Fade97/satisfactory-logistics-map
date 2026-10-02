"""Satisfactory .sav reader (read-only) - returns object headers + raw object data per level.

File: int32 header version, int32 save version, int32 build, … then zlib chunks (same as .sbp, see sbp.py).
Inflated body (layout as in the community parser satisfactory-file-parser):
    int32 body size, int32 0
    version data (save version >= 53, see read_version_data)
    grid validation (>= 38): int32 n × (string grid, int32 cell size, uint32 hash, uint32 m × (string level, uint32 hash))
    int32 level count, then count+1 levels; all but the last start with their name, the last is the persistent level:
        int32 TOC bytes, int32 0, TOC:  int32 n, n object headers, [collectables / destroyed actors]
        int32 data bytes, int32 0, data: int32 n, n × object
        sublevel:   [int32 level save version (>= 51)], refs list, [int32 has version data (>= 53) + version data]
        persistent: destroyed actors: int32 n × (string level, refs list)
    object: [int32 object save version, int32 migrate flag (level version >= 38)], int32 size, data,
            [int32 has version data + version data (object version >= 53)]
    int32 n + n refs (unresolved world save data)

Worlds that were migrated from older game versions keep sublevels and objects in their old version, so the level
and object versions above vary inside one save — the framing therefore follows the stored sizes and versions.
"""
import struct, sys
import sbp

# save versions (FGSaveCustomVersion) that change the layout
V_WORLD_PARTITION = 38                # per-object save version + migrate flag
V_PER_LEVEL_VERSION = 51              # sublevels store their own save version
V_VERSION_DATA = 53                   # optional package/engine/custom version block per body, level and object
ENGINE_VERSION_BYTES = 6              # uint16 major, minor, patch
CUSTOM_VERSION_BYTES = 20             # guid16 + int32 version


def save_version(path):
    """(header version, save version, build) from the start of the file."""
    with open(path, 'rb') as f:
        return struct.unpack('<iii', f.read(12))


def read_body(path):
    with open(path, 'rb') as f:
        d = f.read()
    return sbp.read_chunks(d, d.find(sbp.MAGIC))


def read_version_data(r):
    """FSaveObjectVersionData: uint32 version, int32 UE4 + UE5 package version, int32 licensee,
    engine version (uint16[3], uint32 changelist, string branch), custom versions (int32 n × guid16 + int32)."""
    r.u32(); ue4 = r.i32(); ue5 = r.i32(); r.i32()
    r.raw(ENGINE_VERSION_BYTES); r.u32(); r.s()
    r.raw(CUSTOM_VERSION_BYTES * r.i32())
    return ue4, ue5


def read_refs(r):
    return [(r.s(), r.s()) for _ in range(r.i32())]          # (level name, path name)


def read_destroyed(r):
    return [(r.s(), read_refs(r)) for _ in range(r.i32())]   # (level name, refs)


def skip_grids(r):
    for _ in range(r.i32()):
        r.s(); r.i32(); r.u32()
        for _ in range(r.u32()):
            r.s(); r.u32()


def read_level(r, name, persistent, version):
    """One level at r (after its name). Returns dict(name, version, headers, objs, coll, error)."""
    body = r.b
    toc_len = r.i32(); r.i32(); toc_at = r.p; r.p += toc_len
    data_len = r.i32(); r.i32(); data_at = r.p; r.p += data_len
    level = dict(name=name, version=version, headers=[], objs=[], coll=[], error=None)
    if persistent:
        level['coll'] = read_destroyed(r)
    else:
        if version >= V_PER_LEVEL_VERSION:
            level['version'] = r.i32()
        level['coll'] = read_refs(r)
        if version >= V_VERSION_DATA and r.i32() >= 1:
            read_version_data(r)
    # TOC and data are bounded by their sizes: an error inside one level does not affect the next
    try:
        t = sbp.Reader(body, toc_at)
        level['headers'] = [sbp.read_object_header(t) for _ in range(t.i32())]
        if t.p < toc_at + toc_len:                          # newer saves repeat the list inside the TOC
            level['coll'] = read_destroyed(t) if persistent else read_refs(t)
        d = sbp.Reader(body, data_at)
        n = d.i32()
        if n != len(level['headers']):
            raise ValueError('%d objects for %d headers' % (n, len(level['headers'])))
        for _ in range(n):
            ov = level['version']
            if level['version'] >= V_WORLD_PARTITION:
                ov = d.i32(); d.i32()                       # object save version, migrate flag
            level['objs'].append(d.raw(d.i32()))
            if ov >= V_VERSION_DATA and d.i32() == 1:
                read_version_data(d)
        if d.p != data_at + data_len:
            raise ValueError('object data ends at %d, expected %d' % (d.p, data_at + data_len))
    except Exception as e:
        level.update(headers=[], objs=[], error=repr(e)[:160])
    return level


def parse_levels(body, version):
    """All levels of an inflated body; version = save version from the file header. Returns (levels, end offset)."""
    r = sbp.Reader(body)
    r.i32(); r.i32()                                        # body size, 0
    if version >= V_VERSION_DATA:
        read_version_data(r)
    if version >= V_WORLD_PARTITION:
        skip_grids(r)
    count = r.i32()
    levels = [read_level(r, r.s() if i < count else '', i == count, version) for i in range(count + 1)]
    if r.p < len(body):
        read_refs(r)                                        # unresolved world save data
    return levels, r.p


def load_index(path):
    """name -> (header, raw object data) over all levels; levels that could not be read are reported on stderr."""
    levels, _ = parse_levels(read_body(path), save_version(path)[1])
    bad = [l for l in levels if l['error']]
    if bad:
        print('sav: %d of %d levels unreadable, e.g. %s: %s' % (len(bad), len(levels), bad[0]['name'] or 'persistent', bad[0]['error']),
              file=sys.stderr)
    idx = {}
    for l in levels:
        for h, o in zip(l['headers'], l['objs']):
            idx[h['name']] = (h, o)
    return idx


def obj(idx, name):
    h, o = idx[name]
    try: return h, sbp.parse_object(o, h['type'] == 1)
    except Exception as e: return h, dict(err=repr(e)[:80], raw=o)


def show(idx, name, maxlen=200):
    h, ob = obj(idx, name)
    if h['type'] == 1: print('A', sbp.short(h['cls']), sbp.short(h['name']), 'pos', [round(x, 1) for x in h['pos']], 'rot', [round(x, 4) for x in h['rot']], 'fl', h['flags'])
    else: print('C', sbp.short(h['cls']), h['name'].split('.', 1)[-1], 'fl', h['flags'])
    if 'err' in ob: print('   RAW', ob['err'], ob['raw'][:120]); return ob
    if h['type'] == 1: print('   parent', sbp.short(ob['parent'][1]), 'comps', [c[1].split('.', 1)[-1] for c in ob['components']])
    for p in ob['props']: print('   -', p['name'], sbp.typestr(p['type']), 'fl', p['flags'], repr(p['value'])[:maxlen])
    if ob['trail']: print('   trail', ob['trail'][:40].hex(), len(ob['trail']))
    return ob


if __name__ == '__main__':
    # python sav.py <file.sav>  — structure check: levels, versions, unreadable levels
    from collections import Counter
    hv, sv, build = save_version(sys.argv[1])
    body = read_body(sys.argv[1])
    levels, end = parse_levels(body, sv)
    print('header version', hv, 'save version', sv, 'build', build)
    print('levels', len(levels), 'end', end, 'of', len(body))
    print('level versions', dict(sorted(Counter(l['version'] for l in levels).items())))
    print('headers total', sum(len(l['headers']) for l in levels), '· persistent level', len(levels[-1]['headers']))
    bad = [l for l in levels if l['error']]
    print('unreadable levels', len(bad))
    for l in bad[:10]:
        print('  ', l['name'] or 'persistent', 'v%d' % l['version'], l['error'])
