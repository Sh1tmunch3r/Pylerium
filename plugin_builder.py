"""In-app multi-file plugin authoring, validation and host lifecycle integration."""
import ast
import json
import re
from pathlib import Path

from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,
    QComboBox,QPushButton,QLabel,QMessageBox,QInputDialog)
from workshop_editor import WorkshopEditor
from editor_focus import EditorCard
from file_saving import write_text_atomic
from gui_components import Disclosure,horizontal_strip


TEMPLATES = {
 'Custom extension': "def echo(value):\n    return value\n\nSCRIPT_COMMANDS = {'echo': echo}\n\ndef register(ctx):\n    ctx.add_action('Hello extension', lambda: ctx.log('Plugin ready'))\n",
 'Custom UI page': "def register(ctx):\n    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel\n    page = QWidget()\n    layout = QVBoxLayout(page)\n    layout.addWidget(QLabel('Build your custom interface here'))\n    ctx.add_page('My tools', page)\n",
 'Project launcher': "def register(ctx):\n    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton\n    page = QWidget()\n    layout = QVBoxLayout(page)\n    project = ctx.selector('project')\n    profile = ctx.selector('profile')\n    run = QPushButton('Run selected project')\n    run.clicked.connect(lambda: ctx.window.safe(lambda: ctx.window.launch(project.currentData(), profile.currentData())))\n    layout.addWidget(project)\n    layout.addWidget(profile)\n    layout.addWidget(run)\n    ctx.add_page('Project launcher', page)\n",
 'Shared data tool': "def read_shared(key, default=None):\n    from shared_loadout import get\n    return get(key, default)\n\nSCRIPT_COMMANDS = {'read': read_shared}\n\ndef register(ctx):\n    ctx.add_action('Inspect shared data', lambda: ctx.log(ctx.store.shared()))\n",
 'Execution hook': "def register(ctx):\n    ctx.on('run_finished', lambda run_id, status: ctx.log(f'Run {run_id}: {status}'))\n",
 'Output style and template': "def register(ctx):\n    ctx.add_style('highlight', foreground='#ff7b1c', bold=True)\n    ctx.add_template('Styled report', \"from ultimate_terminal import terminal as term\\nterm.success('Ready')\\n\")\n",
 'Script commands': "def transform(value):\n    return str(value).upper()\n\nSCRIPT_COMMANDS = {'transform': transform}\n\ndef register(ctx):\n    ctx.add_action('Command ready', lambda: ctx.log('Call transform from a Workshop script'))\n"
}

from extended_templates import TOOL_PLUGIN_TEMPLATES
TEMPLATES.update(TOOL_PLUGIN_TEMPLATES)


from creative_templates import CREATIVE_PLUGINS
TEMPLATES.update(CREATIVE_PLUGINS)

class PluginBuilder(QWidget):
    def __init__(self,window):
        super().__init__()
        self.window = window
        self.folder = None
        self.entry = 'plugin.py'
        self.current_file = 'plugin.py'
        self.file_contents = {}
        self.dirty = False
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('PLUGIN BUILDER // metadata, Python code, companion files and live integration'))
        form = QFormLayout()
        self.ident,self.name,self.description = QLineEdit(),QLineEdit(),QLineEdit()
        form.addRow('Plugin ID (created from the name)',self.ident)
        form.addRow('Display name',self.name)
        form.addRow('Description',self.description)
        metadata=QWidget();metadata_box=QVBoxLayout(metadata);metadata_box.setContentsMargins(0,0,0,0);metadata_box.addLayout(form)
        layout.addWidget(Disclosure('PLUGIN DETAILS',metadata))
        row = QHBoxLayout()
        self.template = QComboBox();self.template.addItems(TEMPLATES)
        self.files = QComboBox();self.files.currentTextChanged.connect(self.switch_file)
        self.template.hide()  # New templates remain available in the editor toolbar.
        row.addWidget(self.files,1)
        row.addWidget(self.action('ADD FILE',self.add_file))
        layout.addLayout(row)
        self.editor = WorkshopEditor()
        self.editor_card=EditorCard(self.editor,'PLUGIN BUILDER',self.save,
            templates=TEMPLATES,new_template=self.new_from_card)
        layout.addWidget(self.editor_card,1)
        action_scroll,actions = horizontal_strip(52)
        for title,callback in [('VALIDATE',self.validate),('SAVE PLUGIN',self.save),
                               ('SAVE & ENABLE / RELOAD',self.enable),('DISABLE',self.disable)]:
            actions.addWidget(self.action(title,callback))
        layout.addWidget(action_scroll)
        self.status = QLabel('Choose a template to create any Python extension, or edit the selected plugin. Newly saved plugins stay disabled.')
        self.status.setWordWrap(True);self.status.setStyleSheet('color:#26d8ee;')
        layout.addWidget(self.status)
        for field in (self.ident,self.name,self.description):
            field.textEdited.connect(self.mark_dirty)
        self.editor.textChanged.connect(self.mark_dirty)

    def action(self,title,callback):
        b=QPushButton(title);b.clicked.connect(callback);return b

    def mark_dirty(self,*args):
        self.dirty = True

    def confirm_discard(self):
        if not self.dirty:
            return True
        answer = QMessageBox.question(self,'Unsaved plugin','Save plugin changes before continuing?',
            QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel)
        if answer==QMessageBox.StandardButton.Cancel:return False
        if answer==QMessageBox.StandardButton.Save:return self.save()
        return True

    def new_plugin(self):
        if not self.confirm_discard():return
        self.folder=None;self.entry='plugin.py';self.current_file='plugin.py'
        self.file_contents={'plugin.py':TEMPLATES[self.template.currentText()]}
        self.ident.clear();self.ident.setReadOnly(False)
        self.name.setText('New extension');self.description.setText(self.template.currentText())
        self.files.blockSignals(True);self.files.clear();self.files.addItem('plugin.py');self.files.blockSignals(False)
        self.editor.setPlainText(self.file_contents['plugin.py']);self.dirty=True
        self.status.setText('Name your extension, customize its code, then Save. Save & Enable explicitly runs register(ctx).')

    def new_from_card(self,name):
        self.template.setCurrentText(name)
        self.new_plugin()

    def load(self,descriptor):
        if not self.confirm_discard():return False
        try:
            self.folder=Path(descriptor['folder']).resolve()
            self.entry=Path(descriptor['entry_path']).relative_to(self.folder).as_posix()
            paths=[p for p in self.folder.rglob('*.py') if '__pycache__' not in p.parts and p.resolve().is_relative_to(self.folder)]
            self.file_contents={p.relative_to(self.folder).as_posix():p.read_text(encoding='utf-8') for p in paths}
            self.current_file=self.entry
            self.ident.setText(descriptor['id']);self.ident.setReadOnly(True)
            self.name.setText(descriptor.get('name',descriptor['id']));self.description.setText(descriptor.get('description',''))
            self.files.blockSignals(True);self.files.clear();self.files.addItems(self.file_contents);self.files.setCurrentText(self.entry);self.files.blockSignals(False)
            self.editor.setPlainText(self.file_contents[self.entry]);self.dirty=False
            self.status.setText('Editing '+descriptor.get('name',descriptor['id'])+'. Save & Enable reloads its pages, actions, templates and commands.')
            return True
        except (OSError,ValueError,KeyError) as exc:
            self.status.setText(str(exc));return False

    def switch_file(self,name):
        if not name or name not in self.file_contents:return
        was_dirty=self.dirty
        self.file_contents[self.current_file]=self.editor.toPlainText()
        self.current_file=name;self.editor.setPlainText(self.file_contents[name])
        self.dirty=was_dirty

    def add_file(self):
        if not self.file_contents:self.new_plugin()
        name,ok=QInputDialog.getText(self,'Companion module','Module filename, for example helpers.py')
        if not ok:return
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*\.py',name) or name in self.file_contents:
            self.status.setText('Choose a unique Python module filename.');return
        self.file_contents[name]='# Companion module: import with from .'+name[:-3]+' import ...\n'
        self.files.addItem(name);self.files.setCurrentText(name);self.dirty=True

    def check(self):
        if not self.name.text().strip():raise ValueError('Enter a display name')
        ident=self.ident.text().strip() or re.sub(r'[^a-z0-9]+','_',self.name.text().lower()).strip('_')
        if not re.fullmatch(r'[A-Za-z0-9_-]+',ident):raise ValueError('Plugin ID must contain letters, numbers, underscores or hyphens')
        self.file_contents[self.current_file]=self.editor.toPlainText()
        for filename,code in self.file_contents.items():
            ast.parse(code,filename=filename)
        tree=ast.parse(self.file_contents[self.entry])
        if not any(isinstance(n,ast.FunctionDef) and n.name=='register' for n in tree.body):
            raise ValueError('The entry file must define register(ctx)')
        return {'id':ident,'name':self.name.text().strip(),'description':self.description.text().strip(),
                'api_version':1,'entry':self.entry}

    def validate(self):
        try:
            self.check();self.status.setText('All Python files pass syntax validation. Save & Enable tests registration in the live workspace.');return True
        except (ValueError,SyntaxError,KeyError) as exc:
            self.status.setText('Validation failed: '+str(exc));return False

    def save(self):
        try:
            metadata=self.check()
            folder=self.folder or self.window.plugin_host.root/metadata['id']
            if self.folder is None and folder.exists():
                answer=QMessageBox.question(self, 'Plugin already exists',
                    'A plugin with this ID already exists. Replace its matching files?\n'
                    'Yes: update existing plugin. No: save a separate numbered copy. Cancel: keep editing.',
                    QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No|QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.No)
                if answer==QMessageBox.StandardButton.Cancel:return False
                if answer==QMessageBox.StandardButton.No:
                    base=metadata['id'];number=2
                    while (self.window.plugin_host.root/f'{base}_{number}').exists():number+=1
                    metadata['id']=f'{base}_{number}'
                    folder=self.window.plugin_host.root/metadata['id']
            folder.mkdir(parents=True,exist_ok=True)
            for name,code in self.file_contents.items():
                path=(folder/name).resolve()
                if not path.is_relative_to(folder.resolve()):raise ValueError('Module paths must stay inside the plugin folder')
                path.parent.mkdir(parents=True,exist_ok=True)
                write_text_atomic(path, code)
            write_text_atomic(folder/'plugin.json', json.dumps(metadata,indent=2))
            self.folder=folder.resolve();self.ident.setText(metadata['id']);self.ident.setReadOnly(True);self.dirty=False
            self.window.refresh_plugins();self.status.setText('Saved '+metadata['name']+'. Use Save & Enable to activate these changes.');return True
        except (OSError,ValueError,SyntaxError,KeyError) as exc:
            self.status.setText('Save failed: '+str(exc));return False

    def enable(self):
        if not self.save():return
        ident=self.ident.text()
        try:
            self.window.plugin_host.disable(ident)
            descriptor=next(d for d in self.window.plugin_host.descriptors() if d['id']==ident)
            self.window.plugin_host.enable(descriptor)
            self.window.store.put('settings','plugins',self.window.plugin_host.enabled())
            self.window.refresh_plugins();self.status.setText('Enabled '+self.name.text()+'. Its contributions are now available across the workspace.')
        except Exception as exc:
            self.window.store.put('settings','plugins',self.window.plugin_host.enabled())
            self.window.refresh_plugins();self.status.setText('Registration failed; plugin remains disabled: '+str(exc))

    def disable(self):
        self.window.navigate('PLUGINS');self.window.plugin_host.disable(self.ident.text())
        self.window.store.put('settings','plugins',self.window.plugin_host.enabled());self.window.refresh_plugins()
        self.status.setText('Plugin disabled. Saved code is retained.')
