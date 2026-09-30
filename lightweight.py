"""Leichtbau-Objekte aus dem Save: Fundamente, Wände, Rampen, Träger … (FGLightweightBuildableSubsystem).

Das Spiel speichert sie nicht als Actors, sondern als Liste je Klasse im Rohtrail des Subsystems:
  int32 0, int32 Version, int32 Anzahl Klassen, je Klasse: int32 0, string Klasse, int32 n,
  n × { double[4] Quaternion, double[3] Position (cm), double[3] Skalierung,
        Objektref Swatch, Material, Pattern, Skin, float[4] Primär, float[4] Sekundär, Objektref PaintFinish,
        uint8 PatternRotation, Objektref Rezept, Objektref BlueprintProxy,
        v≥2: int32 Datenflag [+ int32 0, string Typ, int32 Größe, Properties], v≥3: uint8 ServiceProvider, int32 Spielerindex }
Aufbau nach dem Format, das auch sat_sav_parse liest; eigene Umsetzung.
"""
import math, struct
import sbp, sav


def _ref(r):
    return r.s(), r.s()


def parse(S):
    """Liefert [(klasse, [(x, y, z, yaw_grad), …]), …]; Positionen in cm."""
    n = next((k for k in S.idx if k.endswith('.LightweightBuildableSubsystem')), None)
    if not n:
        return []
    t = sav.obj(S.idx, n)[1]['trail']
    r = sbp.R(t)
    first = r.i32()
    ver = r.i32() if first == 0 else first           # je nach Save steht vorne noch ein Null-Wort
    ncls = r.i32()
    out = []
    for _ in range(ncls):
        r.i32(); cls = r.s(); cnt = r.i32()
        items = []
        for _ in range(cnt):
            qx, qy, qz, qw = struct.unpack_from('<4d', t, r.p); r.p += 32
            x, y, z = struct.unpack_from('<3d', t, r.p); r.p += 24
            r.p += 24                                  # Skalierung
            _ref(r); _ref(r); _ref(r); _ref(r)         # Swatch, Material, Pattern, Skin
            r.p += 32                                  # Farben
            _ref(r); r.u8(); _ref(r); _ref(r)          # PaintFinish, PatternRotation, Rezept, BlueprintProxy
            if ver >= 2:
                if r.i32():
                    r.i32(); r.s(); size = r.i32(); r.p += size
                if ver >= 3:
                    r.u8(); r.i32()
            yaw = math.degrees(math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz)))
            items.append((x, y, z, yaw))
        out.append((sbp.short(cls), items))
    return out


if __name__ == '__main__':
    import sys, factory, collections
    S = factory.Save(sys.argv[1] if len(sys.argv) > 1 else 'saves/latest.sav')
    res = parse(S)
    print(sum(len(i) for _, i in res), 'Objekte in', len(res), 'Klassen')
    for c, i in sorted(res, key=lambda x: -len(x[1]))[:15]:
        print('%6d %s' % (len(i), c))


MATERIAL = [('Asphalt', 1), ('Concrete', 2), ('Polished', 2), ('Metal', 3), ('Glass', 4), ('Frame', 3), ('Tar', 5)]


def detail(S):
    """Kompakte Detailebene für die Karte (Meter, ganzzahlig):
      tiles: [x, y, yaw/90-Stufe, material, stockwerk-z] je Fundament/Dach — Größe 8 × 8 m
      walls: [x1, y1, x2, y2, z] je Wand/Geländer (8 m bzw. 4 m breit, entlang der Drehung)
    Fundamente stapeln sich (8x1 übereinander): je Rasterzelle und Höhe nur eines behalten."""
    tiles, walls, seen = [], [], set()
    for cls, items in parse(S):
        is_found = any(k in cls for k in ('Foundation', 'Ramp', 'Roof', 'QuarterPipe'))
        is_wall = any(k in cls for k in ('Wall', 'Barrier', 'Railing', 'Fence'))
        if not (is_found or is_wall):
            continue
        mat = next((m for k, m in MATERIAL if k in cls), 0)
        width = 400 if ('_4x' in cls or 'Railing' in cls or 'Barrier' in cls) else 800
        for x, y, z, yaw in items:
            if is_found:
                key = (round(x / 200), round(y / 200), round(z / 400))
                if key in seen:
                    continue
                seen.add(key)
                tiles.append([round(x / 100), round(y / 100), round(((yaw % 360) / 90)) % 4, mat, round(z / 100)])
            else:
                # Wände/Geländer erstrecken sich entlang der lokalen Y-Achse (Yaw 0 = Nord-Süd-Flucht)
                a = math.radians(yaw + 90)
                dx, dy = math.cos(a) * width / 2, math.sin(a) * width / 2
                walls.append([round((x - dx) / 100, 1), round((y - dy) / 100, 1), round((x + dx) / 100, 1), round((y + dy) / 100, 1), round(z / 100)])
    return dict(tiles=tiles, walls=walls)


def detail_binary(S):
    """Detailebene als Int16-Binärpaket (Little Endian), für die Karte ~4× kleiner als JSON:
      Kopf: int32 n_tiles, int32 n_walls
      Tiles: n × [x, y, z] (m) + n × uint8 (rot 2 Bit | material << 2)
      Walls: n × [x1, y1, x2, y2, z] (dm-genau für x/y: Wert / 2 = m, damit 4-m-Wände nicht springen → halbe Meter)
    """
    import struct
    d = detail(S)
    T, W = d['tiles'], d['walls']
    clamp = lambda v: max(-32768, min(32767, int(round(v))))
    out = bytearray(struct.pack('<ii', len(T), len(W)))
    out += struct.pack('<%dh' % (3 * len(T)), *[clamp(v) for t in T for v in (t[0], t[1], t[4])])
    out += bytes((t[2] & 3) | (t[3] << 2) for t in T)
    if len(T) % 2:
        out += b'\0'                                  # Ausrichtung auf 2 Byte für die Int16-Ansicht
    out += struct.pack('<%dh' % (5 * len(W)), *[clamp(v) for w in W for v in (w[0] * 2, w[1] * 2, w[2] * 2, w[3] * 2, w[4])])
    return bytes(out)
