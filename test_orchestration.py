"""Run with a Python interpreter that has PyQt6 installed (no visible window)."""
import json
import os
import runpy
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, str(Path(__file__).parent))
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication
from asset_helper import ASSETS, AssetLibrary
from orchestration_ui import OrchestrationWindow
from runner_core import Runner, Store, validate_workflow

APP = QApplication.instance() or QApplication([])
if not QFontDatabase.families():
    for filename in ('arial.ttf','consola.ttf'):
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+filename)


def wait_until(predicate, seconds=8):
    deadline = time.monotonic()+seconds
    while not predicate() and time.monotonic() < deadline:
        APP.processEvents()
        time.sleep(0.01)
    APP.processEvents()
    if not predicate():
        raise AssertionError('Timed out waiting for condition')


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.runner = Runner(self.store)
        self.profile = {'id':'default','python':sys.executable,'timeout':5,'env':{}}
        self.windows = []

    def tearDown(self):
        for window in self.windows:
            window.code.document().setModified(False)
            window.runner.stop_all()
            wait_until(lambda:not window.runner.jobs)
            window.close()
        self.runner.stop_all()
        wait_until(lambda:not self.runner.jobs)
        self.store.db.close()
        self.temp.cleanup()

    def project(self, name, code):
        script = self.root / (name+'.py')
        script.write_text(code,encoding='utf-8')
        return {'id':name,'name':name,'script':str(script),'cwd':str(self.root),'args':[]}

    def test_shared_parallel_and_logs(self):
        code = "from shared_loadout import update\nfor i in range(100): update('count', lambda old: (old or 0)+1)\nprint('finished ✓')\n"
        for name in ('one','two'):
            self.runner.launch(self.project(name,code),self.profile)
        wait_until(lambda:not self.runner.jobs)
        self.assertEqual(self.store.shared()['count'],200)
        self.assertTrue(all(row[2]=='succeeded' for row in self.store.history()))
        self.assertTrue(all('finished' in row[0] for row in self.store.db.execute('SELECT log FROM runs')))

    def test_workflow_order_and_failure_propagation(self):
        a = self.project('a',"from shared_loadout import set_value\nset_value('ready', True)\n")
        b = self.project('b',"from shared_loadout import get\nassert get('ready') is True\n")
        c = self.project('c','raise RuntimeError("expected")\n')
        wf = {'name':'ordered','nodes':[{'id':'a','project':'a'},
            {'id':'b','project':'b','depends_on':['a']},
            {'id':'c','project':'c','depends_on':['b']},
            {'id':'skip','project':'b','depends_on':['c']}]}
        self.runner.start_workflow(wf,{'a':a,'b':b,'c':c},{'default':self.profile},{})
        wait_until(lambda:self.runner.workflow is None)
        result = self.store.list('workflow_result')[0]
        self.assertEqual([n['status'] for n in result['nodes']],['succeeded','succeeded','failed','skipped'])

    def test_timeout_and_cancel(self):
        slow = self.project('slow','import time\nprint("started",flush=True)\ntime.sleep(30)\n')
        profile = dict(self.profile,timeout=1)
        self.runner.launch(slow,profile)
        wait_until(lambda:not self.runner.jobs)
        self.assertEqual(self.store.history()[0][2],'timed out')
        ident = self.runner.launch(slow,self.profile)
        wait_until(lambda:self.runner.jobs[ident]['status']=='running')
        self.runner.stop_all()
        wait_until(lambda:not self.runner.jobs)
        self.assertEqual(self.store.history()[0][2],'cancelled')

    def test_invalid_graph(self):
        with self.assertRaises(ValueError):
            validate_workflow({'nodes':[{'id':'a','project':'p','depends_on':['b']},
                {'id':'b','project':'p','depends_on':['a']}]},{'p'})
        with self.assertRaises(ValueError):
            validate_workflow({'nodes':[{'id':'a','project':'missing'}]},{'p'})

    def test_assets_and_ui(self):
        # User manifests are editable; the regression must own its asset fixture.
        from PyQt6.QtGui import QImage,QColor
        assets=self.root/'fixture_assets';assets.mkdir()
        (assets/'mesh.obj').write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
        image=QImage(32,32,QImage.Format.Format_RGB32);image.fill(QColor('cyan'));image.save(str(assets/'icon.png'))
        (assets/'manifest.json').write_text(json.dumps({'items':{'XM4':{'model':'mesh.obj','icon':'icon.png'}}}))
        library=AssetLibrary(assets)
        self.assertTrue(library.model('XM4'))
        self.assertFalse(library.image(library.entry('XM4')['icon']).isNull())
        self.assertFalse(library.icon('XM4',QSize(120,80),2).isNull())
        self.assertIsNone(library.path('../runner_core.py'))
        theme = SimpleNamespace(**runpy.run_path(str(Path(__file__).parent/'orchestration-menu.py')))
        window = OrchestrationWindow(theme,self.root/'ui')
        self.windows.append(window)
        window.show()
        APP.processEvents()
        for name in window.nav:
            window.navigate(name)
            APP.processEvents()
            self.assertFalse(window.grab().isNull())
        self.assertFalse(window.settings['ai_enabled'])
        self.assertEqual(window.stack.count(),11)
        self.assertEqual(window.preview.canvas.item_data.name,window.projects[0]['name'])
        window.runner.launch(window.projects[0],window.profiles[0])
        wait_until(lambda:not window.runner.jobs)
        self.assertEqual(window.store.shared()['runs_completed'],1)
        # Scheduler deploys deterministic maps and stop-all disables automation.
        window.store.put('schedule','test',{'id':'test','name':'mission','workflow':'demo',
            'interval':60,'enabled':True,'next_due':time.time()-1})
        window.tick_schedules()
        wait_until(lambda:window.runner.workflow is None)
        self.assertEqual(window.store.shared()['runs_completed'],3)
        window.stop_operations()
        self.assertFalse(window.store.get('schedule','test')['enabled'])
        # Bundles remap references instead of overwriting existing project IDs.
        archive_path = self.root/'bundle.zip'
        window.write_bundle(archive_path)
        window.read_bundle(archive_path)
        self.assertEqual(len(window.projects),2)
        imported = next(w for w in window.workflows if w['id'] != 'demo')
        window.runner.start_workflow(imported,{p['id']:p for p in window.projects},
            {p['id']:p for p in window.profiles},{p['id']:p for p in window.operators})
        wait_until(lambda:window.runner.workflow is None)
        self.assertEqual(window.store.shared()['runs_completed'],5)
        window.code.document().setModified(False)
        window.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
