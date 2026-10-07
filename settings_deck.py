"""Category settings with aligned option rows and a contextual detail pane."""
from PyQt6.QtCore import Qt,QEvent
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QStackedWidget,QFrame,QScrollArea,QLineEdit,QSpinBox,QCheckBox,QComboBox,QTableWidget,QTableWidgetItem,QHeaderView,QMessageBox
from gui_components import button,label,horizontal_strip
from asset_helper import ASSETS
from workspace_inventory import WorkspaceInventory


class SettingsDeck(QWidget):
    def __init__(self,window):
        super().__init__();self.host=window;self.rows=[];self.help={};self.inventory=WorkspaceInventory(window)
        root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0)
        strip,nav=horizontal_strip(52);root.addWidget(strip)
        self.tabs=QStackedWidget();body=QHBoxLayout();body.addWidget(self.tabs,3)
        details=QFrame();details.setObjectName('settingsDetails');details.setMinimumWidth(280);details.setMaximumWidth(580)
        info=QVBoxLayout(details);info.setContentsMargins(24,10,12,10)
        self.heading=label('WORKSPACE SETTINGS',26);self.description=label('Select a setting to see its purpose and stored value.',14,'#a3b4bc')
        self.visual=label('PYLERIUM\nLOCAL // PERSISTENT',25,'#26d8ee');self.visual.setAlignment(Qt.AlignmentFlag.AlignCenter);self.visual.setMinimumHeight(170)
        self.visual.setStyleSheet('background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #15262d,stop:1 #090d10);border:1px solid #344047;color:#26d8ee;padding:18px;')
        info.addWidget(self.heading);info.addWidget(self.visual);info.addWidget(self.description);info.addStretch()
        body.addWidget(details,2);root.addLayout(body,1)
        self.search=QLineEdit();self.search.setPlaceholderText('Search settings or stored items…');self.search.textChanged.connect(self.filter)
        root.insertWidget(1,self.search)
        self.categories={};self.nav={}
        for name in ('Runtime','Display','Ambient','Marquee','Editors','Models','Console','Audio','Assistance','Storage','Builds'):
            page=QWidget();box=QVBoxLayout(page);box.setContentsMargins(0,0,16,0);box.setSpacing(8)
            scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(page)
            scroll.setStyleSheet('QScrollArea {background:transparent;border:0;}');page.setAutoFillBackground(False)
            index=self.tabs.addWidget(scroll);self.categories[name]=box
            item=button(name.upper(),lambda checked=False,n=name:self.select(n));item.setCheckable(True);nav.addWidget(item);self.nav[name]=item
        self.runtime();self.display();self.assistance();self.storage();self.builds()
        self.clipboard_capture=QCheckBox('Enabled');self.clipboard_capture.setChecked(window.settings.get('clipboard_capture',True))
        self.row('Runtime','Global clipboard capture',self.clipboard_capture,'Capture future text and image clipboard changes while Pylerium runs. Pause here or in Killchain; remove entries in its Clipboard queue.')
        self.clipboard_capture.toggled.connect(self.toggle_clipboard)
        self.row('Runtime','Killchain command bar',button('OPEN // Ctrl+Space',lambda:window.killchain.toggle()),'Global overlay for Jumpback search, Workshop launch commands, shared values and clipboard history. Pylerium must remain running.')
        self.advanced_controls={};self.advanced()
        for name,box in self.categories.items():
            if name!='Storage':box.addStretch()
        root.addWidget(button('SAVE SETTINGS',window.save_settings,True))
        self.setStyleSheet('QFrame#settingRow {background:rgba(32,36,39,210);border:1px solid #41474b;} QFrame#settingRow:hover {background:#383b3e;border-color:#f06413;} QFrame#settingsDetails {border-left:2px solid #344047;}')
        self.select('Runtime')

    def toggle_clipboard(self,enabled):
        self.host.settings['clipboard_capture']=enabled
        self.host.store.put('settings','app',self.host.settings)
        if hasattr(self.host,'killchain'):self.host.killchain.capture.setChecked(enabled)

    def select(self,name):
        self.tabs.setCurrentIndex(list(self.categories).index(name))
        for key,item in self.nav.items():item.setChecked(key==name)
        self.heading.setText(name.upper());self.description.setText({'Runtime':'Process limits and persistent local execution.','Display':'Editor visibility, interface scaling and ambient motion.','Assistance':'Optional code drafting. The editor remains yours; generated drafts are reviewed before use.','Storage':'Inspect stored projects, configurations, shared keys, run logs, plugins and asset bundles. Removal moves managed files to recoverable trash. Linked configurations are listed before removal. External source files are preserved.','Builds':'Export standalone applications from Workshop. Shared widgets, styling and rendering modules are bundled with your project.'}.get(name,'Select an option for details. Changes persist when you save settings.'))
        if name=='Storage':self.refresh_inventory()

    def row(self,category,title,widget,description):
        frame=QFrame();frame.setObjectName('settingRow');layout=QHBoxLayout(frame);layout.setContentsMargins(14,9,12,9)
        layout.addWidget(label(title,14),1);widget.setMinimumWidth(160);widget.setMaximumWidth(300);layout.addWidget(widget,1)
        self.categories[category].addWidget(frame);self.rows.append((title.casefold(),frame))
        for target in (frame,widget):target.installEventFilter(self);self.help[target]=(title,description)
        widget.setToolTip(description);return widget

    def advanced(self):
        options=[
            ('Audio','audio_enabled','UI audio feedback',False,None,'Opt-in tactile cues across app, plugins and shared GUI widgets.'),
            ('Audio','audio_volume','Cue volume (%)',18,(0,100),'Master volume for subtle UI feedback.'),
            *[('Audio','audio_'+cue,cue.title()+' cues',True,None,'Enable this cue independently.') for cue in ('hover','click','deploy','success','error')],
            *[('Audio','audio_'+cue+'_file',cue.title()+' audio override','','text','Optional local WAV or MP3 path. Blank uses assets/audio defaults.') for cue in ('hover','click','deploy','success','error')],
            ('Runtime','refresh_ms','Refresh interval (ms)',1000,(250,5000),'How often run lists and scheduled missions refresh.'),
            ('Display','remember_window','Remember window size',True,None,'Restore the main window geometry at startup.'),
            ('Ambient','ambient_mode','Animation pattern','Sweep',['Sweep','Breathe','Orbit'],'Choose a moving sweep, breathing light or drifting illumination.'),
            ('Ambient','ambient_speed','Animation speed (%)',100,(0,300),'Speed of atmospheric motion; zero freezes its phase.'),
            ('Ambient','ambient_intensity','Overlay intensity (%)',100,(0,100),'Strength of atmospheric overlays.'),
            ('Ambient','ambient_fps','Animation frame limit',28,(10,60),'Lower values reduce background rendering work.'),
            ('Ambient','ambient_accent','Glow colour','#ff4500','text','Hex colour for the warm ambient glow.'),
            ('Ambient','ambient_grid','Brick grid',True,None,'Show the subtle background grid.'),
            ('Ambient','ambient_particles','Floating particles',False,None,'Add a bounded field of 24 drifting points.'),
            ('Ambient','ambient_scanlines','Scanline overlay',False,None,'Add subtle horizontal scanlines.'),
            ('Ambient','background_opacity','Background image opacity (%)',55,(0,100),'Persistent image opacity in the asset manifest.'),
            ('Marquee','marquee_animation','Terminal animation','Gradient',['Static','Gradient','Rainbow','Pulse','Scanner'],'Cached glyph rendering with smooth gradients and nonblocking pulse/scanner effects.'),
            ('Marquee','marquee_fps','Animation frame limit',30,(10,60),'Bound marquee rendering work; hidden marquees stop their animation timer.'),
            ('Marquee','marquee_scroll','Scrolling enabled',True,None,'Disable scrolling to show the latest status as a static label.'),
            ('Marquee','marquee_speed','Scroll speed (px/s)',45,(10,200),'Marquee movement speed independent of frame rate.'),
            ('Marquee','marquee_pause_hover','Pause on hover',True,None,'Pause text while reading; tooltip retains recent events.'),
            ('Marquee','marquee_styles','Cycle terminal styles',True,None,'Cycle all terminal and custom styles; events use semantic colours.'),
            ('Editors','editor_wrap','Wrap long lines',False,None,'Default wrapping for all Python editors.'),
            ('Editors','editor_suggestions','Python suggestions',True,None,'Enable local completion suggestions without running imports.'),
            ('Editors','editor_completion_ms','Suggestion delay (ms)',180,(80,1200),'Delay before local suggestions appear.'),
            ('Models','model_quality','Surface quality',2560,[1024,1440,2560,4096],'Maximum surface resolution; 4096 adds paused studio supersampling.'),
            ('Models','model_grid','Floor grid',True,None,'Default grid visibility in model canvases.'),
            ('Models','model_auto_orbit','Automatic model orbit',True,None,'Rotate previews automatically when ambient motion is enabled.'),
            ('Models','model_orbit_speed','Orbit speed (%)',100,(0,300),'Speed of automatic model rotation.'),
            ('Console','console_follow','Follow output',True,None,'Scroll to new terminal output by default.'),
            ('Console','console_flush_ms','Output refresh (ms)',40,(16,250),'Batch terminal paints for responsiveness during large outputs.'),
            ('Builds','build_assets','Include assets by default',True,None,'Default for new executable build dialogs.'),
            ('Builds','build_plugins','Include plugins by default',True,None,'Default for installed plugin source inclusion.'),
        ]
        for category,key,title,default,choices,description in options:
            value=self.host.settings.get(key,default)
            if key=='background_opacity':value=round(ASSETS.manifest.get('background_opacity',.55)*100)
            if choices is None:
                widget=QCheckBox('Enabled');widget.setChecked(bool(value))
            elif choices=='text':widget=QLineEdit(str(value))
            elif isinstance(choices,tuple):
                widget=QSpinBox();widget.setRange(*choices);widget.setValue(int(value))
            else:
                widget=QComboBox()
                for choice in choices:widget.addItem(str(choice),choice)
                widget.setCurrentIndex(max(0,widget.findData(value)))
            self.advanced_controls[key]=widget;self.row(category,title,widget,description)

    def values(self):
        result={}
        for key,widget in self.advanced_controls.items():
            result[key]=widget.isChecked() if isinstance(widget,QCheckBox) else widget.value() if isinstance(widget,QSpinBox) else widget.currentData() if isinstance(widget,QComboBox) else widget.text()
        return result

    def eventFilter(self,obj,event):
        if obj in self.help and event.type() in (QEvent.Type.Enter,QEvent.Type.FocusIn):
            title,description=self.help[obj];self.heading.setText(title);self.description.setText(description)
        return super().eventFilter(obj,event)

    def runtime(self):
        w=self.host;w.parallel=QSpinBox();w.parallel.setRange(1,16);w.parallel.setValue(w.settings.get('parallel',2))
        self.row('Runtime','Concurrent processes',w.parallel,'Maximum simultaneous project processes. Saved in the workspace database.')
        self.categories['Runtime'].addWidget(label('WORKSPACE DATABASE\n'+str(w.store.db_path),12,'#9aabb4'))

    def display(self):
        w=self.host;w.motion=QCheckBox('Enabled');w.motion.setChecked(w.settings.get('motion',True))
        self.row('Display','Ambient animation',w.motion,'Animate the background and model rotation. Disable for a quieter workspace.')
        w.editor_size=QSpinBox();w.editor_size.setRange(10,28);w.editor_size.setValue(w.settings.get('editor_font_size',15))
        self.row('Display','Editor font size',w.editor_size,'Applies to every code editor, including plugin and focus editors. Ctrl+wheel zooms an editor temporarily.')
        w.ui_scale=QSpinBox();w.ui_scale.setRange(80,150);w.ui_scale.setSuffix('%');w.ui_scale.setValue(w.settings.get('ui_scale',100))
        self.row('Display','Interface scale',w.ui_scale,'Scales shared text and button padding. Qt also handles the monitor DPI automatically.')

    def assistance(self):
        w=self.host;w.ai_enabled=QCheckBox('Enabled');w.ai_enabled.setChecked(w.settings.get('ai_enabled',False))
        w.ollama_url=QLineEdit(w.settings.get('ollama_url','http://localhost:11434'));w.ollama_model=QComboBox()
        saved=w.settings.get('ollama_model','')
        if saved:w.ollama_model.addItem(saved,saved)
        self.row('Assistance','Ollama assistance',w.ai_enabled,'Enable local code drafting. Open Assist beside the Workshop editor when needed.')
        self.row('Assistance','Connection URL',w.ollama_url,'Address of your Ollama server. Connection errors appear below.')
        self.row('Assistance','Downloaded model',w.ollama_model,'Choose an installed model for code drafting; this does not download models.')
        w.models_status=label('Enable assistance to discover downloaded models.',11,'#26d8ee')
        w.refresh_models_button=button('REFRESH MODELS',w.refresh_models)
        self.categories['Assistance'].addWidget(w.refresh_models_button);self.categories['Assistance'].addWidget(w.models_status)
        w.ai_enabled.toggled.connect(w.ollama_toggle);w.ollama_url.editingFinished.connect(w.refresh_models)

    def storage(self):
        self.table=QTableWidget(0,2);self.table.setHorizontalHeaderLabels(['TYPE','STORED ITEM'])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.inspect)
        self.categories['Storage'].addWidget(self.table,1)
        row=QHBoxLayout();row.addWidget(button('REMOVE SELECTED',self.remove));row.addWidget(button('RESTORE LAST REMOVAL',self.restore));row.addWidget(button('REFRESH',self.refresh_inventory))
        self.categories['Storage'].addLayout(row)
        self.categories['Storage'].addWidget(label('Managed files go to orchestration_data/trash. Original imported files outside the workspace remain untouched.',11,'#9aabb4'))

    def builds(self):
        self.categories['Builds'].addWidget(label('WORKSHOP → BUILD EXE',22))
        self.categories['Builds'].addWidget(label('Save a project, choose Build EXE, then select a build interpreter and destination. The build log stays live and builds can be cancelled. GUI and console applications are supported. PyInstaller must be installed in the selected build Python.'))
        self.categories['Builds'].addWidget(button('OPEN WORKSHOP',lambda:self.host.navigate('WORKSHOP')))

    def refresh_inventory(self):
        self.items=self.inventory.items();self.table.setRowCount(len(self.items))
        for row,item in enumerate(self.items):
            self.table.setItem(row,0,QTableWidgetItem(item['kind'].upper()));self.table.setItem(row,1,QTableWidgetItem(item['name']))
        self.filter(self.search.text())

    def filter(self,text):
        text=text.casefold().strip()
        for title,frame in self.rows:frame.setVisible(text in title)
        if hasattr(self,'items'):
            for row,item in enumerate(self.items):self.table.setRowHidden(row,text not in (item['kind']+' '+item['name']).casefold())

    def inspect(self):
        row=self.table.currentRow()
        if row<0 or row>=len(self.items):return
        item=self.items[row];plan=self.inventory.plan(item)
        self.heading.setText(item['name']);self.description.setText(self.summary(item,plan))

    def summary(self,item,plan):
        return ('Selected: '+item['kind']+' / '+item['id']+'\n\nLinked records removed with it:\n'+
            ('\n'.join(k+' / '+i for k,i in plan['documents']) or 'None')+'\n\nAsset assignments detached:\n'+
            ('\n'.join((name or 'Global')+' / '+key for name,key in plan['references']) or 'None')+'\n\nManaged files moved to trash:\n'+
            ('\n'.join(str(p) for p in plan['files']) or 'None'))

    def remove(self):
        row=self.table.currentRow()
        if row<0 or self.table.isRowHidden(row):return
        if not self.host.dirty_check() or not self.host.plugin_builder.confirm_discard():return
        item=self.items[row];plan=self.inventory.plan(item)
        if QMessageBox.question(self,'Remove stored item',self.summary(item,plan)+'\n\nProceed with this removal?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        self.host.safe(lambda:self.inventory.remove(item));self.refresh_all()

    def restore(self):
        self.host.safe(self.inventory.restore_latest);self.refresh_all()

    def refresh_all(self):
        self.host.current_project=None;self.host.current_operator=None;self.host.current_workflow=None;self.host.current_schedule=None
        self.host.code.clear();self.host.code.document().setModified(False)
        self.host.project_name.clear();self.host.project_path.clear();self.host.project_cwd.clear();self.host.project_args.setText('[]')
        self.host.refresh_lists();self.host.refresh_plugins();self.host.sync_plugin_environment();self.host.reload_assets();self.refresh_inventory()
