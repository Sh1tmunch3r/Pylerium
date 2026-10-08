"""Local, durable activity archive. Each operation owns its SQLite connection."""
import csv
import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager, nullcontext
from pathlib import Path


def event_key(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode('utf-8')).hexdigest()


class HistoryStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, event_key TEXT UNIQUE NOT NULL,
                    occurred REAL NOT NULL, ended REAL, duration REAL DEFAULT 0,
                    kind TEXT NOT NULL, source TEXT NOT NULL, title TEXT NOT NULL,
                    target TEXT DEFAULT '', app TEXT DEFAULT '', detail TEXT DEFAULT '',
                    note TEXT DEFAULT '', pinned INTEGER DEFAULT 0, note_revision INTEGER DEFAULT 0);
                CREATE INDEX IF NOT EXISTS event_time ON events(occurred DESC, id DESC);
                CREATE INDEX IF NOT EXISTS event_source ON events(source, occurred);
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
            ''')
            if 'note_revision' not in {row[1] for row in db.execute('PRAGMA table_info(events)')}:
                db.execute('ALTER TABLE events ADD COLUMN note_revision INTEGER DEFAULT 0')
            try:
                db.executescript('''
                    CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
                        title, target, app, detail, note,
                        content='events', content_rowid='id', tokenize='trigram');
                    CREATE TRIGGER IF NOT EXISTS events_ai AFTER INSERT ON events BEGIN
                        INSERT INTO search_index(rowid,title,target,app,detail,note)
                        VALUES(new.id,new.title,new.target,new.app,new.detail,new.note);
                    END;
                    CREATE TRIGGER IF NOT EXISTS events_au AFTER UPDATE ON events BEGIN
                        INSERT INTO search_index(search_index,rowid,title,target,app,detail,note)
                        VALUES('delete',old.id,old.title,old.target,old.app,old.detail,old.note);
                        INSERT INTO search_index(rowid,title,target,app,detail,note)
                        VALUES(new.id,new.title,new.target,new.app,new.detail,new.note);
                    END;
                ''')
                if not db.execute("SELECT 1 FROM settings WHERE key='search_initialized'").fetchone():
                    db.execute("INSERT INTO search_index(search_index) VALUES('rebuild')")
                    db.execute("INSERT INTO settings VALUES('search_initialized','true')")
                self.fts = True
            except sqlite3.OperationalError:
                self.fts = False

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=3)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, key, default=None):
        with self.connect() as db:
            row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (key, json.dumps(value)))

    def append(self, events):
        with self.connect() as db:
            # Preserve notes, pins and visit identity when a source is scanned again.
            count = 0
            for event in events:
                cur = db.execute('''INSERT OR IGNORE INTO events
                    (event_key,occurred,ended,duration,kind,source,title,target,app,detail)
                    VALUES(?,?,?,?,?,?,?,?,?,?)''', (
                    event['event_key'], event['occurred'], event.get('ended'),
                    event.get('duration', 0), event['kind'], event['source'],
                    event['title'], event.get('target', ''), event.get('app', ''),
                    event.get('detail', '')))
                count += cur.rowcount
        return count

    def extend_session(self, key, ended, duration):
        with self.connect() as db:
            db.execute('UPDATE events SET ended=?,duration=? WHERE event_key=?', (ended, duration, key))

    def annotate(self, ident, note=None, pinned=None, revision=None):
        with self.connect() as db:
            if note is not None:
                revision = time.time_ns() if revision is None else revision
                db.execute('UPDATE events SET note=?,note_revision=? WHERE id=? AND note_revision<=?',
                           (note, revision, ident, revision))
            if pinned is not None:
                db.execute('UPDATE events SET pinned=? WHERE id=?', (int(pinned), ident))

    def query(self, text='', kind='ALL', source='ALL', since=0, pinned=False, offset=0, limit=100, connection=None):
        clauses, args = ['e.occurred>=?'], [since]
        terms = text.split()
        if terms and self.fts and all(len(term) >= 3 for term in terms):
            expression = ' AND '.join('"' + term.replace('"', '""') + '"' for term in terms)
            clauses.append('e.id IN (SELECT rowid FROM search_index WHERE search_index MATCH ?)')
            args.append(expression)
        else:
            for term in terms:
                clauses.append("(e.title||' '||e.target||' '||e.app||' '||e.detail||' '||e.note) LIKE ? ESCAPE '\\'")
                args.append('%' + term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%')
        if kind != 'ALL':
            clauses.append('e.kind=?'); args.append(kind)
        if source != 'ALL':
            clauses.append('e.source=?'); args.append(source)
        if pinned:
            clauses.append('e.pinned=1')
        where = ' AND '.join(clauses)
        with (nullcontext(connection) if connection is not None else self.connect()) as db:
            count = db.execute('SELECT COUNT(*) FROM events e WHERE ' + where, args).fetchone()[0]
            rows = db.execute('SELECT e.* FROM events e WHERE ' + where +
                              ' ORDER BY e.occurred DESC,e.id DESC LIMIT ? OFFSET ?',
                              args + [limit, offset]).fetchall()
        return [dict(row) for row in rows], count

    def summary(self, today):
        with self.connect() as db:
            row = db.execute('''SELECT COUNT(*) total,
                COALESCE(SUM(occurred>=?),0) today,
                COALESCE(SUM(kind IN ('WEB','VIDEO')),0) web,
                COALESCE(SUM(CASE WHEN kind='APP' AND occurred>=? THEN duration ELSE 0 END),0) focus
                FROM events''', (today, today)).fetchone()
            sources = [r[0] for r in db.execute('SELECT DISTINCT source FROM events ORDER BY source')]
        return dict(row), sources

    def export(self, filename, filters, cancel):
        """Stream every matching row, including notes and bookmarks, off the UI thread."""
        target = Path(filename)
        temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.part')
        offset = total = 0
        try:
            with self.connect() as snapshot, temporary.open('w', encoding='utf-8', newline='') as output:
                # A WAL snapshot keeps pagination stable even as live capture appends.
                snapshot.execute('BEGIN')
                writer = None
                if target.suffix.lower() == '.json':
                    output.write('[\n')
                while not cancel.is_set():
                    rows, _ = self.query(**filters, offset=offset, limit=1000, connection=snapshot)
                    if not rows:
                        break
                    if target.suffix.lower() == '.json':
                        for row in rows:
                            if total:
                                output.write(',\n')
                            output.write(json.dumps(row, ensure_ascii=False))
                            total += 1
                    else:
                        if writer is None:
                            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
                            writer.writeheader()
                        for row in rows:
                            # Spreadsheet-safe text: do not interpret titles or URLs as formulas.
                            safe = {k: ("'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v)
                                    for k, v in row.items()}
                            writer.writerow(safe)
                        total += len(rows)
                    offset += len(rows)
                if target.suffix.lower() == '.json':
                    output.write('\n]\n')
            if cancel.is_set():
                return 0
            temporary.replace(target)
            return total
        finally:
            temporary.unlink(missing_ok=True)


class SessionRecorder:
    """Coalesce unchanged foreground windows; never count idle or paused intervals."""
    def __init__(self, store):
        self.store = store
        self.current = None
        self.key = None
        self.last = None
        self.duration = 0

    def sample(self, activity, now=None):
        now = time.time() if now is None else now
        identity = (activity['app'], activity['title'], activity.get('target', '')) if activity else None
        if identity is None:
            self.current = self.key = self.last = None
            return
        if identity == self.current and self.last is not None and 0 <= now - self.last <= 10:
            self.duration += now - self.last
            self.store.extend_session(self.key, now, self.duration)
        else:
            self.key = event_key('foreground', now, identity)
            self.duration = 0
            self.store.append([dict(activity, event_key=self.key, occurred=now, ended=now,
                                    kind='APP', source='Live desktop')])
        self.current, self.last = identity, now
