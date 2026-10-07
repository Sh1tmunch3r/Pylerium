import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from test_orchestration import APP,wait_until
from toolkit_core import execute,TOOLS
from toolkit_ui import ToolPage
from starter_catalog import STARTER_PLUGIN_IDS,ADVANCED_TEMPLATES
from systematic_gui import theme
from orchestration_ui import OrchestrationWindow


class ToolkitTests(unittest.TestCase):
    def test_structured_analysis(self):
        self.assertEqual(json.loads(execute('json_lab','{"a":[2]}'))['leaf_paths'],{'/a/0':2})
        csv=json.loads(execute('csv_profiler','name,score\na,10\nb,20\nc,\n'))
        self.assertEqual(csv['columns']['score']['mean'],15)
        self.assertEqual(csv['columns']['score']['missing'],1)
        matches=json.loads(execute('regex_lab','task-12',r'task-(\d+)'))['matches']
        self.assertEqual(matches[0]['groups'],['12'])
        self.assertIn('+after',execute('text_diff','before\n','after\n'))
        self.assertEqual(json.loads(execute('python_inspector','def f(x):\n return x'))['functions'][0]['name'],'f')
        self.assertEqual(json.loads(execute('log_analyzer','INFO hello\nERROR failed'))['severity'],{'INFO':1,'ERROR':1})
        self.assertEqual(json.loads(execute('codec_lab','aGVsbG8=','decode'))['base64_decoded'],'hello')
        self.assertIn('alpha',execute('markdown_report','[{"name":"alpha"}]','Report'))

    def test_file_tools_and_readonly_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'a.txt').write_text('same');(root/'b.txt').write_text('same');(root/'c.txt').write_text('different')
            result=json.loads(execute('duplicate_finder',directory))
            self.assertEqual(len(result['records']),1);self.assertEqual(result['records'][0]['recoverable_bytes'],4)
            digest=json.loads(execute('file_integrity',str(root/'a.txt')))['sha256']
            self.assertTrue(json.loads(execute('file_integrity',str(root/'b.txt'),digest))['expected_matches'])
            self.assertEqual(len(json.loads(execute('file_catalog',directory,'.txt'))['records']),3)
            path=root/'test.sqlite3'
            with sqlite3.connect(path) as db:db.execute('CREATE TABLE items(value)');db.execute('INSERT INTO items VALUES (42)')
            db.close()
            self.assertEqual(json.loads(execute('sqlite_explorer',str(path),'SELECT * FROM items'))['rows'],[[42]])
            with self.assertRaises(sqlite3.OperationalError):execute('sqlite_explorer',str(path),'DELETE FROM items')

    def test_process_page_results_errors_and_cancellation(self):
        page=ToolPage('json_lab');page.analyze()
        wait_until(lambda:page.start.isEnabled(),seconds=15)
        self.assertIn('leaf_paths',page.result)
        page.input.setPlainText('not json');page.analyze();wait_until(lambda:page.start.isEnabled(),seconds=15)
        self.assertIn('JSONDecodeError',page.result);page.shutdown()
        regex=ToolPage('regex_lab');regex.input.setPlainText('a'*30000+'!');regex.option.setText('(a+)+$');regex.analyze()
        wait_until(lambda:regex.process.processId()>0);regex.cancel();wait_until(lambda:regex.start.isEnabled())
        regex.shutdown()

    def test_every_plugin_registers_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as directory:
            window=OrchestrationWindow(theme(),state_root=Path(directory))
            baseline=len(window.page_ids)
            try:
                descriptors={d['id']:d for d in window.plugin_host.descriptors()}
                for ident in STARTER_PLUGIN_IDS:
                    with self.subTest(plugin=ident):
                        window.plugin_host.enable(descriptors[ident]);self.assertEqual(len(window.page_ids),baseline+1)
                        window.plugin_host.disable(ident);self.assertEqual(len(window.page_ids),baseline)
            finally:
                for ident in list(window.plugin_host.enabled()):window.plugin_host.disable(ident)
                window.code.document().setModified(False);window.plugin_builder.dirty=False;window.close();window.store.db.close()

    def test_advanced_projects_construct(self):
        for name,code in ADVANCED_TEMPLATES.items():
            with self.subTest(project=name):
                namespace={'__name__':'fixture'};exec(compile(code,name,'exec'),namespace)
                window=namespace['MyWindow']()
                self.assertEqual(len(window.pages),len(window.tool_pages)+5)
                window.show();APP.processEvents();window.close();APP.processEvents()
