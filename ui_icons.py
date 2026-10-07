"""Small vector action icons, rendered crisply at multiple display scales."""
from functools import lru_cache
from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

PATHS={
    'command':'<path d="m5 7 5 5-5 5M13 17h6"/>',
    'fullscreen':'<path d="M9 4H4v5m11-5h5v5M4 15v5h5m11-5v5h-5"/>',
    'stop':'<rect x="6" y="6" width="12" height="12" rx="1.5"/>',
}

@lru_cache(maxsize=24)
def action_icon(name,colour='#d3d6d8'):
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g fill="none" stroke="{colour}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</g></svg>'
    renderer=QSvgRenderer(QByteArray(svg.encode()));icon=QIcon()
    for scale in (1,2,3):
        pixmap=QPixmap(22*scale,22*scale);pixmap.fill(Qt.GlobalColor.transparent)
        pixmap.setDevicePixelRatio(scale);painter=QPainter(pixmap)
        renderer.render(painter);painter.end();icon.addPixmap(pixmap)
    return icon

def icon_button(name,tooltip,callback):
    from gui_components import button
    widget=button('',callback);widget.setIcon(action_icon(name,'#ff7b1c' if name=='stop' else '#d3d6d8'))
    widget.setIconSize(QSize(22,22));widget.setFixedSize(40,40)
    widget.setStyleSheet('QPushButton {padding:8px;min-height:0px;}')
    widget.setToolTip(tooltip);widget.setAccessibleName(tooltip);widget.setProperty('audio_hover',True)
    return widget
