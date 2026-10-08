"""Public Workshop GUI toolkit. Reuses application widgets and shared style."""
import runpy
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import *

from ui_icons import action_icon, icon_button
from gui_components import STYLE, button, label, panel,horizontal_strip
from asset_helper import ASSETS, AssetTask
from workshop_editor import WorkshopEditor
from editor_focus import EditorCard
from ui_audio import audio_engine, configure_audio, play_cue
from terminal_console import TerminalConsole

_theme=None
THEME_EXPORTS = ('BackgroundWidget','IconButton','TopBar','SidebarLoadoutButton',
    'LoadoutSidebar','LoadoutCard','SelectorItem','ItemSelectorDialog','StatBar',
    'WeaponPreviewCanvas','PreviewPanel','LoadoutGrid','LoadoutWindow','LoadoutItem','Loadout',
    'font','condensed_font','BG','PANEL','PANEL_2','CARD','CARD_HOVER','CARD_SELECTED',
    'TEXT','TEXT_DIM','TEXT_DARK','ORANGE','ORANGE_BRIGHT','ORANGE_DARK','CYAN','CYAN_GLOW','BORDER','BLACK')


def register_theme(theme):
    global _theme
    _theme=theme


def theme():
    global _theme
    if _theme is None:
        main=sys.modules.get('__main__')
        if main is not None and hasattr(main,'BackgroundWidget') and hasattr(main,'LoadoutCard'):
            _theme=SimpleNamespace(**vars(main))
        else:
            # Loads class definitions only: the guarded application entry is not run.
            from app_paths import resource_root
            _theme=SimpleNamespace(**runpy.run_path(str(resource_root()/'orchestration-menu.py')))
    return _theme


def __getattr__(name):
    if name=='InspectWeaponDialog':
        from model_inspector import InspectWeaponDialog
        return InspectWeaponDialog
    if name in THEME_EXPORTS:
        return getattr(theme(),name)
    if name=='WorkflowMap':
        from orchestration_ui import WorkflowMap
        return WorkflowMap
    if name=='NodeDialog':
        from workflow_builder import NodeDialog
        return NodeDialog
    if name=='InteractiveModelCanvas':
        from model_preview import InteractiveModelCanvas
        return InteractiveModelCanvas
    raise AttributeError(name)


def create_application(name='Pylerium GUI'):
    app=QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(name); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    import os,json
    from PyQt6.QtCore import QSettings
    settings=QSettings('Pylerium',name)
    try:audio_options=json.loads(os.environ.get('PYLERIUM_AUDIO',settings.value('audio/options','{}')))
    except (ValueError,TypeError):audio_options={}
    audio_engine().configure(audio_options)
    from PyQt6.QtGui import QIcon
    icon=os.environ.get('PYLERIUM_APP_ICON')
    if icon and Path(icon).is_file():app.setWindowIcon(QIcon(icon))
    return app


def demo_loadout(name='My loadout'):
    source=theme()
    return source.Loadout(name=name,primary=source.PRIMARY_ITEMS[0],secondary=source.SECONDARY_ITEMS[0],
        melee=source.MELEE_ITEMS[0],tactical=source.TACTICAL_ITEMS[0],lethal=source.LETHAL_ITEMS[0],
        field_upgrade=source.FIELD_ITEMS[0],perk1=source.PERK_1_ITEMS[0],perk2=source.PERK_2_ITEMS[0],
        perk3=source.PERK_3_ITEMS[0],specialty=source.SPECIALTY_ITEMS[0],wildcard=source.WILDCARD_ITEMS[0])


class AppWindow(QMainWindow):
    """Independent application window; compose only the widgets your tool needs."""
    def __init__(self,title='MY APPLICATION',subtitle='',motion=False):
        super().__init__()
        self.setWindowTitle(title); self.resize(960,640); self.setMinimumSize(400,300)
        self.setStyleSheet(STYLE)
        self.pages={}; self.nav={}; self.tasks={}
        self.background=theme().BackgroundWidget() if motion else QWidget()
        self.background.setObjectName('applicationContent')
        self.background.setStyleSheet('QWidget#applicationContent {background:#0b1115;}')
        self.setCentralWidget(self.background)
        self.content=QVBoxLayout(self.background); self.content.setContentsMargins(16,16,16,16)
        self.content.setSpacing(12)
        self.stack=None; self.navigation=None; self.toolbar=None; self.file_menu=None

    @property
    def theme(self):
        """Load optional original widgets only when explicitly requested."""
        return theme()

    def add_action(self,title,callback,shortcut=None,menu=None):
        action=QAction(title,self); action.triggered.connect(callback)
        if shortcut: action.setShortcut(shortcut)
        if self.toolbar is None:
            self.toolbar=self.addToolBar('Actions'); self.toolbar.setMovable(False)
        if self.file_menu is None:self.file_menu=self.menuBar().addMenu('File')
        self.toolbar.addAction(action)
        (menu or self.file_menu).addAction(action)
        return action

    def add_page(self,name,subtitle=''):
        if self.stack is None:
            navigation_scroll,self.navigation=horizontal_strip()
            self.content.addWidget(navigation_scroll)
            self.stack=QStackedWidget(); self.content.addWidget(self.stack,1)
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(0,16,0,0)
        layout.addWidget(label(name,28))
        if subtitle: layout.addWidget(label(subtitle,12,'#9aabb4'))
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(page)
        page.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        scroll.setStyleSheet('QScrollArea {background:transparent;border:0;}')
        index=self.stack.addWidget(scroll); self.pages[name]=scroll
        item=button(name.upper(),lambda checked=False,n=name:self.navigate(n)); item.setCheckable(True)
        self.nav[name]=item; self.navigation.addWidget(item)
        if len(self.pages)==1: self.navigate(name)
        return layout

    def navigate(self,name):
        self.stack.setCurrentWidget(self.pages[name])
        for title,item in self.nav.items(): item.setChecked(title==name)

    def notice(self,message):
        self.statusBar().showMessage(str(message))

    def fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape and self.isFullScreen(): self.showNormal()
        else: super().keyPressEvent(event)

    def run_background(self,function,on_success=None,on_error=None):
        """Run blocking work off-thread; callbacks are delivered on the GUI thread."""
        key=uuid.uuid4().hex; task=AssetTask(key,function)
        self.tasks[key]=(task,on_success,on_error)
        task.signals.finished.connect(self._task_finished); QThreadPool.globalInstance().start(task)
        return key

    def _task_finished(self,key,result,error):
        task,success,failure=self.tasks.pop(key)
        play_cue("error" if error else "success")
        if error:
            if failure: failure(error)
            else: self.notice('Task failed: '+error)
        elif success: success(result)


# Compatibility for saved Workshop projects. New projects use AppWindow.
SystematicWindow=AppWindow
PyleriumWindow=AppWindow


def run(window):
    """Keep the top-level window alive for the application's event loop."""
    window.show()
    return QApplication.instance().exec()
