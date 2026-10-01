"""Shared state: pre-rendered API blobs, database, FRM status, log."""
import datetime, gzip, hashlib, json, os, threading, time

import store as storemod

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(HERE, 'frontend', 'dist')
DATA = os.environ.get('MAP_DATA', os.path.join(HERE, 'data'))          # database, pin password
SAVES = os.environ.get('MAP_SAVES', os.path.join(HERE, 'saves'))       # most recently fetched save (latest.sav)
PW_FILE = os.path.join(DATA, 'pin_password')
TITLE = os.environ.get('MAP_TITLE', '')                                # name shown top left; empty = session name from the save

LIVE_EVERY, FACTORY_EVERY, SAVE_EVERY = 5, 60, 60


def log(*a):
    print(datetime.datetime.now().strftime('%H:%M:%S'), *a, flush=True)


class State:
    """Everything the API serves — pre-rendered as JSON bytes (gzip), swapped under a lock."""

    def __init__(self):
        self.lock = threading.Lock()
        self.blobs = {}                     # name -> (etag, gzip-bytes, raw-bytes)
        self.frm_ok = False
        self.frm_since = None               # since when FRM has (not) been responding
        self.frm_error = None
        self.save_meta = None
        self.save_error = None              # last error fetching/reading the save
        self.stations = None                # save: stations, routes
        self.factory = None                 # save or FRM: machines, power …
        self.factory_source = None
        self.geo = None                     # network geometry
        self.live = None
        self.prev_live = None

    def put(self, name, obj):
        raw = obj if isinstance(obj, (bytes, bytearray)) else json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode()
        z = gzip.compress(raw, 5)
        tag = '"%s"' % hashlib.md5(raw).hexdigest()[:16]
        with self.lock:
            self.blobs[name] = (tag, z, raw)

    def get(self, name):
        with self.lock:
            return self.blobs.get(name)


ST = State()
DB = storemod.Store()


# ================================================================ FRM status
def frm_status(ok, err=None):
    if ok != ST.frm_ok or ST.frm_since is None:
        ST.frm_since = time.time()
        if ST.frm_ok and not ok:
            DB.event('system', 'warn', 'Live data (FRM) lost — the map continues from the save', ref='frm')
        elif ok and ST.frm_since and ST.save_meta:
            DB.event('system', 'info', 'Live data (FRM) is back', ref='frm')
    ST.frm_ok, ST.frm_error = ok, (str(err)[:160] if err else None)


def status_obj():
    now = time.time()
    return dict(now=int(now), title=TITLE or (ST.save_meta or {}).get('session') or 'Satisfactory',
                frm=dict(ok=ST.frm_ok, since=int(ST.frm_since or now), error=ST.frm_error, configured=frm_configured()),
                save=ST.save_meta, save_error=ST.save_error, factory_source=ST.factory_source)


def frm_configured():
    import frm
    return bool(frm.BASE)


def paused():
    """Game paused (nobody online)? Then the factory is idle — do not record."""
    return bool(ST.frm_ok and ST.live and ST.live.get('paused'))
