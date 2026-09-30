"""Woher das Save kommt — einstellbar über SAVE_SOURCE:

  (leer)                          Ordner saves/ (MAP_SAVES): *.sav dort ablegen oder als Volume einhängen
  /pfad/zum/ordner                lokaler Ordner, auch Unterordner (Windows-Saves liegen unter SaveGames/<ID>/)
  sftp://user@host:port/pfad      SFTP; Passwort SAVE_PASSWORD oder Schlüsseldatei SAVE_KEY
  ftp://user@host:port/pfad       FTP, ftps:// mit TLS (viele Server-Hoster); Passwort SAVE_PASSWORD
  api://host:7777                 HTTPS-API des Dedicated Servers; Admin-Passwort SAVE_PASSWORD oder Token SAVE_TOKEN

Genommen wird das jüngste Save (SAVE_PATTERN, Standard *.sav). Geladen wird nur, wenn es sich geändert hat;
das Ergebnis liegt immer in saves/latest.sav, der Stand in saves/latest.stamp.
"""
import datetime, fnmatch, ftplib, json, os, shutil, ssl, stat, time, urllib.parse, urllib.request

from .core import SAVES, log

SOURCE = os.environ.get('SAVE_SOURCE', '').strip()
PASSWORD = os.environ.get('SAVE_PASSWORD', '')
TOKEN = os.environ.get('SAVE_TOKEN', '')
KEY = os.path.expanduser(os.environ.get('SAVE_KEY', ''))
PATTERN = os.environ.get('SAVE_PATTERN', '*.sav')
FRESH = 10                                  # jünger als 10 s: wird evtl. noch geschrieben → nächster Takt


class SourceError(Exception):
    pass


def describe(src=None):
    """Quelle ohne Passwort, für Log und Statusanzeige."""
    src = SOURCE if src is None else src
    if not src:
        return 'Ordner ' + SAVES
    u = urllib.parse.urlsplit(src)
    if not u.scheme or len(u.scheme) == 1:          # Pfad (auch C:\…)
        return 'Ordner ' + src
    host = u.hostname or ''
    return '%s://%s%s%s' % (u.scheme, (u.username + '@') if u.username else '', host, (':%d' % u.port) if u.port else '') + (u.path or '')


def fetch_latest(src=None):
    """→ (lokaler Pfad, Anzeigename, mtime, geändert?)"""
    src = SOURCE if src is None else src
    u = urllib.parse.urlsplit(src)
    if not src or not u.scheme or len(u.scheme) == 1:
        return _dir(src or SAVES)
    fn = {'sftp': _sftp, 'ssh': _sftp, 'ftp': _ftp, 'ftps': _ftp, 'api': _api, 'https': _api}.get(u.scheme)
    if not fn:
        raise SourceError('unbekannte Save-Quelle %r (erlaubt: Ordner, sftp://, ftp://, ftps://, api://)' % u.scheme)
    return fn(u)


# ---------------------------------------------------------------- gemeinsam
def _paths():
    os.makedirs(SAVES, exist_ok=True)
    return os.path.join(SAVES, 'latest.sav'), os.path.join(SAVES, 'latest.stamp')


def _take(name, mtime, download, version=None):
    """Neues Save laden, wenn Name/Zeit anders sind als beim letzten Mal. download(ziel) schreibt die Datei."""
    local, stamp = _paths()
    prev = open(stamp).read().strip() if os.path.exists(stamp) else ''
    tag = '%s|%s' % (name, version or int(mtime))
    changed = tag != prev or not os.path.exists(local)
    if changed and time.time() - mtime < FRESH and os.path.exists(local):
        return local, prev.split('|')[0] or name, os.path.getmtime(local), False
    if changed:
        log('lade Save', name, '…')
        tmp = local + '.part'
        download(tmp)
        if os.path.getsize(tmp) < 1024:
            raise SourceError('Save %s ist leer oder unvollständig' % name)
        os.replace(tmp, local)
        os.utime(local, (mtime, mtime))
        open(stamp, 'w').write(tag)
    return local, name, mtime, changed


def _newest(entries):
    """entries: [(name, mtime, pfad)] → jüngstes passendes Save."""
    hits = [e for e in entries if fnmatch.fnmatch(e[0], PATTERN) and e[0] != 'latest.sav']
    if not hits:
        raise SourceError('kein Save (%s) in %s' % (PATTERN, describe()))
    return max(hits, key=lambda e: e[1])


# ---------------------------------------------------------------- Ordner
def _dir(path):
    path = os.path.expanduser(path)
    if not os.path.isdir(path):
        raise SourceError('Ordner %s fehlt' % path)
    entries = []
    for root, _dirs, files in os.walk(path):
        entries += [(f, os.path.getmtime(os.path.join(root, f)), os.path.join(root, f)) for f in files]
    if not any(e[0] != 'latest.sav' and fnmatch.fnmatch(e[0], PATTERN) for e in entries):
        local, stamp = _paths()                      # nur ein früher geholtes latest.sav da → das nehmen
        if os.path.exists(local):
            name = open(stamp).read().split('|')[0] if os.path.exists(stamp) else 'latest.sav'
            return local, os.path.basename(name), os.path.getmtime(local), False
    name, mtime, full = _newest(entries)
    return _take(name, mtime, lambda dst: shutil.copyfile(full, dst))


# ---------------------------------------------------------------- SFTP
def _sftp(u):
    try:
        import paramiko
    except ImportError:
        raise SourceError('SFTP braucht paramiko (pip install paramiko)')
    t = paramiko.Transport((u.hostname, u.port or 22))
    try:
        pkey = paramiko.PKey.from_path(KEY) if KEY else None
        t.connect(username=urllib.parse.unquote(u.username or ''),
                  password=(urllib.parse.unquote(u.password) if u.password else PASSWORD) or None, pkey=pkey)
        s = paramiko.SFTPClient.from_transport(t)
        d = urllib.parse.unquote(u.path) or '.'
        entries = [(a.filename, a.st_mtime, d.rstrip('/') + '/' + a.filename)
                   for a in s.listdir_attr(d) if stat.S_ISREG(a.st_mode or 0)]
        name, mtime, full = _newest(entries)
        return _take(name, mtime, lambda dst: s.get(full, dst))
    except (paramiko.SSHException, OSError) as e:
        raise SourceError('SFTP %s: %s' % (describe(), e))
    finally:
        t.close()


# ---------------------------------------------------------------- FTP
def _ftp(u):
    f = ftplib.FTP_TLS() if u.scheme == 'ftps' else ftplib.FTP()
    try:
        f.connect(u.hostname, u.port or 21, timeout=30)
        f.login(urllib.parse.unquote(u.username or 'anonymous'), urllib.parse.unquote(u.password) if u.password else PASSWORD)
        if u.scheme == 'ftps':
            f.prot_p()
        d = urllib.parse.unquote(u.path) or '/'
        entries = []
        try:
            for name, facts in f.mlsd(d, facts=['type', 'modify']):
                if facts.get('type') == 'file':
                    entries.append((name, _ftptime(facts['modify']), d.rstrip('/') + '/' + name))
        except ftplib.error_perm:                    # Server ohne MLSD: Liste + MDTM je Datei
            for full in f.nlst(d):
                name = full.rsplit('/', 1)[-1]
                if fnmatch.fnmatch(name, PATTERN):
                    full = full if '/' in full else d.rstrip('/') + '/' + full
                    entries.append((name, _ftptime(f.voidcmd('MDTM ' + full)[4:].strip()), full))

        def download(dst):
            with open(dst, 'wb') as fh:
                f.retrbinary('RETR ' + full, fh.write)
        name, mtime, full = _newest(entries)
        return _take(name, mtime, download)
    except ftplib.all_errors as e:
        raise SourceError('FTP %s: %s' % (describe(), e))
    finally:
        try:
            f.quit()
        except Exception:
            f.close()


def _ftptime(v):
    return datetime.datetime.strptime(v[:14], '%Y%m%d%H%M%S').replace(tzinfo=datetime.timezone.utc).timestamp()


# ---------------------------------------------------------------- Server-API (Dedicated Server, HTTPS)
_token = [TOKEN]
_CTX = ssl._create_unverified_context()          # der Server nutzt ein selbstsigniertes Zertifikat


def _call(base, fn, data=None, raw_to=None):
    body = json.dumps({'function': fn, 'data': data or {}}).encode()
    h = {'Content-Type': 'application/json'}
    if _token[0]:
        h['Authorization'] = 'Bearer ' + _token[0]
    req = urllib.request.Request(base, body, h)
    try:
        with urllib.request.urlopen(req, context=_CTX, timeout=120) as r:
            if raw_to and 'json' not in (r.headers.get('Content-Type') or ''):
                with open(raw_to, 'wb') as fh:
                    shutil.copyfileobj(r, fh, 1 << 20)
                return None
            return json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read()).get('errorCode', '')
        except Exception:
            err = ''
        raise SourceError('Server-API %s: %s %s' % (fn, e.code, err))
    except OSError as e:
        raise SourceError('Server-API %s nicht erreichbar: %s' % (describe(), e))


def _api(u, retry=True):
    base = 'https://%s:%d/api/v1' % (u.hostname, u.port or 7777)
    if not _token[0]:
        if not PASSWORD:
            raise SourceError('Server-API braucht SAVE_PASSWORD (Admin-Passwort) oder SAVE_TOKEN')
        r = _call(base, 'PasswordLogin', {'MinimumPrivilegeLevel': 'Administrator', 'Password': PASSWORD})
        _token[0] = r['data']['authenticationToken']
    try:
        d = _call(base, 'EnumerateSessions')['data']
    except SourceError as e:
        if TOKEN or not retry or ('401' not in str(e) and '403' not in str(e)):
            raise
        _token[0] = ''                              # Token abgelaufen → einmal neu anmelden
        return _api(u, retry=False)
    sessions = d.get('sessions') or []
    if not sessions:
        raise SourceError('Server-API: keine Session gefunden')
    cur = sessions[d.get('currentSessionIndex', 0) or 0]
    heads = [h for h in cur.get('saveHeaders') or [] if fnmatch.fnmatch(h['saveName'] + '.sav', PATTERN)]
    if not heads:
        raise SourceError('Server-API: Session %s hat kein Save' % cur.get('sessionName'))
    h = max(heads, key=lambda h: h.get('saveDateTime', ''))
    mtime = _apitime(h.get('saveDateTime', ''))

    def download(dst):
        _call(base, 'DownloadSaveGame', {'SaveName': h['saveName']}, raw_to=dst)
        if not os.path.exists(dst):
            raise SourceError('Server-API: DownloadSaveGame lieferte keine Datei')
    return _take(h['saveName'] + '.sav', mtime, download, version=h.get('saveDateTime'))


def _apitime(v):
    """saveDateTime der API ('2024.09.21-17.02.33' oder FDateTime-Ticks, UTC); unbekanntes Format → jetzt."""
    if v.isdigit() and len(v) >= 17:               # 100-ns-Ticks seit 0001-01-01
        return (int(v) - 621355968000000000) / 1e7
    for fmt in ('%Y.%m.%d-%H.%M.%S', '%Y-%m-%dT%H:%M:%S', '%Y%m%d%H%M%S'):
        try:
            return datetime.datetime.strptime(v[:19], fmt).replace(tzinfo=datetime.timezone.utc).timestamp()
        except ValueError:
            pass
    return time.time() - FRESH
