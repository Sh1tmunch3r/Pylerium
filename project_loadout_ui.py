"""Embedded Arsenal screen built from the supplied asset-backed template."""
import copy
import importlib.util
import json
import sys
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QDialog, QPlainTextEdit, QDialogButtonBox, QLabel, QScrollArea, QCheckBox, QComboBox, QMenu, QFileDialog, QFormLayout, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from asset_helper import ASSETS
from gui_components import button
from project_loadout import default_loadout, validate_loadout, POLICIES, TACTICALS, LETHALS, WILDCARDS


def template():
    name = 'project_loadout_asset_template'
    if name not in sys.modules:
        path=Path(__file__).with_name('loadout-menu.assets-backup.py')
        if not path.is_file():
            from app_paths import sdk_root
            path=sdk_root()/'loadout-menu.assets-backup.py'
        spec = importlib.util.spec_from_file_location(name,path)
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return sys.modules[name]

class ProjectLoadoutScreen(QWidget):
    def __init__(self, host):
        super().__init__(); self.host=host; self.project=None; self.value=None
        self.theme=template(); root=QVBoxLayout(self)
        from loadout_artwork import card_class
        self.Card=card_class(self.theme.LoadoutCard); self.cards={}; self.selected_slot='primary_target'
        root.setContentsMargins(0,8,0,0); root.setSpacing(14)
        actions=QHBoxLayout(); root.addLayout(actions)
        actions.addWidget(button('BACK TO ARSENAL',lambda:host.navigate('ARSENAL')))
        self.title=QLabel(); self.title.setFont(QFont('Arial',14,QFont.Weight.Bold)); actions.addWidget(self.title,1)
        actions.addWidget(button('SCHEMA / IMPORT / EXPORT',self.schema))
        actions.addWidget(button('RUN PROJECT',self.run,True))
        body=QHBoxLayout(); root.addLayout(body,1)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); holder=QWidget(); holder.setStyleSheet("background:transparent;"); self.grid=QGridLayout(holder); self.grid.setSpacing(12); scroll.setStyleSheet("QScrollArea {background:transparent;border:0;}"); scroll.setWidget(holder); body.addWidget(scroll,3)
        self.preview=host.theme.PreviewPanel(); self.preview.setMinimumWidth(300); self.preview.setMaximumWidth(440)
        self.preview.name.setFont(QFont('Arial',20,QFont.Weight.Bold))
        self.preview.description.setWordWrap(True); self.preview.description.setMinimumWidth(0)
        self.preview.description.setMaximumWidth(340)
        self.preview.canvas.paused=True
        for stat in self.preview.stats.values(): stat.hide()
        for caption in self.preview.findChildren(QLabel):
            if caption.text()=='WEAPON STATS': caption.hide()
        self.preview.level.hide()
        for control in self.preview.findChildren(QPushButton): control.hide()
        preview_controls=QGridLayout()
        for index,(title,callback) in enumerate([
            ('ORBIT / PAUSE',self.preview.toggle_preview),('FIT MODEL',self.preview.canvas.reset_view),
            ('MATERIALS / WIRE',self.preview.toggle_textures),('INSPECT MODEL',self.preview.inspect_weapon)]):
            preview_controls.addWidget(button(title,callback),index//2,index%2)
        self.preview.layout().insertLayout(4,preview_controls)
        self.preview.canvas.setMinimumHeight(300)
        body.addWidget(self.preview,1)
        root.addWidget(QLabel('Select PRIMARY to open attachments, editor and deployment. Every slot is saved with this project.'))

    def load(self, project):
        self.project=project; self.value=validate_loadout(self.host.store.get('project_loadout',project['id'],default_loadout(project))); self.refresh()

    def refresh(self):
        self.title.setText(self.project['name'].upper()+' // EXECUTION LOADOUT')
        while self.grid.count():
            widget=self.grid.takeAt(0).widget()
            if widget: widget.deleteLater()
        slots=[('primary_target','PRIMARY / ENTRY POINT','primary',0,0,4),('secondary_target','SECONDARY / AUXILIARY PIPELINE','weapon',1,0,2),('context','FIELD UPGRADE / ENVIRONMENT','equipment',1,2,2),('tactical_hook','TACTICAL / MONITORING','equipment',2,0,2),('lethal_hook','LETHAL / OUTPUT','equipment',2,2,2),('perk1','PERK 1','perk',3,0,1),('perk2','PERK 2','perk',3,1,1),('perk3','PERK 3','perk',3,2,1),('specialty','SPECIALTY','perk',3,3,1),('wildcard','WILDCARD / PIPELINE','wildcard',4,0,4)]
        for key,title,kind,row,col,span in slots:
            value=self.value.get('policy_slots',{}).get(key,[]) if key in ('perk1','perk2','perk3','specialty') else self.value.get(key)
            if key=='primary_target': text=Path(value['script']).name; description='Entry point • '+str(len(value.get('attachments_flags',[])))+' runtime arguments'
            elif key=='secondary_target': text=str(len(value))+' auxiliary processes' if value else 'No companion processes'; description='Pre-run checks and background services'
            elif key=='context': text=Path(value.get('env_file','')).name or 'Inherited environment'; description=str(len(value.get('env',{})))+' environment overrides'
            elif key in ('perk1','perk2','perk3','specialty'): text=' / '.join(p.replace('_',' ').title() for p in value) or 'No policies equipped'; description='Assign execution policies'
            else:
                registry={'tactical_hook':TACTICALS,'lethal_hook':LETHALS,'wildcard':WILDCARDS}[key]
                text=registry.get(value,'None'); description={'tactical_hook':'Runtime diagnostics and telemetry','lethal_hook':'Reports and post-run hooks','wildcard':'Pipeline and hardware overrides'}[key]
            data=self.theme.LoadoutItem(text or 'None',title,description=description,attachments=self.value['primary_target'].get('attachments_flags',[]) if key=='primary_target' else [])
            data.asset_key=self.asset_key(key)
            card=self.Card(data,kind); card.setMinimumHeight(184 if key=='primary_target' else 160)
            self.cards[key]=card
            card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            card.customContextMenuRequested.connect(lambda pos,k=key,c=card:self.slot_menu(k,c.mapToGlobal(pos)))
            card.set_selected(key==self.selected_slot)
            card.clicked.connect(lambda ignored,k=key,d=data:self.select(k,d)); self.grid.addWidget(card,row,col,1,span)
        self.show_preview(self.selected_slot)

    def asset_key(self,slot):
        return 'project:'+self.project['id'] if slot=='primary_target' else 'loadout:'+self.project['id']+':'+slot

    def show_preview(self,key):
        if key in self.cards:
            self.preview.set_item(self.cards[key].item_data)
            self.preview.canvas.paused=True

    def slot_menu(self,key,position):
        menu=QMenu(self)
        menu.addAction('Configure slot',lambda:self.select(key,self.cards[key].item_data))
        menu.addSeparator()
        menu.addAction('Assign image…',lambda:self.assign_slot(key,'icon'))
        menu.addAction('Assign static 3D model…',lambda:self.assign_slot(key,'model'))
        menu.addAction('Manage in Assets',lambda:self.host.manage_project_assets(self.project['id'],key))
        menu.addAction('Clear artwork',lambda:self.host.clear_asset(self.asset_key(key)))
        menu.exec(position)

    def assign_slot(self,key,kind):
        self.host.manage_project_assets(self.project['id'],key,navigate=False)
        self.host.assign_asset(kind)

    def configuration_form(self,key,value):
        dialog=QDialog(self);dialog.setWindowTitle('GUNSMITH / RUNTIME ATTACHMENTS' if key=='primary_target' else 'CONTEXT / ENVIRONMENT')
        dialog.resize(780,560);layout=QVBoxLayout(dialog);form=QFormLayout();layout.addLayout(form)
        path=QLineEdit(value.get('script','') if key=='primary_target' else value.get('env_file',''))
        row=QHBoxLayout();row.addWidget(path,1)
        def browse():
            filename,_=QFileDialog.getOpenFileName(dialog,'Choose entry point' if key=='primary_target' else 'Choose environment file',self.project['cwd'],'Python (*.py)' if key=='primary_target' else 'Environment files (*)')
            if filename:path.setText(filename)
        row.addWidget(button('BROWSE',browse));form.addRow('Entry point' if key=='primary_target' else 'Environment file',row)
        flags=QLineEdit(json.dumps(value.get('attachments_flags',[])))
        if key=='primary_target':form.addRow('Base arguments (JSON array)',flags)
        hint=QLabel('Name each attachment and assign its argument array. The saved arrays are passed in row order.' if key=='primary_target' else 'Environment overrides are private to this execution. The selected file is read at launch.')
        hint.setWordWrap(True);layout.addWidget(hint)
        table=QTableWidget(0,2);table.setHorizontalHeaderLabels(['Attachment','Arguments (JSON array)'] if key=='primary_target' else ['Variable','Value'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);layout.addWidget(table,1)
        values=value.get('attachments',{}) if key=='primary_target' else value.get('env',{})
        def add(name='',val=''):
            index=table.rowCount();table.insertRow(index);table.setItem(index,0,QTableWidgetItem(name));table.setItem(index,1,QTableWidgetItem(val))
        for name,val in values.items():add(name,json.dumps(val) if key=='primary_target' else str(val))
        controls=QHBoxLayout();layout.addLayout(controls)
        controls.addWidget(button('ADD ATTACHMENT' if key=='primary_target' else 'ADD VARIABLE',lambda:add()))
        controls.addWidget(button('REMOVE SELECTED',lambda:table.removeRow(table.currentRow()) if table.currentRow()>=0 else None))
        if key=='primary_target':
            controls.addWidget(button('OPEN EDITOR',lambda:(dialog.reject(),self.host.open_project(self.project['id']))))
            controls.addWidget(button('RUN SAVED LOADOUT',lambda:(dialog.reject(),self.run())))
        error=QLabel();error.setStyleSheet('color:#ff9564;');layout.addWidget(error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);layout.addWidget(buttons);buttons.rejected.connect(dialog.reject)
        result=[]
        def accept():
            try:
                fields={}
                for row in range(table.rowCount()):
                    name=table.item(row,0).text().strip();raw=table.item(row,1).text()
                    if not name or name in fields:raise ValueError('Names must be unique and nonempty')
                    fields[name]=json.loads(raw) if key=='primary_target' else raw
                updated=copy.deepcopy(value)
                if key=='primary_target':updated.update(script=path.text().strip(),attachments_flags=json.loads(flags.text()),attachments=fields)
                else:updated.update(env_file=path.text().strip(),env=fields)
                candidate=copy.deepcopy(self.value);candidate[key]=updated;validate_loadout(candidate)
                result.append(updated);dialog.accept()
            except (ValueError,TypeError,KeyError,AttributeError) as exc:error.setText(str(exc))
        buttons.accepted.connect(accept);dialog.exec();return result

    def edit(self,title,value,help_text='',primary=False):
        dialog=QDialog(self); dialog.setWindowTitle(title); dialog.resize(760,540); layout=QVBoxLayout(dialog)
        hint=QLabel(help_text); hint.setWordWrap(True); layout.addWidget(hint)
        editor=QPlainTextEdit(json.dumps(value,indent=2)); layout.addWidget(editor)
        if primary:
            row=QHBoxLayout(); layout.addLayout(row)
            row.addWidget(button('EDITOR / WORKSHOP',lambda:(dialog.reject(),self.host.open_project(self.project['id']))))
            row.addWidget(button('RUN SAVED LOADOUT',lambda:(dialog.reject(),self.run())))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); layout.addWidget(buttons)
        buttons.rejected.connect(dialog.reject)
        result=[]
        def save():
            try: result.append(json.loads(editor.toPlainText())); dialog.accept()
            except ValueError as exc: self.host.notice(str(exc))
        buttons.accepted.connect(save); dialog.exec()
        return result

    def select(self,key,data):
        self.selected_slot=key
        for slot,card in self.cards.items(): card.set_selected(slot==key)
        self.show_preview(key)
        policies=key in ('perk1','perk2','perk3','specialty')
        value=self.value.get('policy_slots',{}).get(key,[]) if policies else self.value.get(key)
        help_text={'primary_target':'GUNSMITH: script, attachments_flags, and any named attachment array (Muzzle, Barrel, Optic, Stock…). Each array supplies CLI arguments. Use EDITOR to change code.', 'secondary_target':'Array of {"script":"helper.py", "run_mode":"pre_execution" or "companion", "args":[]}. Companions stop with the primary process.', 'context':'{"env_file":".env", "env":{}}. Paths are relative to the project working directory.', 'tactical_hook':str(TACTICALS),'lethal_hook':str(LETHALS),'wildcard':str(WILDCARDS)}.get(key,str(POLICIES)+' — enter an array of policy IDs.')
        registry={'tactical_hook':TACTICALS,'lethal_hook':LETHALS,'wildcard':WILDCARDS}.get(key)
        if policies or registry:
            dialog=QDialog(self); dialog.setWindowTitle(data.category); dialog.resize(520,300)
            layout=QVBoxLayout(dialog); controls={}
            if policies:
                for ident,title in POLICIES.items():
                    control=QCheckBox(title); control.setChecked(ident in value)
                    controls[ident]=control; layout.addWidget(control)
            else:
                combo=QComboBox()
                for ident,title in registry.items(): combo.addItem(title,ident)
                combo.setCurrentIndex(combo.findData(value)); layout.addWidget(combo)
                hint=QLabel('Configure custom post_script and repeat passes in SCHEMA. Formatting tools must be installed in the selected interpreter. Executable packaging is available through Workshop Build EXE.')
                hint.setWordWrap(True); layout.addWidget(hint)
            buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
            layout.addWidget(buttons); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
            result=([ [ident for ident,control in controls.items() if control.isChecked()] if policies else combo.currentData() ]
                    if dialog.exec()==QDialog.DialogCode.Accepted else [])
        elif key in ('primary_target','context'):
            result=self.configuration_form(key,value)
        else:
            result=self.edit(key.upper(),value,help_text,key=='primary_target')
        if result:
            candidate=copy.deepcopy(self.value)
            if policies: candidate.setdefault('policy_slots',{})[key]=result[0]
            else: candidate[key]=result[0]
            self.save(candidate)

    def save(self,candidate):
        try:
            candidate=validate_loadout(candidate); self.host.store.put('project_loadout',self.project['id'],candidate); self.value=candidate; self.refresh()
        except (ValueError,KeyError,TypeError) as exc: self.host.notice('Loadout: '+str(exc))

    def schema(self):
        result=self.edit('LOADOUT SCHEMA',self.value,'Copy or paste JSON to export or import. Configure post_script, passes, arbitrary attachment names, policies and environment here.')
        if result: self.save(result[0])

    def run(self):
        self.host.safe(lambda:self.host.launch(self.project['id'],self.host.lobby_profile.currentData() or 'default'))
