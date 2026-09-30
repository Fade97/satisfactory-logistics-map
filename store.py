"""SQLite-Ablage der Logistikkarte: Zeitreihen, Ereignisse, Spielerspuren, Pins, Fabriknamen.

Verlauf in drei Stufen (Entscheidung 29.09.2026):
  series_min  — Minutenwerte, 48 h
  series_hour — Stundenmittel, 90 Tage
  series_day  — Tagesmittel, für immer
Schlüssel einer Reihe: z. B. 'prod:Iron Plate', 'cons:Iron Plate', 'power:229:prod', 'count:machines'.
"""
import json, os, sqlite3, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get('MAP_DB', os.path.join(os.environ.get('MAP_DATA', os.path.join(HERE, 'data')), 'map.db'))

SCHEMA = """
CREATE TABLE IF NOT EXISTS series_min  (key TEXT, t INTEGER, v REAL, PRIMARY KEY (key, t)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS series_hour (key TEXT, t INTEGER, v REAL, PRIMARY KEY (key, t)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS series_day  (key TEXT, t INTEGER, v REAL, PRIMARY KEY (key, t)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, t INTEGER, kind TEXT, level TEXT, text TEXT, ref TEXT, x REAL, y REAL);
CREATE INDEX IF NOT EXISTS events_t ON events (t);
CREATE TABLE IF NOT EXISTS trail (name TEXT, t INTEGER, x REAL, y REAL, PRIMARY KEY (name, t)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS pins (
  id INTEGER PRIMARY KEY, t INTEGER, author TEXT, cat TEXT, color TEXT, text TEXT,
  shape TEXT, geom TEXT, ingame INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS factory_names (key TEXT PRIMARY KEY, name TEXT, t INTEGER, author TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS snapshot (key TEXT PRIMARY KEY, t INTEGER, data TEXT);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS frames (t INTEGER PRIMARY KEY, data TEXT);
"""

MIN_KEEP = 48 * 3600
HOUR_KEEP = 90 * 86400
TRAIL_KEEP = 2 * 3600
FRAME_KEEP = 24 * 3600          # Zeitreise: Minutenbilder der letzten 24 h


class Store:
    def __init__(self, path=DB):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=NORMAL')
        self.db.executescript(SCHEMA)
        cols = [r[1] for r in self.db.execute('PRAGMA table_info(factory_names)')]
        if 'status' not in cols:                      # Migration: Fabrikstatus seit 30.09.2026
            self.db.execute('ALTER TABLE factory_names ADD COLUMN status TEXT')
        self.lock = threading.RLock()

    # ------------------------------------------------------------ Zeitreihen
    def put_series(self, t, values):
        """values: {key: float}; t auf die Minute gerundet (Unix-Sekunden)."""
        t = int(t) // 60 * 60
        with self.lock:
            self.db.executemany('INSERT OR REPLACE INTO series_min VALUES (?,?,?)',
                                [(k, t, float(v)) for k, v in values.items() if v is not None])

    def compact(self, now=None):
        """Minuten → Stunden → Tage verdichten und Altes löschen. Idempotent."""
        now = int(now or time.time())
        with self.lock:
            done_h = now // 3600 * 3600                  # nur abgeschlossene Stunden
            self.db.execute("""INSERT OR REPLACE INTO series_hour
                SELECT key, t/3600*3600, AVG(v) FROM series_min WHERE t < ? AND t >= ?
                GROUP BY key, t/3600""", (done_h, done_h - 3 * 3600))
            done_d = now // 86400 * 86400
            self.db.execute("""INSERT OR REPLACE INTO series_day
                SELECT key, t/86400*86400, AVG(v) FROM series_hour WHERE t < ? AND t >= ?
                GROUP BY key, t/86400""", (done_d, done_d - 3 * 86400))
            self.db.execute('DELETE FROM series_min WHERE t < ?', (now - MIN_KEEP,))
            self.db.execute('DELETE FROM series_hour WHERE t < ?', (now - HOUR_KEEP,))
            self.db.execute('DELETE FROM trail WHERE t < ?', (now - TRAIL_KEEP,))
            self.db.execute('DELETE FROM frames WHERE t < ?', (now - FRAME_KEEP,))
            self.db.execute('DELETE FROM events WHERE t < ?', (now - 30 * 86400,))

    def series(self, keys, since, until=None):
        """Passende Auflösung je Zeitraum: ≤ 48 h Minuten, ≤ 90 d Stunden, sonst Tage."""
        until = int(until or time.time())
        span = until - since
        tabs = ['series_min', 'series_hour', 'series_day']
        i = 0 if span <= MIN_KEEP else 1 if span <= HOUR_KEEP else 2
        out = {}
        with self.lock:
            # Gröbste passende Auflösung zuerst; ist sie (noch) leer, feinere nehmen — sonst zeigt
            # eine junge Datenbank bei langen Zeiträumen gar nichts
            for tab in tabs[i::-1]:
                if self.db.execute(f'SELECT 1 FROM {tab} LIMIT 1').fetchone():
                    break
            for k in keys:
                if k.endswith('*'):
                    rows = self.db.execute(f'SELECT key, t, v FROM {tab} WHERE key LIKE ? AND t BETWEEN ? AND ? ORDER BY t',
                                           (k[:-1] + '%', since, until)).fetchall()
                else:
                    rows = self.db.execute(f'SELECT key, t, v FROM {tab} WHERE key = ? AND t BETWEEN ? AND ? ORDER BY t',
                                           (k, since, until)).fetchall()
                for key, t, v in rows:
                    out.setdefault(key, []).append([t, round(v, 3)])
        return dict(res=tab.split('_')[1], data=out)

    def series_keys(self, prefix=''):
        with self.lock:
            return [r[0] for r in self.db.execute(
                'SELECT DISTINCT key FROM series_min WHERE key LIKE ?', (prefix + '%',))]

    # ------------------------------------------------------------ Ereignisse
    def event(self, kind, level, text, ref=None, x=None, y=None, t=None):
        with self.lock:
            self.db.execute('INSERT INTO events (t, kind, level, text, ref, x, y) VALUES (?,?,?,?,?,?,?)',
                            (int(t or time.time()), kind, level, text, ref, x, y))

    def events(self, since=0, limit=200):
        with self.lock:
            rows = self.db.execute('SELECT id, t, kind, level, text, ref, x, y FROM events WHERE t >= ? '
                                   'ORDER BY id DESC LIMIT ?', (since, limit)).fetchall()
        return [dict(id=r[0], t=r[1], kind=r[2], level=r[3], text=r[4], ref=r[5], x=r[6], y=r[7]) for r in rows]

    # ------------------------------------------------------------ Spuren
    def trail_add(self, t, players):
        with self.lock:
            self.db.executemany('INSERT OR REPLACE INTO trail VALUES (?,?,?,?)',
                                [(p['name'], int(t), p['pos'][0] / 100, p['pos'][1] / 100) for p in players if p.get('online')])

    def trails(self, since):
        out = {}
        with self.lock:
            for n, t, x, y in self.db.execute('SELECT name, t, x, y FROM trail WHERE t >= ? ORDER BY t', (since,)):
                out.setdefault(n, []).append([t, round(x), round(y)])
        return out

    # ------------------------------------------------------------ Zeitreise
    def frame_put(self, t, data):
        """Ein Bild je Minute: Positionen (m, ganzzahlig) von Spielern/Zügen/LKW, Zustand je Fabrik, Strom."""
        with self.lock:
            self.db.execute('INSERT OR REPLACE INTO frames VALUES (?,?)', (int(t) // 60 * 60, json.dumps(data, separators=(',', ':'))))

    def frames(self, since, until=None, step=60):
        """Bilder im Zeitraum; step > 60 dünnt aus (für lange Zeiträume auf dem Handy)."""
        until = int(until or time.time())
        with self.lock:
            rows = self.db.execute('SELECT t, data FROM frames WHERE t BETWEEN ? AND ? ORDER BY t', (since, until)).fetchall()
        out, last = [], -1e18
        for t, d in rows:
            if t - last >= step:
                out.append([t, json.loads(d)]); last = t
        return out

    # ------------------------------------------------------------ Pins
    def pins(self):
        with self.lock:
            rows = self.db.execute('SELECT id, t, author, cat, color, text, shape, geom, ingame FROM pins ORDER BY id').fetchall()
        return [dict(id=r[0], t=r[1], author=r[2], cat=r[3], color=r[4], text=r[5], shape=r[6],
                     geom=json.loads(r[7]), ingame=bool(r[8])) for r in rows]

    def pin_save(self, p):
        with self.lock:
            if p.get('id'):
                self.db.execute('UPDATE pins SET author=?, cat=?, color=?, text=?, shape=?, geom=? WHERE id=?',
                                (p['author'], p['cat'], p['color'], p['text'], p['shape'], json.dumps(p['geom']), p['id']))
                return p['id']
            cur = self.db.execute('INSERT INTO pins (t, author, cat, color, text, shape, geom) VALUES (?,?,?,?,?,?,?)',
                                  (int(time.time()), p['author'], p['cat'], p['color'], p['text'], p['shape'], json.dumps(p['geom'])))
            return cur.lastrowid

    def pin_delete(self, pid):
        with self.lock:
            self.db.execute('DELETE FROM pins WHERE id=?', (pid,))

    # ------------------------------------------------------------ Fabriknamen
    def factory_names(self):
        with self.lock:
            return {k: dict(name=n, author=a, status=s) for k, n, a, s in
                    self.db.execute('SELECT key, name, author, status FROM factory_names')}

    def factory_rename(self, key, name, author, status=None):
        """Name und/oder Status setzen; beides leer → Eintrag weg (Automatik gilt wieder)."""
        with self.lock:
            if name or (status and status != 'aktiv'):
                self.db.execute('INSERT OR REPLACE INTO factory_names (key, name, t, author, status) VALUES (?,?,?,?,?)',
                                (key, name or None, int(time.time()), author, status))
            else:
                self.db.execute('DELETE FROM factory_names WHERE key=?', (key,))

    # ------------------------------------------------------------ Schnappschüsse (Änderungsprotokoll)
    def snapshot_get(self, key):
        with self.lock:
            r = self.db.execute('SELECT t, data FROM snapshot WHERE key=?', (key,)).fetchone()
        return (r[0], json.loads(r[1])) if r else (None, None)

    def snapshot_put(self, key, t, data):
        with self.lock:
            self.db.execute('INSERT OR REPLACE INTO snapshot VALUES (?,?,?)', (key, int(t), json.dumps(data)))

    def kv_get(self, k, default=None):
        with self.lock:
            r = self.db.execute('SELECT v FROM kv WHERE k=?', (k,)).fetchone()
        return json.loads(r[0]) if r else default

    def kv_put(self, k, v):
        with self.lock:
            self.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)', (k, json.dumps(v)))
