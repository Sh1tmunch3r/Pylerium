import tempfile,unittest
from pathlib import Path
from test_orchestration import APP
from status_marquee import StatusMarquee


class PyleriumTests(unittest.TestCase):
    def test_tags_reload_events_and_custom_terminal_styles(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'tags.txt';path.write_text('First tag\n\nSecond tag\nFirst tag\n')
            marquee=StatusMarquee(path);marquee.resize(600,25);marquee.show();APP.processEvents()
            try:
                self.assertEqual(marquee.tags,['First tag','Second tag'])
                path.write_text('Changed content\n');marquee.reload_tags();self.assertEqual(marquee.tags,['Changed content'])
                marquee.setText('PROJECT SAVED');self.assertEqual(marquee.text(),'PROJECT SAVED')
                marquee.configure({'marquee_speed':80},{'custom':{'foreground':'#ff00ff','bold':True}})
                self.assertEqual(marquee.terminal.get_style('custom').foreground.r,255)
                self.assertEqual(marquee.speed,80);self.assertIn('PROJECT SAVED',marquee.toolTip())
                marquee.grab()
                path.unlink();marquee.reload_tags();self.assertEqual(marquee.tags,[])
            finally:marquee.close()

    def test_new_sdk_keeps_existing_imports_compatible(self):
        import pylerium_gui,systematic_gui
        self.assertIs(pylerium_gui.AppWindow,systematic_gui.SystematicWindow)
        self.assertIs(pylerium_gui.button,systematic_gui.button)
