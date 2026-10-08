"""Global tactical command palette; no shell execution or keyboard hook."""
import ctypes
import hashlib
import json
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, closing
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl, QByteArray, QBuffer, QIODevice, QEvent
from PyQt6.QtGui import QDesktopServices, QImage, QIcon, QPixmap, QShortcut, QKeySequence
from PyQt6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLineEdit, QListWidget, QListWidgetItem, QLabel, QPushButton, QCheckBox)
from gui_components import STYLE


class ClipboardArchive:
    def __init__(self, path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS clips (id TEXT PRIMARY KEY, created REAL, kind TEXT, text TEXT, image BLOB)')

    @contextmanager
    def connect(self):
        with closing(sqlite3.connect(self.path, timeout=2)) as db:
            with db:
                yield db

    def add(self, text='', image=b'', limit=200):
        if not text and not image: return
        ident = hashlib.sha256(image or text.encode('utf-8')).hexdigest()
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO clips VALUES (?,?,?,?,?)',
                       (ident, time.time(), 'image' if image else 'text', text, image))
            db.execute('DELETE FROM clips WHERE id NOT IN (SELECT id FROM clips ORDER BY created DESC LIMIT ?)', (limit,))

    def query(self, text=''):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute('SELECT * FROM clips WHERE instr(lower(text),lower(?))>0 OR ?="" ORDER BY created DESC LIMIT 60', (text,text))]

    def remove(self, ident=None):
        with self.connect() as db:
            if ident: db.execute('DELETE FROM clips WHERE id=?',(ident,))
            else: db.execute('DELETE FROM clips')


def search_history(path, text):
    """Read the live plugin archive without importing/enabling the plugin."""
    if not Path(path).exists(): return []
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True, timeout=.3)) as db:
        db.row_factory = sqlite3.Row
        clauses=[]; args=[]
        for term in text.split():
            clauses.append("instr(lower(title||' '||target||' '||app||' '||detail||' '||note),lower(?))>0")
            args.append(term)
        return [dict(row) for row in db.execute('SELECT * FROM events'+
            (' WHERE '+' AND '.join(clauses) if clauses else '')+' ORDER BY occurred DESC LIMIT 60',args)]


class Killchain(QDialog):
    HOTKEY = 0x5059
    def __init__(self, host):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.host=host; self.setWindowTitle('PYLERIUM // KILLCHAIN'); self.setStyleSheet(STYLE)
        self.resize(760,510); self.setMinimumSize(420,300)
        self.archive=ClipboardArchive(host.store.root/'killchain'/'clipboard.sqlite3')
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='killchain-search')
        self.future=None; self.generation=0; self.registered=False; self.stopped=False
        root=QVBoxLayout(self); root.setContentsMargins(22,18,22,18)
        title=QLabel('KILLCHAIN  //  GLOBAL OPERATIONS');title.setStyleSheet('color:#f06413;font-size:20px;font-weight:bold;');root.addWidget(title)
        self.input=QLineEdit();self.input.setPlaceholderText('Search history  ·  run <project>  ·  set <key> <value>  ·  clip <text>  ·  go <page>');root.addWidget(self.input)
        row=QHBoxLayout();self.capture=QCheckBox('INTEL // CLIPBOARD');self.capture.setChecked(host.settings.get('clipboard_capture',True))
        self.capture.toggled.connect(self.capture_changed);row.addWidget(self.capture)
        for name,action in [('Clipboard',lambda:self.input.setText('clip ')),('Forget selected',self.forget),('Clear queue',self.clear_clips),('Close',self.hide)]:
            b=QPushButton(name);b.clicked.connect(action);row.addWidget(b)
        root.addLayout(row)
        self.results=QListWidget();self.results.setIconSize(__import__('PyQt6.QtCore',fromlist=['QSize']).QSize(64,48));root.addWidget(self.results,1)
        self.status=QLabel('Enter to open / launch / copy  ·  ↑↓ select  ·  Esc dismiss');self.status.setWordWrap(True);root.addWidget(self.status)
        self.debounce=QTimer(self);self.debounce.setSingleShot(True);self.debounce.setInterval(120);self.debounce.timeout.connect(self.refresh)
        self.input.textChanged.connect(self.queue_search);self.input.returnPressed.connect(self.execute)
        self.input.installEventFilter(self);self.results.itemActivated.connect(lambda _:self.execute())
        self.clipboard=QApplication.clipboard();self.clipboard.dataChanged.connect(self.capture_clipboard)
        self.poll=QTimer(self);self.poll.setInterval(30);self.poll.timeout.connect(self.finish_search);self.poll.start()
        self.fallback=QShortcut(QKeySequence('Ctrl+Space'),host);self.fallback.activated.connect(self.toggle)
        self.register_hotkey()

    def register_hotkey(self):
        if sys.platform=='win32':
            from ctypes import wintypes
            self.user32=ctypes.WinDLL('user32',use_last_error=True)
            self.user32.RegisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int,wintypes.UINT,wintypes.UINT]
            self.user32.UnregisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int]
            self.registered=bool(self.user32.RegisterHotKey(int(self.winId()),self.HOTKEY,0x4002,0x20))
            if not self.registered:self.status.setText('Ctrl+Space is already registered elsewhere. Use the header button or the app shortcut.')
            else:self.fallback.setEnabled(False)

    def nativeEvent(self, kind, message):
        if sys.platform=='win32':
            from ctypes.wintypes import MSG
            msg=MSG.from_address(int(message))
            if msg.message==0x312 and msg.wParam==self.HOTKEY:
                self.toggle();return True,0
        return False,0

    def toggle(self):
        if self.isVisible():self.hide();return
        screen=QApplication.screenAt(__import__('PyQt6.QtGui',fromlist=['QCursor']).QCursor.pos()) or QApplication.primaryScreen()
        rect=screen.availableGeometry();self.resize(min(760,rect.width()-40),min(510,rect.height()-40))
        self.move(rect.center().x()-self.width()//2,rect.top()+max(20,rect.height()//6))
        self.show();self.raise_();self.activateWindow();self.input.setFocus();self.input.selectAll();self.refresh()

    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Down,Qt.Key.Key_Up):
            step=1 if event.key()==Qt.Key.Key_Down else -1
            self.results.setCurrentRow(max(0,min(self.results.count()-1,self.results.currentRow()+step)));return True
        return super().eventFilter(obj,event)

    def queue_search(self):
        self.generation+=1;self.debounce.start()

    def add_result(self,title,data,icon=None):
        item=QListWidgetItem(title);item.setData(Qt.ItemDataRole.UserRole,data)
        if icon:item.setIcon(icon)
        self.results.addItem(item)

    def refresh(self):
        self.results.clear();query=self.input.text().strip()
        if query.startswith('clip'):
            for clip in self.archive.query(query[4:].strip()):
                icon=None
                if clip['image']:
                    pix=QPixmap();pix.loadFromData(clip['image']);icon=QIcon(pix)
                self.add_result(('IMAGE' if clip['kind']=='image' else clip['text'][:180]).replace('\n',' '),('clip',clip),icon)
        elif query.startswith('run '):
            term=query[4:].casefold()
            for project in self.host.store.list('project'):
                if term in (project['name']+' '+project['id']+' '+Path(project.get('script','')).stem).casefold():
                    self.add_result('RUN // '+project['name'],('run',project))
        elif query.startswith('set '):
            self.add_result('SET // shared Workshop value: '+query[4:],('set',query[4:]))
        elif query.startswith('go '):
            for page in self.host.page_ids:
                if query[3:].casefold() in page.casefold():self.add_result('OPEN // '+page,('go',page))
        else:
            # Coalesce requests: only one database query runs at a time.
            if self.future is None:
                self.future=(self.generation,self.pool.submit(search_history,self.host.store.root/'jumpback'/'history.sqlite3',query))
            return
        if self.results.count():self.results.setCurrentRow(0)

    def finish_search(self):
        if self.future is None or not self.future[1].done():return
        generation,future=self.future;self.future=None
        if generation!=self.generation:self.refresh();return
        try:
            rows=future.result();self.results.clear()
            for row in rows:self.add_result(row['kind']+' // '+row['title']+'\n'+(row['note'] or row['target'])[:150],('history',row))
            if rows:self.results.setCurrentRow(0)
            self.status.setText(f'{len(rows)} recent matches  ·  Enter open/copy  ·  run / set / clip / go')
        except Exception as error:self.status.setText('History unavailable: '+str(error))

    def execute(self):
        item=self.results.currentItem()
        if item is None:return
        kind,value=item.data(Qt.ItemDataRole.UserRole)
        try:
            if kind=='run':
                if len(self.host.runner.jobs)>=self.host.runner.max_parallel:raise ValueError('All execution slots are busy')
                ident=self.host.runner.launch(value,self.host.store.get('profile','default'),'Killchain')
                self.host.notice('KILLCHAIN // DEPLOYED '+ident[:8]);self.status.setText('Launched '+value['name']);return
            if kind=='set':
                key,sep,raw=value.partition(' ')
                if not sep:raise ValueError('Use set <key> <value>; JSON supported')
                try:parsed=json.loads(raw)
                except json.JSONDecodeError:parsed=raw
                self.host.store.set_shared(key,parsed);self.status.setText('Saved Workshop shared value: '+key);return
            if kind=='clip':
                if value['image']:self.clipboard.setImage(QImage.fromData(value['image']))
                else:self.clipboard.setText(value['text'])
            elif kind=='go':self.host.showNormal();self.host.navigate(value);self.host.raise_();self.host.activateWindow()
            else:
                target=value['target'];url=QUrl(target)
                if url.scheme() in ('http','https'):QDesktopServices.openUrl(url)
                elif target and Path(target).exists():QDesktopServices.openUrl(QUrl.fromLocalFile(target))
                else:self.clipboard.setText(value['note'] or target or value['title'])
            self.hide()
        except Exception as error:self.status.setText(str(error))

    def capture_changed(self,enabled):
        self.host.settings['clipboard_capture']=enabled;self.host.store.put('settings','app',self.host.settings)
        deck=getattr(self.host,'settings_deck',None)
        if deck is not None:deck.clipboard_capture.setChecked(enabled)

    def capture_clipboard(self):
        if not self.capture.isChecked() or self.stopped:return
        try:
            mime=self.clipboard.mimeData()
            if mime.hasImage():
                image=self.clipboard.image()
                if image.isNull():return
                if image.width()*image.height()>16000000:return
                data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.OpenModeFlag.WriteOnly);image.save(buffer,'PNG')
                if data.size()<=16*1024*1024:self.archive.add(image=bytes(data))
            elif mime.hasText():
                text=mime.text()
                if len(text)<=1000000:self.archive.add(text=text)
            if self.isVisible() and self.input.text().startswith('clip'):self.refresh()
        except Exception as error:self.status.setText('Clipboard capture: '+str(error))

    def forget(self):
        item=self.results.currentItem()
        if item and item.data(Qt.ItemDataRole.UserRole)[0]=='clip':
            self.archive.remove(item.data(Qt.ItemDataRole.UserRole)[1]['id']);self.refresh()

    def clear_clips(self):
        self.archive.remove();self.input.setText('clip ');self.refresh()

    def shutdown(self):
        self.stopped=True;self.poll.stop();self.debounce.stop();self.hide()
        self.clipboard.dataChanged.disconnect(self.capture_clipboard)
        if self.registered:self.user32.UnregisterHotKey(int(self.winId()),self.HOTKEY)
        self.pool.shutdown(wait=False,cancel_futures=True)
