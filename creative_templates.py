"""Creative GUI, plugin, element and boilerplate catalog."""
from textwrap import dedent
from gui_templates import starter
from creative_gallery import EXPERIENCES
CREATIVE_TEMPLATES={}
CREATIVE_PLUGINS={}
for mode,(title,description) in EXPERIENCES.items():
    CREATIVE_TEMPLATES['GUI / Creative / '+title]=starter(f'''
        class MyWindow(AppWindow):
            def __init__(self):
                super().__init__({title!r})
                self.content.addWidget(CreativePage({mode!r}),1)
    ''','from creative_gallery import CreativePage\n')
    CREATIVE_PLUGINS['Experience / '+title]=dedent(f'''
        def register(ctx):
            from creative_gallery import CreativePage
            page=CreativePage({mode!r},ctx)
            ctx.add_page({title!r},page)
            ctx.add_template({title!r},{CREATIVE_TEMPLATES['GUI / Creative / '+title]!r})
    ''').strip()+'\n'

ELEMENTS={
 'Searchable list':('''
        search=QLineEdit();search.setPlaceholderText('Filter items')
        items=QListWidget();items.addItems(['Nebula','Reactor','Observatory','Garden'])
        def filter_items(text):
            for i in range(items.count()):items.item(i).setHidden(text.casefold() not in items.item(i).text().casefold())
        search.textChanged.connect(filter_items);self.content.addWidget(search);self.content.addWidget(items)
 ''','QLineEdit,QListWidget'),
 'Context action menu':('''
        card=QLabel('Right-click this card');card.setMinimumHeight(180);card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        def menu_at(position):
            menu=QMenu(card);menu.addAction('Inspect',lambda:self.notice('Inspect selected'));menu.addAction('Duplicate',lambda:self.notice('Duplicate selected'));menu.exec(card.mapToGlobal(position))
        card.customContextMenuRequested.connect(menu_at);self.content.addWidget(card)
 ''','QLabel,QMenu'),
 'Drag and drop idea list':('''
        items=QListWidget();items.addItems(['Sketch','Prototype','Polish','Share']);items.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.content.addWidget(items);self.content.addWidget(label('Drag items to reorder'))
 ''','QListWidget'),
 'Validated inline form':('''
        name=QLineEdit();name.setPlaceholderText('Project name');hint=QLabel('Enter at least three characters');save=QPushButton('Create');save.setEnabled(False)
        def validate(text):
            valid=len(text.strip())>=3;save.setEnabled(valid);hint.setText('Ready' if valid else 'Enter at least three characters')
        name.textChanged.connect(validate);save.clicked.connect(lambda:self.notice('Created '+name.text().strip()))
        self.content.addWidget(name);self.content.addWidget(hint);self.content.addWidget(save)
 ''','QLineEdit,QLabel,QPushButton'),
 'Editable property table':('''
        table=QTableWidget(3,2);table.setHorizontalHeaderLabels(['Property','Value'])
        for row,(key,value) in enumerate([('Name','Untitled'),('Mode','Preview'),('Version','1')]):
            table.setItem(row,0,QTableWidgetItem(key));table.setItem(row,1,QTableWidgetItem(value))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.content.addWidget(table)
 ''','QTableWidget,QTableWidgetItem,QHeaderView'),
 'Expandable inspector':('''
        details=QWidget();layout=QVBoxLayout(details);layout.addWidget(label('Advanced properties'));layout.addWidget(QLineEdit('Default value'))
        self.content.addWidget(Disclosure('Show inspector',details,False));self.content.addStretch()
 ''','QWidget,QVBoxLayout,QLineEdit'),
 'Progress with cancellation':('''
        self.progress=QProgressBar();self.progress.setRange(0,100);self.timer=QTimer(self)
        self.timer.timeout.connect(lambda:self.progress.setValue(min(100,self.progress.value()+1)))
        self.content.addWidget(self.progress);self.content.addWidget(button('Start',lambda:(self.progress.setValue(0),self.timer.start(50))))
        self.content.addWidget(button('Cancel',self.timer.stop));self.progress.valueChanged.connect(lambda n:self.timer.stop() if n==100 else None)
 ''','QProgressBar'),
 'Tabbed detail panel':('''
        tabs=QTabWidget()
        for title,text in [('Overview','Project summary'),('Activity','Recent events'),('Settings','Your configuration')]:
            page=QWidget();layout=QVBoxLayout(page);layout.addWidget(label(text));layout.addStretch();tabs.addTab(page,title)
        self.content.addWidget(tabs)
 ''','QTabWidget,QWidget,QVBoxLayout'),
 'Clipboard color swatch':('''
        entry=QLineEdit('#26d8ee');swatch=QPushButton('Copy color')
        def apply(text):
            color=QColor(text)
            if color.isValid():swatch.setStyleSheet('background:'+color.name()+';color:black;')
        entry.textChanged.connect(apply);apply(entry.text());swatch.clicked.connect(lambda:QApplication.clipboard().setText(entry.text()))
        self.content.addWidget(entry);self.content.addWidget(swatch)
 ''','QLineEdit,QPushButton,QApplication'),
 'Split preview workspace':('''
        splitter=QSplitter(Qt.Orientation.Horizontal);editor=QPlainTextEdit('Write something here');preview=QLabel('Live preview');preview.setWordWrap(True)
        editor.textChanged.connect(lambda:preview.setText(editor.toPlainText()));splitter.addWidget(editor);splitter.addWidget(preview);self.content.addWidget(splitter,1)
 ''','QSplitter,QPlainTextEdit,QLabel'),
 'Sortable records':('''
        table=QTableWidget(4,2);table.setHorizontalHeaderLabels(['Name','Status'])
        for row,name in enumerate(['Atlas','Nova','Orion','Vega']):
            table.setItem(row,0,QTableWidgetItem(name));table.setItem(row,1,QTableWidgetItem('Ready'))
        table.setSortingEnabled(True);table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.content.addWidget(table)
 ''','QTableWidget,QTableWidgetItem,QHeaderView'),
 'Responsive command palette':('''
        query=QLineEdit();query.setPlaceholderText('Search commands');commands=QListWidget();commands.addItems(['New scene','Export artwork','Open settings'])
        def search(text):
            for i in range(commands.count()):commands.item(i).setHidden(text.casefold() not in commands.item(i).text().casefold())
        query.textChanged.connect(search);commands.itemActivated.connect(lambda item:self.notice(item.text()));self.content.addWidget(query);self.content.addWidget(commands)
 ''','QLineEdit,QListWidget'),
}
for title,(body,widgets) in ELEMENTS.items():
    code=starter('class MyWindow(AppWindow):\n    def __init__(self):\n        super().__init__('+repr(title)+')\n'+ '\n'.join('        '+line for line in dedent(body).strip().splitlines()),
        'from PyQt6.QtWidgets import '+widgets+'\nfrom PyQt6.QtCore import Qt,QTimer\nfrom PyQt6.QtGui import QColor\nfrom gui_components import Disclosure\n')
    CREATIVE_TEMPLATES['GUI / Element / '+title]=code

BOILERPLATES={
 'Boilerplate / Event bus': '''from collections import defaultdict
class EventBus:
    def __init__(self): self.listeners=defaultdict(list)
    def subscribe(self,event,callback): self.listeners[event].append(callback)
    def publish(self,event,payload):
        for callback in tuple(self.listeners[event]): callback(payload)
bus=EventBus();bus.subscribe('scene_changed',print);bus.publish('scene_changed',{'scene':'garden'})
''',
 'Boilerplate / Undo redo history': '''class History:
    def __init__(self): self.past=[];self.future=[]
    def record(self,value): self.past.append(value);self.future.clear()
    def undo(self):
        if len(self.past)>1:self.future.append(self.past.pop())
        return self.past[-1] if self.past else None
    def redo(self):
        if self.future:self.past.append(self.future.pop())
        return self.past[-1] if self.past else None
history=History();history.record('draft');history.record('polished');print(history.undo());print(history.redo())
''',
 'Boilerplate / Deterministic world generation': '''import random
rng=random.Random(42)
biomes=['forest','desert','ocean','mountain']
world=[[rng.choice(biomes) for x in range(8)] for y in range(8)]
for row in world: print(' '.join(cell[:3] for cell in row))
''',
 'Boilerplate / Plugin registry': '''class Registry:
    def __init__(self):self.entries={}
    def register(self,name):
        def decorate(function):
            if name in self.entries:raise ValueError('Duplicate registration')
            self.entries[name]=function;return function
        return decorate
    def invoke(self,name,*args,**kwargs):return self.entries[name](*args,**kwargs)
registry=Registry()
@registry.register('greet')
def greet(name):return f'Hello {name}'
print(registry.invoke('greet','World'))
''',
 'Boilerplate / State machine': '''class StateMachine:
    def __init__(self,state,transitions):self.state=state;self.transitions=transitions
    def send(self,event):
        key=(self.state,event)
        if key not in self.transitions:raise ValueError(f'Invalid event {event} in {self.state}')
        self.state=self.transitions[key];return self.state
machine=StateMachine('idle',{('idle','start'):'running',('running','pause'):'paused',('paused','resume'):'running'})
print(machine.send('start'));print(machine.send('pause'));print(machine.send('resume'))
''',
 'Boilerplate / Atomic document save': '''import json,os,tempfile
from pathlib import Path
def save_document(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=path.parent,suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:json.dump(data,stream,indent=2)
        os.replace(name,path)
    finally:
        Path(name).unlink(missing_ok=True)
save_document('scene.json',{'title':'My world','objects':[]})
''',
}
CREATIVE_TEMPLATES.update(BOILERPLATES)
