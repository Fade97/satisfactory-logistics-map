"""Satisfactory .sbp (blueprint) reader/writer, format of 'anniversary-2026' build (UE5.4+ property tags)."""
import struct, zlib, io, sys

MAGIC = b'\xc1\x83\x2a\x9e'

class R:
    def __init__(self, b, pos=0): self.b=b; self.p=pos
    def u8(self): v=self.b[self.p]; self.p+=1; return v
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

class W:
    def __init__(self): self.o=io.BytesIO()
    def u8(self,v): self.o.write(struct.pack('<B',v))
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
            b=v.encode('utf-16-le'); self.i32(-(len(v)+1)); self.raw(b+b'\0\0')
    def bytes(self): return self.o.getvalue()

# ---------- file level ----------
def read_file(path):
    d=open(path,'rb').read()
    i=d.find(MAGIC)
    header=d[:i]
    body=b''
    while i<len(d):
        assert d[i:i+4]==MAGIC
        cs,us=struct.unpack_from('<qq',d,i+17)
        start=i+49
        body+=zlib.decompress(d[start:start+cs])
        i=start+cs
    return header, body

def write_file(path, header, body, maxchunk=131072):
    out=bytearray(header)
    for off in range(0,len(body),maxchunk):
        chunk=body[off:off+maxchunk]
        comp=zlib.compress(chunk,6)
        out+=MAGIC+struct.pack('<I',0x22222222)+struct.pack('<q',maxchunk)+b'\x03'
        out+=struct.pack('<qqqq',len(comp),len(chunk),len(comp),len(chunk))
        out+=comp
    open(path,'wb').write(bytes(out))

def parse_header(h):
    r=R(h)
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
    w=W(); w.i32(H['hv']); w.i32(H['sv']); w.i32(H['bv'])
    for d in H['dims']: w.i32(d)
    w.i32(len(H['cost']))
    for lvl,p,amt in H['cost']: w.s(lvl); w.s(p); w.i32(amt)
    w.i32(len(H['recipes']))
    for lvl,p in H['recipes']: w.s(lvl); w.s(p)
    w.raw(H['tail'])
    return w.bytes()

# ---------- body ----------
def parse_body(b):
    r=R(b)
    total=r.i32(); hdrsize=r.i32(); n=r.i32()
    headers=[]
    for _ in range(n):
        t=r.i32(); h=dict(type=t, cls=r.s(), root=r.s(), name=r.s())
        if t==1:
            h['flags']=r.i32(); h['needTransform']=r.i32()
            h['rot']=[r.f32() for _ in range(4)]; h['pos']=[r.f32() for _ in range(3)]; h['scale']=[r.f32() for _ in range(3)]
            h['placed']=r.i32()
        else:
            h['flags']=r.i32(); h['outer']=r.s()
        headers.append(h)
    objsize=r.i32(); n2=r.i32()
    objs=[]
    for _ in range(n2):
        size=r.i32()
        objs.append(dict(data=r.raw(size)))
    rest=b[r.p:]
    return dict(headers=headers,objs=objs,rest=rest)

def build_body(B):
    hw=W(); hw.i32(len(B['headers']))
    for h in B['headers']:
        hw.i32(h['type']); hw.s(h['cls']); hw.s(h['root']); hw.s(h['name'])
        if h['type']==1:
            hw.i32(h['flags']); hw.i32(h['needTransform'])
            for v in h['rot']: hw.f32(v)
            for v in h['pos']: hw.f32(v)
            for v in h['scale']: hw.f32(v)
            hw.i32(h['placed'])
        else:
            hw.i32(h['flags']); hw.s(h['outer'])
    hb=hw.bytes()
    ow=W(); ow.i32(len(B['objs']))
    for o in B['objs']:
        ow.i32(len(o['data'])); ow.raw(o['data'])
    ob=ow.bytes()
    inner=struct.pack('<i',len(hb))+hb+struct.pack('<i',len(ob))+ob+B['rest']
    return struct.pack('<i',len(inner))+inner

# ---------- object data (properties) ----------
def parse_object(data, is_actor):
    r=R(data)
    o={}
    if is_actor:
        o['parent']=[r.s(),r.s()]
        n=r.i32(); o['components']=[[r.s(),r.s()] for _ in range(n)]
    o['pre']=r.u8()
    o['props']=parse_props(r)
    o['trail']=data[r.p:]
    return o

def build_object(o, is_actor):
    w=W()
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
    if t['flags']&1: t['index']=r.i32()
    if t['flags']&2: t['pguid']=r.raw(16)
    assert not (t['flags']&4), 'property extensions unsupported'
    return t

def write_tag(w,t,size):
    w.s(t['name']); write_type(w,t['type']); w.i32(size); w.u8(t['flags'])
    if t['flags']&1: w.i32(t['index'])
    if t['flags']&2: w.raw(t['pguid'])

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
    if tn=='BoolProperty': return bool(tag['flags']&16) if tag else r.u8()
    if tn=='IntProperty': return r.i32()
    if tn=='Int8Property': return r.u8()
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
    elif tn=='Int8Property': w.u8(v)
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
        vw=W(); write_value(vw,t['type'],t['value']); vb=vw.bytes()
        if t['type'][0]=='BoolProperty':
            t['flags']=(t['flags']&~16)|(16 if t['value'] else 0)
        write_tag(w,t,len(vb)); w.raw(vb)
    w.s('None')

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

if __name__=='__main__':
    import glob,os
    if sys.argv[1]=='dump':
        dump(sys.argv[2], full=len(sys.argv)>3); sys.exit()
    for f in sorted(glob.glob(sys.argv[1]+'/*.sbp')):
        header,body=read_file(f)
        H=parse_header(header); B=parse_body(body)
        ok_h=build_header(H)==header
        ok_b=build_body(B)==body
        ok_o=True
        for h,o in zip(B['headers'],B['objs']):
            try:
                ob=parse_object(o['data'],h['type']==1)
                if build_object(ob,h['type']==1)!=o['data']: ok_o=False; print('  MISMATCH',h['cls'],h['name'])
            except Exception as e:
                ok_o=False; print('  ERR',short(h['cls']),short(h['name']),repr(e))
        print(os.path.basename(f), 'hdr',ok_h,'body',ok_b,'objs',ok_o, 'n=',len(B['headers']), 'rest=',len(B['rest']))
