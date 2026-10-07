"""Real SQLite fixtures: full imports, WAL reads, archive search, sessions and exports."""
import csv
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from threading import Event
from unittest.mock import patch

from plugins.jumpback.collectors import (CHROME_EPOCH, browser_sources, import_browser,
                                         collect_history, browser_connection, file_digest)
from plugins.jumpback.history_store import HistoryStore, SessionRecorder


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = HistoryStore(self.root / 'archive.sqlite3')
        self.cancel = Event()

    def tearDown(self):
        self.temp.cleanup()

    def browser(self, count=1205):
        path = self.root / 'Opera Stable' / 'History'
        path.parent.mkdir(exist_ok=True)
        db = sqlite3.connect(path)
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('CREATE TABLE urls(id INTEGER PRIMARY KEY,url TEXT,title TEXT);'
                         'CREATE TABLE visits(id INTEGER PRIMARY KEY,url INTEGER,visit_time INTEGER);')
        db.execute('INSERT INTO urls VALUES(1,?,?)', ('https://www.youtube.com/watch?v=fish', 'Fishing tutorials'))
        db.executemany('INSERT INTO visits VALUES(?,1,?)',
                       [(i, int((CHROME_EPOCH + 1000 + i) * 1_000_000)) for i in range(1, count + 1)])
        db.commit()
        return path, db

    def test_full_browser_import_wal_dedup_incremental_and_preservation(self):
        path, db = self.browser()
        try:
            source = ('Opera / Default', path, 'chromium')
            added, seen = import_browser(self.store, source, self.cancel, [])
            self.assertEqual((added, seen), (1205, 1205))
            rows, total = self.store.query(text='tutorials', kind='VIDEO', limit=2000)
            self.assertEqual(total, 1205)
            self.assertEqual(rows[-1]['occurred'], 1001)
            self.store.annotate(rows[0]['id'], note='Return to this fishing idea', pinned=True)
            self.assertEqual(import_browser(self.store, source, self.cancel, [])[0], 0)
            self.assertEqual(self.store.query(text='fishing idea', pinned=True)[1], 1)
            db.execute('INSERT INTO visits VALUES(1206,1,?)', (int((CHROME_EPOCH + 2206) * 1_000_000),))
            db.commit()
            self.assertEqual(import_browser(self.store, source, self.cancel, [])[0], 1)
            self.assertEqual(self.store.query()[1], 1206)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM visits').fetchone()[0], 1206)
            # Reopening the archive must retain notes, visits, pins and its search index.
            reopened = HistoryStore(self.store.path)
            self.assertEqual(reopened.query(text='fishing idea', pinned=True)[1], 1)
        finally:
            db.close()

    def test_firefox_exclusions_cancel_and_visible_errors(self):
        path = self.root / 'places.sqlite'
        with closing(sqlite3.connect(path)) as db, db:
            db.executescript('CREATE TABLE moz_places(id INTEGER,url TEXT,title TEXT);'
                            'CREATE TABLE moz_historyvisits(id INTEGER,place_id INTEGER,visit_date INTEGER);'
                            "INSERT INTO moz_places VALUES(1,'https://example.com/secret','Hidden');"
                            'INSERT INTO moz_historyvisits VALUES(1,1,1234000000);')
        source = ('Firefox / Test', path, 'firefox')
        self.assertEqual(import_browser(self.store, source, self.cancel, ['example.com'])[0], 0)
        self.assertEqual(self.store.query()[1], 0)
        self.store.set('cursor:' + str(path.resolve()), 0)
        self.assertEqual(import_browser(self.store, source, self.cancel, [])[0], 1)
        self.assertEqual(self.store.query()[0][0]['occurred'], 1234)
        self.cancel.set()
        self.assertEqual(import_browser(self.store, source, self.cancel, [])[0], 0)
        self.cancel.clear()
        with patch('plugins.jumpback.collectors.browser_sources', return_value=[('Broken', self.root/'missing', 'chromium')]):
            report = collect_history(self.store, self.cancel, lambda **kw: [])
        self.assertEqual(report['sources'][0]['status'], 'Retry needed')

    def test_locked_opera_snapshot_includes_wal_and_leaves_original_untouched(self):
        path, writer = self.browser(count=5)
        try:
            writer.execute('PRAGMA locking_mode=EXCLUSIVE')
            writer.execute('BEGIN EXCLUSIVE')
            # This visit is not committed; the copied WAL must not import it.
            writer.execute('INSERT INTO visits VALUES(6,1,?)', (int((CHROME_EPOCH+1006)*1_000_000),))
            originals = [file for file in path.parent.glob('History*') if not file.name.endswith('-shm')]
            before = {file.name: file_digest(file) for file in originals}
            with browser_connection(path, self.cancel) as snapshot:
                copied_path = Path(snapshot.execute('PRAGMA database_list').fetchone()[2])
                self.assertNotEqual(copied_path, path)
                self.assertEqual(snapshot.execute('SELECT COUNT(*) FROM visits').fetchone()[0], 5)
            self.assertFalse(copied_path.exists())
            self.assertEqual(import_browser(self.store, ('Opera GX',path,'chromium'),self.cancel,[])[0], 5)
            self.assertEqual({file.name:file_digest(file) for file in originals}, before)
        finally:
            writer.close()

    def test_sessions_do_not_count_idle_paused_or_missing_intervals(self):
        recorder = SessionRecorder(self.store)
        activity = dict(title='A video - Opera', app='opera.exe', target='C:/opera.exe')
        recorder.sample(activity, 100)
        recorder.sample(activity, 102)
        recorder.sample(activity, 104)
        recorder.sample(None, 106)
        recorder.sample(activity, 1000)
        recorder.sample(activity, 1002)
        recorder.sample(activity, 1100)
        rows, count = self.store.query()
        self.assertEqual(count, 3)
        self.assertEqual(sorted(r['duration'] for r in rows), [0, 2, 4])

    def test_paused_browser_visits_are_not_imported_after_resume(self):
        path, db = self.browser(count=5)
        try:
            self.store.set('pause_intervals', [[1002, 1004]])
            import_browser(self.store, ('Opera', path, 'chromium'), self.cancel, [])
            rows, count = self.store.query()
            self.assertEqual(count, 2)
            self.assertEqual([row['occurred'] for row in rows], [1005, 1001])
        finally:
            db.close()

    def test_search_pagination_short_terms_literal_symbols_and_ordered_notes(self):
        self.store.append([dict(event_key=str(i), occurred=i, kind='DOC', source='Windows recent',
                                title='file 100%_test notes' if i==150 else f'item {i}', target=f'C:/item{i}')
                           for i in range(250)])
        self.assertEqual(self.store.query(offset=100)[0][0]['occurred'], 149)
        self.assertEqual(self.store.query(text='100%_test')[1], 1)
        self.assertEqual(self.store.query(text='%_')[1], 1)
        ident = self.store.query(text='100%_test')[0][0]['id']
        self.store.annotate(ident, note='new value', revision=20)
        self.store.annotate(ident, note='stale value', revision=10)
        self.assertEqual(self.store.query(text='new value')[1], 1)
        self.assertEqual(self.store.query(text='stale value')[1], 0)
        self.store.fts = False
        self.assertEqual(self.store.query(text='100%_test')[1], 1)

    def test_full_snapshot_export_with_concurrent_append_and_cancel(self):
        self.store.append([dict(event_key=str(i), occurred=i, kind='WEB', source='Opera',
                                title='=Spreadsheet formula' if i==0 else f'Title {i}') for i in range(1205)])
        original = self.store.query
        called = []
        def query_and_append(**kw):
            result = original(**kw)
            if not called:
                called.append(True)
                self.store.append([dict(event_key='later', occurred=99999, kind='WEB', source='Opera', title='Later')])
            return result
        path = self.root / 'export.json'
        with patch.object(self.store, 'query', side_effect=query_and_append):
            self.assertEqual(self.store.export(path, {}, self.cancel), 1205)
        exported = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(len({row['event_key'] for row in exported}), 1205)
        self.assertNotIn('later', {row['event_key'] for row in exported})
        csv_path = self.root / 'export.csv'
        self.store.export(csv_path, {}, self.cancel)
        with csv_path.open(encoding='utf-8', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[-1]['title'], "'=Spreadsheet formula")
        self.cancel.set()
        self.assertEqual(self.store.export(path, {}, self.cancel), 0)
        self.assertEqual(len(json.loads(path.read_text(encoding='utf-8'))), 1205)
        self.assertEqual(list(self.root.glob('*.part')), [])

    def test_opera_gx_default_profile_and_custom_source_discovery(self):
        root = self.root / 'Opera Software' / 'Opera GX Stable'
        root.mkdir(parents=True)
        (root / 'History').touch()
        profile = root / 'Default'; profile.mkdir(); (profile / 'History').touch()
        with patch.dict(os.environ, APPDATA=str(self.root), LOCALAPPDATA=str(self.root/'local')):
            sources = browser_sources([str(self.root/'custom'/'History')])
        self.assertEqual(len(sources), 3)
        self.assertTrue(any('Opera GX' in source[0] for source in sources))

    def test_cancelled_recent_scan_keeps_committed_batches_without_advancing_cursor(self):
        items = [dict(shortcut_path=f'C:/Recent/{i}.lnk', mtime=100+i, category='DOC',
                      name=f'File {i}', target_path=f'C:/Files/{i}.txt', category_label='Document')
                 for i in range(20)]
        def partial_scan(**kwargs):
            kwargs['on_batch'](items)
            kwargs['cancel'].set()
            return []
        with patch('plugins.jumpback.collectors.browser_sources', return_value=[]):
            collect_history(self.store, self.cancel, partial_scan)
        self.assertEqual(self.store.query()[1], 20)
        self.assertIsNone(self.store.get('recent_cursor'))
        self.cancel.clear()
        with patch('plugins.jumpback.collectors.browser_sources', return_value=[]):
            collect_history(self.store, self.cancel, lambda **kwargs: items)
        self.assertEqual(self.store.query()[1], 20)
        self.assertEqual(self.store.get('recent_cursor'), 119)


if __name__ == '__main__':
    unittest.main()
