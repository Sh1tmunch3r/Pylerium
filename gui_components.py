"""Shared styling and widget factories used by Pylerium and Workshop GUIs."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QPushButton, QFrame, QVBoxLayout,QWidget,QScrollArea,QHBoxLayout


class Disclosure(QWidget):
    """Compact optional controls; content and state survive collapse."""
    def __init__(self,title,content,expanded=False):
        super().__init__();box=QVBoxLayout(self);box.setContentsMargins(0,0,0,0);box.setSpacing(6)
        self.toggle=QPushButton(title);self.toggle.setCheckable(True);self.toggle.setChecked(expanded)
        self.toggle.setToolTip('Show or hide '+title.lower());self.content=content
        self.toggle.toggled.connect(content.setVisible);content.setVisible(expanded)
        box.addWidget(self.toggle);box.addWidget(content)


def horizontal_strip(height=62):
    """Scrollable action/navigation row that keeps buttons usable in large workspaces."""
    scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFixedHeight(height)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet('QScrollArea {background:transparent;border:0;}')
    content=QWidget();row=QHBoxLayout(content);row.setContentsMargins(0,0,0,0)
    scroll.setWidget(content);content.setAutoFillBackground(False);scroll.viewport().setAutoFillBackground(False)
    return scroll,row

STYLE = '''
QWidget {color:#e7e9eb;font-family:Arial;font-size:13px;}
QLabel {background:transparent;}
QFrame#panel {background:rgba(10,14,17,220);border:1px solid #344047;}
QPushButton,QToolButton {background:#262b2f;border:1px solid #50595f;padding:8px 12px;color:#d3d6d8;min-height:18px;}
QPushButton:hover,QToolButton:hover {background:#3a4044;border-color:#f06413;color:white;}
QPushButton:checked, QPushButton#deploy {background:#8c3008;border:1px solid #ff7b1c;color:white;}
QPushButton:disabled {color:#566066;background:#161a1d;border-color:#262d31;}
QLineEdit,QPlainTextEdit,QComboBox,QSpinBox {background:#0b1115;color:#cbdee3;border:1px solid #3b474d;padding:8px;selection-background-color:#8c3008;}
QPlainTextEdit {font-family:Consolas;font-size:15px;}
QListWidget,QTableWidget,QTreeWidget {background:rgba(10,14,17,220);border:1px solid #344047;alternate-background-color:#171e22;}
QListWidget::item {padding:12px;border-bottom:1px solid #252e33;}
QListWidget::item:selected {background:#414243;border-left:3px solid #f06413;}
QHeaderView::section {background:#20282e;color:#a3b4bc;border:0;padding:9px;}
QCheckBox {spacing:10px;padding:6px;}
QSplitter::handle {background:#344047;}
QScrollBar:vertical {background:#10171b;width:8px;}
QScrollBar::handle:vertical {background:#52616a;min-height:30px;}
QScrollBar:horizontal {background:#10171b;height:8px;}
QScrollBar::handle:horizontal {background:#52616a;min-width:30px;}
QScrollBar::add-line,QScrollBar::sub-line {width:0;height:0;}
QScrollBar::add-page,QScrollBar::sub-page {background:transparent;}
QMenuBar,QMenu,QToolBar,QStatusBar {background:#10171b;color:#e7e9eb;border:1px solid #344047;}
QMenu::item {padding:8px 25px;}
QMenu::item:selected,QMenuBar::item:selected {background:#8c3008;color:white;}
QTabWidget::pane {border:1px solid #344047;background:#0b1115;}
QTabBar {background:#10171b;}
QTabBar::tab {background:#20282e;padding:10px 16px;color:#a3b4bc;}
QTabBar::tab:selected {color:white;border-bottom:2px solid #f06413;}
QProgressBar {background:#0b1115;border:1px solid #344047;color:#cbdee3;text-align:center;}
QProgressBar::chunk {background:#26d8ee;}
QDialog {background:#0b1115;}
QToolTip {background:#111315;color:white;border:1px solid #f06413;padding:6px;}
QSlider::groove:horizontal {background:#26343c;height:6px;border-radius:3px;}
QSlider::handle:horizontal {background:#26d8ee;width:14px;margin:-4px 0;border-radius:5px;}
QDateEdit,QDoubleSpinBox {background:#0b1115;color:#cbdee3;border:1px solid #3b474d;padding:8px;}
'''


def label(text, size=14, color='#e7e9eb'):
    widget=QLabel(text); widget.setWordWrap(True)
    widget.setStyleSheet(f'color:{color};font-size:{size}px;')
    return widget


def button(text, callback, primary=False):
    widget=QPushButton(text); widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.clicked.connect(callback)
    from ui_audio import play_cue
    widget.clicked.connect(lambda:play_cue("click"))
    if primary: widget.setObjectName('deploy')
    return widget


def panel():
    widget=QFrame(); widget.setObjectName('panel')
    layout=QVBoxLayout(widget); layout.setContentsMargins(20,20,20,20); layout.setSpacing(12)
    return widget,layout
