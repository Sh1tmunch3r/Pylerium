#!/usr/bin/env python3
"""
BO6-STYLE LOADOUT MENU
======================

A polished PyQt6 recreation of the supplied BO6 loadout screen.

Features
--------
- Responsive 16:9-inspired layout
- Dark BO6-style interface
- Orange selection glow
- Cyan weapon progression bars
- Loadout sidebar
- Primary weapon
- Secondary weapon
- Melee weapon
- Tactical
- Lethal
- Field upgrade
- Three perks
- Specialty
- Wildcard
- Interactive hover/selection states
- Animated transitions
- Animated ambient background
- Right-side preview panel
- Weapon/item preview cards
- Preview statistics
- Attachment information
- Loadout creation
- Loadout switching
- Item selection dialog
- Custom frameless-style cards
- High-DPI support
- No external image assets required

Install:
    pip install PyQt6

Run:
    python bo6_loadout.py
"""

from __future__ import annotations

import math
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Optional
from asset_helper import ASSETS
from model_preview import InteractiveModelCanvas

from PyQt6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


# =============================================================================
# THEME
# =============================================================================

BG = QColor("#050709")
PANEL = QColor("#111315")
PANEL_2 = QColor("#191b1d")
CARD = QColor("#343536")
CARD_HOVER = QColor("#414243")
CARD_SELECTED = QColor("#494a4b")

TEXT = QColor("#f3f3f3")
TEXT_DIM = QColor("#9a9a9a")
TEXT_DARK = QColor("#5f6264")

ORANGE = QColor("#f06413")
ORANGE_BRIGHT = QColor("#ff7b1c")
ORANGE_DARK = QColor("#8c3008")

CYAN = QColor("#26d8ee")
CYAN_GLOW = QColor("#22e8ff")

BORDER = QColor("#55585b")
BLACK = QColor("#000000")


# =============================================================================
# DATA
# =============================================================================

@dataclass
class LoadoutItem:
    name: str
    category: str
    level: int = 1
    description: str = ""
    damage: int = 50
    firepower: int = 50
    accuracy: int = 50
    mobility: int = 50
    handling: int = 50
    range_stat: int = 50
    attachments: list[str] = field(default_factory=list)


@dataclass
class Loadout:
    name: str
    primary: LoadoutItem
    secondary: LoadoutItem
    melee: LoadoutItem
    tactical: LoadoutItem
    lethal: LoadoutItem
    field_upgrade: LoadoutItem
    perk1: LoadoutItem
    perk2: LoadoutItem
    perk3: LoadoutItem
    specialty: LoadoutItem
    wildcard: LoadoutItem


def item(name, category, **kwargs):
    return LoadoutItem(name=name, category=category, **kwargs)


PRIMARY_ITEMS = [
    item(
        "XM4",
        "ASSAULT RIFLE",
        level=27,
        description="Full-auto assault rifle. A reliable all-round weapon with "
                    "balanced damage, accuracy and handling.",
        damage=68,
        firepower=76,
        accuracy=73,
        mobility=61,
        handling=67,
        range_stat=72,
        attachments=[
            "Kepler Microflex",
            "Suppressor",
            "Vertical Foregrip",
            "Extended Mag I",
            "Quickdraw Grip",
        ],
    ),
    item(
        "AMES 85",
        "ASSAULT RIFLE",
        level=18,
        description="Highly accurate assault rifle designed for controlled "
                    "medium-to-long-range engagements.",
        damage=62,
        firepower=69,
        accuracy=87,
        mobility=58,
        handling=70,
        range_stat=81,
        attachments=[
            "Accu-Spot Reflex",
            "Compensator",
            "Ranger Foregrip",
            "Extended Mag I",
        ],
    ),
    item(
        "AK-74",
        "ASSAULT RIFLE",
        level=31,
        description="Hard-hitting automatic rifle with strong stopping power "
                    "and heavier recoil.",
        damage=84,
        firepower=82,
        accuracy=59,
        mobility=56,
        handling=55,
        range_stat=75,
        attachments=[
            "Volzhskiy Reflex",
            "Ported Compensator",
            "Vertical Foregrip",
            "Ergonomic Grip",
        ],
    ),
    item(
        "C9",
        "SUBMACHINE GUN",
        level=22,
        description="Fast-handling SMG designed for aggressive close-quarter combat.",
        damage=61,
        firepower=86,
        accuracy=59,
        mobility=91,
        handling=88,
        range_stat=44,
        attachments=[
            "Merlin Mini",
            "Suppressor",
            "Long Barrel",
            "Extended Mag II",
        ],
    ),
]

SECONDARY_ITEMS = [
    item(
        "9MM PM",
        "PISTOL",
        level=14,
        description="Semi-automatic sidearm with dependable close-range performance.",
        damage=54,
        firepower=48,
        accuracy=70,
        mobility=94,
        handling=91,
        range_stat=38,
    ),
    item(
        "GS45",
        "PISTOL",
        level=11,
        description="High-caliber pistol delivering increased damage per shot.",
        damage=73,
        firepower=51,
        accuracy=62,
        mobility=87,
        handling=82,
        range_stat=42,
    ),
]

MELEE_ITEMS = [
    item(
        "KNIFE",
        "MELEE",
        description="Fast close-quarter melee weapon.",
        damage=100,
        firepower=0,
        accuracy=100,
        mobility=100,
        handling=100,
        range_stat=5,
    ),
]

TACTICAL_ITEMS = [
    item("STIM SHOT", "TACTICAL", description="Combat stimulant for rapid recovery."),
    item("FLASHBANG", "TACTICAL", description="Blinds and disorients enemies."),
    item("CONCUSSION", "TACTICAL", description="Slows enemy movement and aiming."),
]

LETHAL_ITEMS = [
    item("FRAG", "LETHAL", description="Cookable fragmentation grenade."),
    item("SEMTEX", "LETHAL", description="Sticky timed explosive."),
    item("C4", "LETHAL", description="Remote-detonated explosive charge."),
]

FIELD_ITEMS = [
    item(
        "ASSAULT PACK",
        "FIELD UPGRADE",
        description="Deploy a supply pack that replenishes ammunition and equipment.",
    ),
    item(
        "TROPHY SYSTEM",
        "FIELD UPGRADE",
        description="Destroys incoming enemy projectiles.",
    ),
    item(
        "SCRAMBLER",
        "FIELD UPGRADE",
        description="Disrupts enemy electronic systems within its radius.",
    ),
]

PERK_1_ITEMS = [
    item("GUNG-HO", "PERK 1", description="Improved movement while reloading and using equipment."),
    item("DEXTERITY", "PERK 1", description="Reduced weapon motion during movement."),
]

PERK_2_ITEMS = [
    item("ASSASSIN", "PERK 2", description="Identify high-value enemy targets."),
    item("FAST HANDS", "PERK 2", description="Swap weapons faster."),
]

PERK_3_ITEMS = [
    item("DOUBLE TIME", "PERK 3", description="Improved tactical sprint duration."),
    item("VIGILANCE", "PERK 3", description="Enhanced awareness of enemy threats."),
]

SPECIALTY_ITEMS = [
    item("ENFORCER", "SPECIALTY", description="Combat-focused perk specialty."),
    item("RECON", "SPECIALTY", description="Information and awareness specialty."),
]

WILDCARD_ITEMS = [
    item(
        "TACTICAL EXPERT",
        "WILDCARD",
        description="Spawn with two additional tactical equipment items.",
    ),
    item(
        "GUNFIGHTER",
        "WILDCARD",
        description="Equip additional attachments to your primary weapon.",
    ),
    item(
        "PERK GREED",
        "WILDCARD",
        description="Equip an additional perk.",
    ),
]


# =============================================================================
# FONT HELPERS
# =============================================================================

def font(size=12, weight=QFont.Weight.Normal):
    f = QFont("Arial")
    f.setPixelSize(size)
    f.setWeight(weight)
    return f


def condensed_font(size=12, weight=QFont.Weight.Bold):
    candidates = [
        "Arial Narrow",
        "Bahnschrift Condensed",
        "Roboto Condensed",
        "Arial",
    ]

    families = QFontDatabase.families()

    family = "Arial"
    for candidate in candidates:
        if candidate in families:
            family = candidate
            break

    f = QFont(family)
    f.setPixelSize(size)
    f.setWeight(weight)
    f.setStretch(QFont.Stretch.Condensed)
    return f


# =============================================================================
# BACKGROUND
# =============================================================================

class BackgroundWidget(QWidget):

    def __init__(self):
        super().__init__()

        self.phase = 0.0
        self.ambient_speed=1.0;self.ambient_intensity=1.0;self.ambient_grid=True
        self.ambient_particles=False;self.ambient_scanlines=False;self.ambient_mode='Sweep'
        self.ambient_accent=QColor('#ff4500');self.ambient_fps=28

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(35)

    def animate(self):
        if not self.isVisible() or self.window().isMinimized():return
        self.phase += .336*self.ambient_speed/max(1,self.ambient_fps)
        self.update()

    def configure(self,settings):
        self.ambient_speed=settings.get('ambient_speed',100)/100
        self.ambient_intensity=settings.get('ambient_intensity',100)/100
        self.ambient_grid=settings.get('ambient_grid',True)
        self.ambient_particles=settings.get('ambient_particles',False)
        self.ambient_scanlines=settings.get('ambient_scanlines',False)
        self.ambient_mode=settings.get('ambient_mode','Sweep')
        colour=QColor(settings.get('ambient_accent','#ff4500'))
        self.ambient_accent=colour if colour.isValid() else QColor('#ff4500')
        self.ambient_fps=settings.get('ambient_fps',28)
        self.timer.setInterval(round(1000/max(1,self.ambient_fps)));self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Base
        gradient = QLinearGradient(0, 0, w, h)
        gradient.setColorAt(0.0, QColor("#050607"))
        gradient.setColorAt(0.50, QColor("#071015"))
        gradient.setColorAt(1.0, QColor("#020304"))
        painter.fillRect(self.rect(), gradient)

        # Image is below every atmospheric layer, preserving the animated overlay.
        painter.save()
        try:
            opacity = float(ASSETS.manifest.get('background_opacity', 0.55))
        except (TypeError, ValueError):
            opacity = 0.55
        painter.setOpacity(max(0.0, min(1.0, opacity)))
        ASSETS.paint_image(painter, QRectF(self.rect()), ASSETS.manifest.get('background'), cover=True)
        painter.restore()

        painter.setOpacity(self.ambient_intensity)
        painter.save()
        painter.setOpacity(0.45)
        painter.fillRect(self.rect(), gradient)
        painter.restore()

        # Right blue atmospheric illumination
        radial = QRadialGradient(
            QPointF(w * (.78+.04*math.sin(self.phase) if self.ambient_mode=='Orbit' else .78), h * .38),
            w * 0.55
        )
        radial.setColorAt(0.0, QColor(15, 42, 57, 115))
        radial.setColorAt(0.55, QColor(6, 22, 30, 60))
        radial.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), radial)

        # Brick wall
        painter.setPen(QPen(QColor(90, 105, 110, 18 if self.ambient_grid else 0), 1))

        brick_w = max(70, int(w / 19))
        brick_h = max(28, int(h / 31))

        start_x = int(w * 0.54)

        for y in range(80, h - 90, brick_h):
            row = y // brick_h
            offset = brick_w // 2 if row % 2 else 0

            painter.drawLine(start_x, y, w, y)

            x = start_x - offset
            while x < w:
                painter.drawLine(x, y, x, min(y + brick_h, h))
                x += brick_w

        # Bottom orange light
        orange = QRadialGradient(
            QPointF(w * 0.39, h * 1.05),
            w * 0.35
        )
        accent=QColor(self.ambient_accent);accent.setAlpha(90)
        orange.setColorAt(0.0, accent)
        orange.setColorAt(0.4, QColor(200, 35, 0, 28))
        orange.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), orange)

        # Slow moving atmospheric sweep
        sweep_x = (
            w * 0.55
            + math.sin(self.phase) * w * (0 if self.ambient_mode=='Breathe' else .08)
        )

        sweep = QLinearGradient(
            sweep_x - 200,
            0,
            sweep_x + 200,
            0
        )
        sweep.setColorAt(0.0, QColor(0, 0, 0, 0))
        sweep.setColorAt(0.5, QColor(30, 80, 100, int(10+8*math.sin(self.phase)) if self.ambient_mode=='Breathe' else 10))
        sweep.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), sweep)
        if self.ambient_particles:
            painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor(70,180,200,40))
            for index in range(24):
                x=((index*.618+self.phase*.01)%1)*w;y=((index*.381+self.phase*.005)%1)*h
                painter.drawEllipse(QPointF(x,y),1.5,1.5)
        if self.ambient_scanlines:
            painter.setPen(QPen(QColor(0,0,0,30),1))
            for y in range(0,h,8):painter.drawLine(0,y,w,y)

        # Vignette
        vignette = QRadialGradient(
            QPointF(w / 2, h / 2),
            max(w, h) * 0.75
        )
        vignette.setColorAt(0.35, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 205))
        painter.fillRect(self.rect(), vignette)


# =============================================================================
# TOP BAR
# =============================================================================

class IconButton(QPushButton):

    def __init__(self, text):
        super().__init__(text)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(42, 42)
        self.setFont(font(17, QFont.Weight.Bold))

        self.setStyleSheet("""
            QPushButton {
                background: rgba(10, 12, 14, 215);
                color: #bfc2c4;
                border: 1px solid #34383b;
            }

            QPushButton:hover {
                background: rgba(45, 48, 50, 230);
                color: white;
                border: 1px solid #777;
            }

            QPushButton:pressed {
                background: #f06413;
                color: white;
            }
        """)


class TopBar(QWidget):

    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(25, 0, 28, 0)
        layout.setSpacing(8)

        back = IconButton("‹")
        back.setFixedSize(38, 38)

        title = QLabel("LOADOUTS")
        title.setFont(condensed_font(34, QFont.Weight.Black))
        title.setStyleSheet("color:white;")
        title.setAlignment(
            Qt.AlignmentFlag.AlignVCenter |
            Qt.AlignmentFlag.AlignLeft
        )

        layout.addWidget(back)
        layout.addSpacing(10)
        layout.addWidget(title)
        layout.addStretch()

        for symbol in ["▦", "◉", "♟", "⚙"]:
            layout.addWidget(IconButton(symbol))

        profile = QLabel("  ◉   25  ")
        profile.setFont(font(14, QFont.Weight.Bold))
        profile.setStyleSheet("""
            QLabel {
                background: rgba(10,12,14,220);
                border: 1px solid #34383b;
                color: white;
                padding: 10px 16px;
            }
        """)

        friends = QLabel("  ♟   10  ")
        friends.setFont(font(14, QFont.Weight.Bold))
        friends.setStyleSheet("""
            QLabel {
                background: rgba(10,12,14,220);
                border: 1px solid #34383b;
                color: #d8d8d8;
                padding: 10px 16px;
            }
        """)

        layout.addWidget(profile)
        layout.addWidget(friends)

        self.setFixedHeight(65)


# =============================================================================
# LOADOUT SIDEBAR
# =============================================================================

class SidebarLoadoutButton(QPushButton):

    selected = pyqtSignal(object)

    def __init__(self, loadout: Loadout):
        super().__init__(loadout.name.upper())

        self.loadout = loadout
        self.active = False

        self.setMinimumHeight(52)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(condensed_font(16, QFont.Weight.Bold))

        self.clicked.connect(
            lambda: self.selected.emit(self.loadout)
        )

        self.refresh()

    def set_active(self, active):
        self.active = active
        self.refresh()

    def refresh(self):
        if self.active:
            self.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding-left: 14px;
                    color: white;
                    background: rgba(90,90,90,210);
                    border: 1px solid #f06413;
                    border-left: 3px solid #ff7b1c;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding-left: 14px;
                    color: #b0b0b0;
                    background: rgba(12,14,16,190);
                    border: 1px solid #292b2d;
                }

                QPushButton:hover {
                    color: white;
                    background: rgba(55,57,59,210);
                    border-left: 2px solid #f06413;
                }
            """)


class LoadoutSidebar(QFrame):

    loadout_selected = pyqtSignal(object)
    create_requested = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.buttons = []

        self.setMinimumWidth(300)
        self.setMaximumWidth(340)

        self.setStyleSheet("""
            QFrame {
                background: rgba(4,5,6,205);
                border: 1px solid #24272a;
            }
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 16, 14, 16)
        self.layout.setSpacing(10)

        favorite = QLabel("★")
        favorite.setAlignment(Qt.AlignmentFlag.AlignRight)
        favorite.setFont(font(17))
        favorite.setStyleSheet(
            "color:#d8d8d8; border:none;"
        )

        self.layout.addWidget(favorite)

        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(8)

        self.layout.addLayout(self.list_layout)
        self.layout.addStretch()

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background:#313335;border:none;")
        self.layout.addWidget(separator)

        create = QPushButton("＋   Create New")
        create.setMinimumHeight(48)
        create.setCursor(Qt.CursorShape.PointingHandCursor)
        create.setFont(font(14, QFont.Weight.Bold))
        create.clicked.connect(self.create_requested.emit)

        create.setStyleSheet("""
            QPushButton {
                text-align:left;
                padding-left:12px;
                color:#eeeeee;
                background:#1d1f21;
                border:1px solid #4b4d4f;
            }

            QPushButton:hover {
                background:#292b2d;
                border:1px solid #f06413;
            }
        """)

        self.layout.addWidget(create)

    def add_loadout(self, loadout):
        button = SidebarLoadoutButton(loadout)
        button.selected.connect(self.loadout_selected.emit)

        self.buttons.append(button)
        self.list_layout.addWidget(button)

    def select_loadout(self, loadout):
        for button in self.buttons:
            button.set_active(button.loadout is loadout)


# =============================================================================
# LOADOUT CARD
# =============================================================================

class LoadoutCard(QWidget):

    clicked = pyqtSignal(object)

    def __init__(
        self,
        item_data: LoadoutItem,
        card_type="weapon",
        compact=False
    ):
        super().__init__()

        self.item_data = item_data
        self.card_type = card_type
        self.compact = compact

        self.hover_progress = 0.0
        self.selected = False

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.animation = QVariantAnimation(self)
        self.animation.setDuration(160)
        self.animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )
        self.animation.valueChanged.connect(
            self._animation_value
        )

        if compact:
            self.setMinimumHeight(130)
        elif card_type == "primary":
            self.setMinimumHeight(195)
        else:
            self.setMinimumHeight(140)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

    def set_item(self, data):
        self.item_data = data
        self.update()

    def set_selected(self, value):
        self.selected = value
        self.update()

    def _animation_value(self, value):
        self.hover_progress = float(value)
        self.update()

    def enterEvent(self, event):
        self.animation.stop()
        self.animation.setStartValue(self.hover_progress)
        self.animation.setEndValue(1.0)
        self.animation.start()

    def leaveEvent(self, event):
        self.animation.stop()
        self.animation.setStartValue(self.hover_progress)
        self.animation.setEndValue(0.0)
        self.animation.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)

        base = QColor(
            int(47 + 12 * self.hover_progress),
            int(48 + 12 * self.hover_progress),
            int(49 + 12 * self.hover_progress),
            245,
        )

        p.fillRect(r, base)

        if self.selected:
            glow = QLinearGradient(
                r.left(),
                r.top(),
                r.right(),
                r.bottom()
            )
            glow.setColorAt(
                0,
                QColor(255, 98, 10, 25)
            )
            glow.setColorAt(
                1,
                QColor(255, 98, 10, 2)
            )
            p.fillRect(r, glow)

        border = ORANGE if self.selected else QColor("#606265")

        if self.hover_progress > 0:
            border = QColor(
                int(
                    border.red() +
                    (ORANGE.red() - border.red()) *
                    self.hover_progress
                ),
                int(
                    border.green() +
                    (ORANGE.green() - border.green()) *
                    self.hover_progress
                ),
                int(
                    border.blue() +
                    (ORANGE.blue() - border.blue()) *
                    self.hover_progress
                )
            )

        p.setPen(QPen(border, 1))
        p.drawRect(r)

        # Top header
        header_h = 25 if not self.compact else 22

        p.fillRect(
            QRectF(
                r.left(),
                r.top(),
                r.width(),
                header_h
            ),
            QColor(24, 25, 26, 150)
        )

        p.setFont(condensed_font(12))
        p.setPen(QColor("#a6a6a6"))

        p.drawText(
            QRectF(
                r.left() + 8,
                r.top() + 2,
                r.width() - 16,
                header_h - 3
            ),
            Qt.AlignmentFlag.AlignLeft |
            Qt.AlignmentFlag.AlignVCenter,
            self.item_data.category.upper()
        )

        # Icon / weapon silhouette
        icon_rect = QRectF(
            r.left() + 14,
            r.top() + header_h + 10,
            r.width() - 28,
            max(35, r.height() - header_h - 65)
        )

        self.draw_item_icon(p, icon_rect)

        # Name
        p.setFont(
            condensed_font(
                18 if self.card_type == "primary" else 15,
                QFont.Weight.Bold
            )
        )
        p.setPen(TEXT)

        p.drawText(
            QRectF(
                r.left() + 8,
                r.bottom() - 40,
                r.width() - 70,
                24
            ),
            Qt.AlignmentFlag.AlignLeft |
            Qt.AlignmentFlag.AlignVCenter,
            self.item_data.name.upper()
        )

        # Level
        if self.card_type in ("primary", "weapon"):
            p.setFont(condensed_font(10))
            p.setPen(QColor("#e0e0e0"))

            p.drawText(
                QRectF(
                    r.right() - 75,
                    r.bottom() - 40,
                    65,
                    24
                ),
                Qt.AlignmentFlag.AlignRight |
                Qt.AlignmentFlag.AlignVCenter,
                f"LVL {self.item_data.level}"
            )

            # Cyan progression line
            y = r.bottom() - 8

            p.fillRect(
                QRectF(
                    r.left() + 8,
                    y,
                    r.width() - 16,
                    4
                ),
                QColor("#30383a")
            )

            ratio = max(
                .08,
                min(
                    1.0,
                    self.item_data.level / 40
                )
            )

            p.fillRect(
                QRectF(
                    r.left() + 8,
                    y,
                    (r.width() - 16) * ratio,
                    4
                ),
                CYAN
            )

    def draw_item_icon(self, p, rect):
        if ASSETS.paint_image(p, rect, ASSETS.entry(getattr(self.item_data, 'asset_key', self.item_data.name)).get('icon')):
            return
        category = self.item_data.category.upper()

        if (
            "RIFLE" in category
            or "SMG" in category
            or category == "PISTOL"
        ):
            self.draw_weapon(p, rect)

        elif "PERK" in category or category == "SPECIALTY":
            self.draw_perk(p, rect)

        elif category == "FIELD UPGRADE":
            self.draw_field_upgrade(p, rect)

        elif category in ("TACTICAL", "LETHAL"):
            self.draw_equipment(p, rect)

        elif category == "WILDCARD":
            self.draw_wildcard(p, rect)

        elif category == "MELEE":
            self.draw_knife(p, rect)

    def draw_weapon(self, p, rect):
        p.save()

        p.setPen(Qt.PenStyle.NoPen)

        center_y = rect.center().y()

        length = min(rect.width() * .72, 280)
        x = rect.center().x() - length / 2

        body = QPainterPath()
        body.moveTo(x, center_y - 10)
        body.lineTo(x + length * .55, center_y - 10)
        body.lineTo(x + length * .62, center_y - 4)
        body.lineTo(x + length * .79, center_y - 4)
        body.lineTo(x + length * .79, center_y + 4)
        body.lineTo(x + length * .57, center_y + 5)
        body.lineTo(x + length * .52, center_y + 12)
        body.lineTo(x + length * .35, center_y + 12)
        body.lineTo(x + length * .32, center_y + 4)
        body.lineTo(x, center_y + 4)
        body.closeSubpath()

        weapon_gradient = QLinearGradient(
            x,
            center_y - 15,
            x,
            center_y + 15
        )
        weapon_gradient.setColorAt(
            0,
            QColor("#a2a5a6")
        )
        weapon_gradient.setColorAt(
            .5,
            QColor("#5d6163")
        )
        weapon_gradient.setColorAt(
            1,
            QColor("#282a2b")
        )

        p.fillPath(body, weapon_gradient)

        # Stock
        p.fillRect(
            QRectF(
                x - length * .14,
                center_y - 5,
                length * .17,
                10
            ),
            QColor("#414446")
        )

        # Barrel
        p.fillRect(
            QRectF(
                x + length * .78,
                center_y - 2,
                length * .18,
                4
            ),
            QColor("#8c8f91")
        )

        # Grip
        grip = QPolygonF([
            QPointF(
                x + length * .47,
                center_y + 7
            ),
            QPointF(
                x + length * .55,
                center_y + 7
            ),
            QPointF(
                x + length * .52,
                center_y + 29
            ),
            QPointF(
                x + length * .46,
                center_y + 27
            ),
        ])

        p.setBrush(QColor("#343637"))
        p.drawPolygon(grip)

        # Magazine
        mag = QPolygonF([
            QPointF(
                x + length * .36,
                center_y + 8
            ),
            QPointF(
                x + length * .44,
                center_y + 8
            ),
            QPointF(
                x + length * .42,
                center_y + 27
            ),
            QPointF(
                x + length * .36,
                center_y + 24
            ),
        ])

        p.drawPolygon(mag)

        p.restore()

    def draw_perk(self, p, rect):
        p.save()

        size = min(rect.width(), rect.height()) * .42

        center = rect.center()

        points = []

        for i in range(6):
            a = math.radians(60 * i - 30)
            points.append(
                QPointF(
                    center.x() + math.cos(a) * size / 2,
                    center.y() + math.sin(a) * size / 2,
                )
            )

        p.setPen(QPen(QColor("#818486"), 2))
        p.setBrush(QColor("#141617"))
        p.drawPolygon(QPolygonF(points))

        inner_size = size * .7

        inner = []

        for i in range(6):
            a = math.radians(60 * i - 30)
            inner.append(
                QPointF(
                    center.x() +
                    math.cos(a) * inner_size / 2,
                    center.y() +
                    math.sin(a) * inner_size / 2,
                )
            )

        p.setPen(QPen(QColor("#343638"), 1))
        p.drawPolygon(QPolygonF(inner))

        p.setPen(QPen(QColor("#55585a"), 2))
        p.drawLine(
            QPointF(center.x() - 10, center.y() - 10),
            QPointF(center.x() + 10, center.y() + 10)
        )
        p.drawLine(
            QPointF(center.x() + 10, center.y() - 10),
            QPointF(center.x() - 10, center.y() + 10)
        )

        p.restore()

    def draw_field_upgrade(self, p, rect):
        p.save()

        center = rect.center()
        radius = min(rect.width(), rect.height()) * .22

        p.setPen(QPen(QColor("#d1d1d1"), 2))
        p.setBrush(QColor(20, 20, 20, 20))

        p.drawEllipse(center, radius, radius)

        p.setPen(QPen(QColor("#686b6d"), 1))
        p.drawEllipse(
            center,
            radius * .72,
            radius * .72
        )

        p.restore()

    def draw_equipment(self, p, rect):
        p.save()

        s = min(rect.width(), rect.height()) * .38

        x = rect.center().x() - s / 2
        y = rect.center().y() - s / 2

        gradient = QLinearGradient(x, y, x + s, y + s)
        gradient.setColorAt(0, QColor("#e8e8e8"))
        gradient.setColorAt(1, QColor("#8d8f90"))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(gradient)

        p.drawRoundedRect(
            QRectF(x, y, s, s),
            3,
            3
        )

        p.setBrush(QColor("#333638"))
        p.drawRect(
            QRectF(
                x + s * .32,
                y - s * .12,
                s * .36,
                s * .18
            )
        )

        p.restore()

    def draw_wildcard(self, p, rect):
        p.save()

        w = min(rect.width() * .35, 80)
        h = min(rect.height() * .72, 120)

        card = QRectF(
            rect.center().x() - w / 2,
            rect.center().y() - h / 2,
            w,
            h
        )

        gradient = QLinearGradient(
            card.topLeft(),
            card.bottomRight()
        )
        gradient.setColorAt(0, QColor("#7a6227"))
        gradient.setColorAt(.45, QColor("#1b1a17"))
        gradient.setColorAt(1, QColor("#a57a1e"))

        p.setBrush(gradient)
        p.setPen(QPen(QColor("#d5b85c"), 1))
        p.drawRoundedRect(card, 3, 3)

        p.setPen(QPen(QColor("#d8c078"), 2))
        p.drawLine(
            QPointF(card.center().x(), card.top() + 15),
            QPointF(card.center().x(), card.bottom() - 15)
        )

        p.drawEllipse(
            QPointF(
                card.center().x(),
                card.center().y()
            ),
            8,
            8
        )

        p.restore()

    def draw_knife(self, p, rect):
        p.save()

        c = rect.center()

        p.setPen(QPen(QColor("#c3c5c6"), 7))
        p.drawLine(
            QPointF(c.x() - 60, c.y() + 25),
            QPointF(c.x() + 45, c.y() - 25)
        )

        p.setPen(QPen(QColor("#3a3b3c"), 11))
        p.drawLine(
            QPointF(c.x() - 70, c.y() + 31),
            QPointF(c.x() - 48, c.y() + 20)
        )

        p.restore()


# =============================================================================
# ITEM SELECTOR
# =============================================================================

class SelectorItem(QPushButton):

    def __init__(self, item_data):
        super().__init__()

        self.item_data = item_data

        self.setText(
            f"{item_data.name.upper()}\n"
            f"{item_data.category.upper()}"
        )

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(80)
        self.setFont(condensed_font(14, QFont.Weight.Bold))

        self.setStyleSheet("""
            QPushButton {
                text-align:left;
                padding:12px;
                color:white;
                background:#292b2d;
                border:1px solid #515355;
            }

            QPushButton:hover {
                background:#414345;
                border:1px solid #f06413;
                border-left:4px solid #f06413;
            }

            QPushButton:pressed {
                background:#f06413;
            }
        """)


class ItemSelectorDialog(QDialog):

    item_selected = pyqtSignal(object)

    def __init__(
        self,
        title,
        items,
        parent=None
    ):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(720, 600)

        self.setStyleSheet("""
            QDialog {
                background:#080a0b;
            }

            QScrollArea {
                border:none;
                background:transparent;
            }

            QWidget#content {
                background:transparent;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)

        heading = QLabel(title.upper())
        heading.setFont(
            condensed_font(
                30,
                QFont.Weight.Black
            )
        )
        heading.setStyleSheet(
            "color:white;"
        )

        sub = QLabel(
            "SELECT AN ITEM FOR THIS LOADOUT SLOT"
        )
        sub.setFont(condensed_font(13))
        sub.setStyleSheet(
            "color:#888;"
        )

        root.addWidget(heading)
        root.addWidget(sub)
        root.addSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        content.setObjectName("content")

        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(8)

        for entry in items:
            button = SelectorItem(entry)

            button.clicked.connect(
                lambda checked=False, x=entry:
                self.choose(x)
            )

            content_layout.addWidget(button)

        content_layout.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll)

    def choose(self, item_data):
        self.item_selected.emit(item_data)
        self.accept()


# =============================================================================
# PREVIEW
# =============================================================================

class StatBar(QWidget):

    def __init__(self, title, value=50):
        super().__init__()

        self.title = title
        self.value = value

        self.setFixedHeight(30)

    def set_value(self, value):
        self.value = value
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.setFont(condensed_font(11))
        p.setPen(QColor("#b8b8b8"))

        p.drawText(
            QRectF(0, 0, 90, self.height()),
            Qt.AlignmentFlag.AlignVCenter |
            Qt.AlignmentFlag.AlignLeft,
            self.title.upper()
        )

        x = 92
        y = self.height() / 2 - 3
        width = self.width() - x - 35

        p.fillRect(
            QRectF(x, y, width, 6),
            QColor("#25282a")
        )

        p.fillRect(
            QRectF(
                x,
                y,
                width * self.value / 100,
                6
            ),
            QColor("#d9d9d9")
        )

        p.setFont(condensed_font(10))
        p.drawText(
            QRectF(
                self.width() - 32,
                0,
                30,
                self.height()
            ),
            Qt.AlignmentFlag.AlignRight |
            Qt.AlignmentFlag.AlignVCenter,
            str(self.value)
        )


class WeaponPreviewCanvas(InteractiveModelCanvas):
    pass


class PreviewPanel(QFrame):

    def __init__(self):
        super().__init__()

        self.setMinimumWidth(390)

        self.setStyleSheet("""
            QFrame {
                background: rgba(5,8,10,145);
                border-left:1px solid rgba(70,75,80,80);
            }

            QLabel {
                border:none;
                background:transparent;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 25, 35, 30)
        root.setSpacing(5)

        self.category = QLabel("ASSAULT RIFLE")
        self.category.setFont(
            condensed_font(
                13,
                QFont.Weight.Bold
            )
        )
        self.category.setStyleSheet(
            "color:#92979a;"
        )

        self.name = QLabel("XM4")
        self.name.setFont(
            condensed_font(
                36,
                QFont.Weight.Black
            )
        )
        self.name.setStyleSheet(
            "color:white;"
        )

        self.level = QLabel("LEVEL 27")
        self.level.setFont(
            condensed_font(
                12,
                QFont.Weight.Bold
            )
        )
        self.level.setStyleSheet(
            "color:#27d9ed;"
        )

        root.addWidget(self.category)
        root.addWidget(self.name)
        root.addWidget(self.level)

        self.canvas = WeaponPreviewCanvas()
        root.addWidget(
            self.canvas,
            1
        )

        controls = QHBoxLayout()
        for title, callback in [("Pause", self.toggle_preview),
                                ("Stat profile", self.toggle_profile),
                                ("Reset view", self.canvas.reset_view)]:
            button = QPushButton(title)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(28)
            button.setStyleSheet("QPushButton {color:#b9e7ec;background:#132027;border:1px solid #29434a;padding:4px;} QPushButton:hover {border-color:#f06413;color:white;}")
            button.clicked.connect(callback)
            controls.addWidget(button)
            if title == "Pause":
                self.pause_button = button
                button.setCheckable(True)
            elif title == "Stat profile":
                button.setCheckable(True)
        root.addLayout(controls)
        hint = QLabel("DRAG TO ORBIT   •   RIGHT/MIDDLE DRAG TO PAN   •   SCROLL TO ZOOM   •   RIGHT-CLICK FOR VIEWS / QUALITY / EXPORT")
        hint.setWordWrap(True)
        hint.setFont(QFont("Consolas", 8))
        hint.setStyleSheet("color:#70858c;")
        root.addWidget(hint)

        self.model_help = QLabel()
        self.model_help.setWordWrap(True)
        self.model_help.setFont(font(11))
        self.model_help.setStyleSheet("color:#8299a4;")
        self.canvas.model_status.connect(self.model_help.setText)
        root.addWidget(self.model_help)

        texture_button = QPushButton("Textured / wireframe")
        texture_button.setToolTip("Show discovered material textures, or inspect the lightweight wireframe.")
        texture_button.clicked.connect(self.toggle_textures)
        controls.addWidget(texture_button)
        inspect_button=QPushButton('Inspect weapon')
        inspect_button.clicked.connect(self.inspect_weapon);controls.addWidget(inspect_button)

        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setFont(font(12))
        self.description.setStyleSheet(
            "color:#b3b5b7;"
        )

        root.addWidget(self.description)
        root.addSpacing(12)

        stats_title = QLabel("WEAPON STATS")
        stats_title.setFont(
            condensed_font(
                13,
                QFont.Weight.Bold
            )
        )
        stats_title.setStyleSheet(
            "color:white;"
        )

        root.addWidget(stats_title)

        self.stats = {
            "DAMAGE": StatBar("Damage"),
            "FIREPOWER": StatBar("Firepower"),
            "ACCURACY": StatBar("Accuracy"),
            "MOBILITY": StatBar("Mobility"),
            "HANDLING": StatBar("Handling"),
            "RANGE": StatBar("Range"),
        }

        for stat in self.stats.values():
            root.addWidget(stat)

        root.addSpacing(12)

        self.attachments_title = QLabel("ATTACHMENTS")
        self.attachments_title.setFont(
            condensed_font(
                13,
                QFont.Weight.Bold
            )
        )
        self.attachments_title.setStyleSheet(
            "color:white;"
        )

        self.attachments = QLabel()
        self.attachments.setWordWrap(True)
        self.attachments.setFont(
            condensed_font(11)
        )
        self.attachments.setStyleSheet(
            "color:#96999b;"
        )

        root.addWidget(self.attachments_title)
        root.addWidget(self.attachments)

        root.addStretch()

        self.set_item(PRIMARY_ITEMS[0])

    def toggle_preview(self):
        self.canvas.paused = not self.canvas.paused
        self.canvas.update()

    def inspect_weapon(self):
        from model_inspector import InspectWeaponDialog
        dialog=InspectWeaponDialog(self.canvas,self)
        dialog.exec()

    def toggle_textures(self):
        self.canvas.textured = not self.canvas.textured
        self.canvas.update_gpu_visibility()
        self.canvas.update()

    def toggle_profile(self):
        self.canvas.profile_mode = not self.canvas.profile_mode
        self.canvas.update_gpu_visibility()
        self.canvas.update()

    def set_item(self, data):
        self.category.setText(
            data.category.upper()
        )

        self.name.setText(
            data.name.upper()
        )

        self.level.setText(
            f"LEVEL {data.level}"
        )

        self.description.setText(
            data.description or
            "No additional information available."
        )

        self.canvas.set_item(data)

        values = [
            data.damage,
            data.firepower,
            data.accuracy,
            data.mobility,
            data.handling,
            data.range_stat,
        ]

        for stat, value in zip(
            self.stats.values(),
            values
        ):
            stat.set_value(value)

        if data.attachments:
            self.attachments_title.show()
            self.attachments.show()

            self.attachments.setText(
                "   •   ".join(
                    data.attachments
                )
            )

        else:
            self.attachments_title.hide()
            self.attachments.hide()


# =============================================================================
# MAIN LOADOUT GRID
# =============================================================================

class LoadoutGrid(QWidget):

    item_preview_requested = pyqtSignal(object)

    def __init__(self):
        super().__init__()

        self.loadout = None
        self.cards = []

        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(9)
        self.grid.setVerticalSpacing(9)

        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        self.grid.setColumnStretch(2, 1)
        self.grid.setColumnStretch(3, 1)

    def clear(self):
        while self.grid.count():
            item = self.grid.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

        self.cards.clear()

    def create_card(
        self,
        data,
        card_type,
        selector_items,
        setter,
        row,
        column,
        row_span=1,
        col_span=1,
    ):
        card = LoadoutCard(
            data,
            card_type,
            compact=card_type in (
                "perk",
                "equipment"
            )
        )

        card.clicked.connect(
            lambda c:
            self.card_clicked(
                c,
                selector_items,
                setter
            )
        )

        self.cards.append(card)

        self.grid.addWidget(
            card,
            row,
            column,
            row_span,
            col_span
        )

        return card

    def set_loadout(self, loadout):
        self.loadout = loadout
        self.clear()

        self.create_card(
            loadout.primary,
            "primary",
            PRIMARY_ITEMS,
            "primary",
            0,
            0,
            1,
            4,
        )

        self.create_card(
            loadout.secondary,
            "weapon",
            SECONDARY_ITEMS,
            "secondary",
            1,
            0,
            1,
            2,
        )

        self.create_card(
            loadout.melee,
            "weapon",
            MELEE_ITEMS,
            "melee",
            1,
            2,
            1,
            2,
        )

        self.create_card(
            loadout.tactical,
            "equipment",
            TACTICAL_ITEMS,
            "tactical",
            2,
            0,
        )

        self.create_card(
            loadout.lethal,
            "equipment",
            LETHAL_ITEMS,
            "lethal",
            2,
            1,
        )

        self.create_card(
            loadout.field_upgrade,
            "equipment",
            FIELD_ITEMS,
            "field_upgrade",
            2,
            2,
            1,
            2,
        )

        self.create_card(
            loadout.perk1,
            "perk",
            PERK_1_ITEMS,
            "perk1",
            3,
            0,
        )

        self.create_card(
            loadout.perk2,
            "perk",
            PERK_2_ITEMS,
            "perk2",
            3,
            1,
        )

        self.create_card(
            loadout.perk3,
            "perk",
            PERK_3_ITEMS,
            "perk3",
            3,
            2,
        )

        self.create_card(
            loadout.specialty,
            "perk",
            SPECIALTY_ITEMS,
            "specialty",
            3,
            3,
        )

        wildcard = self.create_card(
            loadout.wildcard,
            "wildcard",
            WILDCARD_ITEMS,
            "wildcard",
            4,
            1,
            1,
            2,
        )

        wildcard.setMinimumHeight(130)

        self.cards[0].set_selected(True)

    def card_clicked(
        self,
        card,
        selector_items,
        attribute
    ):
        for c in self.cards:
            c.set_selected(
                c is card
            )

        self.item_preview_requested.emit(
            card.item_data
        )

        dialog = ItemSelectorDialog(
            f"Select {card.item_data.category}",
            selector_items,
            self
        )

        def changed(new_item):
            setattr(
                self.loadout,
                attribute,
                new_item
            )

            card.set_item(new_item)

            self.item_preview_requested.emit(
                new_item
            )

        dialog.item_selected.connect(changed)
        dialog.exec()


# =============================================================================
# MAIN WINDOW
# =============================================================================

class LoadoutWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Loadouts"
        )

        self.setMinimumSize(
            1280,
            720
        )

        self.resize(
            1920,
            1080
        )

        self.loadouts = []

        self.background = BackgroundWidget()
        self.setCentralWidget(self.background)

        root = QVBoxLayout(self.background)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.top_bar = TopBar()
        root.addWidget(self.top_bar)

        body = QWidget()

        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(
            60,
            10,
            0,
            35
        )
        body_layout.setSpacing(35)

        # Sidebar
        self.sidebar = LoadoutSidebar()
        self.sidebar.loadout_selected.connect(
            self.select_loadout
        )
        self.sidebar.create_requested.connect(
            self.create_new_loadout
        )

        body_layout.addWidget(
            self.sidebar
        )

        # Center loadout section
        center_container = QWidget()

        center_container.setMaximumWidth(
            650
        )
        center_container.setMinimumWidth(
            500
        )

        center_layout = QVBoxLayout(
            center_container
        )

        center_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        center_layout.setSpacing(0)

        self.loadout_grid = LoadoutGrid()
        self.loadout_grid.item_preview_requested.connect(
            self.preview_item
        )

        center_layout.addWidget(
            self.loadout_grid
        )

        body_layout.addWidget(
            center_container
        )

        # Preview
        self.preview = PreviewPanel()

        body_layout.addWidget(
            self.preview,
            1
        )

        root.addWidget(
            body,
            1
        )

        self.create_initial_loadouts()

    def create_initial_loadouts(self):
        default = Loadout(
            name="Custom Loadout 1",
            primary=PRIMARY_ITEMS[0],
            secondary=SECONDARY_ITEMS[0],
            melee=MELEE_ITEMS[0],
            tactical=TACTICAL_ITEMS[0],
            lethal=LETHAL_ITEMS[0],
            field_upgrade=FIELD_ITEMS[0],
            perk1=PERK_1_ITEMS[0],
            perk2=PERK_2_ITEMS[0],
            perk3=PERK_3_ITEMS[0],
            specialty=SPECIALTY_ITEMS[0],
            wildcard=WILDCARD_ITEMS[0],
        )

        self.add_loadout(default)
        self.select_loadout(default)

    def add_loadout(self, loadout):
        self.loadouts.append(loadout)
        self.sidebar.add_loadout(loadout)

    def select_loadout(self, loadout):
        self.sidebar.select_loadout(
            loadout
        )

        self.loadout_grid.set_loadout(
            loadout
        )

        self.preview.set_item(
            loadout.primary
        )

    def preview_item(self, item_data):
        self.preview.set_item(
            item_data
        )

    def create_new_loadout(self):
        number = len(self.loadouts) + 1

        new_loadout = Loadout(
            name=f"Custom Loadout {number}",
            primary=PRIMARY_ITEMS[
                (number - 1) %
                len(PRIMARY_ITEMS)
            ],
            secondary=SECONDARY_ITEMS[0],
            melee=MELEE_ITEMS[0],
            tactical=TACTICAL_ITEMS[0],
            lethal=LETHAL_ITEMS[0],
            field_upgrade=FIELD_ITEMS[0],
            perk1=PERK_1_ITEMS[0],
            perk2=PERK_2_ITEMS[0],
            perk3=PERK_3_ITEMS[0],
            specialty=SPECIALTY_ITEMS[0],
            wildcard=WILDCARD_ITEMS[0],
        )

        self.add_loadout(
            new_loadout
        )

        self.select_loadout(
            new_loadout
        )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return

        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            return

        super().keyPressEvent(event)


# =============================================================================
# APPLICATION
# =============================================================================

def main():
    app = QApplication(sys.argv)

    app.setApplicationName(
        "BO6 Loadout UI"
    )

    app.setStyle("Fusion")

    app.setStyleSheet("""
        QToolTip {
            color: white;
            background: #111315;
            border: 1px solid #f06413;
            padding: 6px;
        }

        QScrollBar:vertical {
            background: #111315;
            width: 8px;
            margin: 0;
        }

        QScrollBar::handle:vertical {
            background: #55585a;
            min-height: 30px;
        }

        QScrollBar::handle:vertical:hover {
            background: #f06413;
        }

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            height: 0px;
        }
    """)

    from types import SimpleNamespace
    from orchestration_ui import OrchestrationWindow
    window = OrchestrationWindow(SimpleNamespace(**globals()))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
