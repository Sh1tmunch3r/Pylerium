"""Host-integrated starter guide, execution observatory and workspace inspector."""
import json
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QTableWidget,QTableWidgetItem,QCheckBox,QComboBox
from gui_components import button,label
from workshop_editor import WorkshopEditor
from starter_catalog import ADVANCED_TEMPLATES


def guide(ctx):
    page=QWidget();box=QVBoxLayout(page);box.addWidget(label('GET STARTED // BUILD YOUR WORKSPACE',25))
    saved=ctx.store.get('settings','starter_checklist',{})
    for key,title,destination in [('project','Create and run a Workshop project','WORKSHOP'),('loadout','Choose a Python interpreter and execution settings','LOADOUTS'),('operator','Equip a saved operator','OPERATORS'),('pipeline','Connect projects into a dependency graph','MAPS'),('schedule','Schedule a recurring operation','MISSIONS'),('assets','Assign models, textures and backgrounds','ASSETS'),('plugins','Enable the tools you want','PLUGINS'),('history','Review persistent run logs','BARRACKS')]:
        row=QHBoxLayout();check=QCheckBox(title);check.setChecked(saved.get(key,False))
        def save(checked,k=key):
            state=ctx.store.get('settings','starter_checklist',{});state[k]=checked;ctx.store.put('settings','starter_checklist',state)
        check.toggled.connect(save);row.addWidget(check);row.addWidget(button('OPEN',lambda checked=False,d=destination:ctx.window.navigate(d)));box.addLayout(row)
    box.addWidget(label('COMPLETE ADVANCED APPLICATIONS',19));combo=QComboBox();combo.addItems(ADVANCED_TEMPLATES);box.addWidget(combo)
    def create():
        title=combo.currentText();ctx.window.create_project(title.split(' / ')[-1],ADVANCED_TEMPLATES[title],interactive=True);ctx.window.navigate('WORKSHOP')
    box.addWidget(button('CREATE EDITABLE WORKSHOP PROJECT',create,True));box.addStretch()
    ctx.add_page('Getting started',page)
    for title,code in ADVANCED_TEMPLATES.items():ctx.add_template(title,code)
    return page


def observatory(ctx):
    page=QWidget();box=QVBoxLayout(page);box.addWidget(label('RUN OBSERVATORY',25))
    summary=label('',12,'#26d8ee');box.addWidget(summary);table=QTableWidget(0,6);table.setHorizontalHeaderLabels(['ID','Project','Status','Started','Ended','Exit']);box.addWidget(table)
    output=WorkshopEditor();output.setReadOnly(True);box.addWidget(output)
    def refresh():
        rows=ctx.store.history();table.setRowCount(len(rows))
        counts={}
        for i,row in enumerate(rows):
            counts[row[2]]=counts.get(row[2],0)+1
            for j,value in enumerate(row):table.setItem(i,j,QTableWidgetItem(str(value) if value is not None else ''))
        summary.setText('LATEST 200 RUNS // '+json.dumps(counts)+' // active '+str(len(ctx.runner.jobs)))
    def selected():
        if table.currentRow()<0:return
        ident=table.item(table.currentRow(),0).text();row=ctx.store.db.execute('SELECT log FROM runs WHERE id=?',(ident,)).fetchone();output.setPlainText(row[0] if row else '')
    table.itemSelectionChanged.connect(selected);box.addWidget(button('REFRESH',refresh));ctx.on('run_finished',lambda *_:refresh());refresh();ctx.add_page('Run observatory',page);return page


def inspector(ctx):
    page=QWidget();box=QVBoxLayout(page);box.addWidget(label('WORKSPACE INSPECTOR',25))
    editor=WorkshopEditor();editor.setReadOnly(True);box.addWidget(editor)
    def refresh():
        from asset_helper import ASSETS
        from plugin_system import discover
        report={'workspace':str(ctx.store.root),'projects':ctx.store.list('project'),'loadouts':ctx.store.list('profile'),'operators':ctx.store.list('operator'),'workflows':ctx.store.list('workflow'),'schedules':ctx.store.list('schedule'),'shared':ctx.store.shared(),'assets_root':str(ASSETS.root),'plugins':[{'id':p['id'],'error':p.get('error','')} for p in discover(ctx.host.root)]}
        # Environment values may contain credentials; expose names, not values.
        for profile in report['loadouts']:profile['env']={key:'[configured]' for key in profile.get('env',{})}
        editor.setPlainText(json.dumps(report,indent=2,default=str))
    box.addWidget(button('REFRESH WORKSPACE REPORT',refresh));refresh();ctx.add_page('Workspace inspector',page);return page
