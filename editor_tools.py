"""Document tools shared by embedded and focused Workshop editors."""
import re,ast
from PyQt6.QtCore import Qt,QRegularExpression
from PyQt6.QtGui import QTextCursor,QTextDocument
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QCheckBox,QInputDialog
from gui_components import label,button


class FindDialog(QDialog):
    def __init__(self,editor):
        super().__init__(editor.window());self.editor=editor;self.setWindowTitle('Find / Replace');self.resize(600,220)
        box=QVBoxLayout(self);self.query=QLineEdit();self.query.setPlaceholderText('Find text or regular expression')
        self.replacement=QLineEdit();self.replacement.setPlaceholderText('Replacement')
        box.addWidget(self.query);box.addWidget(self.replacement)
        row=QHBoxLayout();self.case=QCheckBox('Match case');self.regex=QCheckBox('Regex');self.word=QCheckBox('Whole word')
        for widget in (self.case,self.regex,self.word):row.addWidget(widget)
        box.addLayout(row);row=QHBoxLayout()
        for title,callback in [('Previous',lambda:self.find(True)),('Next',self.find),('Replace',self.replace),('Replace all',self.replace_all)]:row.addWidget(button(title,callback))
        box.addLayout(row);self.status=label('Search wraps at the document boundary.',11,'#9aabb4');box.addWidget(self.status)
        self.query.returnPressed.connect(self.find)

    def pattern(self):
        value=self.query.text()
        if not value:raise ValueError('Enter search text')
        expression=value if self.regex.isChecked() else re.escape(value)
        if self.word.isChecked():expression=r'\b(?:'+expression+r')\b'
        return re.compile(expression,0 if self.case.isChecked() else re.IGNORECASE)

    def find(self,backward=False):
        try:pattern=self.pattern()
        except (ValueError,re.error) as exc:self.status.setText(str(exc));return False
        source=self.editor.toPlainText();cursor=self.editor.textCursor()
        encoded=source.encode('utf-16-le')
        selection_start=len(encoded[:cursor.selectionStart()*2].decode('utf-16-le',errors='ignore'))
        selection_end=len(encoded[:cursor.selectionEnd()*2].decode('utf-16-le',errors='ignore'))
        matches=list(pattern.finditer(source))
        if not matches:self.status.setText('No matches');return False
        if backward:
            matches_before=[m for m in matches if m.end()<=selection_start and m.start()<selection_start]
            match=matches_before[-1] if matches_before else matches[-1]
        else:
            match=next((m for m in matches if m.start()>=selection_end and (m.end()>selection_end or not cursor.hasSelection())),matches[0])
        # QTextCursor offsets use UTF-16, while Python regex offsets use code points.
        start=len(source[:match.start()].encode('utf-16-le'))//2
        end=len(source[:match.end()].encode('utf-16-le'))//2
        cursor.setPosition(start);cursor.setPosition(end,QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor);self.editor.ensureCursorVisible();self.status.setText(f'{len(matches)} matches');return True

    def replace(self):
        try:
            pattern=self.pattern();cursor=self.editor.textCursor();selected=cursor.selectedText().replace('\u2029','\n')
            if not cursor.hasSelection() or not pattern.fullmatch(selected):self.find();return
            replacement=self.replacement.text() if self.regex.isChecked() else lambda match:self.replacement.text()
            cursor.insertText(pattern.sub(replacement,selected,count=1));self.editor.setTextCursor(cursor);self.find()
        except (ValueError,re.error) as exc:self.status.setText(str(exc))

    def replace_all(self):
        try:
            replacement=self.replacement.text() if self.regex.isChecked() else lambda match:self.replacement.text()
            result,count=self.pattern().subn(replacement,self.editor.toPlainText())
            if count:
                cursor=self.editor.textCursor();cursor.beginEditBlock();cursor.select(QTextCursor.SelectionType.Document);cursor.insertText(result);cursor.endEditBlock()
            self.status.setText(f'Replaced {count} matches (one undo operation)')
        except (ValueError,re.error) as exc:self.status.setText(str(exc))


def transform_lines(editor,mode):
    cursor=editor.textCursor();selected=cursor.hasSelection();start=cursor.selectionStart();end=cursor.selectionEnd()
    first=editor.document().findBlock(start);last=editor.document().findBlock(max(start,end-1))
    cursor.setPosition(first.position());cursor.setPosition(last.position()+len(last.text().encode('utf-16-le'))//2,QTextCursor.MoveMode.KeepAnchor)
    lines=cursor.selectedText().replace('\u2029','\n').split('\n')
    if mode=='indent':lines=['    '+line for line in lines]
    elif mode=='outdent':lines=[re.sub(r'^(?: {1,4}|\t)','',line) for line in lines]
    elif mode=='comment':
        uncomment=all(not line.strip() or line.lstrip().startswith('#') for line in lines)
        lines=[re.sub(r'^(\s*)# ?',r'\1',line) if uncomment else re.sub(r'^(\s*)',r'\1# ',line,count=1) for line in lines]
    elif mode=='duplicate':lines=lines+lines
    start=cursor.selectionStart();text='\n'.join(lines)
    cursor.beginEditBlock();cursor.insertText(text);cursor.endEditBlock()
    if selected:
        cursor.setPosition(start);cursor.setPosition(start+len(text.encode('utf-16-le'))//2,QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)


def goto_line(editor,line=None):
    if line is None:
        line,ok=QInputDialog.getInt(editor,'Go to line','Line number',editor.textCursor().blockNumber()+1,1,editor.blockCount())
        if not ok:return
    cursor=QTextCursor(editor.document().findBlockByNumber(max(0,line-1)));editor.setTextCursor(cursor);editor.ensureCursorVisible();editor.setFocus()


def check_syntax(editor):
    try:ast.parse(editor.toPlainText());return 'Python syntax OK'
    except SyntaxError as exc:
        goto_line(editor,exc.lineno or 1);return f'Line {exc.lineno}: {exc.msg}'
