"""Satisfactory .sav Reader (nur Lesen) für den Build 'anniversary-2026' – liefert Objekt-Header + Rohdaten."""
import struct, zlib, sys
import sbp

def read_body(path):
    d=open(path,'rb').read(); i=d.find(sbp.MAGIC); parts=[]
    while i<len(d):
        cs,us=struct.unpack_from('<qq',d,i+17); parts.append(zlib.decompress(d[i+49:i+49+cs])); i+=49+cs
    return b''.join(parts)   # join statt += : += kopiert den ganzen Puffer je Chunk

def read_header(r):
    t=r.i32(); h=dict(type=t, cls=r.s(), root=r.s(), name=r.s())
    if t==1:
        h['flags']=r.i32(); h['needTransform']=r.i32()
        h['rot']=[r.f32() for _ in range(4)]; h['pos']=[r.f32() for _ in range(3)]; h['scale']=[r.f32() for _ in range(3)]; h['placed']=r.i32()
    else:
        h['flags']=r.i32(); h['outer']=r.s()
    return h

def parse_levels(body, start):
    r=sbp.R(body,start); levels=[]
    while True:
        p0=r.p
        a=r.i32()
        if a!=60: r.p=p0; break
        ne=r.i32(); prev=[(r.s(),r.s()) for _ in range(ne)]
        r.i32(); r.i32()
        r.i32(); r.i32(); r.i32(); r.raw(6); r.u32(); r.s(); n=r.i32(); r.raw(20*n)
        # Hauptlevel hat keinen Namen: prüfen, ob ein kurzer ASCII-String folgt
        pk=r.p; ln=struct.unpack_from('<i',body,pk)[0]
        if 0<ln<64 and all(32<=c<127 for c in body[pk+4:pk+3+ln]): name=r.s()
        else: name=''
        sz=r.i64(); nh=r.i32(); hstart=r.p
        headers=[read_header(r) for _ in range(nh)]
        end=hstart+sz-4; pc=r.p; coll=[]
        # Die Sammelliste ist entweder gruppiert (Levelname + Eintraege) oder flach.
        # Ohne Schranken liest der falsche Zweig Muellaengen und kopiert Megabytes,
        # bevor er scheitert -- daher jede Laenge gegen das Abschnittsende pruefen.
        def gs():
            n,=struct.unpack_from('<i',r.b,r.p)
            if not -1000<n<1000 or r.p+4+abs(n)*(2 if n<0 else 1)>end: raise ValueError('len')
            return r.s()
        def gn(lim=200000):
            n=r.i32()
            if not 0<=n<=lim: raise ValueError('count')
            return n
        try:
            for _ in range(gn()):
                gl=gs(); coll.append((gl,[(gs(),gs()) for _ in range(gn())]))
            assert r.p==end
        except Exception:
            r.p=pc; nc=r.i32(); coll=[(r.s(),r.s()) for _ in range(nc)]
            assert r.p==end,(name,r.p,end)
        osz=r.i64(); no=r.i32()
        objs=[]
        for _ in range(no):
            r.i32(); r.i32(); s=r.i32(); objs.append(r.raw(s)); r.i32()
        levels.append(dict(name=name,headers=headers,objs=objs,coll=coll))
    return levels, r.p

if __name__=='__main__':
    body=read_body(sys.argv[1])
    vb=b'\x0a\x02\x00\x00\xf9\x03\x00\x00\x03\x00\x00\x00'
    j=body.find(vb,1000)-16
    levels,end=parse_levels(body,j)
    print('levels',len(levels),'end',end,'of',len(body), 'next bytes',body[end:end+40].hex())
    tot=sum(len(l['headers']) for l in levels); print('headers total',tot)
    from collections import Counter
    c=Counter(sbp.short(h['cls']) for l in levels for h in l['headers'])
    for k in sorted(c):
        if any(s in k for s in ('Railroad','Train','Railing','Fence','Lightweight','Designer')): print(c[k],k)

def load_index(path):
    body=read_body(path)
    vb=b'\x0a\x02\x00\x00\xf9\x03\x00\x00\x03\x00\x00\x00'
    levels,_=parse_levels(body, body.find(vb,1000)-16)
    idx={}
    for l in levels:
        for h,o in zip(l['headers'],l['objs']):
            idx[h['name']]=(h,o)
    return idx

def obj(idx,name):
    h,o=idx[name]
    try: return h, sbp.parse_object(o,h['type']==1)
    except Exception as e: return h, dict(err=repr(e)[:80], raw=o)

def show(idx,name,maxlen=200):
    h,ob=obj(idx,name)
    if h['type']==1: print('A',sbp.short(h['cls']),sbp.short(h['name']),'pos',[round(x,1) for x in h['pos']],'rot',[round(x,4) for x in h['rot']],'fl',h['flags'])
    else: print('C',sbp.short(h['cls']),h['name'].split('.',1)[-1],'fl',h['flags'])
    if 'err' in ob: print('   RAW',ob['err'],ob['raw'][:120]); return ob
    if h['type']==1: print('   parent',sbp.short(ob['parent'][1]),'comps',[c[1].split('.',1)[-1] for c in ob['components']])
    for p in ob['props']: print('   -',p['name'],sbp.typestr(p['type']),'fl',p['flags'],repr(p['value'])[:maxlen])
    if ob['trail']: print('   trail',ob['trail'][:40].hex(),len(ob['trail']))
    return ob
