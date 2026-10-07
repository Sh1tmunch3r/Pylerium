import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QImage
from runner_core import Store
from killchain import Killchain, ClipboardArchive, search_history
from plugins.jumpback.history_store import HistoryStore


class KillchainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)

    def tearDown(self):self.temp.cleanup()

    def test_history_browser_file_note_and_literal_query(self):
        history=HistoryStore(self.root/'history.sqlite3')
        history.append([dict(event_key=str(i),occurred=i,kind=kind,source='Opera',title=title,target=target)
            for i,kind,title,target in [(1,'WEB','YouTube demo','https://youtube.com'),(2,'FILE','report','C:/report.txt')]])
        history.annotate(2,note='meeting notes')
        self.assertEqual(search_history(history.path,'youtube')[0]['source'],'Opera')
        self.assertEqual(search_history(history.path,'meeting')[0]['kind'],'FILE')
        self.assertEqual(search_history(history.path,"' OR 1=1"),[])
        self.assertEqual(search_history(self.root/'absent',''),[])

    def test_clipboard_retention_dedupe_restore_and_delete(self):
        path=self.root/'clipboard.sqlite3';archive=ClipboardArchive(path)
        archive.add('first');archive.add('first');self.assertEqual(len(archive.query()),1)
        archive.add('second',limit=1);self.assertEqual(archive.query()[0]['text'],'second')
        self.assertEqual(ClipboardArchive(path).query('SECOND')[0]['text'],'second')
        archive.remove();self.assertEqual(archive.query(),[])

    def test_overlay_commands_clipboard_pause_and_minimized_host(self):
        host=QWidget();host.store=Store(self.root);host.settings={'clipboard_capture':True}
        host.runner=SimpleNamespace(jobs={},max_parallel=2,launch=Mock(return_value='123456789'))
        host.notice=Mock();host.page_ids={'WORKSHOP':0};host.navigate=Mock()
        host.store.put('project','demo',{'id':'demo','name':'Demo tool','script':'demo.py'})
        host.store.put('profile','default',{'id':'default'})
        with patch.object(Killchain,'register_hotkey'):
            overlay=Killchain(host)
        try:
            host.showMinimized();overlay.toggle();self.assertTrue(overlay.isVisible());self.assertTrue(host.isMinimized())
            overlay.input.setText('run demo');overlay.refresh();overlay.execute();host.runner.launch.assert_called_once()
            overlay.input.setText('set sample {"value": 4}');overlay.refresh();overlay.execute()
            self.assertEqual(host.store.shared()['sample'],{'value':4})
            self.app.clipboard().setText('clip test');overlay.capture_clipboard()
            image=QImage(8,8,QImage.Format.Format_RGB32);image.fill(0xff123456)
            self.app.clipboard().setImage(image);overlay.capture_clipboard()
            self.assertTrue(any(c['image'] for c in overlay.archive.query()))
            overlay.input.setText('clip clip test');overlay.refresh();overlay.execute()
            self.assertEqual(self.app.clipboard().text(),'clip test')
            overlay.capture.setChecked(False);self.app.clipboard().setText('do not store');overlay.capture_clipboard()
            self.assertEqual(overlay.archive.query('do not store'),[])
            self.assertFalse(host.store.get('settings','app')['clipboard_capture'])
        finally:
            overlay.shutdown();overlay.deleteLater();host.store.db.close();host.close()


if __name__=='__main__':unittest.main()
