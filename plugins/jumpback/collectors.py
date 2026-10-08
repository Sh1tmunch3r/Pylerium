"""Read saved browser visits and sample Windows foreground metadata."""
import ctypes
import os
import hashlib
import shutil
import sqlite3
import tempfile
import time
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path
from urllib.parse import urlsplit

from .history_store import event_key
from .scanner import get_recent_items

CHROME_EPOCH = 11644473600


def file_stamp(path):
    try:
        stat = path.stat()
        return stat.st_size, stat.st_mtime_ns
    except FileNotFoundError:
        return None


def file_digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').digest()


@contextmanager
def browser_connection(path, cancel):
    """Prefer a live read; locked Opera profiles use a verified disposable copy.

    Only the private copy is writable (for SQLite journal recovery). Never
    checkpoint, change lock mode or write to the browser's database files.
    """
    path = Path(path).resolve()
    live = None
    try:
        live = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=0.3)
        live.execute('SELECT name FROM sqlite_master LIMIT 1').fetchone()
    except sqlite3.OperationalError as exc:
        if live is not None:
            live.close()
            live = None
        if not any(word in str(exc).lower() for word in ('locked', 'readonly', 'unable to open')):
            raise
    if live is not None:
        try:
            yield live
        finally:
            live.close()
        return
    if cancel.is_set():
        raise sqlite3.OperationalError('History import cancelled')
    # Include transaction sidecars. SHM is regenerated in the private directory.
    files = [path, Path(str(path) + '-wal'), Path(str(path) + '-journal')]
    for attempt in range(3):
        if cancel.is_set():
            raise sqlite3.OperationalError('History import cancelled')
        with tempfile.TemporaryDirectory(prefix='jumpback-browser-') as directory:
            copy = Path(directory) / path.name
            before = {str(file): file_stamp(file) for file in files}
            for file in files:
                if before[str(file)] is not None:
                    shutil.copyfile(file, Path(directory) / file.name)
            after = {str(file): file_stamp(file) for file in files}
            if before != after:
                continue
            # Windows can defer modification timestamps: compare contents too.
            if any(file_digest(file) != file_digest(Path(directory) / file.name)
                   for file in files if before[str(file)] is not None):
                continue
            if {str(file): file_stamp(file) for file in files} != after:
                continue
            db = sqlite3.connect(copy, timeout=0.3)
            db.set_progress_handler(lambda: int(cancel.is_set()), 1000)
            try:
                check = db.execute('PRAGMA quick_check(1)').fetchone()
                if not check or check[0] != 'ok':
                    continue
                yield db
                return
            finally:
                db.close()
    raise sqlite3.OperationalError('Browser history changed during snapshot; will retry on the next import')


def allowed(event, exclusions, paused=()):
    occurred = event.get('occurred')
    if occurred is not None and any(start <= occurred <= end for start, end in paused):
        return False
    haystack = ' '.join(str(event.get(key, '')) for key in ('title', 'target', 'app', 'source')).casefold()
    return not any(value.strip().casefold() in haystack for value in exclusions if value.strip())


def browser_sources(extra=()):
    local = Path(os.environ.get('LOCALAPPDATA', ''))
    roaming = Path(os.environ.get('APPDATA', ''))
    roots = [
        ('Opera', roaming / 'Opera Software' / 'Opera Stable'),
        ('Opera GX', roaming / 'Opera Software' / 'Opera GX Stable'),
        ('Opera Beta', roaming / 'Opera Software' / 'Opera Next'),
        ('Chrome', local / 'Google' / 'Chrome' / 'User Data'),
        ('Edge', local / 'Microsoft' / 'Edge' / 'User Data'),
        ('Brave', local / 'BraveSoftware' / 'Brave-Browser' / 'User Data'),
        ('Vivaldi', local / 'Vivaldi' / 'User Data'),
    ]
    found = {}
    for browser, root in roots:
        candidates = [root / 'History']
        if root.is_dir():
            candidates.extend(root.glob('*/History'))
        for filename in candidates:
            if filename.is_file():
                profile = filename.parent.name
                label = browser + ' / ' + profile
                found[str(filename.resolve())] = (label, filename, 'chromium')
    firefox = roaming / 'Mozilla' / 'Firefox' / 'Profiles'
    if firefox.is_dir():
        for filename in firefox.glob('*/places.sqlite'):
            found[str(filename.resolve())] = ('Firefox / ' + filename.parent.name, filename, 'firefox')
    for name in extra:
        filename = Path(name)
        # Let missing custom paths report a visible error rather than disappear.
        found[str(filename.resolve())] = ('Custom / ' + filename.parent.name, filename,
                                          'firefox' if filename.name == 'places.sqlite' else 'chromium')
    return list(found.values())


def import_browser(store, source, cancel, exclusions):
    label, path, engine = source
    checkpoint_key = 'cursor:' + str(path.resolve())
    watermark = store.get(checkpoint_key, 0)
    # A short overlap captures delayed writes. Identity makes rescans idempotent.
    minimum = max(0, watermark - 120_000_000)
    imported = seen = 0
    latest = watermark
    paused = store.get('pause_intervals', [])
    pause_started = store.get('pause_started')
    if pause_started:
        paused.append([pause_started, time.time()])
    with browser_connection(path, cancel) as db:
        db.set_progress_handler(lambda: int(cancel.is_set()), 1000)
        if engine == 'firefox':
            sql = '''SELECT v.id,v.visit_date,p.url,COALESCE(p.title,'')
                     FROM moz_historyvisits v JOIN moz_places p ON p.id=v.place_id
                     WHERE v.visit_date>=? ORDER BY v.visit_date,v.id'''
        else:
            sql = '''SELECT v.id,v.visit_time,u.url,COALESCE(u.title,'')
                     FROM visits v JOIN urls u ON u.id=v.url
                     WHERE v.visit_time>=? ORDER BY v.visit_time,v.id'''
        cursor = db.execute(sql, (minimum,))
        while not cancel.is_set():
            rows = cursor.fetchmany(500)
            if not rows:
                store.set(checkpoint_key, latest)
                break
            batch = []
            for ident, stamp, url, title in rows:
                latest = max(latest, stamp)
                seen += 1
                parsed = urlsplit(url)
                if parsed.scheme not in ('http', 'https', 'file'):
                    continue
                host = (parsed.hostname or '').lower()
                video = host == 'youtu.be' or host == 'youtube.com' or host.endswith('.youtube.com')
                event = dict(event_key=event_key(str(path.resolve()), ident, stamp, url),
                             occurred=stamp / 1_000_000 - (CHROME_EPOCH if engine == 'chromium' else 0),
                             title=title or url, target=url, kind='VIDEO' if video else 'WEB',
                             source=label, app=label.split(' / ')[0], detail=host)
                if allowed(event, exclusions, paused):
                    batch.append(event)
            imported += store.append(batch)
    return imported, seen


def collect_history(store, cancel, recent_scanner=get_recent_items):
    exclusions = store.get('exclusions', [])
    paused = store.get('pause_intervals', [])
    pause_started = store.get('pause_started')
    if pause_started:
        paused.append([pause_started, time.time()])
    report = []
    total = 0
    for source in browser_sources(store.get('custom_sources', [])):
        if cancel.is_set():
            return dict(imported=total, sources=report)
        try:
            added, seen = import_browser(store, source, cancel, exclusions)
            total += added
            report.append(dict(source=source[0], path=str(source[1]), status='Ready',
                               message=f'{added:,} new / {seen:,} checked', checked=time.time()))
        except (OSError, sqlite3.Error, ValueError) as exc:
            if cancel.is_set():
                break
            report.append(dict(source=source[0], path=str(source[1]), status='Retry needed',
                               message=str(exc), checked=time.time()))
    if not cancel.is_set():
        try:
            watermark = store.get('recent_cursor', 0)
            added = 0
            def ingest_recent(items):
                nonlocal added
                if cancel.is_set():
                    return
                batch = []
                for item in items:
                    event = dict(event_key=event_key('recent', item['shortcut_path'], item['mtime']),
                                 occurred=item['mtime'], kind=item['category'], source='Windows recent',
                                 title=item['name'], target=item['target_path'], detail=item['category_label'])
                    if allowed(event, exclusions, paused):
                        batch.append(event)
                added += store.append(batch)
            items = recent_scanner(limit=2_147_483_647, cancel=cancel,
                                   min_mtime=max(0, watermark - 2), on_batch=ingest_recent)
            # Also support scanner replacements which return a list without batches.
            ingest_recent(items)
            total += added
            if items and not cancel.is_set():
                store.set('recent_cursor', max(item['mtime'] for item in items))
            report.append(dict(source='Windows recent', path=os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Recent'),
                               status='Ready', message=f'{added:,} new / {len(items):,} checked', checked=time.time()))
        except (OSError, ValueError) as exc:
            report.append(dict(source='Windows recent', path='', status='Retry needed', message=str(exc), checked=time.time()))
    if not browser_sources(store.get('custom_sources', [])):
        report.append(dict(source='Browsers', path='', status='Not found',
                           message='No saved browser history found. Add a History or places.sqlite file in Sources.', checked=time.time()))
    return dict(imported=total, sources=report)


class ForegroundReader:
    def __init__(self):
        self.available = os.name == 'nt'
        if not self.available:
            return
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.user.GetForegroundWindow.restype = wintypes.HWND
        self.user.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self.user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                         wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.GetTickCount.restype = wintypes.DWORD

    def read(self):
        if not self.available:
            return None
        class LastInput(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.UINT), ('dwTime', wintypes.DWORD)]
        info = LastInput()
        info.cbSize = ctypes.sizeof(info)
        if self.user.GetLastInputInfo(ctypes.byref(info)):
            idle_ms = (self.kernel.GetTickCount() - info.dwTime) & 0xffffffff
            if idle_ms > 60_000:
                return None
        hwnd = self.user.GetForegroundWindow()
        if not hwnd:
            return None
        length = self.user.GetWindowTextLengthW(hwnd)
        if not length:
            return None
        text = ctypes.create_unicode_buffer(min(length + 1, 4096))
        self.user.GetWindowTextW(hwnd, text, len(text))
        pid = wintypes.DWORD()
        self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == os.getpid():
            return None
        process = self.kernel.OpenProcess(0x1000, False, pid.value)
        path = ''
        if process:
            try:
                buffer = ctypes.create_unicode_buffer(32768)
                size = wintypes.DWORD(len(buffer))
                if self.kernel.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
                    path = buffer.value
            finally:
                self.kernel.CloseHandle(process)
        title = text.value
        if any(word in title.casefold() for word in ('inprivate', 'incognito', 'private browsing', 'private window')):
            return None
        return dict(title=title, app=Path(path).name if path else f'Process {pid.value}', target=path,
                    detail='Foreground window title • sampled every 2 seconds; idle after 60 seconds')
