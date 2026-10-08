"""Execution artwork, creative galleries and dynamic template integration."""
import ast
import os
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).parent))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from creative_gallery import CreativePage,EXPERIENCES
from creative_templates import CREATIVE_TEMPLATES,CREATIVE_PLUGINS
from orchestration_ui import OrchestrationWindow
APP=QApplication.instance() or QApplication([])

class LoadoutPolishTests(unittest.TestCase):
    def test_creative_pages_render(self):
        for mode in EXPERIENCES:
            with self.subTest(mode=mode):
                page=CreativePage(mode);page.resize(720,500);page.show();APP.processEvents()
                self.assertFalse(page.grab().isNull());page.close();page.deleteLater()
    def test_template_instantiation(self):
        for title,code in CREATIVE_TEMPLATES.items():
            ast.parse(code)
            if title.startswith('GUI /'):
                with self.subTest(title=title):
                    scope={'__name__':'template_test'};exec(compile(code,title,'exec'),scope)
                    window=scope['MyWindow']();window.close();window.deleteLater()
        for title,code in CREATIVE_PLUGINS.items():ast.parse(code)
    def test_slot_asset_targets_and_navigation(self):
        theme=SimpleNamespace(**runpy.run_path(str(Path(__file__).with_name('orchestration-menu.py')),run_name='test_theme'))
        with tempfile.TemporaryDirectory() as root:
            window=OrchestrationWindow(theme,state_root=root)
            try:
                ident=window.projects[0]['id'];window.open_project_loadout(ident)
                screen=window.project_loadout_screen
                self.assertEqual(len(screen.cards),10)
                self.assertEqual(screen.cards['primary_target'].item_data.asset_key,'project:'+ident)
                self.assertEqual(screen.cards['context'].item_data.asset_key,'loadout:'+ident+':context')
                self.assertEqual(window.project_grid.itemAt(0).widget().contextMenuPolicy(),Qt.ContextMenuPolicy.CustomContextMenu)
                window.manage_project_assets(ident,'context')
                self.assertEqual(window.asset_name.currentData(),'loadout:'+ident+':context')
                self.assertNotIn('{',screen.cards['context'].item_data.name)
                self.assertTrue(screen.preview.canvas.paused)
            finally:
                window.code.document().setModified(False);window.close()
if __name__=='__main__':unittest.main()
