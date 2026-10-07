"""Regression checks for recent-file scans during plugin creation and reload."""
import os
import shutil
import time
import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMessageBox
from plugins.jumpback import scanner
from plugin_system import load_module
import test_dynamic_builders as builders
from test_orchestration import APP, wait_until


class JumpbackTests(unittest.TestCase):
    setUp = builders.BuilderTests.setUp
    tearDown = builders.BuilderTests.tearDown

    def test_create_overwrite_reload_while_scan_is_running(self):
        root = self.w.plugin_host.root
        root.mkdir()
        folder = root / 'jumpback'
        shutil.copytree(Path(__file__).parent / 'plugins' / 'jumpback', folder,
                        ignore=shutil.ignore_patterns('__pycache__'))
        descriptor = self.w.plugin_host.descriptors()[0]
        pages = []

        def load_with_slow_scan(desc):
            module = load_module(desc)

            def scan(**kwargs):
                kwargs['cancel'].wait(2)
                return {'imported': 0, 'sources': []}

            module.collect_history = lambda store, cancel, scanner: scan(cancel=cancel)
            module.ForegroundReader = lambda: SimpleNamespace(read=lambda: None)
            return module

        with patch('plugin_system.load_module', side_effect=load_with_slow_scan):
            start = time.monotonic()
            self.w.plugin_host.enable(descriptor)
            self.assertLess(time.monotonic() - start, 1.5)
            pages.append(self.w.plugin_host.modules['jumpback']._active_page)
            heartbeat = []
            QTimer.singleShot(0, lambda: heartbeat.append(True))
            wait_until(lambda: bool(heartbeat))
            builder = self.w.plugin_builder
            self.assertTrue(builder.load(descriptor))
            builder.editor.insertPlainText('# edited\n')
            builder.enable()
            self.assertIn('jumpback', self.w.plugin_host.enabled(), builder.status.text())
            self.assertTrue(pages[-1].scan_cancel.is_set())
            pages.append(self.w.plugin_host.modules['jumpback']._active_page)
            builder.dirty = False
            builder.new_plugin()
            builder.ident.setText('jumpback')
            builder.name.setText('Redeploy replacement')
            builder.editor.setPlainText((folder / 'plugin.py').read_text(encoding='utf-8'))
            with patch('plugin_builder.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
                builder.enable()
            self.assertIn('jumpback', self.w.plugin_host.enabled(), builder.status.text())
            self.assertTrue(pages[-1].scan_cancel.is_set())
            page = self.w.plugin_host.modules['jumpback']._active_page
            page.set_filter('SRC')
            wait_until(lambda: page.scan_task is None)
            wait_until(lambda: page.query_task is None)
            self.assertEqual(page.table.rowCount(), 0)
            self.w.plugin_host.disable('jumpback')
            self.assertTrue(page.scan_cancel.is_set())
            APP.processEvents()

    def test_archive_ui_search_notes_pin_pause_and_reload_persistence(self):
        root = self.w.plugin_host.root
        root.mkdir()
        shutil.copytree(Path(__file__).parent/'plugins'/'jumpback', root/'jumpback',
                        ignore=shutil.ignore_patterns('__pycache__'))
        descriptor = self.w.plugin_host.descriptors()[0]
        def offline_load(desc):
            module = load_module(desc)
            module.collect_history = lambda *args: {'imported': 0, 'sources': []}
            module.ForegroundReader = lambda: SimpleNamespace(read=lambda: None)
            return module
        with patch('plugin_system.load_module', side_effect=offline_load):
            self.w.plugin_host.enable(descriptor)
            page = self.w.plugin_host.modules['jumpback']._active_page
            wait_until(lambda: page.query_task is None and page.scan_task is None)
            page.store.append([dict(event_key='youtube-visit', occurred=time.time(), kind='VIDEO',
                                    source='Opera GX / Default', title='Fishing video',
                                    target='https://youtube.com/watch?v=123')])
            page.request_query(); wait_until(lambda: page.query_task is None)
            page.table.selectRow(0)
            self.assertEqual(page.selected['title'], 'Fishing video')
            page.note.setPlainText('Try this rig tomorrow')
            page.save_note(); page.toggle_pin()
            wait_until(lambda: not page.tasks)
            self.assertEqual(page.store.query(text='rig tomorrow', pinned=True)[1], 1)
            page.search.setText('does not exist')
            wait_until(lambda: page.query_task is None and not page.search_timer.isActive())
            self.assertEqual(page.table.rowCount(), 0)
            page.search.setText('fishing')
            wait_until(lambda: page.query_task is None and not page.search_timer.isActive())
            self.assertEqual(page.table.rowCount(), 1)
            page.toggle_recording()
            self.assertFalse(page.recording)
            self.assertTrue(page.import_cancel.is_set())
            self.w.plugin_host.disable('jumpback')
            self.w.plugin_host.enable(descriptor)
            page = self.w.plugin_host.modules['jumpback']._active_page
            self.assertFalse(page.recording)
            self.assertIsNone(page.scan_task)
            wait_until(lambda: page.query_task is None)
            self.assertEqual(page.total, 1)
            self.assertEqual(page.store.query(text='rig tomorrow', pinned=True)[1], 1)
            page.table.selectRow(0)
            page.note.setPlainText('Unsaved note retained on unload')
            self.w.plugin_host.disable('jumpback')
            self.assertEqual(page.store.query(text='retained on unload')[1], 1)

    def test_scanner_resolves_only_newest_required_items(self):
        recent = Path(self.temp.name) / 'Microsoft' / 'Windows' / 'Recent'
        recent.mkdir(parents=True)
        for index in range(5):
            path = recent / f'item{index}.url'
            path.write_text('URL=steam://run/123\n')
            os.utime(path, (100 + index, 100 + index))
        with patch.dict(os.environ, APPDATA=self.temp.name), patch.object(
                scanner, 'resolve_shortcut', wraps=scanner.resolve_shortcut) as resolve:
            items = scanner.get_recent_items(limit=2)
            self.assertEqual([item['name'] for item in items], ['item4', 'item3'])
            self.assertEqual(resolve.call_count, 2)
            cancel = Event()
            cancel.set()
            self.assertEqual(scanner.get_recent_items(cancel=cancel), [])
            self.assertEqual(resolve.call_count, 2)
