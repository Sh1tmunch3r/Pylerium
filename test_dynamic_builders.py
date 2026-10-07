import json
import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from test_orchestration import APP,wait_until
from orchestration_ui import OrchestrationWindow
from workflow_builder import NodeDialog,repair_node_ids
from plugin_builder import TEMPLATES
from runner_core import validate_workflow


class BuilderTests(unittest.TestCase):
    def test_workshop_contains_visible_plugin_browser_and_preserves_editors(self):
        from PyQt6.QtCore import Qt
        w=self.w;w.show();w.navigate('PLUGINS');APP.processEvents()
        self.assertEqual(w.workshop_tabs.tabText(w.workshop_tabs.currentIndex()),'PLUGINS')
        self.assertNotIn('PLUGINS',w.nav)
        self.assertTrue(w.nav['WORKSHOP'].isChecked())
        self.assertTrue(w.plugin_search.isVisible());self.assertTrue(w.plugins_table.isVisible())
        self.assertTrue(w.plugin_builder.editor.isVisible())
        w.plugin_builder.editor.setPlainText('# retained plugin draft')
        w.navigate('WORKSHOP');APP.processEvents()
        self.assertEqual(w.workshop_tabs.currentIndex(),0)
        w.navigate('PLUGINS');APP.processEvents()
        self.assertEqual(w.plugin_builder.editor.toPlainText(),'# retained plugin draft')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        theme=SimpleNamespace(**runpy.run_path(str(Path(__file__).parent/'orchestration-menu.py')))
        self.w=OrchestrationWindow(theme,self.temp.name)
        self.w.plugin_host.root=Path(self.temp.name)/'plugins'
        self.w.sync_plugin_environment()

    def tearDown(self):
        self.w.plugin_builder.dirty=False
        self.w.code.document().setModified(False)
        self.w.runner.stop_all();wait_until(lambda:not self.w.runner.jobs)
        self.w.close();APP.processEvents();self.temp.cleanup()

    def test_node_selectors_and_duplicate_repair(self):
        w=self.w
        nodes=[{'id':'233','project':'hello','profile':'default','depends_on':[]} for _ in range(11)]
        nodes=repair_node_ids(nodes)
        self.assertEqual(len({n['id'] for n in nodes}),11)
        validate_workflow({'nodes':nodes},{'hello'})
        dialog=NodeDialog(w,nodes)
        self.assertEqual(dialog.project.currentData(),'hello')
        self.assertEqual(dialog.profile.currentData(),'default')
        self.assertNotIn(dialog.value()['id'],{n['id'] for n in nodes})
        w.workflow_json.setPlainText(json.dumps({'nodes':nodes}))
        self.assertEqual(w.node_table.item(0,1).text(),'Hello operations')

    def test_builder_save_reload_live_selector_and_script_command(self):
        w=self.w;b=w.plugin_builder
        b.template.setCurrentText('Project launcher');b.new_plugin()
        b.name.setText('Dynamic tools');b.editor.setPlainText(TEMPLATES['Project launcher']+"\ndef echo(value):\n    return value+' first'\n\nSCRIPT_COMMANDS={'echo':echo}\n")
        self.assertTrue(b.save(),b.status.text())
        self.assertEqual(w.plugin_host.enabled(),[])
        b.enable()
        self.assertIn('dynamic_tools',w.plugin_host.enabled(),b.status.text())
        ctx=w.plugin_host.contexts['dynamic_tools']
        self.assertEqual(ctx.selectors[0][1].currentData(),'hello')
        project=dict(w.projects[0],id='other',name='Another project')
        w.store.put('project','other',project);w.refresh_lists()
        self.assertEqual(ctx.selectors[0][1].count(),2)
        b.editor.setPlainText(b.editor.toPlainText().replace(' first',' second'))
        b.enable()
        self.assertEqual(w.plugin_host.modules['dynamic_tools'].SCRIPT_COMMANDS['echo']('ok'),'ok second')
        script=Path(self.temp.name)/'commands.py'
        script.write_text("from workspace_plugins import call\nprint(call('dynamic_tools','echo','ok'))\n")
        ident=w.runner.launch({'id':'cmd','name':'cmd','script':str(script),'cwd':self.temp.name,'args':[]},w.profiles[0])
        wait_until(lambda:not w.runner.jobs)
        status,log=w.store.db.execute('SELECT status,log FROM runs WHERE id=?',(ident,)).fetchone()
        self.assertEqual(status,'succeeded',log);self.assertIn('ok second',log)

    def test_assets_use_stable_project_ids(self):
        w=self.w
        self.assertGreaterEqual(w.asset_name.findData('project:hello'),0)
        self.assertFalse(w.asset_name.isEditable())
        w.lobby_project.setCurrentIndex(w.lobby_project.findData('hello'))
        w.select_project_preview()
        self.assertEqual(w.preview.canvas.item_data.asset_key,'project:hello')
        doc=w.store.get('project','hello');doc['name']='Renamed project';w.store.put('project','hello',doc)
        w.refresh_lists();w.select_project_preview()
        self.assertEqual(w.preview.canvas.item_data.asset_key,'project:hello')
        self.assertIn('Renamed project',w.asset_name.itemText(w.asset_name.findData('project:hello')))


if __name__=='__main__':unittest.main(verbosity=2)
