"""Editable GUI starters importing the application's real shared components."""
from textwrap import dedent


def starter(body, imports=''):
    return ('from pylerium_gui import create_application, AppWindow, button, label, panel, run, configure_audio, play_cue\n'
            + imports + '\n' + dedent(body).strip() + '\n\n'
            + 'def main():\n    app = create_application("My application")\n'
              '    # Opt in to shared hover, click and task completion cues.\n    # configure_audio(enabled=True, volume=18)\n    window = MyWindow()\n    return run(window)\n\n'
              'if __name__ == "__main__":\n    raise SystemExit(main())\n')


GUI_TEMPLATES = {
    'GUI / Blank custom application': starter('''
        class MyWindow(AppWindow):
            def __init__(self):
                super().__init__('My custom application')
                # Your own layout: no workspace pages, header or application services.
                card, box = panel()
                box.addWidget(label('My tool', 24))
                self.output = label('Ready')
                box.addWidget(button('Run', lambda: self.output.setText('Done'), primary=True))
                box.addWidget(self.output)
                self.content.addWidget(card)
                self.content.addStretch()
    '''),

    'GUI / Panels and actions': starter('''
        class MyWindow(AppWindow):
            def __init__(self):
                super().__init__('MY APPLICATION', 'YOUR CUSTOM WORKSPACE')
                home = self.add_page('Home', 'Built from Pylerium’s shared style and components.')
                card, box = panel()
                box.addWidget(label('Start building here', 24))
                box.addWidget(button('Run action', lambda: self.notice('Action complete'), primary=True))
                home.addWidget(card)
                home.addStretch()
                self.add_action('My action', lambda: self.notice('Toolbar/menu action'), 'Ctrl+R')
    '''),
    'GUI / Forms and data pages': starter('''
        class MyWindow(AppWindow):
            def __init__(self):
                super().__init__('MY DATA TOOL')
                home = self.add_page('Dashboard', 'Your project at a glance.')
                home.addWidget(label('Welcome to your workspace', 24)); home.addStretch()
                settings = self.add_page('Settings', 'Reusable inputs and panels.')
                card, box = panel(); form = QFormLayout()
                self.name = QLineEdit('My tool'); self.mode = QComboBox()
                self.mode.addItems(['Local', 'Preview', 'Production'])
                self.parallel = QSpinBox(); self.parallel.setRange(1, 32)
                self.enabled = QCheckBox('Enable automatic updates')
                for title, widget in [('Name', self.name), ('Mode', self.mode),
                                      ('Workers', self.parallel), ('Updates', self.enabled)]:
                    form.addRow(title, widget)
                box.addLayout(form)
                box.addWidget(button('Apply settings', self.apply_settings, primary=True))
                settings.addWidget(card); settings.addStretch()
                records = self.add_page('Records', 'Editable application data.')
                self.table = QTableWidget(0, 2); self.table.setHorizontalHeaderLabels(['Name', 'State'])
                self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
                self.table.setAlternatingRowColors(True); records.addWidget(self.table)
                records.addWidget(button('Add record', self.add_record))
                self.add_action('Add record', self.add_record, 'Ctrl+N')

            def apply_settings(self):
                self.notice(f'Applied {self.name.text()} / {self.mode.currentText()}')

            def add_record(self):
                row = self.table.rowCount(); self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(f'Record {row + 1}'))
                self.table.setItem(row, 1, QTableWidgetItem('Ready'))
                self.navigate('Records')
    ''', 'from pylerium_gui import QFormLayout, QLineEdit, QComboBox, QSpinBox, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView\n'),
    'GUI / Complete component gallery': starter(r'''
        # These are the original widgets, not copies of their appearance.
        class MyWindow(AppWindow):
            def __init__(self):
                super().__init__('COMPONENT GALLERY', 'PYLERIUM / REUSABLE UI')
                controls = self.add_page('Controls', 'Buttons, inputs, menus, dialogs and data widgets.')
                card, box = panel(); row = QHBoxLayout()
                row.addWidget(button('Normal', lambda: self.notice('Normal button')))
                row.addWidget(button('Primary', lambda: self.notice('Primary button'), True))
                check = button('Toggle', lambda: self.notice('Toggled')); check.setCheckable(True); row.addWidget(check)
                disabled = button('Disabled', lambda: None); disabled.setEnabled(False); row.addWidget(disabled)
                row.addWidget(IconButton('⚙')); box.addLayout(row)
                form = QFormLayout()
                text = QLineEdit(); text.setPlaceholderText('Your text')
                combo = QComboBox(); combo.addItems(['Option one', 'Option two'])
                spin = QSpinBox(); spin.setRange(0, 100)
                slider = QSlider(Qt.Orientation.Horizontal); slider.setValue(65)
                date = QDateEdit(); date.setCalendarPopup(True)
                for name, widget in [('Text', text), ('Choice', combo), ('Number', spin),
                                     ('Slider', slider), ('Date', date), ('Check', QCheckBox('Enabled')),
                                     ('Radio', QRadioButton('Selected mode'))]: form.addRow(name, widget)
                box.addLayout(form)
                progress = QProgressBar(); progress.setValue(65); box.addWidget(progress)
                box.addWidget(button('Message dialog', lambda: QMessageBox.information(self, 'Information', 'Application-styled dialog')))
                box.addWidget(button('File picker', lambda: QFileDialog.getOpenFileName(self, 'Choose a file')))
                controls.addWidget(card)
                tabs = QTabWidget(); listing = QListWidget(); listing.addItems(['One', 'Two', 'Three'])
                tree = QTreeWidget(); tree.setHeaderLabels(['Project', 'State'])
                QTreeWidgetItem(tree, ['Example project', 'Ready'])
                table = QTableWidget(2, 2); table.setHorizontalHeaderLabels(['Name', 'Value'])
                for row in range(2):
                    table.setItem(row, 0, QTableWidgetItem(f'Item {row+1}'))
                    table.setItem(row, 1, QTableWidgetItem('Ready'))
                tabs.addTab(listing, 'List'); tabs.addTab(tree, 'Tree'); tabs.addTab(table, 'Table')
                controls.addWidget(tabs)
                cards = self.add_page('Original widgets', 'Optional individual cards, stats and item selectors.')
                example = theme().PRIMARY_ITEMS[0]
                weapon = LoadoutCard(example, 'primary'); cards.addWidget(weapon)
                selector = SelectorItem(example); cards.addWidget(selector)
                selector.clicked.connect(lambda: ItemSelectorDialog('Select item', theme().PRIMARY_ITEMS, self).exec())
                stat = StatBar('Accuracy'); stat.set_value(73); cards.addWidget(stat)
                sidebar = LoadoutSidebar(); sidebar.add_loadout(demo_loadout()); cards.addWidget(sidebar)
                cards.addStretch()
                editors = self.add_page('Editor and console', 'The same Python editor, focus card and ANSI console.')
                self.editor = WorkshopEditor(); self.editor.setPlainText('# Your application editor\nprint("Ready")\n')
                self.editor_card = EditorCard(self.editor, 'MY EDITOR', lambda: self.notice('Wire this to your save handler'))
                editors.addWidget(self.editor_card)
                self.console = TerminalConsole(); self.console.feed('demo', '\x1b[32mConsole ready\x1b[0m\n')
                editors.addWidget(self.console)
                self.add_action('Focus editor', self.editor_card.open_focus, 'Ctrl+E')
                self.add_action('About', lambda: QMessageBox.information(self, 'About', 'Pylerium shared component gallery'))
    ''', 'from pylerium_gui import (Qt, QHBoxLayout, QFormLayout, QLineEdit, QComboBox, QSpinBox, QSlider, QDateEdit, QRadioButton, QCheckBox, QProgressBar, QMessageBox, QFileDialog, QTabWidget, QListWidget, QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem, IconButton, LoadoutCard, SelectorItem, ItemSelectorDialog, StatBar, LoadoutSidebar, WorkshopEditor, EditorCard, TerminalConsole, theme, demo_loadout)\n'),
    'GUI / Model preview and workflow': starter('''
        class MyWindow(AppWindow):
            def __init__(self):
                super().__init__('MY VISUAL TOOL')
                page = self.add_page('Preview', 'Reuse the real orbit, zoom, material and stats controls.')
                self.preview = PreviewPanel(); self.preview.set_item(theme().PRIMARY_ITEMS[0])
                page.addWidget(self.preview)
                workflows = self.add_page('Workflow', 'The original dependency map widget.')
                self.map = WorkflowMap()
                self.map.nodes = [{'id': 'prepare', 'depends_on': [], 'status': 'succeeded'},
                                  {'id': 'build', 'depends_on': ['prepare'], 'status': 'ready'}]
                workflows.addWidget(self.map)
                workflows.addWidget(button('Refresh map', self.map.update))
    ''', 'from pylerium_gui import PreviewPanel, WorkflowMap, theme\n'),
    'GUI / Responsive background work': starter('''
        import time

        class MyWindow(AppWindow):
            def __init__(self):
                super().__init__('MY BACKGROUND TOOL')
                page = self.add_page('Tasks', 'Keep blocking work away from the GUI thread.')
                self.progress = QProgressBar(); self.progress.setRange(0, 1); self.progress.setValue(0)
                self.launch_button = button('Start task', self.start_task, primary=True)
                page.addWidget(self.launch_button); page.addWidget(self.progress); page.addStretch()

            def start_task(self):
                self.launch_button.setEnabled(False); self.progress.setRange(0, 0)
                # Worker functions return plain data. Update widgets only in the callbacks.
                def work():
                    time.sleep(1)
                    return 'Work finished successfully'
                self.run_background(work, self.finished, self.failed)

            def finished(self, result):
                self.progress.setRange(0, 1); self.progress.setValue(1)
                self.launch_button.setEnabled(True); self.notice(result)

            def failed(self, error):
                self.progress.setRange(0, 1); self.progress.setValue(0)
                self.launch_button.setEnabled(True); self.notice(error)
    ''', 'from pylerium_gui import QProgressBar\n'),
}

# Insert these inside your window's __init__, after super().__init__().
# They compose with AppWindow.content or any QVBoxLayout you supply.
COMPONENT_TEMPLATES = {
    'GUI element / Buttons and panel': dedent('''
        from pylerium_gui import button, label, panel
        card, box = panel()
        box.addWidget(label('My section', 22))
        box.addWidget(button('Run', lambda: self.notice('Ready'), primary=True))
        toggle = button('Toggle', lambda: None); toggle.setCheckable(True)
        box.addWidget(toggle)
        self.content.addWidget(card)
    '''),
    'GUI element / Form controls': dedent('''
        from pylerium_gui import QFormLayout, QLineEdit, QComboBox, QSpinBox, QCheckBox, QSlider, Qt
        form = QFormLayout()
        self.name_input = QLineEdit(); self.name_input.setPlaceholderText('Name')
        self.mode_input = QComboBox(); self.mode_input.addItems(['Local', 'Preview'])
        self.count_input = QSpinBox(); self.count_input.setRange(1, 100)
        self.enabled_input = QCheckBox('Enabled')
        self.level_input = QSlider(Qt.Orientation.Horizontal)
        for title, widget in [('Name', self.name_input), ('Mode', self.mode_input),
                              ('Count', self.count_input), ('Enabled', self.enabled_input),
                              ('Level', self.level_input)]: form.addRow(title, widget)
        self.content.addLayout(form)
    '''),
    'GUI element / Menu and toolbar': dedent('''
        from pylerium_gui import QAction
        tools_menu = self.menuBar().addMenu('My tools')
        tools_toolbar = self.addToolBar('My tools')
        action = QAction('Run my action', self); action.setShortcut('Ctrl+R')
        action.triggered.connect(lambda: self.notice('Action complete'))
        tools_menu.addAction(action); tools_toolbar.addAction(action)
    '''),
    'GUI element / Tabs and data views': dedent('''
        from pylerium_gui import QTabWidget, QListWidget, QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem
        tabs = QTabWidget()
        listing = QListWidget(); listing.addItems(['First', 'Second'])
        tree = QTreeWidget(); tree.setHeaderLabels(['Name', 'State'])
        QTreeWidgetItem(tree, ['My item', 'Ready'])
        table = QTableWidget(1, 2); table.setHorizontalHeaderLabels(['Name', 'Value'])
        table.setItem(0, 0, QTableWidgetItem('Example'))
        table.setItem(0, 1, QTableWidgetItem('Ready'))
        tabs.addTab(listing, 'List'); tabs.addTab(tree, 'Tree'); tabs.addTab(table, 'Table')
        self.content.addWidget(tabs)
    '''),
    'GUI element / Dialogs and file picker': dedent('''
        from pylerium_gui import button, QMessageBox, QFileDialog
        self.content.addWidget(button('About', lambda: QMessageBox.information(self, 'About', 'My application')))
        # Replace this callback with your file loading handler.
        self.content.addWidget(button('Open file', lambda: self.notice(QFileDialog.getOpenFileName(self, 'Open')[0])))
    '''),
    'GUI element / Editor and terminal': dedent('''
        from pylerium_gui import WorkshopEditor, TerminalConsole, QSplitter
        self.editor = WorkshopEditor(); self.editor.setPlainText('# My document')
        self.console = TerminalConsole(); self.console.feed('my-app', 'Ready\\n')
        split = QSplitter(); split.addWidget(self.editor); split.addWidget(self.console)
        self.content.addWidget(split)
    '''),
    'GUI element / Model canvas': dedent('''
        from pylerium_gui import InteractiveModelCanvas
        from model_assets import load_model
        from types import SimpleNamespace
        self.model = InteractiveModelCanvas()
        self.content.addWidget(self.model)
        # Load off-thread, then deliver the scene on the GUI thread.
        # self.model.item_data = SimpleNamespace(name='My model', category='MODEL')
        # self.run_background(lambda: load_model('my_model.glb'),
        #     lambda scene: self.model.loaded('My model', scene, ''))
    '''),
    'GUI element / Workflow map': dedent('''
        from pylerium_gui import WorkflowMap
        self.workflow = WorkflowMap()
        self.workflow.nodes = [{'id': 'input', 'depends_on': [], 'status': 'ready'},
                               {'id': 'output', 'depends_on': ['input'], 'status': 'ready'}]
        self.content.addWidget(self.workflow)
    '''),
    'GUI element / Background task': dedent('''
        from pylerium_gui import button, label
        self.result_label = label('Ready'); self.content.addWidget(self.result_label)
        def work():
            return 'Replace with your file, network or CPU work'
        self.content.addWidget(button('Start', lambda: self.run_background(work,
            self.result_label.setText, lambda error: self.result_label.setText('Failed: ' + error))))
    '''),
}

COMPONENT_TEMPLATES['GUI element / Opt-in audio controls'] = dedent("""
    from pylerium_gui import configure_audio, play_cue
    from PyQt6.QtWidgets import QCheckBox,QSlider
    from PyQt6.QtCore import Qt
    self.audio_enabled=QCheckBox('Enable subtle audio cues')
    self.audio_volume=QSlider(Qt.Orientation.Horizontal)
    self.audio_volume.setRange(0,100);self.audio_volume.setValue(18)
    def apply_audio():
        configure_audio(enabled=self.audio_enabled.isChecked(),volume=self.audio_volume.value())
    self.audio_enabled.toggled.connect(apply_audio);self.audio_volume.valueChanged.connect(apply_audio)
    self.content.addWidget(self.audio_enabled);self.content.addWidget(self.audio_volume)
""")
