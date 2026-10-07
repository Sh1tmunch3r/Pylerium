"""Jumpback: searchable local activity with visible capture and pause controls."""
import datetime as dt
import time
import uuid
from pathlib import Path
from threading import Event

from PyQt6.QtCore import Qt, QTimer, QThreadPool, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSplitter, QFrame, QPlainTextEdit,
    QFileDialog, QDialog, QDialogButtonBox, QInputDialog)

from asset_helper import AssetTask
from .scanner import get_recent_items
from .collectors import collect_history, ForegroundReader, allowed
from .history_store import HistoryStore, SessionRecorder, event_key

STYLE = '''
QWidget {color:#dce8ee;font-family:Segoe UI;font-size:12px;}
QWidget#jumpback {background:#090e13;color:#e8f0f4;}
QFrame#jbCard {background:#121d25;border:1px solid #2b3f4c;border-radius:9px;}
QLineEdit,QComboBox,QPlainTextEdit {background:#0c151d;border:1px solid #304957;
    border-radius:5px;padding:9px;color:#d8e9f0;selection-background-color:#78401d;}
QLineEdit:focus,QPlainTextEdit:focus {border-color:#ef8a43;}
QPushButton {background:#172833;border:1px solid #355264;border-radius:5px;padding:8px 14px;}
QPushButton:hover {background:#243d4c;border-color:#eb8844;}
QPushButton#jbPrimary {background:#c75c20;border-color:#ef8a43;color:white;font-weight:bold;}
QPushButton:disabled {color:#607582;}
QTableWidget {background:#0c141b;alternate-background-color:#101e27;border:1px solid #2b3f4c;
    border-radius:6px;gridline-color:#172a36;selection-background-color:#283d49;}
QHeaderView::section {background:#152631;color:#9fb7c5;border:0;padding:10px;}
QLabel {background:transparent;border:0;}
'''


def button(text, callback, primary=False):
    widget = QPushButton(text)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.clicked.connect(callback)
    if primary:
        widget.setObjectName('jbPrimary')
    return widget


def local_date(stamp):
    try:
        return dt.datetime.fromtimestamp(stamp).strftime('%d %b %Y  %H:%M:%S')
    except (ValueError, OSError, OverflowError):
        return 'Unknown time'


def today_start():
    return dt.datetime.combine(dt.date.today(), dt.time.min).timestamp()


def duration_label(seconds):
    minutes = int(seconds // 60)
    return f'{minutes // 60}h {minutes % 60:02d}m' if minutes >= 60 else f'{minutes}m {int(seconds % 60):02d}s'


class RedeployPage(QWidget):
    page_size = 100

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.store = HistoryStore(Path(ctx.store.root) / 'jumpback' / 'history.sqlite3')
        self.recorder = SessionRecorder(self.store)
        self.reader = ForegroundReader()
        self.scan_cancel = Event()
        self.import_cancel = Event()
        self.scan_task = self.query_task = self.record_task = None
        self.tasks = {}
        self.generation = self.offset = self.total = 0
        self.rows = []
        self.selected = None
        self.report = self.store.get('source_report', [])
        self.recording = self.store.get('recording', True)
        self.capture_epoch = uuid.uuid4().hex
        self.store.set('capture_epoch', self.capture_epoch)
        self.note_dirty = False
        self.setObjectName('jumpback'); self.setStyleSheet(STYLE)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True); self.search_timer.setInterval(250)
        self.search_timer.timeout.connect(self.request_query)
        self.build_ui()
        self.update_recording_label()
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh_data); self.timer.start(30_000)
        self.record_timer = QTimer(self); self.record_timer.timeout.connect(self.record_activity); self.record_timer.start(2000)
        self.live_timer = QTimer(self); self.live_timer.timeout.connect(self.refresh_visible); self.live_timer.start(5000)
        self.request_query(); self.refresh_data()

    def build_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(22,18,22,18); layout.setSpacing(14)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel('JUMPBACK  /  YOUR ACTIVITY ARCHIVE')
        title.setStyleSheet('font-size:24px;font-weight:bold;color:#f0f6f8;')
        titles.addWidget(title)
        subtitle = QLabel('Find the page, file, video or idea you were working on. Keep the trail.')
        subtitle.setStyleSheet('color:#90acbd;font-size:12px;'); titles.addWidget(subtitle)
        header.addLayout(titles,1)
        self.record_badge = QLabel(); header.addWidget(self.record_badge)
        self.pause_button = button('',self.toggle_recording,True); header.addWidget(self.pause_button)
        header.addWidget(button('Sources & exclusions',self.configure_sources)); layout.addLayout(header)
        metrics = QHBoxLayout(); self.metrics = {}
        for key,caption in [('total','ARCHIVED EVENTS'),('today','EVENTS TODAY'),
                            ('web','WEB & YOUTUBE VISITS'),('focus','ACTIVE APP TIME TODAY')]:
            card = QFrame(); card.setObjectName('jbCard'); box = QVBoxLayout(card)
            label = QLabel(caption); label.setStyleSheet('font-size:10px;color:#8cabbc;')
            value = QLabel('—'); value.setStyleSheet('font-size:25px;font-weight:bold;color:#50d7df;')
            box.addWidget(label); box.addWidget(value); self.metrics[key]=value; metrics.addWidget(card)
        layout.addLayout(metrics)
        filters = QHBoxLayout()
        self.search=QLineEdit(); self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText('Search your entire archive: title, URL, app, file path or note…')
        self.search.textChanged.connect(self.filter_changed); filters.addWidget(self.search,1)
        self.kind=QComboBox()
        for title,code in [('Everything','ALL'),('Web pages','WEB'),('YouTube','VIDEO'),('Apps / sessions','APP'),
                           ('Documents','DOC'),('Code','SRC'),('Folders','DIR'),('Games','GAME'),
                           ('Media','MEDIA'),('Saved moments','MOMENT'),('Other','GENERIC')]:
            self.kind.addItem(title,code)
        self.kind.currentIndexChanged.connect(self.filter_changed); filters.addWidget(self.kind)
        self.source=QComboBox(); self.source.addItem('All sources','ALL')
        self.source.currentIndexChanged.connect(self.filter_changed); filters.addWidget(self.source)
        self.period=QComboBox()
        for title,days in [('All time',0),('Today',-1),('Last 7 days',7),('Last 30 days',30),('Last year',365)]:
            self.period.addItem(title,days)
        self.period.currentIndexChanged.connect(self.filter_changed); filters.addWidget(self.period)
        self.pinned=QCheckBox('Bookmarks'); self.pinned.toggled.connect(self.filter_changed); filters.addWidget(self.pinned)
        layout.addLayout(filters)
        split=QSplitter(Qt.Orientation.Horizontal)
        self.table=QTableWidget(0,5)
        self.table.setHorizontalHeaderLabels(['TIME','TYPE','ACTIVITY','SOURCE','ACTIVE TIME'])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide(); self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        for col,width in [(0,175),(1,80),(3,145),(4,100)]: self.table.setColumnWidth(col,width)
        self.table.itemSelectionChanged.connect(self.show_selection)
        self.table.itemDoubleClicked.connect(self.open_selected); split.addWidget(self.table)
        detail=QFrame(); detail.setObjectName('jbCard'); detail.setMinimumWidth(280); box=QVBoxLayout(detail)
        box.addWidget(QLabel('ACTIVITY DETAILS'))
        self.detail_title=QLabel('Select a moment from your timeline'); self.detail_title.setWordWrap(True)
        self.detail_title.setStyleSheet('font-size:18px;font-weight:bold;color:#f0f6f8;'); box.addWidget(self.detail_title)
        self.detail_meta=QLabel('Your archive stays on this PC. No expiry is applied.'); self.detail_meta.setWordWrap(True)
        self.detail_meta.setStyleSheet('color:#91acbc;'); box.addWidget(self.detail_meta)
        self.detail_target=QPlainTextEdit(); self.detail_target.setReadOnly(True); self.detail_target.setMaximumHeight(115)
        box.addWidget(self.detail_target)
        controls=QHBoxLayout(); self.open_button=button('Open',self.open_selected,True)
        self.copy_button=button('Copy target',self.copy_selected); controls.addWidget(self.open_button); controls.addWidget(self.copy_button)
        box.addLayout(controls); self.pin_button=button('Bookmark',self.toggle_pin); box.addWidget(self.pin_button)
        box.addWidget(QLabel('YOUR NOTES')); self.note=QPlainTextEdit()
        self.note.setPlaceholderText('Why did this matter? Add context for your future self.')
        self.note.textChanged.connect(self.mark_note_dirty); box.addWidget(self.note,1)
        self.note_button=button('Save note',self.save_note); box.addWidget(self.note_button)
        split.addWidget(detail); split.setStretchFactor(0,3); split.setStretchFactor(1,1); layout.addWidget(split,1)
        footer=QHBoxLayout(); self.count_label=QLabel('Loading archive…'); footer.addWidget(self.count_label,1)
        self.prev_button=button('← Newer',lambda:self.move_page(-1)); self.next_button=button('Older →',lambda:self.move_page(1))
        footer.addWidget(self.prev_button); footer.addWidget(self.next_button)
        footer.addWidget(button('Save a moment',self.save_moment)); footer.addWidget(button('Import now',self.refresh_data))
        footer.addWidget(button('Export results',self.export_results)); layout.addLayout(footer)
        self.status=QLabel('Reading available history in the background…'); self.status.setWordWrap(True)
        self.status.setStyleSheet('color:#8fb5c4;font-size:11px;'); layout.addWidget(self.status)
        scope=QLabel('Captures saved browser visits, Windows recent items and foreground app titles while Pylerium runs. '
                    'Private/deleted browser history and unsaved in-page actions cannot be reconstructed. '
                    'App time is approximate, sampled every 2s and excludes idle after 60s. No keystrokes, screenshots or page contents.')
        scope.setWordWrap(True); scope.setStyleSheet('color:#718997;font-size:10px;'); layout.addWidget(scope)
        self.set_detail_enabled(False)

    def start_task(self, operation, function, generation=None):
        key=(operation,uuid.uuid4().hex,generation); task=AssetTask(key,function); self.tasks[key]=task
        task.signals.finished.connect(self.task_finished); QThreadPool.globalInstance().start(task)
        return task

    def filters(self):
        days=self.period.currentData()
        since=today_start() if days==-1 else time.time()-days*86400 if days else 0
        return dict(text=self.search.text().strip(),kind=self.kind.currentData(),source=self.source.currentData(),
                    since=since,pinned=self.pinned.isChecked())

    def filter_changed(self,*_):
        if self.note_dirty: self.save_note()
        self.offset=0; self.generation+=1; self.search_timer.start()

    def set_filter(self,category):
        index=self.kind.findData(category)
        if index>=0: self.kind.setCurrentIndex(index)

    def request_query(self):
        if self.scan_cancel.is_set() or self.query_task is not None: return
        filters,offset,store,today=self.filters(),self.offset,self.store,today_start()
        self.query_task=self.start_task('query',lambda:(store.query(**filters,offset=offset),store.summary(today)),self.generation)

    def refresh_visible(self):
        if self.isVisible() and not self.search_timer.isActive(): self.request_query()

    def refresh_data(self):
        if self.scan_cancel.is_set() or self.scan_task is not None: return
        if not self.recording:
            self.status.setText('Paused. Existing history remains searchable. Resume to append new activity.'); return
        self.status.setText('Importing saved history in the background… You can keep searching.')
        self.import_cancel = Event()
        store,cancel,scanner=self.store,self.import_cancel,get_recent_items
        self.scan_task=self.start_task('import',lambda:collect_history(store,cancel,scanner))

    def record_activity(self):
        if self.scan_cancel.is_set() or self.record_task is not None: return
        recorder,reader,store,cancel=self.recorder,self.reader,self.store,self.scan_cancel
        enabled=self.recording
        epoch=self.capture_epoch
        def record():
            if cancel.is_set(): return
            if getattr(recorder,'epoch',None)!=epoch:
                recorder.sample(None); recorder.epoch=epoch
            activity=reader.read() if enabled and store.get('recording', True) else None
            if activity and not allowed(activity,store.get('exclusions',[])): activity=None
            if store.get('capture_epoch')!=epoch: activity=None
            if not cancel.is_set(): recorder.sample(activity)
        self.record_task=self.start_task('record',record)

    def task_finished(self,key,result,error):
        self.tasks.pop(key,None)
        if self.scan_cancel.is_set(): return
        operation=key[0]
        if operation=='query':
            self.query_task=None
            if key[2]!=self.generation: self.request_query(); return
            if not error: self.render_query(result)
        elif operation=='import':
            self.scan_task=None
            if not error:
                self.report=result['sources']; self.store.set('source_report',self.report)
                problems=sum(source['status']!='Ready' for source in self.report)
                self.status.setText(f"Archive updated {dt.datetime.now():%H:%M:%S} • {result['imported']:,} new events • "
                                    f'{len(self.report)} sources • {problems} need attention. Details in Sources & exclusions.')
                self.generation+=1; self.request_query()
                if self.recording and self.import_cancel.is_set(): self.refresh_data()
        elif operation=='record': self.record_task=None
        elif operation=='export': self.status.setText(f'Exported {result:,} matching events.' if not error else 'Export failed: '+error)
        elif operation=='mutation': self.generation+=1; self.request_query()
        if error: self.status.setText(operation.capitalize()+' failed: '+error)

    def render_query(self,result):
        (rows,self.total),(metrics,sources)=result; self.rows=rows
        selected_id=self.selected['id'] if self.selected else None; current_source=self.source.currentData()
        self.source.blockSignals(True); self.source.clear(); self.source.addItem('All sources','ALL')
        for source in sources: self.source.addItem(source,source)
        self.source.setCurrentIndex(max(0,self.source.findData(current_source))); self.source.blockSignals(False)
        for key,value in metrics.items(): self.metrics[key].setText(duration_label(value) if key=='focus' else f'{value:,}')
        self.table.blockSignals(True); self.table.setRowCount(len(rows)); chosen=-1
        for index,row in enumerate(rows):
            title=('[saved]  ' if row['pinned'] else '')+row['title']
            values=[local_date(row['occurred']),row['kind'],title,row['source'],duration_label(row['duration']) if row['kind']=='APP' else '—']
            for col,value in enumerate(values):
                item=QTableWidgetItem(str(value)); item.setToolTip(row['target'] if col==2 else str(value)); self.table.setItem(index,col,item)
            if row['id']==selected_id: chosen=index
        if chosen>=0: self.table.selectRow(chosen)
        else: self.table.clearSelection()
        self.table.blockSignals(False)
        if chosen>=0: self.show_selection()
        elif not self.note_dirty:
            self.selected=None; self.set_detail_enabled(False)
            self.detail_title.setText('No matches' if not rows else 'Select a moment from your timeline')
            self.detail_target.clear(); self.note.clear()
        start=self.offset+1 if rows else 0
        self.count_label.setText(f'{start:,}–{self.offset+len(rows):,} of {self.total:,} matches  /  all history is searchable')
        self.prev_button.setEnabled(self.offset>0); self.next_button.setEnabled(self.offset+len(rows)<self.total)

    def move_page(self,direction):
        self.offset=max(0,self.offset+direction*self.page_size); self.generation+=1; self.request_query()

    def set_detail_enabled(self,enabled):
        for widget in (self.open_button,self.copy_button,self.pin_button,self.note,self.note_button): widget.setEnabled(enabled)

    def show_selection(self):
        index=self.table.currentRow()
        if index<0 or index>=len(self.rows): return
        row=self.rows[index]; same=self.selected and self.selected['id']==row['id']
        if self.note_dirty and self.selected and not same: self.save_note()
        self.selected=row; self.set_detail_enabled(True); self.detail_title.setText(row['title'])
        self.detail_meta.setText(f"{local_date(row['occurred'])}\n{row['source']}  /  {row['kind']}\n{row['app']}\n{row['detail']}"+
                                 (f"\nActive time: {duration_label(row['duration'])}" if row['kind']=='APP' else ''))
        self.detail_target.setPlainText(row['target']); self.pin_button.setText('Bookmarked / remove' if row['pinned'] else 'Bookmark')
        if not same or not self.note_dirty:
            self.note.blockSignals(True); self.note.setPlainText(row['note']); self.note.blockSignals(False)
            self.note_dirty=False; self.note_button.setText('Save note')

    def mark_note_dirty(self):
        if self.selected: self.note_dirty=True; self.note_button.setText('Save note • unsaved')

    def save_note(self):
        if not self.selected: return
        store,ident,note,revision=self.store,self.selected['id'],self.note.toPlainText(),time.time_ns()
        self.start_task('mutation',lambda:store.annotate(ident,note=note,revision=revision))
        self.selected['note']=note; self.note_dirty=False; self.note_button.setText('Save note')

    def toggle_pin(self):
        if self.selected:
            store,ident,pinned=self.store,self.selected['id'],not self.selected['pinned']
            self.start_task('mutation',lambda:store.annotate(ident,pinned=pinned))

    def copy_selected(self):
        if self.selected:
            QApplication.clipboard().setText(self.selected['target'] or self.selected['title']); self.status.setText('Copied to clipboard.')

    def open_selected(self,*_):
        if not self.selected or not self.selected['target']: return
        target=self.selected['target']; url=QUrl(target)
        if url.scheme().lower() in ('http','https','steam'): opened=QDesktopServices.openUrl(url)
        else:
            path=Path(url.toLocalFile()) if url.isLocalFile() else Path(target)
            if not path.exists():
                self.status.setText('The original file is no longer available. Its history and notes remain archived.'); return
            if path.suffix.lower() in ('.exe','.bat','.cmd','.ps1','.py','.lnk'): path=path.parent
            opened=QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        if not opened: self.status.setText('Windows could not open this target. You can copy its address instead.')

    def update_recording_label(self):
        self.record_badge.setText('● RECORDING LOCALLY' if self.recording else '● PAUSED')
        self.record_badge.setStyleSheet('color:#50d7df;font-weight:bold;' if self.recording else 'color:#efaa63;font-weight:bold;')
        self.pause_button.setText('Pause capture' if self.recording else 'Resume capture')
        for _,_,nav in getattr(self.ctx,'pages',[]):
            nav.setText('JUMPBACK / REC' if self.recording else 'JUMPBACK / PAUSED')

    def toggle_recording(self):
        self.recording=not self.recording; self.store.set('recording',self.recording); self.update_recording_label()
        self.capture_epoch=uuid.uuid4().hex; self.store.set('capture_epoch',self.capture_epoch)
        if self.recording:
            started=self.store.get('pause_started')
            if started:
                intervals=self.store.get('pause_intervals',[])
                intervals.append([started,time.time()]); self.store.set('pause_intervals',intervals)
                self.store.set('pause_started',None)
            self.refresh_data()
        else:
            self.store.set('pause_started',time.time())
            self.import_cancel.set()
            self.status.setText('Capture paused. Existing history remains searchable; no new imports or app sessions will start.')
        self.ctx.log('Jumpback capture '+('resumed' if self.recording else 'paused'))

    def save_moment(self):
        text,ok=QInputDialog.getMultiLineText(self,'Save a moment','What are you doing or want to remember?')
        if ok and text.strip():
            store=self.store
            event=dict(event_key=event_key('moment',uuid.uuid4().hex),occurred=time.time(),kind='MOMENT',
                       source='Your moments',title=text.strip().splitlines()[0],detail=text.strip())
            self.start_task('mutation',lambda:store.append([event]))

    def export_results(self):
        filename,_=QFileDialog.getSaveFileName(self,'Export every matching event','jumpback-history.json',
                                              'JSON archive (*.json);;CSV spreadsheet (*.csv)')
        if filename:
            store,filters,cancel=self.store,self.filters(),self.scan_cancel
            self.start_task('export',lambda:store.export(filename,filters,cancel))
            self.status.setText('Exporting all matching events in the background…')

    def configure_sources(self):
        dialog=QDialog(self); dialog.setWindowTitle('Jumpback / Sources & exclusions'); dialog.resize(780,650)
        box=QVBoxLayout(dialog); box.addWidget(QLabel('SOURCE HEALTH / last import'))
        table=QTableWidget(len(self.report),3); table.setHorizontalHeaderLabels(['Source','Status','Details'])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        for index,source in enumerate(self.report):
            for col,value in enumerate([source['source'],source['status'],source['message']]):
                item=QTableWidgetItem(value); item.setToolTip(source['path']); table.setItem(index,col,item)
        box.addWidget(table,1); box.addWidget(QLabel('CUSTOM BROWSER DATABASES / one full path per line'))
        paths=QPlainTextEdit(); paths.setPlainText('\n'.join(self.store.get('custom_sources',[]))); paths.setMaximumHeight(100); box.addWidget(paths)
        def add_path():
            filename,_=QFileDialog.getOpenFileName(dialog,'Choose browser History or places.sqlite','','All files (*)')
            if filename: paths.appendPlainText(filename)
        box.addWidget(button('Add browser history file…',add_path))
        box.addWidget(QLabel('EXCLUDE FUTURE CAPTURE / app names, domains, titles or path fragments; one per line'))
        exclusions=QPlainTextEdit(); exclusions.setPlainText('\n'.join(self.store.get('exclusions',[]))); exclusions.setMaximumHeight(100); box.addWidget(exclusions)
        info=QLabel(f'Archive: {self.store.path}\nRecords are retained without expiry. Exclusions do not remove existing records. '
                    'Browser history is read only; cookies, passwords, clipboard and page content are not imported. '
                    'Detected private-window titles are skipped. Custom profiles can be added above.')
        info.setWordWrap(True); box.addWidget(info)
        actions=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        actions.accepted.connect(dialog.accept); actions.rejected.connect(dialog.reject); box.addWidget(actions)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.store.set('custom_sources',[line.strip() for line in paths.toPlainText().splitlines() if line.strip()])
            self.store.set('exclusions',[line.strip() for line in exclusions.toPlainText().splitlines() if line.strip()])
            self.status.setText('Settings saved. New settings apply on the next capture/import.'); self.refresh_data()

    def stop(self):
        if self.note_dirty and self.selected:
            self.store.annotate(self.selected['id'],note=self.note.toPlainText()); self.note_dirty=False
        self.scan_cancel.set(); self.import_cancel.set()
        self.timer.stop(); self.record_timer.stop(); self.search_timer.stop(); self.live_timer.stop()


_active_page=None


def register(ctx):
    global _active_page
    _active_page=RedeployPage(ctx)
    ctx.add_page('Jumpback',_active_page)
    _active_page.update_recording_label()
    ctx.add_action('Jumpback / pause or resume capture',_active_page.toggle_recording)
    def finished(run_id,status):
        if _active_page and _active_page.recording:
            store=_active_page.store
            run=ctx.store.db.execute('SELECT name,started,ended,exit_code FROM runs WHERE id=?',(run_id,)).fetchone()
            name=run[0] if run else run_id
            event=dict(event_key=event_key('run',run_id),occurred=time.time(),kind='MOMENT',
                       source='Pylerium runs',title=f'{name} / {status}',
                       detail=f'Run: {run_id}\nExit code: {run[3] if run else "unknown"}')
            _active_page.start_task('mutation',lambda:store.append([event]))
    ctx.on('run_finished',finished)
    ctx.log('Jumpback archive ready. Local capture is '+('on' if _active_page.recording else 'paused')+
            '. Search, sources, exclusions and pause controls are on the Jumpback page.')


def unregister(ctx):
    global _active_page
    if _active_page: _active_page.stop(); _active_page=None
