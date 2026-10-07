"""Instantiate every GUI starter and verify it shares real application components."""
import ast
import tempfile
import time
import unittest
from pathlib import Path

from test_orchestration import APP,wait_until
from gui_templates import GUI_TEMPLATES,COMPONENT_TEMPLATES
from textwrap import indent
from editor_templates import WORKSHOP_TEMPLATES
import gui_components
import systematic_gui as gui
import orchestration_ui


class GuiTemplatesTests(unittest.TestCase):
    def test_all_starters_construct_with_real_shared_styles_and_widgets(self):
        with tempfile.TemporaryDirectory() as directory:
            for name,code in GUI_TEMPLATES.items():
                with self.subTest(template=name):
                    ast.parse(code)
                    self.assertIn(name,WORKSHOP_TEMPLATES)
                    namespace={'__name__':'gui_fixture'}
                    # The full workspace keeps its own state; isolate the fixture.
                    code=code.replace("Path.cwd() / 'my_gui_data'",repr(directory))
                    exec(compile(code,name,'exec'),namespace)
                    window=namespace['MyWindow']()
                    self.assertEqual(window.styleSheet(),gui_components.STYLE)
                    self.assertNotIsInstance(window.background,gui.theme().BackgroundWidget)
                    self.assertNotIsInstance(window,orchestration_ui.OrchestrationWindow)
                    window.show(); APP.processEvents()
                    if hasattr(window,'code'):
                        window.code.document().setModified(False);window.plugin_builder.dirty=False
                    window.close(); APP.processEvents()
            self.assertIs(orchestration_ui.button,gui.button)
            self.assertIs(orchestration_ui.panel,gui.panel)
            self.assertIs(orchestration_ui.label,gui.label)

    def test_blank_application_has_only_selected_components(self):
        window=gui.AppWindow('My app')
        try:
            self.assertEqual(window.content.count(),0)
            self.assertIsNone(window.stack)
            self.assertIsNone(window.toolbar)
            self.assertIsNone(window.file_menu)
            self.assertFalse(window.pages)
            self.assertFalse(hasattr(window,'plugin_builder'))
            self.assertFalse(hasattr(window,'store'))
            self.assertNotIn('GUI / Full operations workspace',WORKSHOP_TEMPLATES)
        finally:window.close()

    def test_component_snippets_compose_in_independent_windows(self):
        for name,code in COMPONENT_TEMPLATES.items():
            with self.subTest(component=name):
                self.assertIn(name,WORKSHOP_TEMPLATES)
                namespace={'AppWindow':gui.AppWindow}
                source="class MyWindow(AppWindow):\n    def __init__(self):\n        super().__init__('My app')\n"+indent(code,'        ')
                exec(compile(source,name,'exec'),namespace)
                window=namespace['MyWindow']()
                try:
                    self.assertGreater(window.content.count()+len(window.findChildren(gui.QToolBar)),0)
                    self.assertFalse(hasattr(window,'plugin_host'))
                finally:window.close();APP.processEvents()

    def test_background_gui_task_delivers_on_application_thread(self):
        from PyQt6.QtCore import QThread
        window=gui.SystematicWindow(motion=False)
        result=[]
        window.run_background(lambda:(time.sleep(.05),'complete')[1],
                              lambda value:result.append((value,QThread.currentThread())))
        wait_until(lambda:bool(result))
        self.assertEqual(result[0][0],'complete')
        self.assertEqual(result[0][1],APP.thread())
        window.close()
