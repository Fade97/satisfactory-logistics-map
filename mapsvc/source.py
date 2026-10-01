"""Where the save comes from — configured via SAVE_SOURCE:

  (empty)                         folder saves/ (MAP_SAVES): drop *.sav there or mount it as a volume
  /path/to/folder                 local folder, including subfolders (Windows saves live under SaveGames/<ID>/)
  sftp://user@host:port/path      SFTP; password SAVE_PASSWORD or key file SAVE_KEY
  ftp://user@host:port/path       FTP, ftps:// with TLS (many server hosts); password SAVE_PASSWORD
  api://host:7777                 HTTPS API of the dedicated server; admin password SAVE_PASSWORD or token SAVE_TOKEN

The newest save is used (SAVE_PATTERN, default *.sav). It is only downloaded when it has changed;
the result is always saves/latest.sav, its version marker saves/latest.stamp.
"""
import datetime, fnmatch, ftplib, json, os, shutil, ssl, stat, time, urllib.parse, urllib.request

from .core import SAVES, log

SOURCE = os.environ.get('SAVE_SOURCE', '').strip()
PASSWORD = os.environ.get('SAVE_PASSWORD', '')
TOKEN = os.environ.get('SAVE_TOKEN', '')
KEY = os.path.expanduser(os.environ.get('SAVE_KEY', ''))
PATTERN = os.environ.get('SAVE_PATTERN', '*.sav')
FRESH = 10                                  # younger than 10 s: may still be being written → next cycle


class SourceError(Exception):
    pass


def describe(src=None):
    """Source without password, for the log and status display."""
    src = SOURCE if src is None else src
    if not src:
        return 'folder ' + SAVES
    u = urllib.parse.urlsplit(src)
    if not u.scheme or len(u.scheme) == 1:          # path (also C:\…)
        return 'folder ' + src
    host = u.hostname or ''
    return '%s://%s%s%s' % (u.scheme, (u.username + '@') if u.username else '', host, (':%d' % u.port) if u.port else '') + (u.path or '')


def fetch_latest(src=None):
    """→ (local path, display name, mtime, changed?)"""
    src = SOURCE if src is None else src
    u = urllib.parse.urlsplit(src)
    if not src or not u.scheme or len(u.scheme) == 1:
        return _dir(src or SAVES)
    fn = {'sftp': _sftp, 'ssh': _sftp, 'ftp': _ftp, 'ftps': _ftp, 'api': _api, 'https': _api}.get(u.scheme)
    if not fn:
        raise SourceError('unknown save source %r (allowed: folder, sftp://, ftp://, ftps://, api://)' % u.scheme)
    return fn(u)


# ---------------------------------------------------------------- shared
def _paths():
    os.makedirs(SAVES, exist_ok=True)
    return os.path.join(SAVES, 'latest.sav'), os.path.join(SAVES, 'latest.stamp')


def _take(name, mtime, download, version=None):
    """Download a new save if name/time differ from last time. download(dst) writes the file."""
    local, stamp = _paths()
    prev = open(stamp).read().strip() if os.path.exists(stamp) else ''
    tag = '%s|%s' % (name, version or int(mtime))
    changed = tag != prev or not os.path.exists(local)
    if changed and time.time() - mtime < FRESH and os.path.exists(local):
        return local, prev.split('|')[0] or name, os.path.getmtime(local), False
    if changed:
        log('fetching save', name, '…')
        tmp = local + '.part'
        download(tmp)
        if os.path.getsize(tmp) < 1024:
            raise SourceError('Save %s is empty or incomplete' % name)
        os.replace(tmp, local)
        os.utime(local, (mtime, mtime))
        open(stamp, 'w').write(tag)
    return local, name, mtime, changed


def _newest(entries):
    """entries: [(name, mtime, path)] → newest matching save."""
    hits = [e for e in entries if fnmatch.fnmatch(e[0], PATTERN) and e[0] != 'latest.sav']
    if not hits:
        raise SourceError('no save (%s) in %s' % (PATTERN, describe()))
    return max(hits, key=lambda e: e[1])


# ---------------------------------------------------------------- folder
def _dir(path):
    path = os.path.expanduser(path)
    if not os.path.isdir(path):
        raise SourceError('folder %s not found' % path)
    entries = []
    for root, _dirs, files in os.walk(path):
        entries += [(f, os.path.getmtime(os.path.join(root, f)), os.path.join(root, f)) for f in files]
    if not any(e[0] != 'latest.sav' and fnmatch.fnmatch(e[0], PATTERN) for e in entries):
        local, stamp = _paths()                      # only a previously fetched latest.sav present → use it
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
        raise SourceError('SFTP needs paramiko (pip install paramiko)')
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
        except ftplib.error_perm:                    # server without MLSD: list + MDTM per file
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


# ---------------------------------------------------------------- server API (dedicated server, HTTPS)
_token = [TOKEN]
_CTX = ssl._create_unverified_context()          # the server uses a self-signed certificate


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
        raise SourceError('Server API %s: %s %s' % (fn, e.code, err))
    except OSError as e:
        raise SourceError('Server API %s not reachable: %s' % (describe(), e))


def _api(u, retry=True):
    base = 'https://%s:%d/api/v1' % (u.hostname, u.port or 7777)
    if not _token[0]:
        if not PASSWORD:
            raise SourceError('Server API needs SAVE_PASSWORD (admin password) or SAVE_TOKEN')
        r = _call(base, 'PasswordLogin', {'MinimumPrivilegeLevel': 'Administrator', 'Password': PASSWORD})
        _token[0] = r['data']['authenticationToken']
    try:
        d = _call(base, 'EnumerateSessions')['data']
    except SourceError as e:
        if TOKEN or not retry or ('401' not in str(e) and '403' not in str(e)):
            raise
        _token[0] = ''                              # token expired → log in again once
        return _api(u, retry=False)
    sessions = d.get('sessions') or []
    if not sessions:
        raise SourceError('Server API: no session found')
    cur = sessions[d.get('currentSessionIndex', 0) or 0]
    heads = [h for h in cur.get('saveHeaders') or [] if fnmatch.fnmatch(h['saveName'] + '.sav', PATTERN)]
    if not heads:
        raise SourceError('Server API: session %s has no save' % cur.get('sessionName'))
    h = max(heads, key=lambda h: h.get('saveDateTime', ''))
    mtime = _apitime(h.get('saveDateTime', ''))

    def download(dst):
        _call(base, 'DownloadSaveGame', {'SaveName': h['saveName']}, raw_to=dst)
        if not os.path.exists(dst):
            raise SourceError('Server API: DownloadSaveGame returned no file')
    return _take(h['saveName'] + '.sav', mtime, download, version=h.get('saveDateTime'))


def _apitime(v):
    """API saveDateTime ('2024.09.21-17.02.33' or FDateTime ticks, UTC); unknown format → now."""
    if v.isdigit() and len(v) >= 17:               # 100 ns ticks since 0001-01-01
        return (int(v) - 621355968000000000) / 1e7
    for fmt in ('%Y.%m.%d-%H.%M.%S', '%Y-%m-%dT%H:%M:%S', '%Y%m%d%H%M%S'):
        try:
            return datetime.datetime.strptime(v[:19], fmt).replace(tzinfo=datetime.timezone.utc).timestamp()
        except ValueError:
            pass
    return time.time() - FRESH
