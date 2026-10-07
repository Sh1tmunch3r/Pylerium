import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from test_orchestration import APP
from runner_core import Store
from asset_helper import AssetLibrary
from workspace_inventory import WorkspaceInventory
from workshop_editor import WorkshopEditor
from editor_tools import transform_lines,FindDialog,check_syntax
from PyQt6.QtGui import QTextCursor


class WorkspacePolishTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=Store(self.root/'data')
        assets=self.root/'assets';assets.mkdir();(assets/'manifest.json').write_text('{"items":{}}')
        self.assets=AssetLibrary(assets);self.patch=patch('asset_helper.ASSETS',self.assets);self.patch.start()
        plugins=self.root/'plugins';plugins.mkdir()
        self.host=SimpleNamespace(store=self.store,runner=SimpleNamespace(jobs={},workflow=None),plugin_host=SimpleNamespace(root=plugins,enabled=lambda:[],descriptors=lambda:[]))
        self.inventory=WorkspaceInventory(self.host)
    def tearDown(self):self.patch.stop();self.store.db.close();self.temp.cleanup()

    def test_remove_project_cascades_and_restores_without_touching_external_sources(self):
        folder=self.store.root/'projects'/'one';folder.mkdir(parents=True);script=folder/'main.py';script.write_text('print(1)')
        self.store.put('project','one',{'id':'one','name':'one','script':str(script)})
        self.store.put('operator','op',{'id':'op','name':'Operator','project':'one'})
        self.store.put('workflow','flow',{'id':'flow','name':'Flow','nodes':[{'project':'one'}]})
        self.store.put('schedule','sched',{'id':'sched','name':'Schedule','workflow':'flow'})
        plan=self.inventory.plan({'kind':'project','id':'one','name':'one'})
        self.assertEqual(len(plan['documents']),4)
        self.inventory.remove({'kind':'project','id':'one','name':'one'})
        self.assertFalse(script.exists());self.assertEqual(self.store.list('project'),[])
        from orchestration_ui import OrchestrationWindow
        OrchestrationWindow.seed(SimpleNamespace(store=self.store))
        self.assertEqual(self.store.list('project'),[])
        self.inventory.restore_latest();self.assertTrue(script.exists());self.assertEqual(len(self.store.list('schedule')),1)
        external=self.root/'external';external.mkdir();source=external/'original.py';source.write_text('keep')
        self.store.put('project','external',{'id':'external','name':'External','script':str(source)})
        self.inventory.remove({'kind':'project','id':'external','name':'External'});self.assertTrue(source.exists())

    def test_asset_detach_is_persistent_and_restore_preserves_new_assignment(self):
        icons=self.assets.root/'icons';icons.mkdir();(icons/'old.png').write_bytes(b'old');(icons/'new.png').write_bytes(b'new')
        self.assets.set_item('tool',icon='icons/old.png')
        self.inventory.remove({'kind':'asset','id':'icons/old.png','name':'Old icon'})
        self.assertNotIn('icon',AssetLibrary(self.assets.root).entry('tool'))
        self.assets.set_item('tool',icon='icons/new.png');self.inventory.restore_latest()
        self.assertEqual(self.assets.entry('tool')['icon'],'icons/new.png');self.assertTrue((icons/'old.png').exists())

    def test_active_operation_blocks_removal_and_invalid_manifest_retains_assignments(self):
        self.store.set_shared('key',{'saved':True});self.host.runner.jobs={'running':{}}
        with self.assertRaises(ValueError):self.inventory.remove({'kind':'shared','id':'key','name':'key'})
        self.assertIn('key',self.store.shared())
        self.assets.save_manifest({'items':{'tool':{'rotation':[1,2,3]}}})
        (self.assets.root/'manifest.json').write_text('broken');self.assets.reload()
        self.assertEqual(self.assets.entry('tool')['rotation'],[1,2,3])

    def test_editor_tools_replace_all_single_undo_and_comment_roundtrip(self):
        editor=WorkshopEditor();editor.setPlainText('value = 1\nvalue = 2')
        dialog=FindDialog(editor);dialog.query.setText('value');dialog.replacement.setText('result');dialog.replace_all()
        self.assertEqual(editor.toPlainText(),'result = 1\nresult = 2');editor.undo()
        self.assertEqual(editor.toPlainText(),'value = 1\nvalue = 2')
        cursor=editor.textCursor();cursor.select(QTextCursor.SelectionType.Document);editor.setTextCursor(cursor)
        transform_lines(editor,'comment');self.assertTrue(editor.toPlainText().startswith('# value'))
        cursor=editor.textCursor();cursor.select(QTextCursor.SelectionType.Document);editor.setTextCursor(cursor)
        transform_lines(editor,'comment');self.assertEqual(check_syntax(editor),'Python syntax OK')
        dialog.close();editor.close()

    def test_element_insertion_uses_current_method_indentation(self):
        import ast
        from editor_focus import EditorCard
        from gui_templates import COMPONENT_TEMPLATES
        editor=WorkshopEditor();editor.setPlainText('class MyWindow:\n    def __init__(self):\n        pass')
        cursor=editor.textCursor();cursor.movePosition(QTextCursor.MoveOperation.End);editor.setTextCursor(cursor)
        card=EditorCard(editor,'fixture',lambda:None,templates=COMPONENT_TEMPLATES)
        card.template_picker.setCurrentText('GUI element / Buttons and panel');card.insert_template()
        tree=ast.parse(editor.toPlainText())
        self.assertGreater(len(tree.body[0].body[0].body),1)
        editor.undo();self.assertTrue(editor.toPlainText().endswith('pass'));card.close()

    def test_project_packaging_includes_sdk_runtime_and_companion_files(self):
        from build_exe import build_project
        source=self.root/'project';source.mkdir();(source/'main.py').write_text('from systematic_gui import AppWindow\nimport json\n')
        (source/'config.json').write_text('{"enabled":true}')
        commands=[]
        def runtime(path):path.mkdir()
        with patch('build_exe.prepare_runtime',side_effect=runtime),patch('build_exe.subprocess.run',side_effect=lambda command,**kw:commands.append(command)):
            build_project(source/'main.py',source/'dist','MyApp',hidden_imports=['my_dynamic_package'])
        command=commands[0]
        self.assertIn('--windowed',command);self.assertIn('my_dynamic_package',command)
        self.assertTrue(any(value.endswith(':runtime') for value in command))
        self.assertTrue(any(value.endswith(':sdk') and 'gui_components.py' in value for value in command))
        stage=next((source/'dist'/'.build').iterdir())
        self.assertTrue((stage/'project'/'config.json').exists())
        self.assertFalse((stage/'project'/'dist').exists())
        launcher=(stage/'launcher.py').read_text(encoding='utf-8')
        self.assertIn("home/'orchestration_data'",launcher)
        self.assertIn("os.chdir(working)",launcher)
