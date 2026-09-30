"""Save-Quellen (mapsvc/source.py): Ordner, FTP und Server-API gegen lokale Testserver — ohne echtes Save."""
import json, os, ssl, subprocess, sys, threading, time
import http.server

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mapsvc import source  # noqa: E402

SAV = b'\xc1\x83\x2a\x9e' + b'x' * 4000          # Inhalt egal, nur > 1 KB


@pytest.fixture
def saves(tmp_path, monkeypatch):
    d = tmp_path / 'saves'
    monkeypatch.setattr(source, 'SAVES', str(d))
    monkeypatch.setattr(source, 'PATTERN', '*.sav')
    return d


def put(path, age, data=SAV):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    t = time.time() - age
    os.utime(path, (t, t))


# ---------------------------------------------------------------- Ordner
def test_dir_newest_recursive_and_change(saves, tmp_path):
    src = tmp_path / 'SaveGames'
    put(src / 'server' / 'Welt_autosave_0.sav', 600)
    put(src / '76561198000000000' / 'Welt_autosave_1.sav', 300)      # Windows-Unterordner
    put(src / 'server' / 'notizen.txt', 10)
    path, name, mtime, changed = source.fetch_latest(str(src))
    assert name == 'Welt_autosave_1.sav' and changed
    assert open(path, 'rb').read() == SAV
    assert source.fetch_latest(str(src))[3] is False                 # unverändert → nicht neu laden
    put(src / 'server' / 'Welt_autosave_2.sav', 60)
    assert source.fetch_latest(str(src))[1:4:2] == ('Welt_autosave_2.sav', True)


def test_dir_skips_file_being_written(saves, tmp_path):
    src = tmp_path / 'SaveGames'
    put(src / 'a.sav', 300)
    source.fetch_latest(str(src))
    put(src / 'b.sav', 1)                                             # gerade geschrieben
    assert source.fetch_latest(str(src))[1:4:2] == ('a.sav', False)


def test_dir_pattern_and_errors(saves, tmp_path, monkeypatch):
    src = tmp_path / 'SaveGames'
    put(src / 'Alt_autosave_0.sav', 60)
    put(src / 'Neu_autosave_0.sav', 600)
    monkeypatch.setattr(source, 'PATTERN', 'Neu_*.sav')
    assert source.fetch_latest(str(src))[1] == 'Neu_autosave_0.sav'
    with pytest.raises(source.SourceError):
        source.fetch_latest(str(tmp_path / 'fehlt'))
    with pytest.raises(source.SourceError):
        source.fetch_latest('gopher://x/y')


def test_default_is_saves_folder(saves):
    put(saves / 'Hochgeladen.sav', 120)
    path, name, _, changed = source.fetch_latest('')
    assert name == 'Hochgeladen.sav' and path.endswith('latest.sav') and changed


def test_describe_hides_password():
    d = source.describe('sftp://nutzer:geheim@host.example:2022/pfad')
    assert 'geheim' not in d and 'nutzer@host.example:2022/pfad' in d
    assert source.describe('/srv/saves') == 'Ordner /srv/saves'


def test_api_time():
    assert source._apitime('2026.09.30-12.00.00') == 1790769600
    assert abs(source._apitime('638946000000000000') - 1759003200) < 1


# ---------------------------------------------------------------- FTP (pyftpdlib)
def test_ftp(saves, tmp_path):
    pytest.importorskip('pyftpdlib')
    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer
    root = tmp_path / 'ftp'
    put(root / 'SaveGames' / 'server' / 'Welt_1.sav', 900)
    put(root / 'SaveGames' / 'server' / 'Welt_2.sav', 300)
    auth = DummyAuthorizer()
    auth.add_user('spieler', 'pw', str(root), perm='elr')
    FTPHandler.authorizer = auth
    srv = FTPServer(('127.0.0.1', 0), FTPHandler)
    port = srv.socket.getsockname()[1]
    threading.Thread(target=srv.serve_forever, kwargs=dict(timeout=0.2), daemon=True).start()
    try:
        path, name, mtime, changed = source.fetch_latest('ftp://spieler:pw@127.0.0.1:%d/SaveGames/server' % port)
        assert name == 'Welt_2.sav' and changed and abs(mtime - (time.time() - 300)) < 5
        assert open(path, 'rb').read() == SAV
    finally:
        srv.close_all()


# ---------------------------------------------------------------- Server-API (nachgebaut, HTTPS)
def test_api(saves, tmp_path, monkeypatch):
    if subprocess.run(['which', 'openssl'], capture_output=True).returncode:
        pytest.skip('openssl fehlt')
    cert = tmp_path / 'c.pem'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=localhost',
                    '-keyout', str(cert), '-out', str(cert)], capture_output=True, check=True)
    calls = []

    class Api(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            fn, auth = req['function'], self.headers.get('Authorization')
            calls.append(fn)
            if fn == 'PasswordLogin':
                ok = req['data']['Password'] == 'admin'
                return self._json({'data': {'authenticationToken': 'T1'}} if ok else {'errorCode': 'wrong_password'}, 200 if ok else 401)
            if auth != 'Bearer T1':
                return self._json({'errorCode': 'invalid_token'}, 401)
            if fn == 'EnumerateSessions':
                return self._json({'data': {'currentSessionIndex': 1, 'sessions': [
                    {'sessionName': 'Alt', 'saveHeaders': [{'saveName': 'Alt_autosave_0', 'saveDateTime': '2026.09.30-11.59.00'}]},
                    {'sessionName': 'Welt', 'saveHeaders': [
                        {'saveName': 'Welt_autosave_0', 'saveDateTime': '2026.09.30-11.00.00'},
                        {'saveName': 'Welt_autosave_1', 'saveDateTime': '2026.09.30-11.05.00'}]}]}})
            if fn == 'DownloadSaveGame':
                assert req['data']['SaveName'] == 'Welt_autosave_1'
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Length', str(len(SAV)))
                self.end_headers()
                return self.wfile.write(SAV)

        def _json(self, o, code=200):
            b = json.dumps(o).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(b)))
            self.end_headers()
            self.wfile.write(b)

    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Api)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(cert))
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = 'api://127.0.0.1:%d' % srv.server_address[1]
    monkeypatch.setattr(source, '_token', [''])
    try:
        monkeypatch.setattr(source, 'PASSWORD', 'falsch')
        with pytest.raises(source.SourceError, match='401'):
            source.fetch_latest(url)
        monkeypatch.setattr(source, 'PASSWORD', 'admin')
        path, name, mtime, changed = source.fetch_latest(url)
        assert name == 'Welt_autosave_1.sav' and changed and open(path, 'rb').read() == SAV
        assert source.fetch_latest(url)[3] is False                  # gleiche Version → kein Download
        assert calls.count('DownloadSaveGame') == 1
        source._token[0] = 'abgelaufen'                              # Token ungültig → neu anmelden
        assert source.fetch_latest(url)[1] == 'Welt_autosave_1.sav'
    finally:
        srv.shutdown()
