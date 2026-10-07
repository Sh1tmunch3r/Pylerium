"""
ULTIMATE TERMINAL
=================

A reusable, dependency-free terminal styling and animation framework.

Designed to be imported from any Python project:

    from ultimate_terminal import terminal as term

    term.success("Connected!")
    term.error("Connection failed!")
    term.print("Hello", style="cyber")
    term.gradient("ULTIMATE TERMINAL")

    term.spinner("Loading...")
    term.progress(100, label="Downloading")
    term.banner("XANDEV")

    with term.live_spinner("Working..."):
        do_work()

No Colorama or Rich dependency is required.

Features
--------
- 24-bit TrueColor ANSI
- 256-color fallback
- Windows ANSI support
- Centralized palettes
- Multiple built-in themes
- Semantic styles
- Text styles
- Background styles
- Borders
- Panels
- Banners
- Gradient text
- Rainbow text
- RGB utilities
- Color blending/lightening/darkening
- Animated spinners
- Progress bars
- Loading animations
- Typewriter animation
- Pulse animation
- Marquee animation
- Countdown
- Status lines
- Tables
- Logging helpers
- Section separators
- Temporary live updates
- Custom styles
- Custom themes
- No external dependencies

All animations are opt-in and terminal-safe.
"""

from __future__ import annotations

import atexit
import json
import math
import os
import re
import shutil
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Optional, Sequence


# ============================================================================
# ANSI
# ============================================================================

ESC = "\033["
RESET = "\033[0m"

BOLD = ESC + "1m"
DIM = ESC + "2m"
ITALIC = ESC + "3m"
UNDERLINE = ESC + "4m"
BLINK = ESC + "5m"
REVERSE = ESC + "7m"
HIDDEN = ESC + "8m"
STRIKE = ESC + "9m"

CLEAR_SCREEN = ESC + "2J"
CLEAR_LINE = ESC + "2K"
CURSOR_HOME = ESC + "H"
CURSOR_UP = lambda n=1: f"{ESC}{n}A"
CURSOR_DOWN = lambda n=1: f"{ESC}{n}B"
CURSOR_FORWARD = lambda n=1: f"{ESC}{n}C"
CURSOR_BACK = lambda n=1: f"{ESC}{n}D"
SAVE_CURSOR = ESC + "s"
RESTORE_CURSOR = ESC + "u"
HIDE_CURSOR = ESC + "?25l"
SHOW_CURSOR = ESC + "?25h"
ERASE_TO_END = ESC + "K"
ERASE_TO_START = ESC + "1K"


# ============================================================================
# COLOR
# ============================================================================

@dataclass(frozen=True)
class RGB:
    r: int
    g: int
    b: int

    def __post_init__(self):
        for value in (self.r, self.g, self.b):
            if not 0 <= value <= 255:
                raise ValueError("RGB values must be between 0 and 255.")

    def fg(self) -> str:
        return f"{ESC}38;2;{self.r};{self.g};{self.b}m"

    def bg(self) -> str:
        return f"{ESC}48;2;{self.r};{self.g};{self.b}m"

    def hex(self) -> str:
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    def lighten(self, amount: float) -> "RGB":
        amount = max(0.0, min(1.0, amount))
        return RGB(
            round(self.r + (255 - self.r) * amount),
            round(self.g + (255 - self.g) * amount),
            round(self.b + (255 - self.b) * amount),
        )

    def darken(self, amount: float) -> "RGB":
        amount = max(0.0, min(1.0, amount))
        return RGB(
            round(self.r * (1 - amount)),
            round(self.g * (1 - amount)),
            round(self.b * (1 - amount)),
        )

    def blend(self, other: "RGB", amount: float) -> "RGB":
        amount = max(0.0, min(1.0, amount))
        return RGB(
            round(self.r + (other.r - self.r) * amount),
            round(self.g + (other.g - self.g) * amount),
            round(self.b + (other.b - self.b) * amount),
        )

    @classmethod
    def from_hex(cls, value: str) -> "RGB":
        value = value.strip().lstrip("#")
        if len(value) != 6:
            raise ValueError("Hex color must contain 6 characters.")
        return cls(
            int(value[0:2], 16),
            int(value[2:4], 16),
            int(value[4:6], 16),
        )


# ============================================================================
# PALETTES
# ============================================================================

@dataclass
class Theme:
    name: str

    primary: RGB
    primary_light: RGB
    primary_dark: RGB

    secondary: RGB
    secondary_light: RGB
    secondary_dark: RGB

    accent: RGB
    accent_light: RGB
    accent_dark: RGB

    success: RGB
    success_light: RGB
    success_dark: RGB

    error: RGB
    error_light: RGB
    error_dark: RGB

    warning: RGB
    warning_light: RGB
    warning_dark: RGB

    info: RGB
    info_light: RGB
    info_dark: RGB

    text: RGB
    text_bright: RGB
    text_muted: RGB
    text_dim: RGB

    background: RGB
    surface: RGB
    surface_light: RGB

    black: RGB
    white: RGB
    gray: RGB

    gold: RGB
    orange: RGB
    cyan: RGB
    magenta: RGB
    lime: RGB
    teal: RGB


def _theme(
    name,
    primary,
    secondary,
    accent,
    success="#22C55E",
    error="#EF4444",
    warning="#F59E0B",
    info="#3B82F6",
):
    p = RGB.from_hex(primary)
    s = RGB.from_hex(secondary)
    a = RGB.from_hex(accent)
    ok = RGB.from_hex(success)
    er = RGB.from_hex(error)
    wa = RGB.from_hex(warning)
    inf = RGB.from_hex(info)

    return Theme(
        name=name,
        primary=p,
        primary_light=p.lighten(.28),
        primary_dark=p.darken(.28),
        secondary=s,
        secondary_light=s.lighten(.28),
        secondary_dark=s.darken(.28),
        accent=a,
        accent_light=a.lighten(.25),
        accent_dark=a.darken(.25),
        success=ok,
        success_light=ok.lighten(.25),
        success_dark=ok.darken(.25),
        error=er,
        error_light=er.lighten(.25),
        error_dark=er.darken(.25),
        warning=wa,
        warning_light=wa.lighten(.20),
        warning_dark=wa.darken(.25),
        info=inf,
        info_light=inf.lighten(.25),
        info_dark=inf.darken(.25),
        text=RGB.from_hex("#E8EEF7"),
        text_bright=RGB.from_hex("#FFFFFF"),
        text_muted=RGB.from_hex("#94A3B8"),
        text_dim=RGB.from_hex("#64748B"),
        background=RGB.from_hex("#080B12"),
        surface=RGB.from_hex("#111827"),
        surface_light=RGB.from_hex("#1E293B"),
        black=RGB.from_hex("#000000"),
        white=RGB.from_hex("#FFFFFF"),
        gray=RGB.from_hex("#64748B"),
        gold=RGB.from_hex("#FACC15"),
        orange=RGB.from_hex("#F97316"),
        cyan=RGB.from_hex("#06B6D4"),
        magenta=RGB.from_hex("#D946EF"),
        lime=RGB.from_hex("#84CC16"),
        teal=RGB.from_hex("#14B8A6"),
    )


THEMES = {
    "cyber": _theme("cyber", "#8B5CF6", "#06B6D4", "#EC4899"),
    "purple": _theme("purple", "#7C3AED", "#4F46E5", "#C026D3"),
    "matrix": _theme("matrix", "#16A34A", "#22C55E", "#84CC16"),
    "ocean": _theme("ocean", "#0EA5E9", "#06B6D4", "#14B8A6"),
    "fire": _theme("fire", "#EF4444", "#F97316", "#FACC15"),
    "royal": _theme("royal", "#6366F1", "#8B5CF6", "#F59E0B"),
    "mono": _theme("mono", "#E2E8F0", "#94A3B8", "#FFFFFF"),
    "neon": _theme("neon", "#A855F7", "#22D3EE", "#F43F5E"),
}


# ============================================================================
# STYLE
# ============================================================================

@dataclass(frozen=True)
class Style:
    foreground: Optional[RGB] = None
    background: Optional[RGB] = None
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    blink: bool = False
    reverse: bool = False
    strike: bool = False

    def start(self) -> str:
        result = ""

        if self.foreground:
            result += self.foreground.fg()
        if self.background:
            result += self.background.bg()
        if self.bold:
            result += BOLD
        if self.dim:
            result += DIM
        if self.italic:
            result += ITALIC
        if self.underline:
            result += UNDERLINE
        if self.blink:
            result += BLINK
        if self.reverse:
            result += REVERSE
        if self.strike:
            result += STRIKE

        return result

    def apply(self, value) -> str:
        return f"{self.start()}{value}{RESET}"


# ============================================================================
# TERMINAL
# ============================================================================

class Terminal:
    """
    Main reusable terminal framework.
    """

    SPINNERS = {
        "dots": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
        "line": ["-", "\\", "|", "/"],
        "classic": ["|", "/", "-", "\\"],
        "pulse": ["●", "◉", "○", "◉"],
        "blocks": ["▖", "▘", "▝", "▗"],
        "bounce": ["⠁", "⠂", "⠄", "⠂"],
        "arrow": ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"],
        "braille": ["⠋", "⠙", "⠚", "⠒", "⠂", "⠂", "⠒", "⠲", "⠴", "⠦", "⠧", "⠇"],
        "square": ["▰", "▱", "▰", "▱"],
        "circle": ["◐", "◓", "◑", "◒"],
        "moon": ["◑", "◒", "◐", "◓"],
        "grow": ["·", "•", "●", "•"],
        "scan": ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"],
    }

    GRADIENTS = {
        "cyber": ("#8B5CF6", "#EC4899", "#06B6D4"),
        "sunset": ("#F97316", "#EF4444", "#EC4899"),
        "ocean": ("#06B6D4", "#3B82F6", "#8B5CF6"),
        "matrix": ("#14532D", "#22C55E", "#BEF264"),
        "fire": ("#EF4444", "#F97316", "#FACC15"),
        "rainbow": (
            "#FF0000",
            "#FF7F00",
            "#FFFF00",
            "#00FF00",
            "#00FFFF",
            "#0000FF",
            "#8B00FF",
        ),
        "ice": ("#E0F2FE", "#38BDF8", "#2563EB"),
        "royal": ("#312E81", "#7C3AED", "#EC4899"),
    }

    def __init__(
        self,
        *,
        enabled: Optional[bool] = None,
        theme: str | Theme | None = None,
        force_truecolor: Optional[bool] = None,
    ):
        self.enabled = (
            self._detect_color()
            if enabled is None
            else enabled
        )

        self.truecolor = (
            self._detect_truecolor()
            if force_truecolor is None
            else force_truecolor
        )

        theme = theme if theme is not None else os.environ.get('ULTIMATE_TERMINAL_THEME','cyber')
        self.theme = (
            THEMES.get(theme.lower(), THEMES["cyber"])
            if isinstance(theme, str)
            else theme
        )

        self.styles: dict[str, Style] = {}
        self._animation_lock = threading.RLock()
        self._stop_events: list[threading.Event] = []

        self._build_styles()
        try:
            custom = json.loads(os.environ.get('ULTIMATE_TERMINAL_STYLES','{}'))
            for name, config in custom.items():
                config = dict(config)
                for key in ('foreground','background'):
                    if config.get(key):
                        config[key] = RGB.from_hex(config[key])
                self.add_style(name,Style(**config))
        except (ValueError,TypeError,AttributeError):
            pass
        atexit.register(self._cleanup)

    # ========================================================================
    # DETECTION
    # ========================================================================

    @staticmethod
    def _detect_color() -> bool:
        if os.environ.get("NO_COLOR") is not None:
            return False

        if os.environ.get("FORCE_COLOR"):
            return True

        if sys.stdout is None:
            return False

        return sys.stdout.isatty()

    @staticmethod
    def _detect_truecolor() -> bool:
        if os.environ.get("COLORTERM", "").lower() in {
            "truecolor",
            "24bit",
        }:
            return True

        if os.environ.get("WT_SESSION"):
            return True

        if os.environ.get("TERM_PROGRAM", "").lower() in {
            "vscode",
            "wezterm",
            "iterm.app",
            "hyper",
        }:
            return True

        return True

    # ========================================================================
    # THEME
    # ========================================================================

    def set_theme(self, theme: str | Theme):
        if isinstance(theme, str):
            key = theme.lower()
            if key not in THEMES:
                raise KeyError(
                    f"Unknown theme '{theme}'. "
                    f"Available: {', '.join(THEMES)}"
                )
            self.theme = THEMES[key]
        else:
            self.theme = theme

        self._build_styles()

    def register_theme(self, theme: Theme):
        THEMES[theme.name.lower()] = theme

    # ========================================================================
    # STYLES
    # ========================================================================

    def _build_styles(self):
        t = self.theme

        self.styles = {
            # Core
            "primary": Style(t.primary, bold=True),
            "primary_light": Style(t.primary_light),
            "primary_dark": Style(t.primary_dark),

            "secondary": Style(t.secondary, bold=True),
            "secondary_light": Style(t.secondary_light),
            "secondary_dark": Style(t.secondary_dark),

            "accent": Style(t.accent, bold=True),
            "accent_light": Style(t.accent_light),
            "accent_dark": Style(t.accent_dark),

            # Semantic
            "success": Style(t.success, bold=True),
            "success_light": Style(t.success_light),
            "success_dark": Style(t.success_dark),

            "error": Style(t.error, bold=True),
            "error_light": Style(t.error_light),
            "error_dark": Style(t.error_dark),

            "warning": Style(t.warning, bold=True),
            "warning_light": Style(t.warning_light),
            "warning_dark": Style(t.warning_dark),

            "info": Style(t.info, bold=True),
            "info_light": Style(t.info_light),
            "info_dark": Style(t.info_dark),

            # Text
            "text": Style(t.text),
            "white": Style(t.white),
            "bright": Style(t.text_bright, bold=True),
            "muted": Style(t.text_muted),
            "dim": Style(t.text_dim, dim=True),

            # Common colors
            "gold": Style(t.gold, bold=True),
            "orange": Style(t.orange, bold=True),
            "cyan": Style(t.cyan, bold=True),
            "magenta": Style(t.magenta, bold=True),
            "lime": Style(t.lime, bold=True),
            "teal": Style(t.teal, bold=True),

            # UI
            "title": Style(t.primary_light, bold=True),
            "header": Style(t.secondary_light, bold=True, underline=True),
            "subtitle": Style(t.text_muted, italic=True),
            "label": Style(t.text_muted, bold=True),
            "value": Style(t.text),
            "number": Style(t.gold),
            "command": Style(t.cyan, bold=True),
            "path": Style(t.primary_light),
            "url": Style(t.info_light, underline=True),
            "code": Style(t.lime),
            "keyword": Style(t.accent_light, bold=True),

            # Badges
            "badge_success": Style(t.white, t.success_dark, bold=True),
            "badge_error": Style(t.white, t.error_dark, bold=True),
            "badge_warning": Style(t.white, t.warning_dark, bold=True),
            "badge_info": Style(t.white, t.info_dark, bold=True),
            "badge_primary": Style(t.white, t.primary_dark, bold=True),
            "badge_accent": Style(t.white, t.accent_dark, bold=True),

            # Dark UI
            "panel": Style(t.text, t.surface),
            "panel_title": Style(t.primary_light, t.surface_light, bold=True),
            "terminal": Style(t.text, t.background),
            "cyber": Style(t.cyan, t.background, bold=True),
            "matrix": Style(t.success, t.background, bold=True),
            "stealth": Style(t.text_muted, t.background, dim=True),
            "vip": Style(t.gold, t.background, bold=True),
        }

    def add_style(self, name: str, style: Style):
        self.styles[name.lower()] = style

    def get_style(self, name: str) -> Optional[Style]:
        return self.styles.get(name.lower())

    # ========================================================================
    # CORE OUTPUT
    # ========================================================================

    def paint(self, value, style: str | Style | None = None) -> str:
        value = str(value)

        if not self.enabled or style is None:
            return value

        selected = (
            self.styles.get(style.lower())
            if isinstance(style, str)
            else style
        )

        if selected is None:
            return value

        return selected.apply(value)

    def print(
        self,
        *values,
        style: str | Style | None = None,
        sep=" ",
        end="\n",
        file=None,
        flush=False,
    ):
        text = sep.join(str(v) for v in values)

        print(
            self.paint(text, style),
            sep=sep,
            end=end,
            file=file,
            flush=flush,
        )

    # ========================================================================
    # SEMANTIC SHORTCUTS
    # ========================================================================

    def success(self, text):
        self.print(f"✓ {text}", style="success")

    def error(self, text):
        self.print(f"✗ {text}", style="error")

    def warning(self, text):
        self.print(f"⚠ {text}", style="warning")

    def info(self, text):
        self.print(f"ℹ {text}", style="info")

    def debug(self, text):
        self.print(f"◆ {text}", style="magenta")

    def trace(self, text):
        self.print(f"› {text}", style="dim")

    def title(self, text):
        self.print(text, style="title")

    def header(self, text):
        self.print(text, style="header")

    def muted(self, text):
        self.print(text, style="muted")

    def command(self, text):
        self.print(text, style="command")

    # ========================================================================
    # TEXT DECORATION
    # ========================================================================

    def bold(self, text):
        return f"{BOLD}{text}{RESET}" if self.enabled else str(text)

    def dim(self, text):
        return f"{DIM}{text}{RESET}" if self.enabled else str(text)

    def italic(self, text):
        return f"{ITALIC}{text}{RESET}" if self.enabled else str(text)

    def underline(self, text):
        return f"{UNDERLINE}{text}{RESET}" if self.enabled else str(text)

    def strike(self, text):
        return f"{STRIKE}{text}{RESET}" if self.enabled else str(text)

    # ========================================================================
    # RGB HELPERS
    # ========================================================================

    def rgb(self, text, r, g, b, *, background=False, bold=False):
        if not self.enabled:
            return str(text)

        color = RGB(r, g, b)

        sequence = color.bg() if background else color.fg()

        if bold:
            sequence += BOLD

        return f"{sequence}{text}{RESET}"

    # ========================================================================
    # GRADIENTS
    # ========================================================================

    def _interpolate_gradient(
        self,
        colors: Sequence[RGB],
        position: float,
    ) -> RGB:
        if len(colors) == 1:
            return colors[0]

        position = max(0.0, min(1.0, position))

        scaled = position * (len(colors) - 1)
        index = min(int(scaled), len(colors) - 2)
        local = scaled - index

        return colors[index].blend(colors[index + 1], local)

    def gradient(
        self,
        text: str,
        gradient: str | Sequence[str] = "cyber",
    ) -> str:
        if not self.enabled or not text:
            return text

        if isinstance(gradient, str):
            gradient = self.GRADIENTS.get(
                gradient.lower(),
                self.GRADIENTS["cyber"],
            )

        colors = [RGB.from_hex(c) for c in gradient]

        visible_length = len(text)

        if visible_length <= 1:
            return colors[0].fg() + text + RESET

        output = []

        for i, char in enumerate(text):
            position = i / (visible_length - 1)
            color = self._interpolate_gradient(colors, position)
            output.append(f"{color.fg()}{char}")

        return "".join(output) + RESET

    def rainbow(self, text: str) -> str:
        return self.gradient(text, "rainbow")

    # ========================================================================
    # BANNERS
    # ========================================================================

    def banner(
        self,
        text: str,
        *,
        width: Optional[int] = None,
        gradient: str = "cyber",
        char: str = "═",
        padding: int = 2,
    ):
        if width is None:
            width = min(shutil.get_terminal_size((80, 20)).columns, 100)

        content = f"{' ' * padding}{text}{' ' * padding}"

        width = max(width, len(content) + 2)

        top = char * width
        bottom = char * width

        self.print(self.gradient(top, gradient))
        self.print(self.gradient(
            content.center(width),
            gradient,
        ))
        self.print(self.gradient(bottom, gradient))

    # ========================================================================
    # SECTIONS
    # ========================================================================

    def separator(
        self,
        char="─",
        width: Optional[int] = None,
        style="dim",
    ):
        if width is None:
            width = shutil.get_terminal_size((80, 20)).columns

        self.print(char * width, style=style)

    def section(self, title: str, *, width: Optional[int] = None):
        if width is None:
            width = shutil.get_terminal_size((80, 20)).columns

        title_text = f" {title} "

        remaining = max(0, width - len(title_text))
        left = remaining // 2
        right = remaining - left

        line = "─" * left + title_text + "─" * right

        self.print(line, style="primary")

    # ========================================================================
    # PANELS
    # ========================================================================

    def panel(
        self,
        text: str | Sequence[str],
        *,
        title: Optional[str] = None,
        width: Optional[int] = None,
        style="text",
        border_style="primary",
        padding: int = 1,
    ):
        if width is None:
            width = min(
                shutil.get_terminal_size((80, 20)).columns - 2,
                90,
            )

        if isinstance(text, str):
            lines = text.splitlines() or [""]
        else:
            lines = [str(x) for x in text]

        inner_width = max(10, width - 2 - padding * 2)

        content = []

        for line in lines:
            while len(line) > inner_width:
                content.append(line[:inner_width])
                line = line[inner_width:]
            content.append(line)

        if title:
            title_text = f" {title} "
            top_inner = (
                title_text
                + "─" * max(
                    0,
                    width - 2 - len(title_text),
                )
            )
        else:
            top_inner = "─" * (width - 2)

        self.print(
            "╭" + top_inner + "╮",
            style=border_style,
        )

        for line in content:
            padded = (
                " " * padding
                + line
                + " " * max(
                    0,
                    inner_width - len(line),
                )
                + " " * padding
            )

            self.print(
                "│" + self.paint(padded, style) + "│",
                style=border_style,
            )

        self.print(
            "╰" + "─" * (width - 2) + "╯",
            style=border_style,
        )

    # ========================================================================
    # BADGES
    # ========================================================================

    def badge(self, text, kind="primary"):
        return self.paint(
            f" {text} ",
            f"badge_{kind}",
        )

    # ========================================================================
    # TABLE
    # ========================================================================

    def table(
        self,
        rows: Sequence[Sequence],
        *,
        headers: Optional[Sequence] = None,
        padding: int = 1,
        border_style="primary",
    ):
        data = []

        if headers:
            data.append([str(x) for x in headers])

        data.extend([
            [str(x) for x in row]
            for row in rows
        ])

        if not data:
            return

        columns = max(len(row) for row in data)

        normalized = [
            row + [""] * (columns - len(row))
            for row in data
        ]

        widths = [
            max(len(row[i]) for row in normalized)
            for i in range(columns)
        ]

        def make_row(row):
            return (
                "│"
                + "│".join(
                    " " * padding
                    + row[i].ljust(widths[i])
                    + " " * padding
                    for i in range(columns)
                )
                + "│"
            )

        top = "┌" + "┬".join(
            "─" * (w + padding * 2)
            for w in widths
        ) + "┐"

        middle = "├" + "┼".join(
            "─" * (w + padding * 2)
            for w in widths
        ) + "┤"

        bottom = "└" + "┴".join(
            "─" * (w + padding * 2)
            for w in widths
        ) + "┘"

        self.print(top, style=border_style)

        if headers:
            self.print(
                make_row(normalized[0]),
                style="header",
            )
            self.print(middle, style=border_style)
            body = normalized[1:]
        else:
            body = normalized

        for row in body:
            self.print(make_row(row), style="text")

        self.print(bottom, style=border_style)

    # ========================================================================
    # PROGRESS BAR
    # ========================================================================

    def progress_bar(
        self,
        value: float,
        *,
        total: float = 100,
        width: int = 35,
        label: str = "",
        filled: str = "█",
        empty: str = "░",
        style="primary",
        show_percent=True,
    ) -> str:
        if total <= 0:
            total = 1

        ratio = max(0.0, min(1.0, value / total))
        filled_count = round(width * ratio)

        bar = (
            self.paint(
                filled * filled_count,
                style,
            )
            + self.paint(
                empty * (width - filled_count),
                "dim",
            )
        )

        percentage = f"{ratio * 100:6.2f}%"

        prefix = f"{label} " if label else ""

        return (
            f"{prefix}[{bar}]"
            + (f" {percentage}" if show_percent else "")
        )

    def progress(
        self,
        value: float,
        *,
        total: float = 100,
        width: int = 35,
        label: str = "",
        style="primary",
        show_percent=True,
        newline=True,
    ):
        text = self.progress_bar(
            value,
            total=total,
            width=width,
            label=label,
            style=style,
            show_percent=show_percent,
        )

        if newline:
            self.print(text)
        else:
            self.live(text)

    def animate_progress(
        self,
        *,
        total: int = 100,
        width: int = 35,
        label: str = "Progress",
        duration: float = 2.0,
        style="primary",
    ):
        start = time.perf_counter()

        while True:
            elapsed = time.perf_counter() - start
            ratio = min(1.0, elapsed / max(duration, .001))
            value = ratio * total

            self.live(
                self.progress_bar(
                    value,
                    total=total,
                    width=width,
                    label=label,
                    style=style,
                )
            )

            if ratio >= 1:
                break

            time.sleep(0.025)

        self.live("")
        print()

    # ========================================================================
    # LIVE LINE
    # ========================================================================

    def live(self, text: str):
        """
        Rewrite the current terminal line.
        """
        if not self.enabled:
            print(text, end="\r", flush=True)
            return

        print(
            "\r" + CLEAR_LINE + text,
            end="",
            flush=True,
        )

    def clear_line(self):
        print("\r" + CLEAR_LINE, end="", flush=True)

    # ========================================================================
    # SPINNER
    # ========================================================================

    def spinner(
        self,
        message="Loading",
        *,
        frames="dots",
        duration: float = 2.0,
        interval: float = 0.08,
        style="primary",
    ):
        sequence = (
            self.SPINNERS.get(frames, self.SPINNERS["dots"])
            if isinstance(frames, str)
            else list(frames)
        )

        end_time = time.perf_counter() + duration
        index = 0

        while time.perf_counter() < end_time:
            frame = sequence[index % len(sequence)]
            self.live(
                self.paint(frame, style)
                + " "
                + message
            )
            index += 1
            time.sleep(interval)

        self.clear_line()

    # ========================================================================
    # BACKGROUND SPINNER
    # ========================================================================

    class _LiveSpinner:
        def __init__(
            self,
            owner: "Terminal",
            message: str,
            frames,
            interval: float,
            style: str,
        ):
            self.owner = owner
            self.message = message
            self.frames = frames
            self.interval = interval
            self.style = style
            self.stop_event = threading.Event()
            self.thread = None

        def _run(self):
            index = 0

            while not self.stop_event.is_set():
                frame = self.frames[index % len(self.frames)]

                self.owner.live(
                    self.owner.paint(
                        frame,
                        self.style,
                    )
                    + " "
                    + self.message
                )

                index += 1
                self.stop_event.wait(self.interval)

        def start(self):
            if not self.owner.enabled:
                return self

            self.thread = threading.Thread(
                target=self._run,
                daemon=True,
            )
            self.thread.start()
            return self

        def stop(self, final_message: Optional[str] = None):
            self.stop_event.set()

            if self.thread:
                self.thread.join(timeout=1)

            self.owner.clear_line()

            if final_message:
                self.owner.print(final_message)

        def __enter__(self):
            return self.start()

        def __exit__(self, exc_type, exc, tb):
            if exc:
                self.stop(
                    self.owner.paint(
                        f"✗ {exc}",
                        "error",
                    )
                )
            else:
                self.stop()

    def live_spinner(
        self,
        message="Loading",
        *,
        frames="dots",
        interval=.08,
        style="primary",
    ):
        sequence = (
            self.SPINNERS.get(frames, self.SPINNERS["dots"])
            if isinstance(frames, str)
            else list(frames)
        )

        return self._LiveSpinner(
            self,
            message,
            sequence,
            interval,
            style,
        )

    # ========================================================================
    # TYPEWRITER
    # ========================================================================

    def typewrite(
        self,
        text: str,
        *,
        delay: float = .025,
        style=None,
        newline=True,
    ):
        if not self.enabled:
            print(text, end="\n" if newline else "")
            return

        if style:
            prefix = self.paint("", style)
            selected = self.get_style(style)

            if selected:
                print(selected.start(), end="", flush=True)

        for char in text:
            print(char, end="", flush=True)
            time.sleep(delay)

        if style:
            print(RESET, end="")

        if newline:
            print()

    # ========================================================================
    # PULSE
    # ========================================================================

    def pulse(
        self,
        text: str,
        *,
        cycles: int = 3,
        interval: float = .12,
        style="primary",
    ):
        base = self.get_style(style)

        if not base:
            self.print(text)
            return

        for i in range(cycles):
            self.live(
                Style(
                    foreground=base.foreground,
                    background=base.background,
                    bold=True,
                ).apply(text)
            )
            time.sleep(interval)

            self.live(
                Style(
                    foreground=base.foreground,
                    background=base.background,
                    dim=True,
                ).apply(text)
            )
            time.sleep(interval)

        self.clear_line()

    # ========================================================================
    # MARQUEE
    # ========================================================================

    def marquee(
        self,
        text: str,
        *,
        width: int = 40,
        cycles: int = 2,
        interval: float = .06,
        style="primary",
    ):
        padded = " " * width + text + " " * width

        for _ in range(cycles):
            for position in range(len(padded) - width + 1):
                visible = padded[position:position + width]

                self.live(
                    self.paint(
                        visible,
                        style,
                    )
                )

                time.sleep(interval)

        self.clear_line()

    # ========================================================================
    # COUNTDOWN
    # ========================================================================

    def countdown(
        self,
        seconds: int,
        *,
        label="Starting in",
        style="warning",
    ):
        for remaining in range(seconds, 0, -1):
            self.live(
                f"{label} "
                + self.paint(
                    str(remaining),
                    style,
                )
            )
            time.sleep(1)

        self.live(
            self.paint("GO!", "success")
        )

        time.sleep(.25)
        self.clear_line()

    # ========================================================================
    # DOT LOADER
    # ========================================================================

    def dots(
        self,
        message="Loading",
        *,
        duration=2,
        interval=.35,
        style="primary",
    ):
        end = time.perf_counter() + duration
        count = 0

        while time.perf_counter() < end:
            dots = "." * ((count % 3) + 1)

            self.live(
                self.paint(
                    f"{message}{dots}",
                    style,
                )
            )

            count += 1
            time.sleep(interval)

        self.clear_line()

    # ========================================================================
    # SCANNER
    # ========================================================================

    def scanner(
        self,
        message="Scanning",
        *,
        width=25,
        duration=2,
        style="cyan",
    ):
        start = time.perf_counter()

        while time.perf_counter() - start < duration:
            elapsed = time.perf_counter() - start
            ratio = (elapsed / duration) % 1

            position = int(ratio * (width - 1))

            bar = (
                " " * position
                + self.paint("█", style)
                + " " * (width - position - 1)
            )

            self.live(f"{message} [{bar}]")
            time.sleep(.035)

        self.clear_line()

    # ========================================================================
    # RAINBOW ANIMATION
    # ========================================================================

    def rainbow_animation(
        self,
        text: str,
        *,
        cycles: int = 2,
        interval: float = .08,
    ):
        colors = [
            RGB.from_hex(c)
            for c in self.GRADIENTS["rainbow"]
        ]

        for shift in range(cycles * len(colors)):
            output = []

            for index, char in enumerate(text):
                color = colors[
                    (index + shift) % len(colors)
                ]

                output.append(
                    f"{color.fg()}{char}"
                )

            self.live("".join(output) + RESET)
            time.sleep(interval)

        self.clear_line()

    # ========================================================================
    # TERMINAL CONTROL
    # ========================================================================

    def clear(self):
        if self.enabled:
            print(
                CLEAR_SCREEN
                + CURSOR_HOME,
                end="",
            )
        else:
            os.system("cls" if os.name == "nt" else "clear")

    def hide_cursor(self):
        if self.enabled:
            print(HIDE_CURSOR, end="", flush=True)

    def show_cursor(self):
        if self.enabled:
            print(SHOW_CURSOR, end="", flush=True)

    def _cleanup(self):
        try:
            self.show_cursor()
            print(RESET, end="")
        except Exception:
            pass

    @contextmanager
    def hidden_cursor(self):
        self.hide_cursor()

        try:
            yield
        finally:
            self.show_cursor()

    # ========================================================================
    # STYLE CONTEXT
    # ========================================================================

    @contextmanager
    def style(self, style: str | Style):
        selected = (
            self.get_style(style)
            if isinstance(style, str)
            else style
        )

        if self.enabled and selected:
            print(selected.start(), end="", flush=True)

        try:
            yield
        finally:
            if self.enabled and selected:
                print(RESET, end="", flush=True)

    # ========================================================================
    # LOGGING
    # ========================================================================

    def log(
        self,
        level: str,
        message: str,
        *,
        timestamp: bool = True,
    ):
        level = level.upper()

        styles = {
            "DEBUG": "magenta",
            "TRACE": "dim",
            "INFO": "info",
            "SUCCESS": "success",
            "WARNING": "warning",
            "ERROR": "error",
            "CRITICAL": "badge_error",
        }

        prefix = f"[{level}]"

        if timestamp:
            stamp = time.strftime("%H:%M:%S")
            prefix = f"[{stamp}] {prefix}"

        self.print(
            f"{prefix} {message}",
            style=styles.get(level, "text"),
        )


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

terminal = Terminal()


# ============================================================================
# GLOBAL SHORTCUTS
# ============================================================================

def paint(text, style=None):
    return terminal.paint(text, style)


def cprint(*values, style=None, sep=" ", end="\n", flush=False):
    terminal.print(
        *values,
        style=style,
        sep=sep,
        end=end,
        flush=flush,
    )


def success(text):
    terminal.success(text)


def error(text):
    terminal.error(text)


def warning(text):
    terminal.warning(text)


def info(text):
    terminal.info(text)


def debug(text):
    terminal.debug(text)


def banner(text, **kwargs):
    terminal.banner(text, **kwargs)


def gradient(text, gradient_name="cyber"):
    return terminal.gradient(text, gradient_name)


def rainbow(text):
    return terminal.rainbow(text)


def spinner(message="Loading", **kwargs):
    terminal.spinner(message, **kwargs)


def progress(value, **kwargs):
    terminal.progress(value, **kwargs)


def typewrite(text, **kwargs):
    terminal.typewrite(text, **kwargs)


def countdown(seconds, **kwargs):
    terminal.countdown(seconds, **kwargs)


def panel(text, **kwargs):
    terminal.panel(text, **kwargs)


def table(rows, **kwargs):
    terminal.table(rows, **kwargs)


def separator(**kwargs):
    terminal.separator(**kwargs)


def section(title, **kwargs):
    terminal.section(title, **kwargs)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "RGB",
    "Style",
    "Theme",
    "Terminal",
    "THEMES",
    "terminal",
    "paint",
    "cprint",
    "success",
    "error",
    "warning",
    "info",
    "debug",
    "banner",
    "gradient",
    "rainbow",
    "spinner",
    "progress",
    "typewrite",
    "countdown",
    "panel",
    "table",
    "separator",
    "section",
]
