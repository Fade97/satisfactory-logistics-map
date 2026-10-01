"""Lightweight buildables from the save: foundations, walls, ramps, beams … (FGLightweightBuildableSubsystem).

The game does not store them as actors but as one list per class in the subsystem's raw trail:
  int32 0, int32 version, int32 class count, per class: int32 0, string class, int32 n,
  n × { double[4] quaternion, double[3] position (cm), double[3] scale,
        objref swatch, material, pattern, skin, float[4] primary, float[4] secondary, objref PaintFinish,
        uint8 PatternRotation, objref recipe, objref BlueprintProxy,
        v≥2: int32 data flag [+ int32 0, string type, int32 size, properties], v≥3: uint8 ServiceProvider, int32 player index }
Layout follows the format that sat_sav_parse reads as well; independent implementation.
"""
import math, struct
import sbp, sav

QUAT_BYTES, POS_BYTES, SCALE_BYTES, COLOURS_BYTES = 32, 24, 24, 32   # double[4], double[3], double[3], float[4] × 2
TILE_CM = 800                           # foundation/roof tile edge
NARROW_CM = 400                         # 4 m walls, railings, barriers
DEDUP_XY_CM, DEDUP_Z_CM = 200, 400      # stacked foundations: one per 2 m cell and 4 m height step


def _ref(r):
    return r.s(), r.s()


def parse(S):
    """Returns [(class, [(x, y, z, yaw_deg), …]), …]; positions in cm."""
    n = next((k for k in S.idx if k.endswith('.LightweightBuildableSubsystem')), None)
    if not n:
        return []
    t = sav.obj(S.idx, n)[1]['trail']
    r = sbp.Reader(t)
    first = r.i32()
    ver = r.i32() if first == 0 else first           # depending on the save there is an extra zero word in front
    ncls = r.i32()
    out = []
    for _ in range(ncls):
        r.i32(); cls = r.s(); cnt = r.i32()
        items = []
        for _ in range(cnt):
            q = struct.unpack_from('<4d', t, r.p); r.p += QUAT_BYTES
            x, y, z = struct.unpack_from('<3d', t, r.p); r.p += POS_BYTES
            r.p += SCALE_BYTES
            _ref(r); _ref(r); _ref(r); _ref(r)         # swatch, material, pattern, skin
            r.p += COLOURS_BYTES                       # primary, secondary
            _ref(r); r.u8(); _ref(r); _ref(r)          # PaintFinish, PatternRotation, recipe, BlueprintProxy
            if ver >= 2:
                if r.i32():
                    r.i32(); r.s(); size = r.i32(); r.p += size
                if ver >= 3:
                    r.u8(); r.i32()
            items.append((x, y, z, sbp.yaw_from_quat(q)))
        out.append((sbp.short(cls), items))
    return out


MATERIAL = [('Asphalt', 1), ('Concrete', 2), ('Polished', 2), ('Metal', 3), ('Glass', 4), ('Frame', 3), ('Tar', 5)]


def detail(S):
    """Compact detail layer for the map (metres, integers):
      tiles: [x, y, yaw/90 step, material, floor z] per foundation/roof — size 8 × 8 m
      walls: [x1, y1, x2, y2, z] per wall/railing (8 m or 4 m wide, along the rotation)
    Foundations stack (8x1 on top of each other): keep only one per grid cell and height."""
    tiles, walls, seen = [], [], set()
    for cls, items in parse(S):
        is_found = any(k in cls for k in ('Foundation', 'Ramp', 'Roof', 'QuarterPipe'))
        is_wall = any(k in cls for k in ('Wall', 'Barrier', 'Railing', 'Fence'))
        if not (is_found or is_wall):
            continue
        mat = next((m for k, m in MATERIAL if k in cls), 0)
        width = NARROW_CM if ('_4x' in cls or 'Railing' in cls or 'Barrier' in cls) else TILE_CM
        for x, y, z, yaw in items:
            if is_found:
                key = (round(x / DEDUP_XY_CM), round(y / DEDUP_XY_CM), round(z / DEDUP_Z_CM))
                if key in seen:
                    continue
                seen.add(key)
                tiles.append([round(x / 100), round(y / 100), round(((yaw % 360) / 90)) % 4, mat, round(z / 100)])
            else:
                # walls/railings extend along the local Y axis (yaw 0 = north-south line)
                a = math.radians(yaw + 90)
                dx, dy = math.cos(a) * width / 2, math.sin(a) * width / 2
                walls.append([round((x - dx) / 100, 1), round((y - dy) / 100, 1), round((x + dx) / 100, 1), round((y + dy) / 100, 1), round(z / 100)])
    return dict(tiles=tiles, walls=walls)


def detail_binary(S):
    """Detail layer as an int16 binary packet (little endian), ~4× smaller than JSON for the map:
      header: int32 n_tiles, int32 n_walls
      tiles: n × [x, y, z] (m) + n × uint8 (rot 2 bits | material << 2)
      walls: n × [x1, y1, x2, y2, z] (x/y in half metres: value / 2 = m, so 4 m walls do not jump)
    """
    d = detail(S)
    T, W = d['tiles'], d['walls']
    clamp = lambda v: max(-32768, min(32767, int(round(v))))
    out = bytearray(struct.pack('<ii', len(T), len(W)))
    out += struct.pack('<%dh' % (3 * len(T)), *[clamp(v) for t in T for v in (t[0], t[1], t[4])])
    out += bytes((t[2] & 3) | (t[3] << 2) for t in T)
    if len(T) % 2:
        out += b'\0'                                  # align to 2 bytes for the int16 view
    out += struct.pack('<%dh' % (5 * len(W)), *[clamp(v) for w in W for v in (w[0] * 2, w[1] * 2, w[2] * 2, w[3] * 2, w[4])])
    return bytes(out)


if __name__ == '__main__':
    import sys, factory
    S = factory.Save(sys.argv[1] if len(sys.argv) > 1 else 'saves/latest.sav')
    res = parse(S)
    print(sum(len(i) for _, i in res), 'objects in', len(res), 'classes')
    for c, i in sorted(res, key=lambda x: -len(x[1]))[:15]:
        print('%6d %s' % (len(i), c))
