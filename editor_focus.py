"""Focus the original editor in a large card, retaining document, cursor and undo state."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShortcut,QKeySequence
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QDialog,QCheckBox,QComboBox,QToolButton,QMenu,QPlainTextEdit


class EditorCard(QWidget):
    def __init__(self,editor,title,save,parent=None,templates=None,new_template=None):
        super().__init__(parent)
        self.editor,self.title,self.save=editor,title,save
        self.save_shortcut=QShortcut(QKeySequence.StandardKey.Save,editor)
        self.save_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.save_shortcut.activated.connect(lambda:save())
        self.dialog=None
        self.templates=templates
        self.new_template=new_template
        self.box=QVBoxLayout(self);self.box.setContentsMargins(0,0,0,0)
        self.toolbar=QWidget(self)
        row=QHBoxLayout(self.toolbar);row.setContentsMargins(0,0,0,0)
        self.template_picker=QComboBox()
        self.template_picker.setMinimumWidth(130);self.template_picker.setMaximumWidth(230)
        self.template_picker.setToolTip('Choose editable boilerplate. Inserting never executes code.')
        if templates:
            self.refresh_templates()
            row.addWidget(self.template_picker)
            if not new_template:
                insert=QPushButton('Insert boilerplate');insert.clicked.connect(self.insert_template)
                row.addWidget(insert)
        if new_template:
            new=QPushButton('New from template');new.clicked.connect(lambda:new_template(self.template_picker.currentText()))
            row.addWidget(new)
        row.addStretch()
        tools=QToolButton();tools.setText('Tools');tools.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu=QMenu(tools)
        from editor_tools import transform_lines,goto_line,check_syntax
        for title,callback in [('Find / Replace (Ctrl+F)',editor.open_find),
            ('Go to line (Ctrl+G)',lambda:goto_line(editor)),
            ('Check Python syntax',lambda:self.editor_status.setText(check_syntax(editor))),
            ('Toggle comment (Ctrl+/)',lambda:transform_lines(editor,'comment')),
            ('Indent (Ctrl+])',lambda:transform_lines(editor,'indent')),
            ('Outdent (Ctrl+[)',lambda:transform_lines(editor,'outdent')),
            ('Duplicate line (Ctrl+D)',lambda:transform_lines(editor,'duplicate')),
            ('Insert terminal example',lambda:editor.insertPlainText('from ultimate_terminal import terminal as term\nterm.success("Ready")\n'))]:
            action=menu.addAction(title);action.triggered.connect(callback)
        wrap=menu.addAction('Wrap long lines');wrap.setCheckable(True)
        wrap.toggled.connect(lambda enabled:editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if enabled else QPlainTextEdit.LineWrapMode.NoWrap))
        suggestions=menu.addAction('Python suggestions');suggestions.setCheckable(True);suggestions.setChecked(editor.suggestions_enabled)
        suggestions.toggled.connect(lambda enabled:setattr(editor,'suggestions_enabled',enabled))
        tools.setMenu(menu);row.addWidget(tools)
        self.focus_button=QPushButton('⤢ Focus editor')
        self.focus_button.setToolTip('Open a large editing card. Your cursor, edits and undo history are retained.')
        self.focus_button.setMaximumHeight(30)
        self.focus_button.clicked.connect(self.open_focus)
        row.addWidget(self.focus_button);self.box.addWidget(self.toolbar)
        self.box.addWidget(editor,1)
        self.editor_status=QLabel();self.editor_status.setStyleSheet('color:#8aa6b6;font-size:11px;')
        self.box.addWidget(self.editor_status)
        editor.cursorPositionChanged.connect(self.update_status);editor.document().modificationChanged.connect(self.update_status)
        self.update_status()

    def update_status(self,*args):
        cursor=self.editor.textCursor()
        self.editor_status.setText(f'Ln {cursor.blockNumber()+1}  Col {cursor.positionInBlock()+1}    •    {self.editor.blockCount()} lines    •    '+('Modified' if self.editor.document().isModified() else 'Saved'))

    def refresh_templates(self):
        selected=self.template_picker.currentText()
        choices=self.templates() if callable(self.templates) else self.templates
        self.template_picker.clear();self.template_picker.addItems(choices or {})
        if selected in (choices or {}):self.template_picker.setCurrentText(selected)
        return choices or {}

    def insert_template(self):
        choices=self.templates() if callable(self.templates) else self.templates
        code=(choices or {}).get(self.template_picker.currentText())
        if code is None:return
        cursor=self.editor.textCursor()
        if self.template_picker.currentText().startswith('GUI element /'):
            import re
            prefix=cursor.block().text()[:cursor.positionInBlock()]
            indentation=re.match(r'[ \t]*',prefix).group(0)
            if prefix.rstrip().endswith(':'):indentation+='    '
            code='\n'.join(indentation+line if line else '' for line in code.rstrip().splitlines())
        cursor.beginEditBlock()
        # Insert complete top-level boilerplate between lines, leaving existing code intact.
        cursor.clearSelection()
        cursor.movePosition(cursor.MoveOperation.EndOfBlock)
        cursor.insertText(('\n\n' if self.editor.toPlainText() else '')+code+'\n')
        cursor.endEditBlock();self.editor.setTextCursor(cursor);self.editor.setFocus()

    def open_focus(self):
        if self.dialog:
            self.dialog.raise_();self.editor.setFocus();return
        self.dialog=FocusDialog(self)
        self.dialog.show();self.editor.setFocus()


class FocusDialog(QDialog):
    def __init__(self,host):
        super().__init__(host.window())
        self.host=host
        self.setWindowTitle(host.title+' // Focus editor')
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setStyleSheet(host.window().styleSheet())
        self.setObjectName('editorFocus')
        self.setStyleSheet(self.styleSheet()+ '\nQDialog#editorFocus {background:#0b1115;border:1px solid #f06413;}')
        box=QVBoxLayout(self);box.setContentsMargins(18,18,18,18)
        header=QHBoxLayout();header.addWidget(QLabel(host.title+' // FOCUS'));header.addStretch()
        suggestions=QCheckBox('Python suggestions');suggestions.setChecked(host.editor.suggestions_enabled)
        suggestions.toggled.connect(self.toggle_suggestions);header.addWidget(suggestions)
        save=QPushButton('Save');save.clicked.connect(lambda:host.save());header.addWidget(save)
        close=QPushButton('Return to menu');close.clicked.connect(self.close);header.addWidget(close)
        box.addLayout(header)
        if host.templates:host.refresh_templates()
        host.box.removeWidget(host.toolbar);box.addWidget(host.toolbar)
        host.focus_button.hide()
        host.box.removeWidget(host.editor);box.addWidget(host.editor,1)
        hint=QLabel('Tab accepts a suggestion • Esc dismisses suggestions / returns to menu • Ctrl+J requests suggestions • Edits remain in the original editor')
        hint.setWordWrap(True);hint.setStyleSheet('color:#8299a4;font-size:11px;');box.addWidget(hint)
        screen=host.window().screen().availableGeometry()
        self.resize(int(screen.width()*0.94),int(screen.height()*0.90))
        self.move(screen.center()-self.rect().center())

    def toggle_suggestions(self,value):
        self.host.editor.suggestions_enabled=value
        if not value:self.host.editor.completer.popup().hide()

    def reject(self):
        if self.host.editor.completer.popup().isVisible():
            self.host.editor.completer.popup().hide();return
        self.close()

    def closeEvent(self,event):
        editor=self.host.editor
        if editor.find_dialog:
            editor.find_dialog.close();editor.find_dialog.deleteLater();editor.find_dialog=None
        editor.completion_timer.stop();editor.completer.popup().hide()
        self.layout().removeWidget(editor);self.host.box.insertWidget(1,editor,1)
        self.layout().removeWidget(self.host.toolbar)
        self.host.box.insertWidget(0,self.host.toolbar)
        self.host.focus_button.show()
        self.host.dialog=None
        editor.setFocus()
        event.accept()
