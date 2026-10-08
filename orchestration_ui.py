"""BO6-inspired local workspace. The copied menu supplies its original visual widgets."""
from __future__ import annotations

import json
import io
import shutil
import sqlite3
import sys
import time
import uuid
import zipfile
from pathlib import Path
from contextlib import redirect_stdout

from PyQt6.QtCore import QByteArray, QPointF, QRectF, QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QShortcut, QKeySequence
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow,
    QMessageBox, QMenu, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,QTabWidget,
)

from asset_helper import ASSETS,AssetTask
from model_assets import import_model_bundle, MODEL_FILTER
from runner_core import Runner, Store, validate_workflow
from terminal_console import TerminalConsole
from generated_code import clean_python_response, validate_python
from plugin_system import PluginHost
from ultimate_terminal import Terminal, THEMES, Style as OutputStyle, RGB
from workshop_editor import WorkshopEditor
from workflow_builder import NodeDialog,repair_node_ids
from plugin_builder import PluginBuilder
from editor_focus import EditorCard
from editor_templates import WORKSHOP_TEMPLATES
from app_paths import workspace_root, writable_resources, python_executable
from file_saving import write_text_atomic


from gui_components import STYLE, label, button, panel, Disclosure


class WorkflowMap(QWidget):
    def __init__(self):
        super().__init__()
        self.nodes = []
        self.setMinimumSize(440, 280)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor('#0b1115'))
        p.setPen(QPen(QColor(38,216,238,20), 1))
        for x in range(0, self.width(), 24):
            p.drawLine(x,0,x,self.height())
        for y in range(0, self.height(), 24):
            p.drawLine(0,y,self.width(),y)
        positions = {}
        remaining = list(self.nodes)
        levels = {}
        for _ in self.nodes:
            for node in remaining[:]:
                deps = node.get('depends_on', [])
                if all(d in levels for d in deps):
                    levels[node['id']] = 1+max((levels[d] for d in deps), default=-1)
                    remaining.remove(node)
        for node in remaining:
            levels[node.get('id','?')] = 0
        columns = max(levels.values(), default=0)+1
        for level in range(columns):
            group = [n for n in self.nodes if levels.get(n.get('id')) == level]
            for row, node in enumerate(group):
                positions[node['id']] = QPointF((level+0.5)*self.width()/columns,
                    (row+1)*self.height()/(len(group)+1))
        for node in self.nodes:
            for dep in node.get('depends_on', []):
                if dep in positions and node['id'] in positions:
                    p.setPen(QPen(QColor('#3e8791'), 2))
                    p.drawLine(positions[dep], positions[node['id']])
        for node in self.nodes:
            c = positions.get(node.get('id'))
            if c is None:
                continue
            box = QRectF(c.x()-62,c.y()-28,124,56)
            status = node.get('status','ready')
            p.setBrush(QColor('#202b32'))
            p.setPen(QPen(QColor('#f06413' if status == 'running' else '#26d8ee' if status == 'succeeded' else '#586975'), 1.5))
            p.drawRect(box)
            p.setFont(QFont('Consolas', 9))
            p.setPen(QColor('#f3f3f3'))
            p.drawText(box.adjusted(4,3,-4,-25), Qt.AlignmentFlag.AlignCenter, node.get('id','?')[:18])
            p.setPen(QColor('#8ea5af'))
            p.drawText(box.adjusted(4,26,-4,-2), Qt.AlignmentFlag.AlignCenter, status.upper())


class OrchestrationWindow(QMainWindow):
    def __init__(self, theme, state_root=None):
        super().__init__()
        self.theme = theme
        from systematic_gui import register_theme
        register_theme(theme)
        self.base = workspace_root()
        self.store = Store(state_root or self.base / 'orchestration_data')
        self.runner = Runner(self.store, self)
        self.runner.output.connect(self.receive_output)
        self.runner.changed.connect(self.refresh_runtime)
        self.runner.completed.connect(lambda ident,status:self.receive_output(ident,'\n\x1b[0mPROCESS '+status.upper()+'\n'))
        self.network = QNetworkAccessManager(self)
        self.ai_reply = None
        self.models_reply = None
        self._closing = False
        self.asset_tasks = {}
        self.plugin_templates, self.plugin_styles = {}, {}
        self.page_widgets = {}
        self.current_project = None
        self.current_profile = 'default'
        self.current_operator = None
        self.current_workflow = None
        self.current_schedule = None
        self._loading = False
        self.settings = self.store.get('settings', 'app', {'ai_enabled':False,
            'ollama_url':'http://localhost:11434', 'ollama_model':'', 'parallel':2, 'motion':True})
        self.runner.max_parallel = self.settings.get('parallel', 2)
        from ui_audio import audio_engine
        self.audio=audio_engine();self.audio.configure(self.settings)
        self.runner.completed.connect(lambda ident,status:self.audio.play("success" if status=="succeeded" else "error" if status in ("failed","timed out") else "click"))
        self.runner.started.connect(lambda ident:self.audio.play("deploy"))
        self.seed()
        self.setWindowTitle('PYLERIUM // LOCAL OPERATIONS')
        from app_paths import resource_root
        from PyQt6.QtGui import QIcon
        application_icon=resource_root()/'application.ico'
        if application_icon.is_file():self.setWindowIcon(QIcon(str(application_icon)))
        self.resize(1680, 1000)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(STYLE)
        self.fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        self.fullscreen_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.fullscreen_shortcut.activated.connect(self.fullscreen)
        self.background = theme.BackgroundWidget()
        self.setCentralWidget(self.background)
        root = QVBoxLayout(self.background)
        root.setContentsMargins(24,18,24,16)
        top = QHBoxLayout()
        self.brand_logo=QLabel();self.brand_logo.setFixedSize(36,36);self.brand_logo.hide();top.addWidget(self.brand_logo)
        title = label('PYLERIUM', 32)
        title.setFont(theme.condensed_font(32))
        top.addWidget(title)
        top.addWidget(label('LOCAL OPERATIONS // WORKSPACE', 11, '#26d8ee'))
        top.addStretch()
        from ui_icons import icon_button
        top.addWidget(icon_button('command','Killchain global command bar (Ctrl+Space)',lambda:self.killchain.toggle()))
        top.addWidget(icon_button('fullscreen','Toggle fullscreen (F11)',self.fullscreen))
        top.addWidget(icon_button('stop','Stop all running operations',self.stop_operations))
        root.addLayout(top)
        tabs = QGridLayout()
        self.nav = {}
        self.stack = QStackedWidget()
        self.page_ids = {}
        for index, name in enumerate(['LOBBY','LOADOUTS','OPERATORS','MAPS','MISSIONS','ARSENAL','WORKSHOP','CONSOLE','BARRACKS','ASSETS','SETTINGS']):
            b = button(name, lambda checked=False, n=name: self.navigate(n))
            b.setCheckable(True)
            self.nav[name] = b
            tabs.addWidget(b,index//6,index%6)
        root.addLayout(tabs)
        from gui_components import horizontal_strip
        self.plugin_navigation_scroll,self.plugin_navigation=horizontal_strip()
        self.plugin_navigation_scroll.hide()
        root.addWidget(self.plugin_navigation_scroll)
        root.addWidget(self.stack, 1)
        from status_marquee import StatusMarquee
        self.status = StatusMarquee(ASSETS.root/'tags.txt',self)
        root.addWidget(self.status)
        self.build_lobby()
        self.build_profiles()
        self.build_operators()
        self.build_maps()
        self.build_missions()
        self.build_arsenal()
        self.build_workshop()
        self.build_console()
        self.build_barracks()
        self.build_assets()
        self.build_settings()
        self.build_plugins()
        self.plugin_host = PluginHost(self,writable_resources('plugins'))
        self.runner.completed.connect(lambda ident,status:self.plugin_host.emit('run_finished',ident,status))
        self.refresh_lists()
        self.refresh_plugins()
        self.sync_plugin_environment()
        enabled = self.store.get('settings','plugins',[])
        for descriptor in self.plugin_host.descriptors():
            if descriptor['id'] in enabled:
                self.safe(lambda d=descriptor:self.plugin_host.enable(d))
        self.refresh_plugins()
        self.navigate('LOBBY')
        self.poll = QTimer(self)
        self.poll.timeout.connect(self.refresh_runtime)
        self.poll.timeout.connect(self.tick_schedules)
        self.poll.start(1000)
        self.apply_motion();self.apply_editor_preferences()
        self.lobby_project.currentIndexChanged.connect(self.select_project_preview)
        if self.settings.get('remember_window',True) and self.settings.get('window_geometry'):
            self.restoreGeometry(QByteArray.fromHex(self.settings['window_geometry'].encode()))
        self.select_project_preview()
        from killchain import Killchain
        self.killchain=Killchain(self)
        if self.settings.get('ai_enabled'):
            QTimer.singleShot(0,self.refresh_models)

    def seed(self):
        if not self.store.get('profile', 'default'):
            self.store.put('profile','default', {'id':'default','name':'LOCAL // DEFAULT',
                'python':python_executable(),'timeout':300,'env':{}})
        elif getattr(sys, 'frozen', False):
            profile = self.store.get('profile', 'default')
            if not Path(profile.get('python', '')).is_file() or '_MEI' in profile.get('python', ''):
                profile['python'] = python_executable()
                self.store.put('profile', 'default', profile)
        if self.store.get('settings','seeded',False):return
        if not self.store.list('project'):
            folder = self.store.root / 'projects' / 'hello-operations'
            folder.mkdir(parents=True, exist_ok=True)
            script = folder / 'main.py'
            script.write_text("from shared_loadout import update, all_values\nimport os\nprint('Operator:', os.environ.get('ORCHESTRATOR_OPERATOR'))\nupdate('runs_completed', lambda old: (old or 0) + 1)\nprint('Shared loadout:', all_values())\n", encoding='utf-8')
            self.store.put('project','hello', {'id':'hello','name':'Hello operations',
                'script':str(script),'cwd':str(folder),'args':[]})
        if not self.store.list('operator'):
            first = self.store.list('project')[0]['id']
            self.store.put('operator','local', {'id':'local','name':'Local operator',
                'project':first,'profile':'default'})
        if not self.store.list('workflow'):
            first = self.store.list('project')[0]['id']
            self.store.put('workflow','demo', {'id':'demo','name':'Two-stage operation', 'nodes':[
                {'id':'prepare','project':first,'profile':'default','operator':'local','depends_on':[]},
                {'id':'build','project':first,'profile':'default','operator':'local','depends_on':['prepare']}]})
        self.store.put('settings','seeded',True)

    def add_page(self, name, subtitle):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0,16,0,0)
        layout.addWidget(label(name, 28))
        layout.addWidget(label(subtitle, 12, '#9aabb4'))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('QScrollArea {background:transparent;border:0;}')
        scroll.setWidget(page)
        page.setAutoFillBackground(False)
        self.page_ids[name] = self.stack.addWidget(scroll)
        self.page_widgets[name] = scroll
        return layout

    def navigate(self, name):
        if name in ('WORKSHOP','PLUGINS'):
            self.workshop_tabs.setCurrentIndex(1 if name=='PLUGINS' else 0)
            name='WORKSHOP'
        self.stack.setCurrentIndex(self.page_ids[name])
        for title, b in self.nav.items():
            b.setChecked(title == name)
        self.refresh_runtime()

    def safe(self, action):
        try:
            return action()
        except (ValueError, OSError, KeyError, TypeError, AttributeError, sqlite3.Error, zipfile.BadZipFile) as exc:
            QMessageBox.warning(self,'Operation could not complete',str(exc))

    def notice(self, text):
        self.status.setText(text)

    def select_project_preview(self):
        project = self.store.get('project',self.lobby_project.currentData())
        if not project:
            return
        data = self.theme.LoadoutItem(project['name'],'PYTHON PROJECT',
            description='Entry script: '+project['script'],
            attachments=['Local Python','Shared SQLite','Dependency workflows'])
        data.asset_key = 'project:'+project['id']
        self.preview.set_item(data)
        self.preview.level.setText('DETERMINISTIC // LOCAL')
        self.refresh_runtime()

    def build_lobby(self):
        root = self.add_page('LOBBY','SELECT AN OPERATION // EQUIP A LOADOUT // DEPLOY LOCALLY')
        row = QHBoxLayout()
        left, layout = panel()
        layout.addWidget(label('MISSION CONTROL',22))
        self.lobby_project = QComboBox()
        self.lobby_profile = QComboBox()
        layout.addWidget(label('PROJECT'))
        layout.addWidget(self.lobby_project)
        layout.addWidget(label('EXECUTION LOADOUT'))
        layout.addWidget(self.lobby_profile)
        layout.addWidget(button('DEPLOY PROJECT',self.deploy_project,True))
        layout.addWidget(button('OPEN WORKSHOP',lambda:self.navigate('WORKSHOP')))
        layout.addWidget(button('STOP ALL OPERATIONS',self.stop_operations))
        layout.addStretch()
        self.lobby_metrics = label('',16,'#26d8ee')
        layout.addWidget(self.lobby_metrics)
        row.addWidget(left,1)
        self.preview = self.theme.PreviewPanel()
        self.preview.setMinimumWidth(340)
        self.preview.set_item(self.theme.LoadoutItem('Python runner','LOCAL EXECUTION',
            description='Run Python projects, coordinate operators, and share data through a persistent loadout.',
            attachments=['Local Python','Shared SQLite','Dependency workflows']))
        self.preview.level.setText('DETERMINISTIC // LOCAL')
        for widget in self.preview.findChildren(QLabel):
            if widget.text() == 'WEAPON STATS':
                widget.setText('WORKSPACE TELEMETRY')
            elif widget.text() == 'ATTACHMENTS':
                widget.setText('CAPABILITIES')
        for stat, title in zip(self.preview.stats.values(), ['Projects','Operators','Maps','Loadouts','Active','Slots']):
            stat.title = title
        row.addWidget(self.preview,2)
        right, layout = panel()
        layout.addWidget(label('SQUAD // ACTIVE OPERATIONS',18))
        self.lobby_jobs = QListWidget()
        layout.addWidget(self.lobby_jobs,1)
        layout.addWidget(button('VIEW CONSOLE',lambda:self.navigate('CONSOLE')))
        layout.addWidget(label('Code runs with your local account permissions. AI assistance is optional; deployment is always an explicit action.',11,'#869ba6'))
        row.addWidget(right,1)
        root.addLayout(row,1)

    def build_profiles(self):
        root = self.add_page('LOADOUTS','REUSABLE PYTHON INTERPRETERS, ENVIRONMENT VARIABLES, TIMEOUTS & SHARED DATA')
        row = QHBoxLayout()
        self.profile_list = QListWidget()
        self.profile_list.currentRowChanged.connect(self.load_profile)
        row.addWidget(self.profile_list,1)
        pane, layout = panel()
        form = QFormLayout()
        self.profile_name, self.profile_python = QLineEdit(), QLineEdit()
        self.profile_timeout = QSpinBox()
        self.profile_timeout.setRange(0,86400)
        self.profile_timeout.setSuffix(' seconds (0 = unlimited)')
        self.profile_env = QPlainTextEdit('{}')
        form.addRow('Name',self.profile_name)
        form.addRow('Python executable',self.profile_python)
        form.addRow('Timeout',self.profile_timeout)
        form.addRow('Environment JSON',self.profile_env)
        layout.addLayout(form)
        layout.addWidget(button('SAVE LOADOUT',self.save_profile,True))
        layout.addWidget(button('NEW LOADOUT',self.new_profile))
        row.addWidget(pane,2)
        shared, layout = panel()
        layout.addWidget(label('SHARED LOADOUT // ALL OPERATORS',18))
        self.shared_table = QTableWidget(0,2)
        self.shared_table.setHorizontalHeaderLabels(['KEY','JSON VALUE'])
        self.shared_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.shared_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.shared_table,1)
        self.shared_key = QLineEdit()
        self.shared_key.setPlaceholderText('Shared key')
        self.shared_value = QPlainTextEdit('null')
        self.shared_value.setMaximumHeight(110)
        layout.addWidget(self.shared_key)
        layout.addWidget(self.shared_value)
        layout.addWidget(button('SET SHARED VALUE',self.save_shared))
        layout.addWidget(label('Scripts use shared_loadout.get(), set_value(), and atomic update(). Every deployed operator connects to this same database.',11,'#869ba6'))
        row.addWidget(shared,2)
        root.addLayout(row,1)

    def build_operators(self):
        root = self.add_page('OPERATORS','SAVED EXECUTION AGENTS // EACH OPERATOR EQUIPS A PROJECT AND A SHARED LOADOUT')
        row = QHBoxLayout()
        self.operator_list = QListWidget()
        self.operator_list.currentRowChanged.connect(self.load_operator)
        row.addWidget(self.operator_list,1)
        pane, layout = panel()
        self.operator_name = QLineEdit()
        self.operator_project, self.operator_profile = QComboBox(), QComboBox()
        form = QFormLayout()
        form.addRow('Callsign',self.operator_name)
        form.addRow('Project',self.operator_project)
        form.addRow('Loadout',self.operator_profile)
        layout.addLayout(form)
        layout.addWidget(button('SAVE OPERATOR',self.save_operator,True))
        layout.addWidget(button('NEW OPERATOR',self.new_operator))
        layout.addWidget(button('DEPLOY OPERATOR',self.deploy_operator,True))
        layout.addWidget(label('An operator is a reusable execution configuration. It can run a bot, a build tool, an analysis script, or any Python application. Map nodes can assign different operators.',14,'#9aabb4'))
        layout.addStretch()
        row.addWidget(pane,2)
        root.addLayout(row,1)

    def build_maps(self):
        root = self.add_page('MAPS','DEPENDENCY GRAPHS // INDEPENDENT NODES RUN IN PARALLEL // FAILED DEPENDENCIES SKIP DOWNSTREAM NODES')
        row = QHBoxLayout()
        self.workflow_list = QListWidget()
        self.workflow_list.currentRowChanged.connect(self.load_workflow)
        row.addWidget(self.workflow_list,1)
        pane, layout = panel()
        self.workflow_name = QLineEdit()
        self.map_view = WorkflowMap()
        self.workflow_json = QPlainTextEdit()
        self.workflow_json.textChanged.connect(self.preview_map)
        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.map_view)
        split.addWidget(self.workflow_json)
        self.node_table = QTableWidget(0,4)
        self.node_table.setHorizontalHeaderLabels(['STEP','PROJECT','LOADOUT','RUN AFTER'])
        self.node_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.node_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.node_table.horizontalHeader().setStretchLastSection(True)
        self.node_table.cellDoubleClicked.connect(lambda row,col:self.edit_node())
        split.addWidget(self.node_table)
        layout.addWidget(self.workflow_name)
        layout.addWidget(split,1)
        actions = QHBoxLayout()
        actions.addWidget(button('SAVE MAP',self.save_workflow,True))
        actions.addWidget(button('NEW MAP',self.new_workflow))
        actions.addWidget(button('ADD NODE',self.add_node))
        actions.addWidget(button('EDIT STEP',self.edit_node))
        actions.addWidget(button('REMOVE STEP',self.remove_node))
        actions.addWidget(button('FIX DUPLICATE LABELS',self.fix_node_ids))
        actions.addWidget(button('DEPLOY MAP',self.deploy_workflow,True))
        layout.addLayout(actions)
        self.map_state = label('READY',11,'#26d8ee')
        layout.addWidget(self.map_state)
        row.addWidget(pane)
        self.workshop_pane=pane
        root.addLayout(row,1)

    def build_arsenal(self):
        root = self.add_page('ARSENAL','PROJECT LIBRARY // IMPORT PYTHON FILES OR CREATE A PROJECT IN THE WORKSHOP')
        self.project_grid = QGridLayout()
        holder = QWidget()
        holder.setLayout(self.project_grid)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        root.addWidget(scroll,1)
        actions = QHBoxLayout()
        actions.addWidget(button('IMPORT PYTHON SCRIPT',self.import_script,True))
        actions.addWidget(button('NEW PROJECT',self.new_project))
        actions.addWidget(button('EXPORT WORKSPACE CONFIGURATION',self.export_workspace))
        actions.addWidget(button('EXPORT PROJECT BUNDLE',self.export_bundle))
        actions.addWidget(button('IMPORT PROJECT BUNDLE',self.import_bundle))
        root.addLayout(actions)

    def build_missions(self):
        root = self.add_page('MISSIONS','RECURRING OPERATIONS // DETERMINISTIC SCHEDULING // RUNS WHILE THIS APP IS OPEN')
        row = QHBoxLayout()
        self.schedule_list = QListWidget()
        self.schedule_list.currentRowChanged.connect(self.load_schedule)
        row.addWidget(self.schedule_list,1)
        pane, layout = panel()
        self.schedule_name = QLineEdit()
        self.schedule_workflow = QComboBox()
        self.schedule_interval = QSpinBox()
        self.schedule_interval.setRange(10,604800)
        self.schedule_interval.setValue(60)
        self.schedule_interval.setSuffix(' seconds')
        self.schedule_enabled = QCheckBox('Enable recurring execution')
        form = QFormLayout()
        form.addRow('Mission name',self.schedule_name)
        form.addRow('Saved map',self.schedule_workflow)
        form.addRow('Interval',self.schedule_interval)
        form.addRow('Automation',self.schedule_enabled)
        layout.addLayout(form)
        layout.addWidget(button('SAVE MISSION',self.save_schedule,True))
        layout.addWidget(button('NEW MISSION',self.new_schedule))
        layout.addWidget(button('DISABLE ALL MISSIONS',self.disable_schedules))
        self.mission_status = label('',14,'#26d8ee')
        layout.addWidget(self.mission_status)
        layout.addWidget(label('Missions deploy saved maps without AI. The first run occurs after the interval. Busy execution slots defer a mission rather than overlap it. Missed intervals are not replayed. Stopping all operations also disables recurring missions.',13,'#9aabb4'))
        layout.addStretch()
        row.addWidget(pane,3)
        root.addLayout(row,1)

    def build_workshop(self):
        root = self.add_page('WORKSHOP','BUILD ANY PYTHON TOOL // SAVE LOCALLY // DEPLOY WITH AN EXECUTION LOADOUT')
        self.workshop_tabs=QTabWidget();root.addWidget(self.workshop_tabs,1)
        projects_page=QWidget();root=QVBoxLayout(projects_page);root.setContentsMargins(0,12,0,0)
        self.workshop_tabs.addTab(projects_page,'PROJECTS')
        row = QSplitter(Qt.Orientation.Horizontal)
        self.editor_projects = QListWidget()
        self.editor_projects.currentRowChanged.connect(self.load_project)
        self.editor_projects.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editor_projects.setMinimumWidth(150)
        self.editor_projects.setMaximumWidth(250)
        row.addWidget(self.editor_projects)
        pane, layout = panel()
        self.project_name = QLineEdit()
        self.project_args = QLineEdit('[]')
        self.project_cwd = QLineEdit()
        self.project_path = label('',11,'#26d8ee')
        form = QFormLayout()
        form.addRow('Project name',self.project_name)
        form.addRow('Arguments (JSON list)',self.project_args)
        form.addRow('Working directory',self.project_cwd)
        details=QWidget();details_box=QVBoxLayout(details);details_box.setContentsMargins(0,0,0,0)
        details_box.addLayout(form);details_box.addWidget(self.project_path)
        layout.addWidget(Disclosure('PROJECT DETAILS / ARGUMENTS',details))
        self.code = WorkshopEditor()
        for field in (self.project_name,self.project_args,self.project_cwd):
            field.textEdited.connect(lambda:self.code.document().setModified(True))
        self.code.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.code_card=EditorCard(self.code,'WORKSHOP',self.save_project, templates=lambda: {**WORKSHOP_TEMPLATES, **self.plugin_templates})
        layout.addWidget(self.code_card,1)
        from gui_components import horizontal_strip
        action_scroll,actions = horizontal_strip(52)
        actions.addWidget(button('SAVE PROJECT',self.save_project,True))
        actions.addWidget(button('NEW',self.new_project))
        actions.addWidget(button('IMPORT',self.import_script))
        actions.addWidget(button('RUN SAVED PROJECT',self.run_editor,True))
        actions.addWidget(button('BUILD EXE',self.build_project_exe))
        layout.addWidget(action_scroll)
        row.addWidget(pane)
        self.workshop_pane=pane
        ai, layout = panel()
        layout.addWidget(label('OPTIONAL // OLLAMA ASSIST',18))
        self.ai_prompt = QPlainTextEdit()
        self.ai_prompt.setPlaceholderText('Describe code you want drafted. Enable Ollama in settings first.')
        self.ai_draft = WorkshopEditor();self.ai_draft.setMinimumHeight(160)
        self.ai_draft.setPlaceholderText('Generated Python draft — review or correct it here before inserting.')
        self.ai_generate = button('GENERATE DRAFT',self.generate_draft)
        layout.addWidget(self.ai_prompt,1)
        layout.addWidget(self.ai_generate)
        layout.addWidget(self.ai_draft,2)
        self.ai_apply = button('USE DRAFT IN EDITOR',self.apply_draft)
        layout.addWidget(self.ai_apply)
        layout.addWidget(label('Drafts are reviewed in the editor. They are never executed automatically.',11,'#869ba6'))
        row.addWidget(ai);ai.setMaximumWidth(420);ai.hide()
        actions.addWidget(button('ASSIST',lambda:ai.setVisible(not ai.isVisible())))
        row.setSizes([190,1100,350]);row.setStretchFactor(1,1)
        root.addWidget(row,1)

    def build_console(self):
        root = self.add_page('CONSOLE','LIVE PROCESS OUTPUT // STDOUT & STDERR // PERSISTENT RUN LOGS')
        toolbar = QHBoxLayout()
        self.console_runs = QComboBox()
        self.console_runs.addItem('ALL RUNS // GROUPED',None)
        self.console_runs.currentIndexChanged.connect(lambda:self.console.select_run(self.console_runs.currentData()))
        self.console_follow = QCheckBox('Follow output')
        self.console_follow.setChecked(True)
        self.console_follow.toggled.connect(lambda value:setattr(self.console,'autoscroll',value))
        self.console_theme = QComboBox()
        self.console_theme.addItems(list(THEMES))
        self.console_theme.setCurrentText(self.settings.get('output_theme','cyber'))
        self.console_font_size = QSpinBox()
        self.console_font_size.setRange(9,28)
        self.console_font_size.setValue(self.settings.get('output_font_size',13))
        toolbar.addWidget(label('RUN'))
        toolbar.addWidget(self.console_runs,1)
        toolbar.addWidget(label('OUTPUT THEME'))
        toolbar.addWidget(self.console_theme)
        toolbar.addWidget(self.console_font_size)
        toolbar.addWidget(self.console_follow)
        freeze = QCheckBox('Freeze view')
        freeze.toggled.connect(lambda value:setattr(self.console,'frozen',value))
        toolbar.addWidget(freeze)
        toolbar.addWidget(button('PREVIEW OUTPUT',self.preview_terminal))
        root.addLayout(toolbar)
        self.console = TerminalConsole()
        root.addWidget(self.console,1)
        custom = QHBoxLayout()
        self.output_styles = QLineEdit(json.dumps(self.settings.get('output_styles',{})))
        self.output_styles.setPlaceholderText('{"important": {"foreground": "#ff7b1c", "bold": true}}')
        custom.addWidget(label('CUSTOM STYLES JSON'))
        custom.addWidget(self.output_styles,1)
        custom.addWidget(button('SAVE OUTPUT STYLE',self.save_output_settings))
        root.addLayout(custom)
        actions = QHBoxLayout()
        self.stop_run = QComboBox()
        actions.addWidget(self.stop_run)
        actions.addWidget(button('STOP SELECTED',lambda:self.runner.stop(self.stop_run.currentData())))
        actions.addWidget(button('STOP ALL',self.stop_operations))
        actions.addWidget(button('CLEAR VIEW',self.clear_console))
        actions.addWidget(button('EXPORT VIEW',self.export_log))
        root.addLayout(actions)

    def build_barracks(self):
        root = self.add_page('BARRACKS','OPERATION HISTORY // STATUS, DURATION, EXIT CODES & SAVED OUTPUT')
        self.history = QTableWidget(0,6)
        self.history.setHorizontalHeaderLabels(['PROJECT','STATUS','STARTED','DURATION','EXIT','RUN ID'])
        self.history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.history,2)
        self.history_log = TerminalConsole()
        root.addWidget(self.history_log,1)
        self.history.itemSelectionChanged.connect(self.show_history_log)

    def build_assets(self):
        root = self.add_page('ASSETS','PER-ITEM ICONS & MULTIFORMAT MODELS // CUSTOM BACKGROUNDS // ORIGINAL GRADIENT OVERLAYS')
        pane, layout = panel()
        self.asset_name = QComboBox()
        self.asset_name.setEditable(False)
        self.asset_name.addItem('Python runner','Python runner')
        self.asset_name.currentTextChanged.connect(self.inspect_asset)
        layout.addWidget(label('Choose a project or existing item — assignments follow the project even after renaming'))
        layout.addWidget(self.asset_name)
        self.asset_search=QLineEdit();self.asset_search.setPlaceholderText('Find project, loadout slot or library asset…')
        self.asset_search.textChanged.connect(self.filter_asset_targets);layout.addWidget(self.asset_search)
        self.asset_rotation=QLineEdit('[0, 0, 0]');self.asset_rotation.setPlaceholderText('Model rotation [X, Y, Z] degrees')
        rotation_row=QHBoxLayout();rotation_row.addWidget(self.asset_rotation);rotation_row.addWidget(button('APPLY ROTATION',self.save_asset_rotation));layout.addLayout(rotation_row)
        clear_row=QHBoxLayout()
        for title,kind in [('REMOVE IMAGE','icon'),('REMOVE MODEL','model'),('REMOVE TEXTURE','texture')]:
            clear_row.addWidget(button(title,lambda checked=False,k=kind:self.clear_asset(kind=k)))
        layout.addLayout(clear_row)
        layout.addWidget(button('ASSIGN IMAGE ICON',lambda:self.assign_asset('icon')))
        layout.addWidget(button('ASSIGN 3D MODEL',lambda:self.assign_asset('model')))
        layout.addWidget(button('OVERRIDE MODEL TEXTURE',lambda:self.assign_asset('texture')))
        layout.addWidget(button('USE AUTOMATIC MODEL MATERIALS',self.use_automatic_materials))
        layout.addWidget(button('ASSIGN BACKGROUND IMAGE',lambda:self.assign_asset('background')))
        layout.addWidget(button('ASSIGN HEADER LOGO',lambda:self.assign_asset('logo')))
        layout.addWidget(button('REMOVE HEADER LOGO',self.remove_header_logo))
        layout.addWidget(button('RELOAD ASSET MANIFEST',lambda:self.reload_assets(True)))
        self.asset_feedback = label('Background loading: OBJ, GLB, glTF, STL, PLY and OFF. Materials and textures are discovered automatically.',13,'#26d8ee')
        layout.addWidget(self.asset_feedback)
        self.asset_image = QLabel()
        self.asset_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.asset_image.setFixedHeight(150)
        layout.addWidget(self.asset_image)
        ASSETS.model_ready.connect(self.asset_inspected)
        self.asset_manifest = QPlainTextEdit()
        self.asset_manifest.setReadOnly(True)
        layout.addWidget(self.asset_manifest,1)
        layout.addWidget(label('Keep the OBJ, its referenced .mtl files, and texture folders together when importing. Materials and base-color maps are assigned automatically. If a texture is missing, use Override Model Texture. Images fit without stretching; backgrounds fill their area beneath the original gradient overlays. Reload after changing source assets.',13,'#9aabb4'))
        from model_preview import InteractiveModelCanvas
        self.asset_canvas=InteractiveModelCanvas();self.asset_canvas.paused=True
        artwork,art_layout=panel();art_layout.addWidget(label('ASSET STUDIO // LIVE MATERIAL PREVIEW',18))
        art_layout.addWidget(self.asset_canvas,1)
        art_layout.addWidget(button('RESET / FIT MODEL',self.asset_canvas.reset_view))
        art_layout.addWidget(label('Drag to inspect • Scroll to zoom • Right-click for rendering and export options',11,'#869ba6'))
        row=QHBoxLayout();row.addWidget(pane,2);row.addWidget(artwork,3);root.addLayout(row,1)

    def filter_asset_targets(self,text):
        model=self.asset_name.model()
        for index in range(self.asset_name.count()):
            item=model.item(index)
            if item:item.setEnabled(text.casefold() in self.asset_name.itemText(index).casefold())

    def build_settings(self):
        from settings_deck import SettingsDeck
        root=self.add_page('SETTINGS','WORKSPACE // DISPLAY // ASSISTANCE // STORAGE // BUILDS')
        self.settings_deck=SettingsDeck(self)
        root.addWidget(self.settings_deck,1)

    def build_project_exe(self):
        from workshop_build import BuildDialog
        if not self.current_project:
            return self.notice('Select or create a Workshop project first')
        if self.code.document().isModified() and not self.save_project():return
        project=self.store.get('project',self.current_project)
        dialog=BuildDialog(self,project)
        dialog.exec()

    def apply_editor_preferences(self):
        size=self.settings.get('editor_font_size',15)
        WorkshopEditor.default_editor_size=size
        WorkshopEditor.default_preferences=self.settings
        for editor in self.findChildren(WorkshopEditor):
            editor.set_editor_size(size);editor.configure(self.settings)
        scale=self.settings.get('ui_scale',100)/100
        style=STYLE.replace('font-size:13px;',f'font-size:{round(13*scale)}px;')
        style=style.replace('padding:8px 12px;',f'padding:{round(8*scale)}px {round(12*scale)}px;')
        self.setStyleSheet(style)
        from model_preview import InteractiveModelCanvas
        InteractiveModelCanvas.default_preferences=self.settings
        for canvas in self.findChildren(InteractiveModelCanvas):
            canvas.quality=self.settings.get('model_quality',2560);canvas.show_grid=self.settings.get('model_grid',True)
            canvas.orbit_speed=self.settings.get('model_orbit_speed',100)/100
            canvas.paused=not(self.settings.get('motion',True) and self.settings.get('model_auto_orbit',True))
            canvas.surface_key=None;canvas.update()
        self.console_follow.setChecked(self.settings.get('console_follow',True))
        self.console.render_timer.setInterval(self.settings.get('console_flush_ms',40))
        if hasattr(self,'poll'):self.poll.setInterval(self.settings.get('refresh_ms',1000))
        self.status.configure(self.settings,{**self.settings.get('output_styles',{}),**self.plugin_styles})

    def remove_header_logo(self):
        data=json.loads(json.dumps(ASSETS.manifest));data.pop('logo',None);ASSETS.save_manifest(data);self.reload_assets()

    def fill_combo(self, combo, documents):
        old = combo.currentData()
        combo.clear()
        for doc in documents:
            combo.addItem(doc['name'],doc['id'])
        index = combo.findData(old)
        if index >= 0:
            combo.setCurrentIndex(index)

    def fill_list(self, widget, docs, selected):
        widget.blockSignals(True)
        widget.clear()
        for doc in docs:
            widget.addItem(doc['name'])
        index = next((i for i,d in enumerate(docs) if d['id'] == selected),0)
        widget.setCurrentRow(index if docs else -1)
        widget.blockSignals(False)

    def refresh_lists(self):
        self.projects = self.store.list('project')
        self.profiles = self.store.list('profile')
        self.operators = self.store.list('operator')
        self.workflows = self.store.list('workflow')
        self.schedules = self.store.list('schedule')
        self.fill_combo(self.schedule_workflow,self.workflows)
        for c in (self.lobby_project,self.operator_project):
            self.fill_combo(c,self.projects)
        for c in (self.lobby_profile,self.operator_profile):
            self.fill_combo(c,self.profiles)
        self.fill_list(self.editor_projects,self.projects,self.current_project)
        self.fill_list(self.profile_list,self.profiles,self.current_profile)
        self.fill_list(self.operator_list,self.operators,self.current_operator)
        self.fill_list(self.workflow_list,self.workflows,self.current_workflow)
        self.fill_list(self.schedule_list,self.schedules,self.current_schedule)
        if self.current_project is None and self.projects:
            self.load_project(self.editor_projects.currentRow())
        self.load_profile(self.profile_list.currentRow())
        self.load_operator(self.operator_list.currentRow())
        self.load_workflow(self.workflow_list.currentRow())
        self.load_schedule(self.schedule_list.currentRow())
        while self.project_grid.count():
            item = self.project_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, project in enumerate(self.projects):
            data = self.theme.LoadoutItem(project['name'],'PYTHON PROJECT',level=1,
                description=project['script'])
            data.asset_key = 'project:'+project['id']
            card = self.theme.LoadoutCard(data,'primary')
            card.setMinimumSize(260,180)
            card.setMaximumHeight(220)
            card.clicked.connect(lambda ignored, ident=project['id']:self.open_project_loadout(ident))
            card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            card.customContextMenuRequested.connect(lambda pos,c=card,ident=project['id']:self.project_context_menu(ident,c.mapToGlobal(pos)))
            self.project_grid.addWidget(card,i//3,i%3)
        self.reload_assets()
        if hasattr(self,'plugin_host'):
            for ctx in self.plugin_host.contexts.values():
                ctx.refresh_selectors()

    def dirty_check(self):
        if self.code.document().isModified():
            answer = QMessageBox.question(self,'Unsaved code','Save your code before continuing?',
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Cancel:
                return False
            if answer == QMessageBox.StandardButton.Save:
                return bool(self.save_project())
            self.code.document().setModified(False)
        return True

    def load_project(self, row):
        if row < 0 or row >= len(self.projects):
            return
        data = self.projects[row]
        if data['id'] == self.current_project:
            return
        if not self.dirty_check():
            self.fill_list(self.editor_projects,self.projects,self.current_project)
            return
        def action():
            code = Path(data['script']).read_text(encoding='utf-8')
            self.current_project = data['id']
            self.project_name.setText(data['name'])
            self.project_args.setText(json.dumps(data.get('args',[])))
            self.project_cwd.setText(data['cwd'])
            self.project_path.setText(data['script'])
            self.code.setPlainText(code)
            self.code.document().setModified(False)
        self.safe(action)

    def project_context_menu(self, ident, position):
        menu=QMenu(self)
        menu.addAction('Execution loadout',lambda:self.open_project_loadout(ident))
        menu.addAction('Edit in Workshop',lambda:self.open_project(ident))
        menu.addAction('Run project',lambda:self.safe(lambda:self.launch(ident,self.lobby_profile.currentData() or 'default')))
        assets=menu.addMenu('Assign assets')
        assets.addAction('Project / primary artwork',lambda:self.manage_project_assets(ident))
        for slot,title in [('secondary_target','Secondary'),('context','Environment'),('tactical_hook','Tactical'),('lethal_hook','Output'),('perk1','Perk 1'),('perk2','Perk 2'),('perk3','Perk 3'),('specialty','Specialty'),('wildcard','Wildcard')]:
            assets.addAction(title,lambda checked=False,k=slot:self.manage_project_assets(ident,k))
        menu.addSeparator()
        menu.addAction('Rename project…',lambda:self.rename_arsenal_project(ident))
        menu.addAction('Duplicate project',lambda:self.safe(lambda:self.duplicate_arsenal_project(ident)))
        menu.addAction('Open project folder',lambda:__import__('PyQt6.QtGui',fromlist=['QDesktopServices']).QDesktopServices.openUrl(QUrl.fromLocalFile(self.store.get('project',ident)['cwd'])))
        menu.addAction('Copy script path',lambda:__import__('PyQt6.QtWidgets',fromlist=['QApplication']).QApplication.clipboard().setText(self.store.get('project',ident)['script']))
        menu.addAction('Export workspace bundle…',self.export_bundle)
        menu.exec(position)

    def rename_arsenal_project(self,ident):
        project=self.store.get('project',ident)
        name,ok=QInputDialog.getText(self,'Rename project','Project name',text=project['name'])
        if ok and name.strip():
            project['name']=name.strip();self.store.put('project',ident,project);self.refresh_lists()
            if self.current_project==ident:self.project_name.setText(name.strip())

    def duplicate_arsenal_project(self,ident):
        project=self.store.get('project',ident)
        code=Path(project['script']).read_text(encoding='utf-8')
        self.create_project(project['name']+' copy',code,interactive=project.get('interactive',False))
        duplicate=self.store.get('project',self.current_project)
        duplicate['args']=project.get('args',[]);self.store.put('project',duplicate['id'],duplicate)
        loadout=self.store.get('project_loadout',ident)
        if loadout:
            loadout['loadout_id']=duplicate['id'];loadout['primary_target']['script']=duplicate['script']
            self.store.put('project_loadout',duplicate['id'],loadout)
        data=json.loads(json.dumps(ASSETS.manifest))
        for key,value in list(data.get('items',{}).items()):
            if key=='project:'+ident or key.startswith('loadout:'+ident+':'):
                data['items'][key.replace(ident,duplicate['id'],1)]=value
        ASSETS.save_manifest(data);self.refresh_lists()

    def manage_project_assets(self,ident,slot='primary_target',navigate=True):
        key='project:'+ident if slot=='primary_target' else 'loadout:'+ident+':'+slot
        self.reload_assets()
        index=self.asset_name.findData(key)
        if index>=0:self.asset_name.setCurrentIndex(index)
        if navigate:self.navigate('ASSETS')

    def clear_asset(self,key=None,kind=None):
        key=key or self.asset_name.currentData()
        data=json.loads(json.dumps(ASSETS.manifest))
        if kind:data.setdefault('items',{}).get(key,{}).pop(kind,None)
        else:data.setdefault('items',{}).pop(key,None)
        ASSETS.save_manifest(data);self.reload_assets()

    def save_asset_rotation(self):
        def action():
            rotation=json.loads(self.asset_rotation.text())
            ASSETS.set_item(self.asset_name.currentData(),rotation=rotation)
            self.reload_assets()
        self.safe(action)

    def open_project_loadout(self, ident):
        from project_loadout_ui import ProjectLoadoutScreen
        if not hasattr(self, 'project_loadout_screen'):
            self.project_loadout_screen = ProjectLoadoutScreen(self)
            self.stack.addWidget(self.project_loadout_screen)
        self.project_loadout_screen.load(self.store.get('project', ident))
        self.navigate('ARSENAL')
        self.stack.setCurrentWidget(self.project_loadout_screen)

    def open_project(self, ident):
        index = next(i for i,d in enumerate(self.projects) if d['id']==ident)
        self.editor_projects.setCurrentRow(index)
        self.navigate('WORKSHOP')

    def save_project(self):
        def action():
            if not self.current_project:
                raise ValueError('Create or import a project first')
            doc = self.store.get('project',self.current_project)
            args = json.loads(self.project_args.text())
            if not isinstance(args,list) or not all(isinstance(v,str) for v in args):
                raise ValueError('Arguments must be a JSON list of strings')
            name = self.project_name.text().strip()
            if not name:
                raise ValueError('Project name is required')
            cwd = Path(self.project_cwd.text()).resolve()
            if not cwd.is_dir():
                raise ValueError('Working directory does not exist')
            write_text_atomic(doc['script'], self.code.toPlainText())
            doc.update(name=name,args=args,cwd=str(cwd))
            self.store.put('project',doc['id'],doc)
            self.code.document().setModified(False)
            self.refresh_lists()
            self.notice('PROJECT SAVED')
            return True
        return self.safe(action)

    def new_project(self):
        if not self.dirty_check():
            return
        name, ok = QInputDialog.getText(self,'New project','Project name')
        if not ok or not name.strip():
            return
        template, ok = QInputDialog.getItem(self,'Project template','Starting point',
            ['Python tool','Shared-state worker','Pipeline report','Command-line utility','Styled terminal output',
             *[name for name in WORKSHOP_TEMPLATES if name.startswith('GUI /')],*self.plugin_templates],0,False)
        if not ok:
            return
        templates = {
            'Python tool':"def main():\n    print('Build anything here')\n\nif __name__ == '__main__':\n    main()\n",
            'Shared-state worker':"from shared_loadout import update, get\nupdate('tasks_completed', lambda old: (old or 0) + 1)\nprint('Tasks:', get('tasks_completed'))\n",
            'Pipeline report':"from shared_loadout import all_values\nfrom pathlib import Path\nimport json\nPath('report.json').write_text(json.dumps(all_values(), indent=2))\nprint('Saved report.json')\n",
            'Command-line utility':"import argparse\np = argparse.ArgumentParser()\np.add_argument('--name', default='world')\nargs = p.parse_args()\nprint(f'Hello {args.name}')\n",
            'Styled terminal output':self.terminal_example()}
        templates.update({name:code for name,code in WORKSHOP_TEMPLATES.items() if name.startswith('GUI /')})
        templates.update(self.plugin_templates)
        self.safe(lambda:self.create_project(name.strip(),templates[template],interactive=template.startswith('GUI /') or '// GUI /' in template))

    def create_project(self, name, code, interactive=False):
        ident = uuid.uuid4().hex[:12]
        folder = self.store.root / 'projects' / ident
        folder.mkdir(parents=True,exist_ok=True)
        script = folder / 'main.py'
        write_text_atomic(script, code)
        document={'id':ident,'name':name,'script':str(script),'cwd':str(folder),'args':[]}
        if interactive: document['interactive']=True
        self.store.put('project',ident,document)
        self.refresh_lists()
        self.open_project(ident)

    def import_script(self):
        if not self.dirty_check():
            return
        filename, _ = QFileDialog.getOpenFileName(self,'Import a copy into the workspace','','Python (*.py)')
        if filename:
            self.safe(lambda:self.create_project(Path(filename).stem,Path(filename).read_text(encoding='utf-8')))

    def load_profile(self,row):
        if 0 <= row < len(self.profiles):
            doc = self.profiles[row]
            self.current_profile = doc['id']
            self.profile_name.setText(doc['name'])
            self.profile_python.setText(doc['python'])
            self.profile_timeout.setValue(doc.get('timeout',300))
            self.profile_env.setPlainText(json.dumps(doc.get('env',{}),indent=2))

    def new_profile(self):
        self.current_profile = uuid.uuid4().hex[:12]
        self.profile_name.setText('NEW LOADOUT')
        self.profile_python.setText(python_executable())
        self.profile_env.setPlainText('{}')

    def save_profile(self):
        def action():
            env = json.loads(self.profile_env.toPlainText())
            if not isinstance(env,dict) or not self.profile_name.text().strip():
                raise ValueError('A name and environment JSON object are required')
            if not Path(self.profile_python.text()).is_file():
                raise ValueError('Select an existing Python executable')
            self.store.put('profile',self.current_profile,{'id':self.current_profile,
                'name':self.profile_name.text().strip(),'python':self.profile_python.text(),
                'timeout':self.profile_timeout.value(),'env':env})
            self.refresh_lists()
            self.notice('LOADOUT SAVED')
        self.safe(action)

    def save_shared(self):
        self.safe(lambda:self.store.set_shared(self.shared_key.text(),json.loads(self.shared_value.toPlainText())))
        self.refresh_runtime()

    def load_operator(self,row):
        if 0 <= row < len(self.operators):
            doc = self.operators[row]
            self.current_operator = doc['id']
            self.operator_name.setText(doc['name'])
            self.operator_project.setCurrentIndex(self.operator_project.findData(doc['project']))
            self.operator_profile.setCurrentIndex(self.operator_profile.findData(doc['profile']))

    def new_operator(self):
        self.current_operator = uuid.uuid4().hex[:12]
        self.operator_name.setText('NEW OPERATOR')

    def save_operator(self):
        if not self.operator_name.text().strip():
            return self.notice('Enter an operator name')
        self.store.put('operator',self.current_operator,{'id':self.current_operator,
            'name':self.operator_name.text().strip(),'project':self.operator_project.currentData(),
            'profile':self.operator_profile.currentData()})
        self.refresh_lists()
        self.notice('OPERATOR SAVED')

    def deploy_project(self):
        self.safe(lambda:self.launch(self.lobby_project.currentData(),self.lobby_profile.currentData()))

    def launch(self, project_id, profile_id, operator='Local operator'):
        if len(self.runner.jobs) >= self.runner.max_parallel:
            raise ValueError('All execution slots are busy')
        ident = self.runner.launch(self.store.get('project',project_id),self.store.get('profile',profile_id),operator)
        self.notice('DEPLOYED // '+ident[:8])
        self.navigate('CONSOLE')
        return ident

    def deploy_operator(self):
        def action():
            doc = self.store.get('operator',self.current_operator)
            if not doc:
                raise ValueError('Save this operator first')
            return self.launch(doc['project'],doc['profile'],doc['name'])
        self.safe(action)

    def run_editor(self):
        if self.save_project():
            self.safe(lambda:self.launch(self.current_project,self.lobby_profile.currentData()))

    def load_workflow(self,row):
        if 0 <= row < len(self.workflows):
            doc = self.workflows[row]
            self.current_workflow = doc['id']
            self.workflow_name.setText(doc['name'])
            self.workflow_json.setPlainText(json.dumps({'nodes':doc['nodes']},indent=2))

    def new_workflow(self):
        self.current_workflow = uuid.uuid4().hex[:12]
        self.workflow_name.setText('NEW OPERATION')
        self.workflow_json.setPlainText('{"nodes": []}')

    def preview_map(self):
        try:
            data = json.loads(self.workflow_json.toPlainText())
            if isinstance(data,dict) and isinstance(data.get('nodes'),list):
                projects = {p['id']:p['name'] for p in self.projects}
                profiles = {p['id']:p['name'] for p in self.profiles}
                self.node_table.setRowCount(len(data['nodes']))
                for row,node in enumerate(data['nodes']):
                    values = [str(node.get('id','')),projects.get(node.get('project'),'Missing project'),
                              profiles.get(node.get('profile','default'),'Missing loadout'),', '.join(node.get('depends_on',[]))]
                    for col,value in enumerate(values):
                        self.node_table.setItem(row,col,QTableWidgetItem(value))
            validate_workflow(data,{p['id'] for p in self.projects})
            self.map_view.nodes = data['nodes']
            self.map_view.update()
            self.map_state.setText('GRAPH VALID // READY TO SAVE')
        except (ValueError,TypeError,KeyError,AttributeError) as exc:
            self.map_state.setText('GRAPH: '+str(exc))

    def add_node(self):
        def action():
            data = json.loads(self.workflow_json.toPlainText())
            nodes = data.setdefault('nodes',[])
            dialog = NodeDialog(self,nodes)
            if not dialog.exec():return
            nodes.append(dialog.value())
            self.workflow_json.setPlainText(json.dumps(data,indent=2))
        self.safe(action)

    def edit_node(self):
        def action():
            row=self.node_table.currentRow()
            if row<0:return self.notice('Select a step in the table first')
            data=json.loads(self.workflow_json.toPlainText());node=data['nodes'][row]
            dialog=NodeDialog(self,data['nodes'],node)
            if not dialog.exec():return
            replacement=dialog.value();old=node['id'];data['nodes'][row]=replacement
            for n in data['nodes']:
                n['depends_on']=[replacement['id'] if d==old else d for d in n.get('depends_on',[])]
            validate_workflow(data,{p['id'] for p in self.projects})
            self.workflow_json.setPlainText(json.dumps(data,indent=2))
        self.safe(action)

    def remove_node(self):
        def action():
            row=self.node_table.currentRow()
            if row<0:return self.notice('Select a step in the table first')
            data=json.loads(self.workflow_json.toPlainText());removed=data['nodes'].pop(row)['id']
            for node in data['nodes']:
                node['depends_on']=[d for d in node.get('depends_on',[]) if d!=removed]
            self.workflow_json.setPlainText(json.dumps(data,indent=2))
        self.safe(action)

    def fix_node_ids(self):
        def action():
            data=json.loads(self.workflow_json.toPlainText());data['nodes']=repair_node_ids(data['nodes'])
            self.workflow_json.setPlainText(json.dumps(data,indent=2))
            self.notice('STEP LABELS MADE UNIQUE // Dependencies on an old duplicate label refer to its first occurrence. Review before saving.')
        self.safe(action)

    def save_workflow(self):
        def action():
            doc = json.loads(self.workflow_json.toPlainText())
            validate_workflow(doc,{p['id'] for p in self.projects})
            profile_ids = {p['id'] for p in self.profiles}
            if any(n.get('profile','default') not in profile_ids for n in doc['nodes']):
                raise ValueError('One or more nodes reference an unknown profile')
            if not self.workflow_name.text().strip():
                raise ValueError('Map name is required')
            doc.update(id=self.current_workflow,name=self.workflow_name.text().strip())
            self.store.put('workflow',self.current_workflow,doc)
            self.refresh_lists()
            self.notice('MAP SAVED')
            return doc
        return self.safe(action)

    def deploy_workflow(self):
        doc = self.save_workflow()
        if doc:
            self.safe(lambda:self.runner.start_workflow(doc,{p['id']:p for p in self.projects},
                {p['id']:p for p in self.profiles},{p['id']:p for p in self.operators}))
            self.notice('WORKFLOW DEPLOYMENT REQUESTED')

    def receive_output(self,ident,text):
        self.console.feed(ident,text)
        for index in range(self.console_runs.count()-1,0,-1):
            if self.console_runs.itemData(index) not in self.console.streams:
                self.console_runs.removeItem(index)
        if self.console_runs.findData(ident) < 0:
            self.console_runs.addItem(ident,ident)
        if hasattr(self,'plugin_host'):
            self.plugin_host.emit('output',ident,text)

    def clear_console(self):
        self.console.clear()
        self.console_runs.clear()
        self.console_runs.addItem('ALL RUNS // GROUPED',None)

    def refresh_runtime(self):
        if not hasattr(self,'history'):
            return
        self.lobby_metrics.setText(f'{len(self.projects):02} PROJECTS  /  {len(self.operators):02} OPERATORS\n{len(self.runner.jobs):02} ACTIVE  /  {self.runner.max_parallel:02} SLOTS')
        for stat, value in zip(self.preview.stats.values(), [len(self.projects),len(self.operators),
                len(self.workflows),len(self.profiles),len(self.runner.jobs),self.runner.max_parallel]):
            stat.set_value(min(100,value))
        data = self.preview.canvas.item_data
        for key, value in zip(['damage','firepower','accuracy','mobility','handling','range_stat'],
                [len(self.projects),len(self.operators),len(self.workflows),len(self.profiles),len(self.runner.jobs),self.runner.max_parallel]):
            setattr(data,key,min(100,value))
        self.lobby_jobs.clear()
        for ident, job in self.runner.jobs.items():
            self.lobby_jobs.addItem(f"{job['name']}\n{job['status'].upper()} // {ident[:8]}")
        self.fill_combo(self.stop_run,[{'id':i,'name':j['name']+' // '+i[:8]} for i,j in self.runner.jobs.items()])
        shared = self.store.shared()
        self.shared_table.setRowCount(len(shared))
        for row,(key,value) in enumerate(shared.items()):
            self.shared_table.setItem(row,0,QTableWidgetItem(key))
            self.shared_table.setItem(row,1,QTableWidgetItem(json.dumps(value)))
        rows = self.store.history()
        selected = self.history.currentRow()
        selected_id = self.history.item(selected,5).text() if selected >= 0 and self.history.item(selected,5) else None
        self.history.blockSignals(True)
        self.history.setRowCount(len(rows))
        for row,(ident,name,status,started,ended,code) in enumerate(rows):
            values = [name,status,time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(started)),
                      f'{(ended or time.time())-started:.1f}s',str(code) if code is not None else '—',ident]
            for col,value in enumerate(values):
                self.history.setItem(row,col,QTableWidgetItem(value))
            if ident == selected_id:
                self.history.selectRow(row)
        self.history.blockSignals(False)
        if self.runner.workflow:
            self.map_view.nodes = self.runner.workflow['nodes']
            self.map_view.update()
            self.map_state.setText('ACTIVE // '+self.runner.workflow['name'])

    def show_history_log(self):
        row = self.history.currentRow()
        if row >= 0:
            item = self.history.item(row,5)
            if item:
                ident = item.text()
                job = self.runner.jobs.get(ident)
                result = self.store.db.execute('SELECT log FROM runs WHERE id=?',(ident,)).fetchone()
                self.history_log.clear()
                self.history_log.feed(ident,job['log'] if job else result[0] if result else '')
                self.history_log.select_run(ident)

    def export_log(self):
        filename, _ = QFileDialog.getSaveFileName(self,'Export console','','Text (*.txt)')
        if filename:
            self.safe(lambda:Path(filename).write_text(self.console.toPlainText(),encoding='utf-8'))

    def export_workspace(self):
        filename, _ = QFileDialog.getSaveFileName(self,'Export configuration','','JSON (*.json)')
        if filename:
            docs = {kind:self.store.list(kind) for kind in ('project','profile','operator','workflow')}
            docs['shared'] = self.store.shared()
            self.safe(lambda:Path(filename).write_text(json.dumps(docs,indent=2),encoding='utf-8'))

    def export_bundle(self):
        if not self.dirty_check():
            return
        filename, _ = QFileDialog.getSaveFileName(self,'Export projects, maps and shared loadouts','','Workspace bundle (*.zip)')
        if not filename:
            return
        self.safe(lambda:self.write_bundle(filename))

    def write_bundle(self,filename):
        data = {kind:self.store.list(kind) for kind in ('project','profile','operator','workflow')}
        data['shared'] = self.store.shared()
        with zipfile.ZipFile(filename,'w',zipfile.ZIP_DEFLATED) as archive:
            for project in data['project']:
                path = Path(project['script'])
                name = 'projects/'+project['id']+'/main.py'
                archive.write(path,name)
                project['script'] = name
                project['cwd'] = 'projects/'+project['id']
            archive.writestr('workspace.json',json.dumps(data,indent=2))
        self.notice('BUNDLE EXPORTED // ENTRY SCRIPTS AND CONFIGURATION')

    def import_bundle(self):
        if not self.dirty_check():
            return
        filename, _ = QFileDialog.getOpenFileName(self,'Import workspace bundle','','Workspace bundle (*.zip)')
        if not filename:
            return
        self.safe(lambda:self.read_bundle(filename))

    def read_bundle(self,filename):
        with zipfile.ZipFile(filename) as archive:
            if sum(info.file_size for info in archive.infolist()) > 50_000_000:
                raise ValueError('Bundle exceeds the 50 MB limit')
            data = json.loads(archive.read('workspace.json'))
            remap = {kind:{doc['id']:uuid.uuid4().hex[:12] for doc in data.get(kind,[])}
                     for kind in ('project','profile','operator','workflow')}
            # Validate and read all content before creating any imported project.
            codes = {}
            for project in data.get('project',[]):
                codes[project['id']] = archive.read(project['script']).decode('utf-8')
            projects = set(remap['project'])
            for workflow in data.get('workflow',[]):
                validate_workflow(workflow,projects)
                for node in workflow['nodes']:
                    if node.get('profile','default') not in remap['profile']:
                        raise ValueError('Bundle workflow references an unknown profile')
                    if node.get('operator') and node['operator'] not in remap['operator']:
                        raise ValueError('Bundle workflow references an unknown operator')
            for operator in data.get('operator',[]):
                if operator['project'] not in remap['project'] or operator['profile'] not in remap['profile']:
                    raise ValueError('Bundle operator references an unknown project/profile')
            for kind in ('project','profile','operator','workflow'):
                for original in data.get(kind,[]):
                    doc = dict(original)
                    old = doc['id']
                    doc['id'] = remap[kind][old]
                    if kind == 'project':
                        folder = self.store.root/'projects'/doc['id']
                        folder.mkdir(parents=True)
                        script = folder/'main.py'
                        script.write_text(codes[old],encoding='utf-8')
                        doc.update(script=str(script),cwd=str(folder))
                    elif kind == 'operator':
                        doc['project'] = remap['project'][doc['project']]
                        doc['profile'] = remap['profile'][doc['profile']]
                    elif kind == 'workflow':
                        doc['nodes'] = [dict(node) for node in doc['nodes']]
                        for node in doc['nodes']:
                            node['project'] = remap['project'][node['project']]
                            node['profile'] = remap['profile'][node.get('profile','default')]
                            if node.get('operator'):
                                node['operator'] = remap['operator'][node['operator']]
                    self.store.put(kind,doc['id'],doc)
            for key,value in data.get('shared',{}).items():
                if key not in self.store.shared():
                    self.store.set_shared(key,value)
        self.refresh_lists()
        self.notice('BUNDLE IMPORTED // NEW IDS // EXISTING SHARED KEYS PRESERVED')

    def load_schedule(self,row):
        if 0 <= row < len(self.schedules):
            doc = self.schedules[row]
            self.current_schedule = doc['id']
            self.schedule_name.setText(doc['name'])
            self.schedule_workflow.setCurrentIndex(self.schedule_workflow.findData(doc['workflow']))
            self.schedule_interval.setValue(doc['interval'])
            self.schedule_enabled.setChecked(doc['enabled'])

    def new_schedule(self):
        self.current_schedule = uuid.uuid4().hex[:12]
        self.schedule_name.setText('NEW MISSION')
        self.schedule_enabled.setChecked(False)

    def save_schedule(self):
        if not self.schedule_name.text().strip() or not self.schedule_workflow.currentData():
            return self.notice('Select a saved map and enter a mission name')
        ident = self.current_schedule or uuid.uuid4().hex[:12]
        self.current_schedule = ident
        self.store.put('schedule',ident,{'id':ident,'name':self.schedule_name.text().strip(),
            'workflow':self.schedule_workflow.currentData(),'interval':self.schedule_interval.value(),
            'enabled':self.schedule_enabled.isChecked(),'next_due':time.time()+self.schedule_interval.value()})
        self.refresh_lists()
        self.notice('MISSION SAVED')

    def disable_schedules(self):
        for doc in self.store.list('schedule'):
            doc['enabled'] = False
            self.store.put('schedule',doc['id'],doc)
        self.schedule_enabled.setChecked(False)
        self.notice('ALL RECURRING MISSIONS DISABLED')

    def stop_operations(self):
        self.disable_schedules()
        self.runner.stop_all()

    def tick_schedules(self):
        active = [doc for doc in self.store.list('schedule') if doc['enabled']]
        self.mission_status.setText('\n'.join(f"{doc['name']} // NEXT IN {max(0,int(doc['next_due']-time.time()))}s" for doc in active) or 'NO ACTIVE RECURRING MISSIONS')
        if self.runner.workflow or self.runner.jobs:
            return
        for doc in active:
            if doc['next_due'] > time.time():
                continue
            workflow = self.store.get('workflow',doc['workflow'])
            try:
                if not workflow:
                    raise ValueError('Scheduled map no longer exists')
                self.runner.start_workflow(workflow,{p['id']:p for p in self.store.list('project')},
                    {p['id']:p for p in self.store.list('profile')},
                    {p['id']:p for p in self.store.list('operator')})
                doc['next_due'] = time.time()+doc['interval']
            except (ValueError,TypeError,KeyError) as exc:
                doc['enabled'] = False
                self.receive_output('mission',f"{doc['name']}: {exc}\n")
            self.store.put('schedule',doc['id'],doc)
            break

    def assign_asset(self,kind):
        def action():
            filename, _ = QFileDialog.getOpenFileName(self,'Choose asset','',
                MODEL_FILTER if kind == 'model' else 'Images (*.png *.jpg *.jpeg *.webp *.svg)')
            if not filename:
                return
            name = self.asset_name.currentData()
            if kind not in ('background','logo') and not name:
                raise ValueError('An exact item name is required')
            ident = uuid.uuid4().hex
            if kind == 'model':
                task = AssetTask(ident,lambda:import_model_bundle(filename,ASSETS.root))
            else:
                task = AssetTask(ident,lambda:(ASSETS.import_file(filename,kind),[]))
            self.asset_tasks[ident] = (task,name,kind)
            task.signals.finished.connect(self.asset_imported)
            self.asset_feedback.setText('Importing '+Path(filename).name+' in the background… You can keep using the workspace.')
            ASSETS.pool.start(task)
        self.safe(action)

    def asset_imported(self,ident,result,error):
        task,name,kind = self.asset_tasks.pop(ident)
        if self._closing:
            return
        if error:
            self.asset_feedback.setText('Import failed: '+error)
            return
        relative,warnings = result
        def assign():
            if kind == 'background':
                ASSETS.set_background(relative)
            elif kind=='logo':
                data=json.loads(json.dumps(ASSETS.manifest));data['logo']=relative;ASSETS.save_manifest(data)
            else:
                ASSETS.set_item(name,**{kind:relative},texture_mode='override' if kind=='texture' else 'automatic' if kind=='model' else None)
            self.reload_assets()
            index = self.asset_name.findData(name)
            display = self.asset_name.itemText(index) if index>=0 else 'the selected item'
            self.asset_feedback.setText('Assigned '+kind+' to '+('the lobby background' if kind=='background' else display)+
                (' • '+ '; '.join(warnings) if warnings else ' • Loading preview…'))
            for card in self.findChildren(self.theme.LoadoutCard):
                card.update()
        self.safe(assign)

    def use_automatic_materials(self):
        name=self.asset_name.currentData()
        if name:self.safe(lambda:ASSETS.set_item(name,texture_mode='automatic'))

    def inspect_asset(self,*args):
        if not hasattr(self,'asset_feedback'):
            return
        name = self.asset_name.currentData()
        if name is None:return
        if hasattr(self,'asset_canvas'):
            item=self.theme.LoadoutItem(self.asset_name.currentText(),'ASSET STUDIO')
            item.asset_key=name;self.asset_canvas.set_item(item);self.asset_canvas.paused=True
        self.asset_rotation.setText(json.dumps(ASSETS.entry(name).get('rotation',[0,0,0])))
        self.asset_image.setPixmap(ASSETS.icon(name,QSize(300,140),self.devicePixelRatioF()).pixmap(QSize(300,140)))
        if ASSETS.entry(name).get('model'):
            self.asset_feedback.setText('Inspecting model materials and textures…')
            ASSETS.request_model(name)
        else:
            self.asset_feedback.setText('No custom model assigned. Choose Assign 3D Model to add one; procedural previews stay available.')

    def asset_inspected(self,name,scene,error):
        if self._closing or name!=self.asset_name.currentData():
            return
        if error:
            self.asset_feedback.setText('Preview could not load: '+error)
        elif scene:
            textures = sum(m['image'] is not None for m in scene.materials.values())
            self.asset_feedback.setText(f'{self.asset_name.currentText()} • {scene.source_faces:,} triangles • {textures} textured materials • GPU-ready'+
                ('\n'+ '; '.join(scene.warnings) if scene.warnings else '\nReady. Select this project in the Lobby to orbit its model.'))

    def reload_assets(self,force=False):
        ASSETS.reload(force=force)
        # Upgrade old name-based project artwork once, retaining the original item entry.
        data=json.loads(json.dumps(ASSETS.manifest));changed=False
        items=data.setdefault('items',{})
        for project in self.projects:
            key='project:'+project['id']
            if key not in items and project['name'] in items:
                items[key]=dict(items[project['name']]);changed=True
        if changed:ASSETS.save_manifest(data)
        if hasattr(self,'asset_manifest'):
            self.asset_manifest.setPlainText(json.dumps(ASSETS.manifest,indent=2))
        self.background.update()
        logo=ASSETS.image(ASSETS.manifest.get('logo'))
        self.brand_logo.setVisible(not logo.isNull())
        if not logo.isNull():self.brand_logo.setPixmap(logo.scaled(self.brand_logo.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        self.preview.canvas.update()
        if hasattr(self,'asset_name'):
            previous = self.asset_name.currentData()
            self.asset_name.blockSignals(True)
            self.asset_name.clear()
            for project in self.projects:
                self.asset_name.addItem(project['name']+' // Primary','project:'+project['id'])
                for slot,title in [('secondary_target','Secondary'),('context','Environment'),('tactical_hook','Tactical'),('lethal_hook','Output'),('perk1','Perk 1'),('perk2','Perk 2'),('perk3','Perk 3'),('specialty','Specialty'),('wildcard','Wildcard')]:
                    self.asset_name.addItem(project['name']+' // '+title,'loadout:'+project['id']+':'+slot)
            project_names={p['name'] for p in self.projects}
            for name in sorted(ASSETS.manifest.get('items',{})):
                if not name.startswith(('project:','loadout:')) and name not in project_names:
                    self.asset_name.addItem(name,name)
            index=self.asset_name.findData(previous)
            if index>=0:self.asset_name.setCurrentIndex(index)
            self.asset_name.blockSignals(False)
            self.inspect_asset()
        if hasattr(self,'project_loadout_screen') and self.project_loadout_screen.project:
            self.project_loadout_screen.refresh()
        self.notice('ASSETS RELOADED'+(' // '+'; '.join(ASSETS.errors) if ASSETS.errors else ''))

    def save_settings(self):
        advanced=self.settings_deck.values()
        if not QColor(advanced.get('ambient_accent','#ff4500')).isValid():return self.notice('Enter a valid ambient glow colour')
        url = QUrl(self.ollama_url.text().strip())
        if self.ai_enabled.isChecked() and (url.scheme() not in ('http','https') or not url.host()):
            return self.notice('Enter a valid http(s) Ollama URL')
        self.settings = {**self.settings,**advanced,'parallel':self.parallel.value(),'motion':self.motion.isChecked(),
            'ai_enabled':self.ai_enabled.isChecked(),'ollama_url':self.ollama_url.text().strip().rstrip('/'),
            'ollama_model':self.ollama_model.currentData() or '',
            'output_theme':self.console_theme.currentText(),
            'output_styles':self.settings.get('output_styles',{}),
            'output_font_size':self.console_font_size.value(),
            'editor_font_size':self.editor_size.value(),'ui_scale':self.ui_scale.value()}
        self.store.put('settings','app',self.settings)
        data=json.loads(json.dumps(ASSETS.manifest));data['background_opacity']=advanced['background_opacity']/100;ASSETS.save_manifest(data)
        self.audio.configure(self.settings)
        self.runner.max_parallel = self.parallel.value()
        if not self.settings['ai_enabled'] and self.ai_reply:
            self.ai_reply.abort()
        self.apply_motion();self.apply_editor_preferences()
        self.notice('SETTINGS SAVED // AI '+('ENABLED' if self.settings['ai_enabled'] else 'DISABLED'))
        self.runner._schedule()
        self.sync_plugin_environment()

    def apply_motion(self):
        enabled = self.settings.get('motion',True)
        self.background.configure(self.settings)
        if enabled:
            self.background.timer.start(round(1000/self.settings.get('ambient_fps',28)))
        else:
            self.background.timer.stop()
        self.preview.canvas.paused = not (enabled and self.settings.get('model_auto_orbit',True))
        self.ai_generate.setEnabled(self.settings.get('ai_enabled',False) and self.ai_reply is None)
        self.ai_apply.setEnabled(self.settings.get('ai_enabled',False))

    def generate_draft(self):
        if not self.settings.get('ai_enabled') or self.ai_reply:
            return
        if not self.settings.get('ollama_model') or not self.ai_prompt.toPlainText().strip():
            return self.notice('Set an installed model in settings and enter a prompt')
        request = QNetworkRequest(QUrl(self.settings['ollama_url']+'/api/generate'))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader,'application/json')
        request.setTransferTimeout(120000)
        body = {'model':self.settings['ollama_model'],'prompt':self.ai_prompt.toPlainText(),
            'system':'Write Python code only. Do not use Markdown fences. Code is a draft for human review.', 'stream':False}
        self.ai_reply = self.network.post(request,QByteArray(json.dumps(body).encode()))
        self.ai_reply.finished.connect(self.finish_draft)
        self.ai_generate.setEnabled(False)
        self.notice('OLLAMA // REQUESTING DRAFT')

    def ollama_toggle(self,enabled):
        if enabled:
            self.refresh_models()
        else:
            if self.models_reply:
                self.models_reply.abort()
            self.models_status.setText('Model discovery disabled. Save settings to disable assistance.')

    def refresh_models(self):
        if not self.ai_enabled.isChecked():
            self.models_status.setText('Enable optional assistance to list downloaded models.')
            return
        url = QUrl(self.ollama_url.text().strip().rstrip('/')+'/api/tags')
        if url.scheme() not in ('http','https') or not url.host():
            self.models_status.setText('Enter a valid HTTP(S) Ollama URL.')
            return
        if self.models_reply:
            self.models_reply.abort()
        request = QNetworkRequest(url)
        request.setTransferTimeout(10000)
        reply = self.network.get(request)
        self.models_reply = reply
        self.models_status.setText('Discovering downloaded models…')
        self.refresh_models_button.setEnabled(False)
        reply.finished.connect(lambda:self.finish_models(reply,url))

    def finish_models(self,reply,url):
        if self._closing:
            reply.deleteLater()
            self.models_reply = None
            return
        if reply is not self.models_reply:
            reply.deleteLater()
            return
        self.models_reply = None
        self.refresh_models_button.setEnabled(True)
        if url.toString() != self.ollama_url.text().strip().rstrip('/')+'/api/tags':
            reply.deleteLater()
            self.refresh_models()
            return
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.models_status.setText('Ollama unavailable: '+reply.errorString())
        else:
            try:
                data = json.loads(bytes(reply.readAll()).decode('utf-8'))
                models = data.get('models',[])
                if not isinstance(models,list):
                    raise ValueError('Invalid models response')
                previous = self.ollama_model.currentData() or self.settings.get('ollama_model')
                self.ollama_model.clear()
                for model in models:
                    name = model.get('name') or model.get('model')
                    if not isinstance(name,str) or not name:
                        continue
                    size = float(model.get('size',0))/1_000_000_000
                    self.ollama_model.addItem(f'{name} // {size:.1f} GB',name)
                selected = self.ollama_model.findData(previous)
                if selected >= 0:
                    self.ollama_model.setCurrentIndex(selected)
                self.models_status.setText(f'{self.ollama_model.count()} downloaded model(s). Save settings to use your selection.'
                    if self.ollama_model.count() else 'No downloaded models found on this server.')
            except (ValueError,TypeError,AttributeError) as exc:
                self.models_status.setText('Invalid Ollama response: '+str(exc))
        reply.deleteLater()

    def build_plugins(self):
        plugins_page=QWidget();root=QVBoxLayout(plugins_page);root.setContentsMargins(0,12,0,0)
        self.workshop_tabs.addTab(plugins_page,'PLUGINS')
        # Existing plugin links still resolve to the Workshop parent.
        self.page_ids['PLUGINS']=self.page_ids['WORKSHOP']
        self.page_widgets['PLUGINS']=self.page_widgets['WORKSHOP']
        self.plugin_search=QLineEdit();self.plugin_search.setPlaceholderText('Search plugins by name, ID or description…')
        self.plugin_search.textChanged.connect(self.filter_plugins)
        self.plugins_table = QTableWidget(0,4)
        self.plugins_table.setHorizontalHeaderLabels(['PLUGIN','STATE','DESCRIPTION','ERROR'])
        self.plugins_table.setColumnHidden(2,True);self.plugins_table.setColumnHidden(3,True)
        self.plugins_table.setColumnWidth(0,190);self.plugins_table.setColumnWidth(1,90)
        self.plugins_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.plugins_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.plugins_table.horizontalHeader().setStretchLastSection(True)
        split = QSplitter(Qt.Orientation.Horizontal)
        browser=QWidget();browser_box=QVBoxLayout(browser);browser_box.setContentsMargins(0,0,0,0)
        browser_box.addWidget(self.plugin_search);browser_box.addWidget(self.plugins_table)
        browser.setMinimumWidth(230);browser.setMaximumWidth(360)
        split.addWidget(browser)
        self.plugin_builder = PluginBuilder(self)
        split.addWidget(self.plugin_builder)
        split.setSizes([290,1100]);split.setStretchFactor(1,1)
        root.addWidget(split,1)
        self.plugins_table.cellDoubleClicked.connect(lambda row,col:self.edit_selected_plugin())
        self.plugins_table.cellClicked.connect(lambda row,col:self.edit_selected_plugin())
        from gui_components import horizontal_strip
        toolbar_scroll,actions = horizontal_strip(52)
        actions.addWidget(button('RESCAN PLUGINS',self.refresh_plugins))
        actions.addWidget(button('ENABLE SELECTED',lambda:self.toggle_plugin(True),True))
        actions.addWidget(button('DISABLE SELECTED',lambda:self.toggle_plugin(False)))
        actions.addWidget(button('NEW PLUGIN IN BUILDER',self.create_plugin))
        actions.addWidget(button('EDIT SELECTED',self.edit_selected_plugin))
        root.addWidget(toolbar_scroll)
        from gui_components import horizontal_strip
        action_scroll,self.plugin_actions=horizontal_strip();root.addWidget(action_scroll)
        root.addWidget(label('Place plugin.json and plugin.py in Pylerium/plugins/<folder>/. Enable only code you trust: plugins have the same permissions as this application. Newly discovered plugins stay disabled. Running scripts keep the enabled-plugin snapshot from deployment.',12,'#9aabb4'))

    def refresh_plugins(self):
        if not hasattr(self,'plugin_host'):
            return
        self.plugin_descriptors = self.plugin_host.descriptors()
        self.plugins_table.setRowCount(len(self.plugin_descriptors))
        for row,desc in enumerate(self.plugin_descriptors):
            values = [desc.get('name',desc['id']), 'ENABLED' if desc['id'] in self.plugin_host.enabled() else 'DISABLED',
                      desc.get('description',''),desc.get('error','')]
            for col,value in enumerate(values):
                self.plugins_table.setItem(row,col,QTableWidgetItem(value))
            self.plugins_table.item(row,0).setToolTip(desc.get('description','')+('\n'+desc['error'] if desc.get('error') else ''))
        self.filter_plugins()

    def filter_plugins(self):
        if not hasattr(self,'plugin_descriptors'):return
        query=self.plugin_search.text().casefold().strip()
        for row,desc in enumerate(self.plugin_descriptors):
            self.plugins_table.setRowHidden(row,query not in ' '.join(str(desc.get(key,'')) for key in ('id','name','description')).casefold())
        if self.plugins_table.currentRow()>=0 and self.plugins_table.isRowHidden(self.plugins_table.currentRow()):self.plugins_table.clearSelection();self.plugins_table.setCurrentCell(-1,-1)

    def toggle_plugin(self,enabled):
        row = self.plugins_table.currentRow()
        if row < 0:
            return self.notice('Select a plugin first')
        desc = self.plugin_descriptors[row]
        def action():
            if enabled:
                self.plugin_host.enable(desc)
            else:
                self.navigate('PLUGINS')
                self.plugin_host.disable(desc['id'])
            self.store.put('settings','plugins',self.plugin_host.enabled())
            self.refresh_plugins()
            self.notice('PLUGIN '+('ENABLED' if enabled else 'DISABLED')+' // '+desc['id'])
        self.safe(action)

    def sync_plugin_environment(self):
        self.runner.enabled_plugins = self.plugin_host.enabled()
        self.runner.plugin_root = str(self.plugin_host.root.resolve())
        styles = dict(self.settings.get('output_styles',{}))
        styles.update(self.plugin_styles)
        self.runner.output_settings = {'theme':self.settings.get('output_theme','cyber'),'styles':styles}
        self.status.configure(self.settings,styles)
        self.console.setStyleSheet('QPlainTextEdit {font-family:Consolas;font-size:'+str(self.settings.get('output_font_size',13))+'px;}')

    def create_plugin(self):
        self.plugin_builder.new_plugin()

    def edit_selected_plugin(self):
        row=self.plugins_table.currentRow()
        if row<0:return self.notice('Select a plugin first')
        descriptor=self.plugin_descriptors[row]
        if descriptor.get('error'):return self.notice(descriptor['error'])
        self.plugin_builder.load(descriptor)

    def terminal_example(self):
        return "from ultimate_terminal import terminal as term, Style, RGB\n\nterm.section('OPERATION REPORT')\nterm.success('Connected')\nterm.warning('This is a warning')\nterm.add_style('custom', Style(foreground=RGB.from_hex('#ff7b1c'), bold=True))\nterm.print('Custom output', style='custom')\nterm.print(term.gradient('PYLERIUM // LOCAL OPERATIONS'))\nterm.table([['Build', 'OK'], ['Tests', 'Passed']], headers=['Stage', 'Result'])\nfor value in range(0, 101, 20):\n    term.progress(value, label='Preparing', newline=False)\nprint()\nterm.success('Complete')\n"

    def insert_terminal_example(self):
        self.code.insertPlainText(self.terminal_example())
        self.code.document().setModified(True)

    def validated_output_styles(self,value):
        styles = json.loads(value)
        if not isinstance(styles,dict):
            raise ValueError('Output styles must be a JSON object')
        for name,config in styles.items():
            if not isinstance(config,dict):
                raise ValueError('Each style must be a JSON object')
            checked = dict(config)
            for key in ('foreground','background'):
                if checked.get(key):
                    checked[key] = RGB.from_hex(checked[key])
            OutputStyle(**checked)
        return styles

    def save_output_settings(self):
        def action():
            styles = self.validated_output_styles(self.output_styles.text())
            self.settings.update(output_theme=self.console_theme.currentText(),output_styles=styles,
                output_font_size=self.console_font_size.value())
            self.store.put('settings','app',self.settings)
            self.sync_plugin_environment()
            self.notice('OUTPUT STYLE SAVED // APPLIES TO NEW RUNS')
        self.safe(action)

    def preview_terminal(self):
        def action():
            stream = io.StringIO()
            term = Terminal(enabled=True,theme=self.console_theme.currentText(),force_truecolor=True)
            styles = self.validated_output_styles(self.output_styles.text())
            for name,config in styles.items():
                checked = dict(config)
                for key in ('foreground','background'):
                    if checked.get(key):
                        checked[key] = RGB.from_hex(checked[key])
                term.add_style(name,OutputStyle(**checked))
            with redirect_stdout(stream):
                term.section('OUTPUT PREVIEW')
                term.success('Connection ready')
                term.error('Example error')
                term.warning('Example warning')
                term.print(term.gradient('PYLERIUM'))
                term.table([['Runner','Ready'],['Shared state','Connected']],headers=['Component','Status'])
                for name in styles:
                    term.print('Custom style // '+name,style=name)
                term.progress(25,label='Progress',newline=False)
                term.progress(100,label='Progress',newline=False)
                print()
            self.receive_output('output-preview',stream.getvalue())
            self.console.render()
        self.safe(action)

    def finish_draft(self):
        reply = self.ai_reply
        self.ai_reply = None
        if self._closing:
            reply.deleteLater()
            return
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.notice('OLLAMA // '+reply.errorString())
        else:
            try:
                data = json.loads(bytes(reply.readAll()).decode())
                cleaned = clean_python_response(data.get('response',''))
                self.ai_draft.setPlainText(cleaned)
                try:
                    validate_python(cleaned)
                    self.notice('PYTHON DRAFT READY // REVIEW BEFORE USE')
                except SyntaxError as exc:
                    self.notice(f'DRAFT NEEDS CORRECTION // line {exc.lineno}: {exc.msg}')
            except (ValueError,AttributeError) as exc:
                self.notice('OLLAMA RESPONSE ERROR // '+str(exc))
        reply.deleteLater()
        self.apply_motion()

    def apply_draft(self):
        if self.settings.get('ai_enabled') and self.ai_draft.toPlainText() and self.dirty_check():
            try:
                cleaned = validate_python(clean_python_response(self.ai_draft.toPlainText()))
            except (ValueError,SyntaxError) as exc:
                self.notice('DRAFT NOT INSERTED // '+str(exc))
                return
            self.code.setPlainText(cleaned)
            self.code.document().setModified(True)

    def fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def keyPressEvent(self,event):
        if event.key() == Qt.Key.Key_F11:
            self.fullscreen()
        elif event.key() == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.navigate('LOBBY')
        else:
            super().keyPressEvent(event)

    def closeEvent(self,event):
        if not self.dirty_check():
            event.ignore()
            return
        if not self.plugin_builder.confirm_discard():
            event.ignore()
            return
        if self.runner.jobs:
            answer = QMessageBox.question(self,'Active operations','Stop running operations and close?')
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.runner.stop_all()
            for job in list(self.runner.jobs.values()):
                job['process'].waitForFinished(2000)
            self.runner._schedule()
            if self.runner.jobs:
                self.notice('Waiting for running processes to stop')
                event.ignore()
                return
        self._closing = True
        from model_preview import InteractiveModelCanvas
        for canvas in self.findChildren(InteractiveModelCanvas):
            canvas.shutdown_renderer()
        # Drain asset workers while Qt and their signal receivers still exist.
        ASSETS.pool.waitForDone()
        self.killchain.shutdown()
        if self.ai_reply:
            self.ai_reply.abort()
        if self.models_reply:
            self.models_reply.abort()
        for ident in list(self.plugin_host.enabled()):
            self.plugin_host.disable(ident)
        self.poll.stop()
        if self.settings.get('remember_window',True):
            self.settings['window_geometry']=bytes(self.saveGeometry().toHex()).decode()
            self.store.put('settings','app',self.settings)
        self.store.db.close()
        event.accept()
