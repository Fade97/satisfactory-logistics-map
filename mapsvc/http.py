"""Website + API."""
import collections, gzip, hmac, http.server, io, json, os, re, socketserver, threading, time, traceback, urllib.parse, zipfile

import store as storemod
from .core import ST, DB, log, DIST, PW_FILE
from .production import publish_factory
from .logistics import schedule_check
from .plan_api import plan

MAX_BODY = 64000
_bp_lock = threading.Lock()     # bpgen writes into one shared folder; one blueprint at a time


# ================================================================ HTTP
def pin_password():
    if os.environ.get('MAP_PIN_PASSWORD'):
        return os.environ['MAP_PIN_PASSWORD']
    if not os.path.exists(PW_FILE):
        return None
    with open(PW_FILE) as f:
        return f.read().strip()


FAILS = collections.defaultdict(list)      # client IP → times of failed password attempts
FAIL_WINDOW, FAIL_MAX = 600, 10


class RequestHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'fgmap'

    def log_message(self, *a):
        pass

    def _send(self, code, body=b'', ctype='application/json', extra=None):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), extra={'Cache-Control': 'no-store'})

    def _blob(self, name):
        b = ST.get(name)
        if not b:
            return self._json(dict(error='no data yet'), 503)
        tag, gz_body, raw = b
        if self.headers.get('If-None-Match') == tag:
            return self._send(304, extra={'ETag': tag, 'Cache-Control': 'no-cache'})
        gz = 'gzip' in (self.headers.get('Accept-Encoding') or '')
        ctype = 'application/octet-stream' if name == 'detail' else 'application/json'
        self._send(200, gz_body if gz else raw, ctype, extra={'ETag': tag, 'Cache-Control': 'no-cache', 'Vary': 'Accept-Encoding',
                                                 **({'Content-Encoding': 'gzip'} if gz else {})})

    def _ip(self):
        return (self.headers.get('CF-Connecting-IP') or self.headers.get('X-Forwarded-For', '').split(',')[0].strip()
                or self.client_address[0])

    def _auth(self):
        pw = pin_password()
        got = self.headers.get('X-Map-Password') or ''
        ip, now = self._ip(), time.time()
        FAILS[ip] = [t for t in FAILS[ip] if now - t < FAIL_WINDOW]
        if len(FAILS[ip]) >= FAIL_MAX:
            self._json(dict(error='Too many failed attempts, wait 10 minutes'), 429); return False
        if not pw or not hmac.compare_digest(pw.encode(), got.encode()):
            FAILS[ip].append(now)
            self._json(dict(error='Wrong password'), 403); return False
        return True

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if n < 0 or n > MAX_BODY:
            raise ValueError('bad Content-Length')
        return json.loads(self.rfile.read(n) or b'{}')

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        p = u.path
        try:
            if p.startswith('/api/'):
                name = p[5:]
                if name in ('live', 'stations', 'factory', 'geo', 'nodes', 'powerlines', 'progress', 'status', 'recipes', 'flow',
                            'collectibles', 'storage', 'sink', 'detail'):
                    return self._blob(name)
                if name == 'events':
                    return self._json(DB.events(int(q.get('since', ['0'])[0]), min(500, int(q.get('limit', ['200'])[0]))))
                if name == 'series':
                    keys = [k for k in q.get('k', []) if re.fullmatch(r'[\w:.\- *]{1,80}', k)][:40]
                    since = int(q.get('since', [str(int(time.time()) - 86400)])[0])
                    return self._json(DB.series(keys, since))
                if name == 'train-flow':
                    hours = max(1, min(168, int(q.get('h', ['24'])[0])))
                    since = int(time.time()) - hours * 3600
                    out = collections.defaultdict(lambda: collections.defaultdict(dict))
                    for k, v in DB.train_totals(since):
                        _, st, d, it = k.split(':', 3)
                        out[st][it][d] = round(out[st][it].get(d, 0) + v / (hours * 60), 2)
                    return self._json(dict(hours=hours, stations=out))
                if name == 'schedule':
                    return self._json(schedule_check())
                if name == 'series-keys':
                    return self._json(DB.series_keys(q.get('prefix', [''])[0]))
                if name == 'frames':
                    hours = max(1, min(24, float(q.get('h', ['6'])[0])))
                    step = max(60, int(q.get('step', ['60'])[0]))
                    return self._json(DB.frames(int(time.time() - hours * 3600), step=step))
                if name == 'trails':
                    return self._json(DB.trails(int(time.time()) - storemod.TRAIL_KEEP))
                if name == 'pins':
                    return self._json(DB.pins())
                return self._json(dict(error='unknown'), 404)
            return self._static(p)
        except BrokenPipeError:
            pass
        except Exception as e:
            log('GET', p, repr(e)[:200])
            try:
                self._json(dict(error='internal error'), 500)
            except Exception:
                pass

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        try:
            if p == '/api/auth':
                if self._auth():
                    self._json(dict(ok=True))
                return
            if p == '/api/pins':
                if not self._auth():
                    return
                b = self._body()
                pin = dict(id=b.get('id'), author=str(b.get('author') or 'anonymous')[:40], cat=str(b.get('cat') or 'note')[:20],
                           color=str(b.get('color') or '#f5a524')[:9], text=str(b.get('text') or '')[:500],
                           shape=b.get('shape') if b.get('shape') in ('point', 'line', 'area') else 'point', geom=b.get('geom'))
                g = pin['geom']
                if not (isinstance(g, list) and 1 <= len(g) <= 200 and all(isinstance(q, list) and len(q) == 2 and
                                                                         all(isinstance(c, (int, float)) for c in q) for q in g)):
                    return self._json(dict(error='Invalid geometry'), 400)
                pin['id'] = DB.pin_save(pin)
                DB.event('pin', 'info', '%s: note “%s”' % (pin['author'], pin['text'][:60]), ref='pin:%d' % pin['id'], x=g[0][0], y=g[0][1])
                return self._json(pin)
            if p.startswith('/api/pins/') and p.endswith('/delete'):
                if not self._auth():
                    return
                DB.pin_delete(int(p.split('/')[3]))
                return self._json(dict(ok=True))
            if p == '/api/plan':
                r = plan(self._body())
                if r.get('ok'):
                    import bpgen        # lazy: loads blueprint templates and recipe paths, only needed by the planner
                    for s in r['steps']:
                        s['bp'] = bpgen.supported(s['cls'])
                return self._json(r)
            if p == '/api/blueprint':
                # generate a blueprint for a planner step and serve it as a ZIP (.sbp + .sbpcfg)
                import bpgen
                b = self._body()
                st = dict(cls=str(b.get('cls')), building=str(b.get('building') or ''), machines=float(b.get('machines') or 0),
                          full_clock=float(b.get('full_clock') or 100), clock=float(b['clock']) if b.get('clock') else None)
                if not (0 < st['machines'] <= 64) or not (1 <= st['full_clock'] <= 250):
                    return self._json(dict(error='Invalid input'), 400)
                buf = io.BytesIO()
                with _bp_lock:
                    try:
                        path, info = bpgen.build(st)
                    except bpgen.BpError as e:
                        return self._json(dict(error=str(e)), 422)
                    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                        zf.write(path, os.path.basename(path)); zf.write(path + 'cfg', os.path.basename(path) + 'cfg')
                name = os.path.splitext(os.path.basename(path))[0]
                return self._send(200, buf.getvalue(), 'application/zip', {
                    'Content-Disposition': "attachment; filename*=UTF-8''" + urllib.parse.quote(name + '.zip'), 'Cache-Control': 'no-store'})
            if p == '/api/factory-name':
                if not self._auth():
                    return
                b = self._body()
                st = b.get('status') if b.get('status') in ('active', 'building', 'decommissioned', 'buffer') else None
                DB.factory_rename(str(b['key'])[:80], str(b.get('name') or '').strip()[:60], str(b.get('author') or '')[:40], st)
                if ST.factory:
                    publish_factory(ST.factory, ST.factory_source, time.time())
                return self._json(dict(ok=True))
            self._json(dict(error='unknown'), 404)
        except BrokenPipeError:
            pass
        except (ValueError, KeyError, TypeError) as e:
            log('POST', p, repr(e)[:200])
            self._json(dict(error='Invalid request'), 400)
        except Exception:
            log('POST', p, 'failed:\n' + traceback.format_exc()[-800:])
            try:
                self._json(dict(error='internal error'), 500)
            except Exception:
                pass

    TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
             '.jpg': 'image/jpeg', '.png': 'image/png', '.svg': 'image/svg+xml', '.webp': 'image/webp',
             '.woff2': 'font/woff2', '.ico': 'image/x-icon', '.webmanifest': 'application/manifest+json'}

    def _static(self, p):
        root = DIST
        rel = urllib.parse.unquote(p).lstrip('/') or 'index.html'
        f = os.path.realpath(os.path.join(root, rel))
        if not f.startswith(os.path.realpath(root) + os.sep) or not os.path.isfile(f):
            # answer missing build files (/assets/…, old hashes from a stale cache) with a real 404 —
            # otherwise the browser loads index.html as JavaScript and a lazily loaded chunk fails silently
            if rel.startswith('assets/') or os.path.splitext(rel)[1] in ('.js', '.css', '.map', '.png', '.jpg', '.svg', '.woff2'):
                return self._send(404, b'not found', 'text/plain', {'Cache-Control': 'no-store'})
            f = os.path.join(root, 'index.html')                 # SPA: unknown paths → app
        ext = os.path.splitext(f)[1]
        st = os.stat(f)
        tag = '"%x-%x"' % (st.st_size, int(st.st_mtime))
        if self.headers.get('If-None-Match') == tag:
            return self._send(304, extra={'ETag': tag})
        immutable = '/assets/' in f                # Vite files carry a hash in their name
        with open(f, 'rb') as fh:
            body = fh.read()
        extra = {'ETag': tag, 'Cache-Control': 'public, max-age=31536000, immutable' if immutable else 'no-cache'}
        if ext in ('.js', '.css', '.html', '.json', '.svg') and 'gzip' in (self.headers.get('Accept-Encoding') or ''):
            body = gzip.compress(body, 6); extra['Content-Encoding'] = 'gzip'; extra['Vary'] = 'Accept-Encoding'
        self._send(200, body, self.TYPES.get(ext, 'application/octet-stream'), extra)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
