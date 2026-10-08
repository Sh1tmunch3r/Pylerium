"""Composable tool starters: real shared services without cloning the host window."""
from textwrap import dedent
from gui_templates import starter
from toolkit_core import TOOLS

TOOL_GUI_TEMPLATES={}
TOOL_PLUGIN_TEMPLATES={}
for kind,(title,description,prompt,option) in TOOLS.items():
    TOOL_GUI_TEMPLATES['GUI / Tool / '+title]=starter(f'''
        class MyWindow(AppWindow):
            def __init__(self):
                super().__init__({title!r})
                self.content.addWidget(ToolPage({kind!r}), 1)
                self.add_action('Enable audio', self.enable_audio)

            def enable_audio(self):
                configure_audio(enabled=True, volume=18)
                play_cue('success')
    ''','from toolkit_ui import ToolPage\n')
    TOOL_PLUGIN_TEMPLATES['Tool page / '+title]=dedent(f'''
        def register(ctx):
            from toolkit_ui import ToolPage
            page = ToolPage({kind!r}, ctx)
            ctx.add_page({title!r}, page)
            ctx.add_style('tool_result', foreground='#26d8ee', bold=True)
            ctx.add_template({title!r}, {TOOL_GUI_TEMPLATES['GUI / Tool / '+title]!r})
    ''').strip()+'\n'

TOOL_GUI_TEMPLATES['GUI / Audio cue studio']=starter('''
    class MyWindow(AppWindow):
        def __init__(self):
            super().__init__('TACTILE AUDIO STUDIO')
            box = self.add_page('Audio', 'Opt-in feedback using assets/audio and the shared engine.')
            self.enabled = QCheckBox('Enable UI audio')
            self.volume = QSlider(Qt.Orientation.Horizontal); self.volume.setRange(0,100); self.volume.setValue(18)
            self.enabled.toggled.connect(self.apply_audio); self.volume.valueChanged.connect(self.apply_audio)
            box.addWidget(self.enabled); box.addWidget(self.volume)
            for cue in ('hover','click','deploy','success','error'):
                box.addWidget(button('Preview '+cue, lambda checked=False,c=cue:play_cue(c)))
            box.addStretch()

        def apply_audio(self):
            configure_audio(enabled=self.enabled.isChecked(), volume=self.volume.value())
''','from PyQt6.QtWidgets import QCheckBox, QSlider\nfrom PyQt6.QtCore import Qt\n')

TOOL_GUI_TEMPLATES['GUI / Background file checksum tool']=starter('''
    class MyWindow(AppWindow):
        def __init__(self):
            super().__init__('FILE CHECKSUM')
            self.path = QLineEdit(); self.path.setPlaceholderText('File to hash')
            self.result = WorkshopEditor(); self.result.setReadOnly(True)
            self.content.addWidget(self.path); self.content.addWidget(button('Calculate SHA-256',self.calculate,True))
            self.content.addWidget(self.result,1)

        def calculate(self):
            path = self.path.text()
            def work():
                digest = hashlib.sha256()
                with open(path,'rb') as source:
                    for chunk in iter(lambda:source.read(1024*1024),b''):digest.update(chunk)
                return digest.hexdigest()
            play_cue('deploy')
            self.run_background(work,self.result.setPlainText,self.result.setPlainText)
''','import hashlib\nfrom PyQt6.QtWidgets import QLineEdit\nfrom pylerium_gui import WorkshopEditor\n')

TOOL_GUI_TEMPLATES['GUI / Persistent notes desk']=starter('''
    class MyWindow(AppWindow):
        def __init__(self):
            super().__init__('NOTES DESK')
            self.notes = WorkshopEditor()
            self.preferences=QSettings('Pylerium','Notes desk')
            self.notes.setPlainText(self.preferences.value('notes',''))
            self.content.addWidget(self.notes,1)
            self.content.addWidget(button('Save notes',self.save,True))
            self.add_action('Save',self.save,'Ctrl+S')

        def save(self):
            self.preferences.setValue('notes',self.notes.toPlainText())
            play_cue('success'); self.notice('Notes saved')
''','from pylerium_gui import WorkshopEditor\nfrom PyQt6.QtCore import QSettings\n')

TOOL_GUI_TEMPLATES['GUI / Live terminal marquee']=starter('''
    class MyWindow(AppWindow):
        def __init__(self):
            super().__init__('LIVE STATUS')
            self.marquee = StatusMarquee(ASSETS.root/'tags.txt')
            self.marquee.configure({'marquee_animation':'Rainbow','marquee_fps':30})
            self.content.addWidget(label('Your custom application',24))
            self.content.addWidget(button('Publish event',lambda:self.marquee.setText('COMPLETE // example event')))
            self.content.addStretch();self.content.addWidget(self.marquee)
''','from status_marquee import StatusMarquee\nfrom asset_helper import ASSETS\n')

TOOL_PLUGIN_TEMPLATES.update({
    'Audio / Cue studio': dedent('''
        def register(ctx):
            from PyQt6.QtWidgets import QWidget, QVBoxLayout
            from pylerium_gui import button, label
            page=QWidget();box=QVBoxLayout(page)
            box.addWidget(label('TACTILE CUES // enable Audio in Settings',20))
            for cue in ('hover','click','deploy','success','error'):
                box.addWidget(button('Preview '+cue,lambda checked=False,c=cue:ctx.play_cue(c)))
            box.addStretch();ctx.add_page('Audio studio',page)
    '''),
    'Shared / Notes panel': dedent('''
        def register(ctx):
            from PyQt6.QtWidgets import QWidget, QVBoxLayout
            from pylerium_gui import WorkshopEditor, button
            page=QWidget();box=QVBoxLayout(page);editor=WorkshopEditor()
            editor.setPlainText(ctx.store.shared().get('plugin_notes',''))
            def save():
                ctx.store.set_shared('plugin_notes',editor.toPlainText())
                ctx.play_cue('success');ctx.log('Notes saved')
            box.addWidget(editor,1);box.addWidget(button('Save notes',save,True));ctx.add_page('Notes',page)
    '''),
    'Runtime / Completion journal': dedent('''
        def register(ctx):
            import time
            def completed(run_id,status):
                journal=ctx.store.shared().get('completion_journal',[])
                journal.append({'id':run_id,'status':status,'time':time.time()})
                ctx.store.set_shared('completion_journal',journal[-1000:])
                ctx.log(f'{run_id}: {status}')
            ctx.on('run_finished',completed)
    '''),
    'Assets / Model inspection page': dedent('''
        def register(ctx):
            from PyQt6.QtWidgets import QWidget,QVBoxLayout,QFileDialog
            from pylerium_gui import InteractiveModelCanvas,button
            from model_assets import MODEL_FILTER,load_model
            from asset_helper import AssetTask
            from PyQt6.QtCore import QThreadPool
            from types import SimpleNamespace
            page=QWidget();box=QVBoxLayout(page);canvas=InteractiveModelCanvas()
            def choose():
                path,_=QFileDialog.getOpenFileName(page,'Select model','',MODEL_FILTER)
                if path:
                    canvas.item_data=SimpleNamespace(name=path,asset_key=path,category="MODEL")
                    page.task=AssetTask(path,lambda:load_model(path))
                    page.task.signals.finished.connect(canvas.loaded)
                    QThreadPool.globalInstance().start(page.task)
            box.addWidget(canvas,1);box.addWidget(button('Open model',choose));ctx.add_page('Models',page)
    '''),
    'Editor / Python scratchpad': dedent('''
        def register(ctx):
            from PyQt6.QtWidgets import QWidget,QVBoxLayout
            from pylerium_gui import WorkshopEditor,EditorCard
            page=QWidget();box=QVBoxLayout(page);editor=WorkshopEditor()
            editor.setPlainText(ctx.store.shared().get('scratchpad',''))
            def save():
                ctx.store.set_shared('scratchpad',editor.toPlainText());ctx.play_cue('success')
            box.addWidget(EditorCard(editor,'SCRATCHPAD',save),1);ctx.add_page('Scratchpad',page)
    '''),
    'Terminal / Event marquee': dedent('''
        def register(ctx):
            from PyQt6.QtWidgets import QWidget,QVBoxLayout
            from status_marquee import StatusMarquee
            from asset_helper import ASSETS
            page=QWidget();box=QVBoxLayout(page);marquee=StatusMarquee(ASSETS.root/'tags.txt')
            marquee.configure(ctx.window.settings,ctx.window.plugin_styles)
            ctx.on('run_finished',lambda ident,status:marquee.setText(f'{status.upper()} // {ident[:8]}'))
            box.addWidget(marquee);box.addStretch();ctx.add_page('Events',page)
    '''),
})
