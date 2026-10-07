"""Python highlighting, line numbers and indentation without external packages."""
import keyword
import re
import builtins
import io
import tokenize

from PyQt6.QtCore import QRect, QSize, Qt, QTimer, QStringListModel
from PyQt6.QtGui import QColor, QPainter, QSyntaxHighlighter, QTextCharFormat, QTextCursor,QShortcut,QKeySequence
from PyQt6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget, QCompleter


class PythonHighlighter(QSyntaxHighlighter):
    def highlightBlock(self,text):
        for expression,color in [(r'\b(?:'+ '|'.join(keyword.kwlist)+r')\b','#ff985b'),
                (r'\b\d+(?:\.\d+)?\b','#c9a1ff'),
                (r'\b(?:print|len|range|str|int|dict|list|self|True|False|None)\b','#63d9ed'),
                (r'\b(?:def|class)\s+(\w+)','#f5d887')]:
            for match in re.finditer(expression,text):
                fmt = QTextCharFormat()
                fmt.setForeground(QColor(color))
                self.setFormat(match.start(),len(match.group(0)),fmt)
        for match in re.finditer(r'''(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|\#.*''',text):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor('#81929e' if match.group(0).startswith('#') else '#8fcfa0'))
            self.setFormat(match.start(),len(match.group(0)),fmt)
        self.setCurrentBlockState(0)
        start = 0
        state = self.previousBlockState()
        while start < len(text):
            if state in (1,2):
                delimiter = "'''" if state == 1 else '"""'
                begin = start
            else:
                matches = [(text.find(d,start),i,d) for i,d in enumerate(("'''",'"""'),1)]
                matches = [m for m in matches if m[0] >= 0]
                if not matches:
                    break
                begin,state,delimiter = min(matches)
                start = begin+3
            end = text.find(delimiter,start)
            fmt = QTextCharFormat()
            fmt.setForeground(QColor('#8fcfa0'))
            if end < 0:
                self.setFormat(begin,len(text)-begin,fmt)
                self.setCurrentBlockState(state)
                break
            self.setFormat(begin,end+3-begin,fmt)
            start,state = end+3,0


class NumberArea(QWidget):
    def __init__(self,editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.number_width(),0)

    def paintEvent(self,event):
        self.editor.paint_numbers(event)


class WorkshopEditor(QPlainTextEdit):
    default_editor_size=15
    default_preferences={}
    def __init__(self):
        super().__init__()
        self.numbers = NumberArea(self)
        self.highlighter = PythonHighlighter(self.document())
        self.blockCountChanged.connect(self.update_margin)
        self.updateRequest.connect(self.update_numbers)
        self.cursorPositionChanged.connect(self.highlight_line)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.update_margin()
        self.highlight_line()
        self.suggestions_enabled = True
        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completion_model = QStringListModel(self)
        self.completer.setModel(self.completion_model)
        self.completer.activated[str].connect(self.insert_completion)
        self.completer.popup().setStyleSheet('QListView {background:#132029;color:#d8e8ef;border:1px solid #f06413;font-family:Consolas;} QListView::item:selected {background:#34454f;color:#ffffff;}')
        self.completion_timer = QTimer(self)
        self.completion_timer.setSingleShot(True)
        self.completion_timer.setInterval(180)
        self.completion_timer.timeout.connect(self.suggest)
        self.dismissed_prefix = None
        self.find_dialog=None
        self.setMinimumHeight(300)
        self.set_editor_size(self.default_editor_size)
        self.tools_shortcuts=[]
        from editor_tools import transform_lines,goto_line,check_syntax
        for key,callback in [('Ctrl+F',self.open_find),('Ctrl+H',self.open_find),
            ('Ctrl+G',lambda:goto_line(self)),('Ctrl+/',lambda:transform_lines(self,'comment')),
            ('Ctrl+D',lambda:transform_lines(self,'duplicate')),
            ('Ctrl+]',lambda:transform_lines(self,'indent')),('Ctrl+[',lambda:transform_lines(self,'outdent'))]:
            shortcut=QShortcut(QKeySequence(key),self);shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback);self.tools_shortcuts.append(shortcut)
        self.configure(self.default_preferences)

    def configure(self,settings):
        self.suggestions_enabled=settings.get('editor_suggestions',True)
        self.completion_timer.setInterval(settings.get('editor_completion_ms',180))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if settings.get('editor_wrap',False) else QPlainTextEdit.LineWrapMode.NoWrap)

    def set_editor_size(self,size):
        self.editor_size=max(10,min(28,int(size)))
        self.setStyleSheet(f'QPlainTextEdit {{background:#0c151c;color:#deedf4;border:1px solid #42606f;selection-background-color:#35576b;font-family:Consolas;font-size:{self.editor_size}px;padding:8px;}}')
        self.update_margin()

    def wheelEvent(self,event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_editor_size(self.editor_size+(1 if event.angleDelta().y()>0 else -1));event.accept()
        else:super().wheelEvent(event)

    def open_find(self):
        from editor_tools import FindDialog
        if self.find_dialog is None:self.find_dialog=FindDialog(self)
        self.find_dialog.show();self.find_dialog.raise_();self.find_dialog.query.setFocus()

    def number_width(self):
        return 14+self.fontMetrics().horizontalAdvance('9')*len(str(max(1,self.blockCount())))

    def update_margin(self,*args):
        self.setViewportMargins(self.number_width(),0,0,0)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ')*4)

    def update_numbers(self,rect,dy):
        if dy:
            self.numbers.scroll(0,dy)
        else:
            self.numbers.update(0,rect.y(),self.numbers.width(),rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_margin()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        rect = self.contentsRect()
        self.numbers.setGeometry(QRect(rect.left(),rect.top(),self.number_width(),rect.height()))

    def highlight_line(self):
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor('#17232b'))
        selection.format.setProperty(QTextCharFormat.Property.FullWidthSelection,True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    def paint_numbers(self,event):
        painter = QPainter(self.numbers)
        painter.fillRect(event.rect(),QColor('#10191f'))
        block = self.firstVisibleBlock()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid() and top <= event.rect().bottom():
            height = int(self.blockBoundingRect(block).height())
            if block.isVisible() and top+height >= event.rect().top():
                painter.setPen(QColor('#f06413' if block.blockNumber() == self.textCursor().blockNumber() else '#647b88'))
                painter.drawText(0,top,self.numbers.width()-6,self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight,str(block.blockNumber()+1))
            block = block.next()
            top += height

    def keyPressEvent(self,event):
        popup = self.completer.popup()
        if popup.isVisible():
            if event.key() == Qt.Key.Key_Escape:
                self.dismissed_prefix = self.completion_prefix()
                popup.hide();self.completion_timer.stop();event.accept();return
            if event.key() == Qt.Key.Key_Tab:
                index = popup.currentIndex()
                if index.isValid():self.insert_completion(index.data())
                popup.hide();event.accept();return
            # Return always inserts a newline; accepting a suggestion is explicit with Tab/click.
            if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):popup.hide()
        if event.key()==Qt.Key.Key_J and event.modifiers()==Qt.KeyboardModifier.ControlModifier:
            self.suggest(manual=True);event.accept();return
        self.completion_timer.stop()
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and not event.modifiers():
            cursor = self.textCursor()
            prefix = cursor.block().text()[:cursor.positionInBlock()]
            indent = re.match(r'[ \t]*',prefix).group(0)
            if prefix.rstrip().endswith(':'):
                indent += '    '
            cursor.beginEditBlock()
            cursor.insertText('\n'+indent)
            cursor.endEditBlock()
            self.setTextCursor(cursor)
        elif event.key() == Qt.Key.Key_Tab and not event.modifiers():
            if self.textCursor().hasSelection():
                from editor_tools import transform_lines
                transform_lines(self,'indent')
            else:self.insertPlainText('    ')
        elif event.key()==Qt.Key.Key_Backtab:
            from editor_tools import transform_lines
            transform_lines(self,'outdent')
        else:
            super().keyPressEvent(event)
        if event.text() and (event.text().isalnum() or event.text() in ('_','.')) and not event.modifiers() & (Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.AltModifier):
            self.completion_timer.start()
        elif event.key()==Qt.Key.Key_Backspace:
            self.completion_timer.start()
        else:
            popup.hide()

    def completion_prefix(self):
        cursor=self.textCursor()
        before=cursor.block().text()[:cursor.positionInBlock()]
        match=re.search(r'[A-Za-z_]\w*$',before)
        return match.group(0) if match else ''

    def suggest(self,manual=False):
        prefix=self.completion_prefix()
        line_before=self.textCursor().block().text()[:self.textCursor().positionInBlock()]
        member=re.search(r'([A-Za-z_]\w*)\.([A-Za-z_]\w*)?$',line_before)
        members={
            'term':['success','error','warning','info','print','gradient','panel','table','section','progress','live_spinner','set_theme','add_style'],
            'ctx':['add_page','add_action','add_template','add_style','selector','log','on','store','runner','window'],
            'json':['loads','dumps','load','dump'],
            'os':['environ','getcwd','listdir','makedirs','path'],
            'sys':['argv','executable','path','exit'],
            'self':sorted(set(re.findall(r'\bself\.([A-Za-z_]\w*)',self.toPlainText()[:100000])))
        }
        member_names=members.get(member.group(1)) if member else None
        if not self.hasFocus() or self.textCursor().hasSelection() or not self.suggestions_enabled:
            self.completer.popup().hide();return
        if not manual and (len(prefix)<2 and member_names is None or prefix==self.dismissed_prefix):
            self.completer.popup().hide();return
        source=self.toPlainText()
        cursor=self.textCursor()
        before=source[:cursor.position()]
        # Keep suggestions out of comments, quoted strings and unfinished multiline strings.
        if cursor.block().previous().isValid() and cursor.block().previous().userState() in (1,2):return
        line=before.rsplit('\n',1)[-1]
        try:
            for token in tokenize.generate_tokens(io.StringIO(line).readline):
                if token.type==tokenize.COMMENT or token.type==tokenize.ERRORTOKEN and token.string in ('"',"'"):
                    self.completer.popup().hide();return
        except tokenize.TokenError as exc:
            if 'string' in str(exc):return
        candidates=set(keyword.kwlist)|{n for n in dir(builtins) if not n.startswith('_')}
        # Document-local names, without executing imports or contacting an AI service.
        candidates.update(re.findall(r'\b[A-Za-z_]\w*\b',source[:100000]))
        if member_names is not None:candidates=set(member_names)
        matches=sorted(n for n in candidates if n.lower().startswith(prefix.lower()) and n!=prefix)[:80]
        if not matches:self.completer.popup().hide();return
        self.completion_model.setStringList(matches)
        self.completer.setCompletionPrefix(prefix)
        self.completer.popup().setCurrentIndex(self.completer.completionModel().index(0,0))
        rect=self.cursorRect();rect.setWidth(max(260,self.completer.popup().sizeHintForColumn(0)+28))
        self.completer.setMaxVisibleItems(7)
        self.completer.complete(rect)

    def insert_completion(self,text):
        cursor=self.textCursor();prefix=self.completion_prefix()
        position=cursor.position()
        suffix=re.match(r'\w*',cursor.block().text()[cursor.positionInBlock():]).group(0)
        cursor.beginEditBlock()
        cursor.setPosition(position-len(prefix))
        cursor.setPosition(position+len(suffix),QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(text);cursor.endEditBlock();self.setTextCursor(cursor)
        self.completer.popup().hide();self.completion_timer.stop()

    def focusOutEvent(self,event):
        self.completion_timer.stop()
        self.completer.popup().hide()
        super().focusOutEvent(event)
