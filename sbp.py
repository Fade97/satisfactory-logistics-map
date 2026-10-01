"""Satisfactory .sbp (blueprint) reader/writer, format of the 'anniversary-2026' build (UE 5.4+ property tags).

File: uncompressed header (versions, designer size, cost + recipe lists, opaque tail), then zlib chunks
(CHUNK_HEADER_SIZE bytes each: magic, version tag, int64 max chunk size, uint8 compressor,
int64 compressed/uncompressed size twice). The inflated body holds object headers, then object data.

Object data = [actor: parent ref + component refs] + uint8 0 + property list + raw trail.
Property tag (UE 5.4+):
    string name ('None' ends the list)
    type tree: string type name, int32 child count, children recursively
               e.g. StructProperty<Vector</Script/CoreUObject>>, ArrayProperty<ObjectProperty>
    int32  value size
    uint8  flags (TAG_*): HAS_INDEX → int32 array index follows, HAS_GUID → 16-byte GUID follows,
           HAS_EXTENSIONS (unsupported), BINARY = struct serialised natively, BOOL_TRUE = value of a BoolProperty
    value  (size bytes; BoolProperty has none — its value lives in the flags)
Arrays of structs are an int32 count + elements without inner tags; Vector/Quat are doubles.
Strings: int32 length incl. terminator; negative = UTF-16 code units.
"""
import math, struct, zlib, io, sys

MAGIC = b'\xc1\x83\x2a\x9e'            # chunk magic (UE package file tag)
CHUNK_VERSION = 0x22222222             # second header word ("v2" marker)
CHUNK_HEADER_SIZE = 49                 # magic, version, int64 max size, uint8 compressor, 4 × int64 sizes
CHUNK_SIZES_AT = 17                    # offset of the first int64 compressed size inside the header
COMPRESSOR_ZLIB = 3
MAX_CHUNK = 131072

# property tag flags (UE EPropertyTagFlags)
TAG_HAS_INDEX = 0x01
TAG_HAS_GUID = 0x02
TAG_HAS_EXTENSIONS = 0x04
TAG_BINARY = 0x08                      # HasBinaryOrNativeSerialize: set on native structs (Vector, PlayerInfoHandle …)
TAG_BOOL_TRUE = 0x10


class Reader:
    def __init__(self, b, pos=0): self.b=b; self.p=pos
    def u8(self): v=self.b[self.p]; self.p+=1; return v
    def i8(self): v,=struct.unpack_from('<b',self.b,self.p); self.p+=1; return v
    def i32(self): v,=struct.unpack_from('<i',self.b,self.p); self.p+=4; return v
    def u32(self): v,=struct.unpack_from('<I',self.b,self.p); self.p+=4; return v
    def i64(self): v,=struct.unpack_from('<q',self.b,self.p); self.p+=8; return v
    def f32(self): v,=struct.unpack_from('<f',self.b,self.p); self.p+=4; return v
    def f64(self): v,=struct.unpack_from('<d',self.b,self.p); self.p+=8; return v
    def raw(self,n): v=self.b[self.p:self.p+n]; self.p+=n; return v
    def s(self):
        n=self.i32()
        if n==0: return ''
        if n<0:
            n=-n; return self.raw(n*2)[:-2].decode('utf-16-le')
        return self.raw(n)[:-1].decode('utf-8')
    def eof(self): return self.p>=len(self.b)

class Writer:
    def __init__(self): self.o=io.BytesIO()
    def u8(self,v): self.o.write(struct.pack('<B',v))
    def i8(self,v): self.o.write(struct.pack('<b',v))
    def i32(self,v): self.o.write(struct.pack('<i',v))
    def u32(self,v): self.o.write(struct.pack('<I',v))
    def i64(self,v): self.o.write(struct.pack('<q',v))
    def f32(self,v): self.o.write(struct.pack('<f',v))
    def f64(self,v): self.o.write(struct.pack('<d',v))
    def raw(self,b): self.o.write(b)
    def s(self,v):
        if v=='': self.i32(0); return
        try:
            b=v.encode('ascii'); self.i32(len(b)+1); self.raw(b+b'\0')
        except UnicodeEncodeError:
            b=v.encode('utf-16-le'); self.i32(-(len(b)//2+1)); self.raw(b+b'\0\0')   # length in UTF-16 code units
    def bytes(self): return self.o.getvalue()

R, W = Reader, Writer                  # old names


def quat_yaw_rad(q):
    """Yaw (rotation about z) in radians of an (x, y, z, w) quaternion."""
    qx, qy, qz, qw = q
    return math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))

def yaw_from_quat(q): return math.degrees(quat_yaw_rad(q))

# ---------- file level ----------
def read_chunks(d, i):
    """Inflate the zlib chunks of d starting at offset i (first chunk magic) into one body."""
    parts=[]
    while i<len(d):
        assert d[i:i+4]==MAGIC, 'chunk magic expected at %d' % i
        cs,_=struct.unpack_from('<qq',d,i+CHUNK_SIZES_AT)
        start=i+CHUNK_HEADER_SIZE
        parts.append(zlib.decompress(d[start:start+cs]))
        i=start+cs
    return b''.join(parts)   # join instead of +=: += copies the whole buffer per chunk

def read_file(path):
    d=open(path,'rb').read()
    i=d.find(MAGIC)
    return d[:i], read_chunks(d,i)

def write_file(path, header, body, maxchunk=MAX_CHUNK):
    out=bytearray(header)
    for off in range(0,len(body),maxchunk):
        chunk=body[off:off+maxchunk]
        comp=zlib.compress(chunk,6)
        out+=MAGIC+struct.pack('<I',CHUNK_VERSION)+struct.pack('<q',maxchunk)+bytes([COMPRESSOR_ZLIB])
        out+=struct.pack('<qqqq',len(comp),len(chunk),len(comp),len(chunk))
        out+=comp
    open(path,'wb').write(bytes(out))

def parse_header(h):
    r=Reader(h)
    hv=r.i32(); sv=r.i32(); bv=r.i32()
    dims=[r.i32(),r.i32(),r.i32()]
    n=r.i32(); cost=[]
    for _ in range(n):
        lvl=r.s(); p=r.s(); amt=r.i32(); cost.append([lvl,p,amt])
    n=r.i32(); recipes=[]
    for _ in range(n):
        lvl=r.s(); p=r.s(); recipes.append([lvl,p])
    tail=h[r.p:]
    return dict(hv=hv,sv=sv,bv=bv,dims=dims,cost=cost,recipes=recipes,tail=tail)

def build_header(H):
    w=Writer(); w.i32(H['hv']); w.i32(H['sv']); w.i32(H['bv'])
    for d in H['dims']: w.i32(d)
    w.i32(len(H['cost']))
    for lvl,p,amt in H['cost']: w.s(lvl); w.s(p); w.i32(amt)
    w.i32(len(H['recipes']))
    for lvl,p in H['recipes']: w.s(lvl); w.s(p)
    w.raw(H['tail'])
    return w.bytes()

# ---------- body ----------
def read_object_header(r):
    """Object header: type (1 = actor with transform, 0 = component/object), class, level, name, …"""
    t=r.i32(); h=dict(type=t, cls=r.s(), root=r.s(), name=r.s())
    if t==1:
        h['flags']=r.i32(); h['needTransform']=r.i32()
        h['rot']=[r.f32() for _ in range(4)]; h['pos']=[r.f32() for _ in range(3)]; h['scale']=[r.f32() for _ in range(3)]
        h['placed']=r.i32()
    else:
        h['flags']=r.i32(); h['outer']=r.s()
    return h

def write_object_header(w,h):
    w.i32(h['type']); w.s(h['cls']); w.s(h['root']); w.s(h['name'])
    if h['type']==1:
        w.i32(h['flags']); w.i32(h['needTransform'])
        for v in h['rot']: w.f32(v)
        for v in h['pos']: w.f32(v)
        for v in h['scale']: w.f32(v)
        w.i32(h['placed'])
    else:
        w.i32(h['flags']); w.s(h['outer'])

def parse_body(b):
    """int32 total, int32 header bytes, int32 n, n headers, int32 object bytes, int32 n, n × (int32 size, data), rest"""
    r=Reader(b)
    r.i32(); r.i32()                      # total size, header section size (recomputed on write)
    headers=[read_object_header(r) for _ in range(r.i32())]
    r.i32()                               # object section size
    objs=[dict(data=r.raw(r.i32())) for _ in range(r.i32())]
    return dict(headers=headers,objs=objs,rest=b[r.p:])

def build_body(B):
    hw=Writer(); hw.i32(len(B['headers']))
    for h in B['headers']: write_object_header(hw,h)
    hb=hw.bytes()
    ow=Writer(); ow.i32(len(B['objs']))
    for o in B['objs']:
        ow.i32(len(o['data'])); ow.raw(o['data'])
    ob=ow.bytes()
    inner=struct.pack('<i',len(hb))+hb+struct.pack('<i',len(ob))+ob+B['rest']
    return struct.pack('<i',len(inner))+inner

# ---------- object data (properties) ----------
def parse_object(data, is_actor):
    r=Reader(data)
    o={}
    if is_actor:
        o['parent']=[r.s(),r.s()]
        n=r.i32(); o['components']=[[r.s(),r.s()] for _ in range(n)]
    o['pre']=r.u8()
    o['props']=parse_props(r)
    o['trail']=data[r.p:]
    return o

def build_object(o, is_actor):
    w=Writer()
    if is_actor:
        w.s(o['parent'][0]); w.s(o['parent'][1])
        w.i32(len(o['components']))
        for a,b in o['components']: w.s(a); w.s(b)
    w.u8(o['pre'])
    write_props(w,o['props'])
    w.raw(o['trail'])
    return w.bytes()

# type tree: [name, [children...]]
def read_type(r):
    name=r.s(); n=r.i32()
    return [name,[read_type(r) for _ in range(n)]]
def write_type(w,t):
    w.s(t[0]); w.i32(len(t[1]))
    for c in t[1]: write_type(w,c)

def read_tag(r):
    """returns tag dict or None for 'None'"""
    name=r.s()
    if name=='None': return None
    t=dict(name=name, type=read_type(r), size=r.i32(), flags=r.u8())
    if t['flags']&TAG_HAS_INDEX: t['index']=r.i32()
    if t['flags']&TAG_HAS_GUID: t['pguid']=r.raw(16)
    assert not (t['flags']&TAG_HAS_EXTENSIONS), 'property extensions unsupported'
    return t

def write_tag(w,t,size):
    w.s(t['name']); write_type(w,t['type']); w.i32(size); w.u8(t['flags'])
    if t['flags']&TAG_HAS_INDEX: w.i32(t['index'])
    if t['flags']&TAG_HAS_GUID: w.raw(t['pguid'])

def parse_props(r):
    props=[]
    while True:
        t=read_tag(r)
        if t is None: break
        start=r.p
        t['value']=parse_value(r,t['type'],t['size'],t)
        assert r.p-start==t['size'],(t['name'],t['type'],t['size'],r.p-start)
        props.append(t)
    return props

BIN_STRUCTS={'Vector','Rotator','Quat','LinearColor','Color','Box','Vector2D','IntVector','Guid','FluidBox','Vector4','Transform_bin'}

def parse_value(r,typ,size,tag=None):
    tn=typ[0]
    if tn=='BoolProperty': return bool(tag['flags']&TAG_BOOL_TRUE) if tag else r.u8()
    if tn=='IntProperty': return r.i32()
    if tn=='Int8Property': return r.i8()
    if tn=='Int64Property': return r.i64()
    if tn=='UInt32Property': return r.u32()
    if tn=='FloatProperty': return r.f32()
    if tn=='DoubleProperty': return r.f64()
    if tn in('StrProperty','NameProperty'): return r.s()
    if tn in('ObjectProperty','InterfaceProperty'): return [r.s(),r.s()]
    if tn=='ByteProperty':
        if typ[1]: return r.s()   # enum name
        return r.u8()
    if tn=='EnumProperty': return r.s()
    if tn=='StructProperty':
        return parse_struct(r,typ[1][0][0],size)
    if tn=='ArrayProperty':
        et=typ[1][0]; n=r.i32()
        if et[0]=='StructProperty':
            return [parse_struct(r,et[1][0][0],None) for _ in range(n)]
        return [parse_value(r,et,None) for _ in range(n)]
    if tn in('MapProperty','SetProperty','TextProperty','SoftObjectProperty'):
        assert size is not None
        return r.raw(size)
    raise Exception('unknown prop type '+tn)

def parse_struct(r,st,size):
    if st in('Vector','Rotator'): return [r.f64(),r.f64(),r.f64()]
    if st=='Quat' or st=='Vector4': return [r.f64() for _ in range(4)]
    if st=='LinearColor': return [r.f32() for _ in range(4)]
    if st=='Color': return list(r.raw(4))
    if st=='Box': return [r.f64() for _ in range(6)]+[r.u8()]
    if st=='Vector2D': return [r.f64(),r.f64()]
    if st=='IntVector': return [r.i32(),r.i32(),r.i32()]
    if st=='Guid': return r.raw(16)
    if st=='FluidBox': return r.f32()
    if st=='InventoryItem':
        # Anniversary-2026: int32 0, item path, rest (formerly lvl/path) as raw bytes
        if size is None: return {'pad':r.i32(),'item':r.s(),'lvl':r.s(),'path':r.s()}
        e=r.p+size; d={'pad':r.i32(),'item':r.s()}; d['rest']=r.raw(e-r.p); return d
    if st=='RailroadTrackPosition': return {'lvl':r.s(),'path':r.s(),'offset':r.f32(),'fwd':r.f32()}
    if st in ('PlayerInfoHandle','ClientIdentityInfo'): return r.raw(size)   # opaque binary
    return parse_props(r)

def write_struct(w,st,v):
    if st in('Vector','Rotator','Quat','Vector4','Vector2D'):
        for x in v: w.f64(x)
        return
    if st=='Box':
        for x in v[:6]: w.f64(x)
        w.u8(v[6]); return
    if st=='LinearColor':
        for x in v: w.f32(x)
        return
    if st=='Color': w.raw(bytes(v)); return
    if st=='IntVector':
        for x in v: w.i32(x)
        return
    if st in('Guid','PlayerInfoHandle','ClientIdentityInfo'): w.raw(v); return
    if st=='FluidBox': w.f32(v); return
    if st=='InventoryItem':
        w.i32(v['pad']); w.s(v['item'])
        if 'rest' in v: w.raw(v['rest'])
        else: w.s(v['lvl']); w.s(v['path'])
        return
    if st=='RailroadTrackPosition': w.s(v['lvl']); w.s(v['path']); w.f32(v['offset']); w.f32(v['fwd']); return
    write_props(w,v)

def write_value(w,typ,v):
    tn=typ[0]
    if tn=='BoolProperty': return
    if tn=='IntProperty': w.i32(v)
    elif tn=='Int8Property': w.i8(v)
    elif tn=='Int64Property': w.i64(v)
    elif tn=='UInt32Property': w.u32(v)
    elif tn=='FloatProperty': w.f32(v)
    elif tn=='DoubleProperty': w.f64(v)
    elif tn in('StrProperty','NameProperty','EnumProperty'): w.s(v)
    elif tn in('ObjectProperty','InterfaceProperty'): w.s(v[0]); w.s(v[1])
    elif tn=='ByteProperty':
        if typ[1]: w.s(v)
        else: w.u8(v)
    elif tn=='StructProperty': write_struct(w,typ[1][0][0],v)
    elif tn=='ArrayProperty':
        et=typ[1][0]
        w.i32(len(v))
        if et[0]=='StructProperty':
            for e in v: write_struct(w,et[1][0][0],e)
        else:
            for e in v: write_value(w,et,e)
    elif tn in('MapProperty','SetProperty','TextProperty','SoftObjectProperty'): w.raw(v)
    else: raise Exception(tn)

def write_props(w,props):
    for t in props:
        vw=Writer(); write_value(vw,t['type'],t['value']); vb=vw.bytes()
        if t['type'][0]=='BoolProperty':
            t['flags']=(t['flags']&~TAG_BOOL_TRUE)|(TAG_BOOL_TRUE if t['value'] else 0)
        write_tag(w,t,len(vb)); w.raw(vb)
    w.s('None')

# ---------- property builders (for generated blueprints) ----------
def T(name, *children): return [name, list(children)]
def P_obj(name, ref): return dict(name=name, type=T('ObjectProperty'), flags=0, value=list(ref))
def P_objarr(name, refs): return dict(name=name, type=T('ArrayProperty', T('ObjectProperty')), flags=0, value=[list(r) for r in refs])
def P_float(name, v): return dict(name=name, type=T('FloatProperty'), flags=0, value=float(v))
def P_int(name, v): return dict(name=name, type=T('IntProperty'), flags=0, value=int(v))
def P_bool(name, v): return dict(name=name, type=T('BoolProperty'), flags=TAG_BOOL_TRUE if v else 0, value=bool(v))
def P_byte(name, v): return dict(name=name, type=T('ByteProperty'), flags=0, value=int(v))
def P_struct(name, sname, pkg, props, flags=0): return dict(name=name, type=T('StructProperty', T(sname, T(pkg))), flags=flags, value=props)
def P_vec(name, v): return P_struct(name, 'Vector', '/Script/CoreUObject', [float(x) for x in v], flags=TAG_BINARY)

def write_cfg(path, text, src):
    """Write a blueprint description (.sbpcfg) modelled on an existing one (keeps icon, colour, icon library).

    Layout: int32 version, string description, int32 icon ID, LinearColor f32[4], rest copied as is.
    """
    tpl = open(src, 'rb').read()
    r = Reader(tpl); ver = r.i32(); r.s(); icon = r.i32(); color = [r.f32() for _ in range(4)]; rest = tpl[r.p:]
    w = Writer(); w.i32(ver); w.s(text); w.i32(icon)
    for c in color: w.f32(c)
    w.raw(rest); open(path, 'wb').write(w.bytes())

# ---------- whole file ----------
def load(path):
    header,body=read_file(path)
    H=parse_header(header); B=parse_body(body)
    for h,o in zip(B['headers'],B['objs']):
        try:
            ob=parse_object(o['data'],h['type']==1)
            if build_object(ob,h['type']==1)!=o['data']: raise Exception('roundtrip mismatch')
            o['obj']=ob
        except Exception as e:
            o['obj']=None; o['err']=repr(e)[:80]
    return H,B

def save(path,H,B):
    for h,o in zip(B['headers'],B['objs']):
        if o.get('obj') is not None:
            o['data']=build_object(o['obj'],h['type']==1)
    write_file(path,build_header(H),build_body(B))

def short(s): return s.split('.')[-1]

def dump(path, full=False):
    H,B=load(path)
    print('== ',path)
    print(' dims',H['dims'],'cost',[(short(p),a) for _,p,a in H['cost']])
    print(' recipes',[short(p) for _,p in H['recipes']])
    for h,o in zip(B['headers'],B['objs']):
        if h['type']==1:
            print(' A',short(h['cls']),short(h['name']),'pos',[round(x,2) for x in h['pos']],'rot',[round(x,4) for x in h['rot']],'scale',h['scale'],'fl',h['flags'],'nt',h['needTransform'],'pl',h['placed'])
            print('    parent',short(o['obj']['parent'][1]),'comps',[short(c[1]) for c in o['obj']['components']])
        else:
            print(' C',short(h['cls']),h['name'].split('.',1)[-1],'outer',short(h['outer']),'fl',h['flags'])
        if o['obj'] is None: print('    RAW (unparsed):',o.get('err')); continue
        for p in o['obj']['props']:
            pv=p['value']
            print('    -',p['name'],typestr(p['type']),'fl',p['flags'],repr(pv)[:300] if full else repr(pv)[:120])
        if o['obj']['trail']: print('    trail',o['obj']['trail'][:40].hex(),len(o['obj']['trail']))
    if B['rest']: print(' rest',B['rest'].hex())

def typestr(t):
    return t[0]+('<'+','.join(typestr(c) for c in t[1])+'>' if t[1] else '')

def roundtrip(path):
    """Byte-exact round trip check of one .sbp: (header ok, body ok, [object problems])."""
    header,body=read_file(path)
    H=parse_header(header); B=parse_body(body)
    bad=[]
    for h,o in zip(B['headers'],B['objs']):
        try:
            if build_object(parse_object(o['data'],h['type']==1),h['type']==1)!=o['data']: bad.append(('MISMATCH',h['cls'],h['name']))
        except Exception as e:
            bad.append(('ERR',short(h['cls']),short(h['name']),repr(e)))
    return build_header(H)==header, build_body(B)==body, bad, B

if __name__=='__main__':
    import glob,os
    if sys.argv[1]=='dump':
        dump(sys.argv[2], full=len(sys.argv)>3); sys.exit()
    for f in sorted(glob.glob(sys.argv[1]+'/*.sbp')):
        ok_h,ok_b,bad,B=roundtrip(f)
        for b in bad: print(' ',*b)
        print(os.path.basename(f), 'hdr',ok_h,'body',ok_b,'objs',not bad, 'n=',len(B['headers']), 'rest=',len(B['rest']))
