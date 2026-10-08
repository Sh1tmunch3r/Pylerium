"""Regression coverage for perk execution and nested-dialog card deletion."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).parent))
from PyQt6.QtCore import Qt,QPointF
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication
from PyQt6 import sip
from project_loadout import default_loadout, validate_loadout, LETHALS
from project_loadout_ui import template
import loadout_runtime
APP=QApplication.instance() or QApplication([])

class ExecutionPerkTests(unittest.TestCase):
    def test_legacy_build_hook_runs_payload_without_building(self):
        self.assertNotIn('pyinstaller',LETHALS)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);script=root/'payload.py';script.write_text('print("PROJECT_ONLY")')
            config=default_loadout({'id':'test','script':str(script)})
            config['lethal_hook']='pyinstaller'
            self.assertEqual(validate_loadout(config)['lethal_hook'],'none')
            result=subprocess.run([sys.executable,str(Path(loadout_runtime.__file__).resolve()),str(script)],cwd=folder,
                env=dict(os.environ,PYLERIUM_EXECUTION_LOADOUT=json.dumps(config)),capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr);self.assertIn('PROJECT_ONLY',result.stdout)
            self.assertEqual(sorted(p.name for p in root.iterdir()),['payload.py'])

    def test_hidden_hardline_repeat_still_runs_payload_and_preserves_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);script=root/'payload.py'
            script.write_text('import os,sys\nfrom pathlib import Path\np=Path("executions.txt")\np.write_text(p.read_text()+"run\\n" if p.exists() else "run\\n")\nprint("PAYLOAD",sys.argv[1:],flush=True)\nsys.exit(int(os.environ.get("TEST_EXIT","0")))\n')
            project={'id':'test','script':str(script),'args':[]}
            config=default_loadout(project);config['policy_slots']['perk2']=['ninja'];config['perks']=['hardline','scavenger'];config['wildcard']='repeat';config['passes']=2
            env=dict(os.environ,PYLERIUM_EXECUTION_LOADOUT=json.dumps(config))
            command=[sys.executable,str(Path(loadout_runtime.__file__).resolve()),str(script),'--test']
            result=subprocess.run(command,cwd=folder,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.count('PAYLOAD'),2)
            self.assertEqual((root/'executions.txt').read_text(),'run\nrun\n')
            env['TEST_EXIT']='7';result=subprocess.run(command,cwd=folder,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,7);self.assertIn('PAYLOAD',result.stdout)
    def test_ghost_executes_project_with_absolute_interpreter_path(self):
        with tempfile.TemporaryDirectory() as folder:
            script=Path(folder)/'payload.py';script.write_text('import sys;from PyQt6 import QtCore;print("GHOST_PAYLOAD",sys.prefix)')
            config=default_loadout({'id':'test','script':str(script)});config['perks']=['ghost']
            result=subprocess.run([sys.executable,str(Path(loadout_runtime.__file__).resolve()),str(script)],cwd=folder,
                env=dict(os.environ,PYLERIUM_EXECUTION_LOADOUT=json.dumps(config)),capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stderr);self.assertIn('GHOST_PAYLOAD',result.stdout)
            self.assertIn(str(Path(folder)/'.venv'),result.stdout)
    @unittest.skipUnless(os.name=='nt','Windows elevation bridge')
    def test_elevation_waits_and_propagates_project_exit(self):
        calls=[]
        class Process:
            returncode=9
            def poll(self): return self.returncode
        def launch(command,**kwargs):
            calls.append(command)
            # Inspect the generated launcher while the temporary directory exists.
            import re
            source=command[-1]
            self.assertIn('-Wait -PassThru',source);self.assertIn('exit $child.ExitCode',source)
            arg=source.split(' -ArgumentList ',1)[1].split(' -WorkingDirectory ',1)[0]
            path=arg.strip("'")[3:].strip('"')
            bootstrap=Path(path).read_text(encoding='utf-8')
            compile(bootstrap,path,'exec')
            self.assertIn('child.wait()',bootstrap);self.assertIn('stderr=subprocess.STDOUT',bootstrap)
            self.assertIn('payload.py',bootstrap);self.assertIn('taskkill',bootstrap)
            return Process()
        with patch.object(loadout_runtime.subprocess,'Popen',side_effect=launch):
            self.assertEqual(loadout_runtime.elevated_launch({'perks':[]},'payload.py',['--test']),9)
        self.assertEqual(len(calls),1)
    def test_card_callback_can_delete_card(self):
        theme=template();card=theme.LoadoutCard(theme.LoadoutItem('test','PRIMARY'),'primary')
        card.clicked.connect(lambda ignored:sip.delete(card))
        event=QMouseEvent(QMouseEvent.Type.MouseButtonPress,QPointF(10,10),QPointF(10,10),Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        card.mousePressEvent(event)
        self.assertTrue(sip.isdeleted(card))

if __name__=='__main__':unittest.main()
