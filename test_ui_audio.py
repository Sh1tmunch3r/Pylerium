import ast
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock
from PyQt6.QtWidgets import QApplication,QPushButton
from PyQt6.QtCore import QEvent
from ui_audio import UIAudio
from status_marquee import StatusMarquee

APP=QApplication.instance() or QApplication([])

class AudioTests(unittest.TestCase):
    def test_default_hover_prefers_predecoded_wav_and_override_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('hover_button.mp3','hover_button.wav','custom.mp3'):
                (root/name).write_bytes(b'test')
            engine=UIAudio(APP,root)
            try:
                self.assertEqual(engine.source('hover'),root/'hover_button.wav')
                engine.settings={'audio_hover_file':str(root/'custom.mp3')}
                self.assertEqual(engine.source('hover'),root/'custom.mp3')
            finally:APP.removeEventFilter(engine);engine.deleteLater()

    def test_opt_in_volume_throttling_and_player_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);(path/'hover_button.wav').write_bytes(b'test')
            engine=UIAudio(APP,path)
            fake=Mock();fake.setVolume=Mock()
            backend=SimpleNamespace(QSoundEffect=Mock(return_value=fake),QMediaPlayer=Mock(),QAudioOutput=Mock())
            try:
                with patch.dict('sys.modules',{'PyQt6.QtMultimedia':backend}):
                    self.assertFalse(engine.play('hover'));backend.QSoundEffect.assert_not_called()
                    engine.configure({'audio_enabled':True,'audio_volume':250})
                    self.assertTrue(engine.play('hover'));self.assertFalse(engine.play('hover'))
                    engine.last.clear();self.assertTrue(engine.play('hover'))
                    backend.QSoundEffect.assert_called_once();fake.setVolume.assert_called_with(1.)
                    engine.configure({'audio_enabled':False});fake.stop.assert_called_once()
                    self.assertFalse(engine.play('hover'))
            finally:APP.removeEventFilter(engine);engine.deleteLater()

    def test_extended_templates_construct_and_plugin_registers(self):
        from extended_templates import TOOL_GUI_TEMPLATES,TOOL_PLUGIN_TEMPLATES
        from PyQt6.QtWidgets import QWidget,QComboBox
        class Context:
            def __init__(self):
                self.store=SimpleNamespace(shared=lambda:{})
                self.window=SimpleNamespace(settings={},plugin_styles={})
                self.pages=[]
            def add_page(self,name,page):self.pages.append(page)
            def add_style(self,*a,**kw):pass
            def add_template(self,*a):pass
            def on(self,*a):pass
            def log(self,*a):pass
            def play_cue(self,*a):pass
        for name,code in TOOL_GUI_TEMPLATES.items():
            with self.subTest(gui=name):
                scope={'__name__':'fixture'};exec(compile(code,name,'exec'),scope)
                window=scope['MyWindow']();window.close();window.deleteLater()
        for name,code in TOOL_PLUGIN_TEMPLATES.items():
            with self.subTest(plugin=name):
                scope={};exec(compile(code,name,'exec'),scope);ctx=Context();scope['register'](ctx)
                for page in ctx.pages:page.close();page.deleteLater()
        APP.processEvents()

    def test_marquee_cached_layout_animations_and_hidden_timer(self):
        with tempfile.TemporaryDirectory() as directory:
            marquee=StatusMarquee(Path(directory)/'tags.txt');marquee.resize(640,25);marquee.show()
            try:
                marquee.setText('My animated terminal');APP.processEvents()
                for animation in ('Static','Gradient','Rainbow','Pulse','Scanner'):
                    marquee.configure({'marquee_animation':animation});marquee.grab();cached=marquee.cache
                    marquee.advance();marquee.grab();self.assertIs(marquee.cache,cached)
                marquee.hide();self.assertFalse(marquee.timer.isActive())
                marquee.show();self.assertTrue(marquee.timer.isActive())
            finally:marquee.close()

if __name__=='__main__':unittest.main()
