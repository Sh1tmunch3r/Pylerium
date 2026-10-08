"""Selector-driven workflow editing; users choose entities rather than enter IDs."""
import copy
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog,QDialogButtonBox,QFormLayout,QLineEdit,QComboBox,QListWidget,QListWidgetItem,QLabel,QVBoxLayout


def unique_node_id(nodes,base='step'):
    used = {n.get('id') for n in nodes}
    i = 1
    while f'{base}_{i}' in used:
        i += 1
    return f'{base}_{i}'


def repair_node_ids(nodes):
    result,used = copy.deepcopy(nodes),set()
    for node in result:
        ident = node.get('id')
        if not isinstance(ident,str) or not ident.strip() or ident in used:
            base = str(ident or 'step')
            ident = unique_node_id([{'id':i} for i in used],base)
            node['id'] = ident
        used.add(ident)
    return result


class NodeDialog(QDialog):
    def __init__(self,window,nodes,node=None):
        super().__init__(window)
        self.setWindowTitle('Configure operation step')
        self.resize(520,500)
        self.nodes,self.original = nodes,node
        layout = QVBoxLayout(self)
        hint = QLabel('Choose the project, execution loadout and operator. Select prerequisites below; no project IDs need typing.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        self.ident = QLineEdit(node['id'] if node else unique_node_id(nodes))
        self.project,self.profile,self.operator = QComboBox(),QComboBox(),QComboBox()
        for combo,kind in [(self.project,'project'),(self.profile,'profile'),(self.operator,'operator')]:
            if kind=='operator':
                combo.addItem('Local operator',None)
            for doc in window.store.list(kind):
                combo.addItem(doc['name'],doc['id'])
            if node:
                index = combo.findData(node.get(kind,'default' if kind=='profile' else None))
                combo.setCurrentIndex(index)
        form.addRow('Step label (generated automatically)',self.ident)
        form.addRow('Project',self.project)
        form.addRow('Execution loadout',self.profile)
        form.addRow('Operator callsign',self.operator)
        layout.addLayout(form)
        layout.addWidget(QLabel('Run after these steps (leave empty for parallel execution)'))
        self.dependencies = QListWidget()
        projects = {d['id']:d['name'] for d in window.store.list('project')}
        for existing in nodes:
            if existing is node:
                continue
            item = QListWidgetItem(existing['id']+' — '+projects.get(existing.get('project'),'Missing project'))
            item.setData(Qt.ItemDataRole.UserRole,existing['id'])
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if node and existing['id'] in node.get('depends_on',[]) else Qt.CheckState.Unchecked)
            self.dependencies.addItem(item)
        layout.addWidget(self.dependencies,1)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color:#ff985b;')
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def validate(self):
        ident = self.ident.text().strip()
        if not ident or any(n is not self.original and n['id']==ident for n in self.nodes):
            self.error.setText('Choose a unique step label. The automatically generated label is ready to use.')
            return
        if not self.project.currentData() or not self.profile.currentData():
            self.error.setText('Select an existing project and loadout first.')
            return
        self.accept()

    def value(self):
        doc = {'id':self.ident.text().strip(),'project':self.project.currentData(),
               'profile':self.profile.currentData(),'depends_on':[
                   self.dependencies.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.dependencies.count())
                   if self.dependencies.item(i).checkState()==Qt.CheckState.Checked]}
        if self.operator.currentData():
            doc['operator'] = self.operator.currentData()
        return doc
