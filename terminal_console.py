"""ANSI-aware Qt display with isolated output state for each Python run."""
import re

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QTextDocument, QTextDocumentFragment
from PyQt6.QtWidgets import QPlainTextEdit


PALETTE = ['#10151a','#ef4444','#22c55e','#eab308','#3b82f6','#a855f7','#06b6d4','#d8dee9',
           '#667788','#ff7777','#86efac','#fde047','#93c5fd','#d8b4fe','#67e8f9','#ffffff']


def ansi_color(index):
    if index < 16:
        return QColor(PALETTE[index])
    if index < 232:
        n = index-16
        levels = [0,95,135,175,215,255]
        return QColor(levels[n//36], levels[n//6%6], levels[n%6])
    n = 8+10*(index-232)
    return QColor(n,n,n)


class AnsiStream:
    def __init__(self, font=None):
        self.document = QTextDocument()
        self.document.setUndoRedoEnabled(False)
        self.document.setMaximumBlockCount(10000)
        if font:
            self.document.setDefaultFont(font)
        self.cursor = QTextCursor(self.document)
        self.format = QTextCharFormat()
        self.pending = ''
        self.saved = 0

    def sgr(self, parameters):
        values = [int(v or 0) for v in parameters.split(';')]
        i = 0
        while i < len(values):
            n = values[i]
            if n == 0:
                self.format = QTextCharFormat()
            elif n in (1,22):
                self.format.setFontWeight(QFont.Weight.Bold if n == 1 else QFont.Weight.Normal)
            elif n in (3,23):
                self.format.setFontItalic(n == 3)
            elif n in (4,24):
                self.format.setFontUnderline(n == 4)
            elif n in (9,29):
                self.format.setFontStrikeOut(n == 9)
            elif 30 <= n <= 37 or 90 <= n <= 97:
                self.format.setForeground(ansi_color(n-30 if n < 90 else n-90+8))
            elif 40 <= n <= 47 or 100 <= n <= 107:
                self.format.setBackground(ansi_color(n-40 if n < 100 else n-100+8))
            elif n == 39:
                self.format.clearForeground()
            elif n == 49:
                self.format.clearBackground()
            elif n in (38,48) and i+1 < len(values):
                color = None
                if values[i+1] == 2 and i+4 < len(values):
                    color = QColor(*[max(0,min(255,v)) for v in values[i+2:i+5]])
                    i += 4
                elif values[i+1] == 5 and i+2 < len(values):
                    color = ansi_color(max(0,min(255,values[i+2])))
                    i += 2
                if color:
                    (self.format.setForeground if n == 38 else self.format.setBackground)(color)
            i += 1

    def control(self, parameters, command):
        values = parameters.lstrip('?').split(';')
        n = int(values[0] or 0) if values[0].isdigit() or not values[0] else 0
        if command == 'm':
            self.sgr(parameters)
        elif command == 'K':
            if n in (1,2):
                self.cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            self.cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock,QTextCursor.MoveMode.KeepAnchor)
            self.cursor.removeSelectedText()
        elif command == 'J' and n == 2:
            self.document.clear()
            self.cursor = QTextCursor(self.document)
        elif command in ('A','B'):
            column = self.cursor.positionInBlock()
            self.cursor.movePosition(QTextCursor.MoveOperation.PreviousBlock if command == 'A' else QTextCursor.MoveOperation.NextBlock,
                                     QTextCursor.MoveMode.MoveAnchor,min(n or 1,10000))
            self.cursor.setPosition(self.cursor.block().position()+min(column,self.cursor.block().length()-1))
        elif command in ('C','D'):
            column = self.cursor.positionInBlock()+(n or 1)*(1 if command == 'C' else -1)
            self.cursor.setPosition(self.cursor.block().position()+max(0,min(column,self.cursor.block().length()-1)))
        elif command == 'G':
            self.cursor.setPosition(self.cursor.block().position()+min(max(0,n-1),self.cursor.block().length()-1))
        elif command in ('H','f'):
            self.cursor.movePosition(QTextCursor.MoveOperation.Start)
        elif command == 's':
            self.saved = self.cursor.position()
        elif command == 'u':
            self.cursor.setPosition(min(self.saved,self.document.characterCount()-1))

    def feed(self, text):
        text = self.pending+text
        self.pending = ''
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == '\x1b':
                if i+1 == len(text):
                    self.pending = text[i:]
                    break
                if text[i+1] == '[':
                    match = re.match(r'\x1b\[([0-9;?]*)([@-~])',text[i:])
                    if not match:
                        self.pending = text[i:][-4096:]
                        break
                    try:
                        self.control(match.group(1),match.group(2))
                    except ValueError:
                        pass
                    i += len(match.group(0))
                    continue
                if text[i+1] == ']':
                    match = re.search(r'\x07|\x1b\\',text[i+2:])
                    if not match:
                        self.pending = text[i:][-4096:]
                        break
                    i += 2+match.end()
                    continue
                i += 2
                continue
            if ch == '\r':
                self.cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            elif ch == '\n':
                self.cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
                if self.cursor.block().next().isValid():
                    self.cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
                else:
                    self.cursor.insertBlock()
            elif ch == '\b':
                if self.cursor.positionInBlock():
                    self.cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
            elif ch == '\t':
                self.cursor.insertText(' '*(4-self.cursor.positionInBlock()%4),self.format)
            elif ord(ch) >= 32:
                match = re.match(r'[^\x00-\x1f\x7f]+',text[i:])
                chunk = match.group(0) if match else ch
                available = self.cursor.block().length()-1-self.cursor.positionInBlock()
                if available:
                    self.cursor.movePosition(QTextCursor.MoveOperation.NextCharacter,QTextCursor.MoveMode.KeepAnchor,
                                             min(len(chunk),available))
                self.cursor.insertText(chunk,self.format)
                i += len(chunk)
                continue
            i += 1
        if self.document.characterCount() > 1_000_000:
            trim = QTextCursor(self.document)
            trim.setPosition(0)
            trim.setPosition(self.document.characterCount()-1_000_000,QTextCursor.MoveMode.KeepAnchor)
            trim.removeSelectedText()


class TerminalConsole(QPlainTextEdit):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.streams = {}
        self.selected_run = None
        self.autoscroll = True
        self.frozen = False
        self.dirty = False
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self.render)
        self.render_timer.start(100)

    def feed(self, ident, text):
        if ident not in self.streams:
            if len(self.streams) >= 64:
                del self.streams[next(iter(self.streams))]
            self.streams[ident] = AnsiStream(self.font())
        self.streams[ident].feed(text)
        self.dirty = True

    def select_run(self,ident):
        self.selected_run = ident
        self.dirty = True
        self.render()

    def render(self):
        if not self.dirty or self.frozen:
            return
        self.dirty = False
        position = self.verticalScrollBar().value()
        document = self.document()
        document.clear()
        document.setMaximumBlockCount(10000)
        cursor = QTextCursor(document)
        for ident, stream in self.streams.items():
            if self.selected_run and ident != self.selected_run:
                continue
            if not self.selected_run:
                fmt = QTextCharFormat()
                fmt.setForeground(QColor('#26d8ee'))
                fmt.setFontWeight(QFont.Weight.Bold)
                cursor.insertText('// RUN '+ident+'\n',fmt)
            cursor.insertFragment(QTextDocumentFragment(stream.document))
            cursor.insertBlock()
        if self.autoscroll:
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        else:
            self.verticalScrollBar().setValue(position)

    def clear(self):
        self.streams.clear()
        self.dirty = False
        super().clear()

    def toPlainText(self):
        self.render()
        return super().toPlainText()
