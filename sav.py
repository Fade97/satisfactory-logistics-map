"""Satisfactory .sav reader (read-only) for build 'anniversary-2026' - returns object headers + raw data.

Inflated body (same zlib chunks as .sbp, see sbp.py): int64 size, version block, grid section, then one
record per level:
    int32 save version (60), int32 n + n × (lvl, path) refs, int32 1, int32 0,
    version block: int32 UE4 package version, int32 UE5 package version, int32 licensee,
                   uint16[3] engine version, uint32 changelist, string branch, int32 n + n × (guid16, int32),
    string level name (the main level has none), int64 header bytes, int32 n, n object headers,
    collected list (flat or grouped by level), int64 object bytes, int32 n,
    n × (int32 save version, int32 0, int32 size, data, int32 0)
"""
import struct, sys
import sbp

SAVE_VERSION = 60
# version block (UE4 522, UE5 1017, licensee 3) — the first level record starts LEVEL_MARKER_OFFSET bytes
# before it: int32 60, int32 0 (no refs), int32 1, int32 0
LEVEL_MARKER = struct.pack('<iii', 522, 1017, 3)
LEVEL_MARKER_OFFSET = 16
LEVEL_SEARCH_FROM = 1000              # skip the save header part of the body
ENGINE_VERSION_BYTES = 6              # uint16 major, minor, patch
CUSTOM_VERSION_BYTES = 20             # guid16 + int32 version
MAX_NAME_LEN = 1000                   # sanity bounds for the collected-list heuristic
MAX_COUNT = 200000


def read_body(path):
    d=open(path,'rb').read()
    return sbp.read_chunks(d, d.find(sbp.MAGIC))

def parse_levels(body, start):
    r=sbp.Reader(body,start); levels=[]
    while True:
        p0=r.p
        if r.i32()!=SAVE_VERSION: r.p=p0; break
        ne=r.i32()
        for _ in range(ne): r.s(); r.s()               # refs to other levels
        r.i32(); r.i32()
        r.i32(); r.i32(); r.i32(); r.raw(ENGINE_VERSION_BYTES); r.u32(); r.s()
        r.raw(CUSTOM_VERSION_BYTES*r.i32())
        # the main level has no name: check whether a short ASCII string follows
        pk=r.p; ln=struct.unpack_from('<i',body,pk)[0]
        if 0<ln<64 and all(32<=c<127 for c in body[pk+4:pk+3+ln]): name=r.s()
        else: name=''
        sz=r.i64(); nh=r.i32(); hstart=r.p
        headers=[sbp.read_object_header(r) for _ in range(nh)]
        end=hstart+sz-4; pc=r.p; coll=[]
        # The collectables list is either grouped (level name + entries) or flat.
        # Without bounds the wrong branch reads garbage lengths and copies megabytes
        # before it fails -- so check every length against the end of the section.
        def bounded_str():
            n,=struct.unpack_from('<i',r.b,r.p)
            if not -MAX_NAME_LEN<n<MAX_NAME_LEN or r.p+4+abs(n)*(2 if n<0 else 1)>end: raise ValueError('len')
            return r.s()
        def bounded_count():
            n=r.i32()
            if not 0<=n<=MAX_COUNT: raise ValueError('count')
            return n
        try:
            for _ in range(bounded_count()):
                gl=bounded_str(); coll.append((gl,[(bounded_str(),bounded_str()) for _ in range(bounded_count())]))
            assert r.p==end
        except Exception:
            r.p=pc; nc=r.i32(); coll=[(r.s(),r.s()) for _ in range(nc)]
            assert r.p==end,(name,r.p,end)
        r.i64(); no=r.i32()                              # object section size, count
        objs=[]
        for _ in range(no):
            r.i32(); r.i32(); s=r.i32(); objs.append(r.raw(s)); r.i32()
        levels.append(dict(name=name,headers=headers,objs=objs,coll=coll))
    return levels, r.p


def find_levels(body):
    """Offset of the first level record."""
    j=body.find(LEVEL_MARKER,LEVEL_SEARCH_FROM)
    if j<0: raise ValueError('level data not found — unsupported save version?')
    return j-LEVEL_MARKER_OFFSET


def load_index(path):
    body=read_body(path)
    levels,_=parse_levels(body, find_levels(body))
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


if __name__=='__main__':
    body=read_body(sys.argv[1])
    levels,end=parse_levels(body,find_levels(body))
    print('levels',len(levels),'end',end,'of',len(body), 'next bytes',body[end:end+40].hex())
    tot=sum(len(l['headers']) for l in levels); print('headers total',tot)
    from collections import Counter
    c=Counter(sbp.short(h['cls']) for l in levels for h in l['headers'])
    for k in sorted(c):
        if any(s in k for s in ('Railroad','Train','Railing','Fence','Lightweight','Designer')): print(c[k],k)
