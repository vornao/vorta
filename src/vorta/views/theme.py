"""
Design tokens and theme plumbing for the GUI.

Native controls keep the platform style untouched (no QSS on buttons, combos, ...).
Custom surfaces (sidebar, grouped sections, switches) paint themselves with the
colours from this module, which are all derived from the live palette so light
mode, dark mode and the system accent colour come for free.

`.ui` files opt into typography and colour roles with dynamic properties::

    <property name="textStyle" stdset="0"><string>title2</string></property>
    <property name="textRole" stdset="0"><string>secondary</string></property>
"""

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PyQt6.QtWidgets import QAbstractButton, QApplication, QWidget

from vorta.utils import uses_dark_mode

# Spacing on an 8-pt grid
SPACE_XS = 4
SPACE_S = 8
SPACE_M = 12
SPACE_L = 16
SPACE_XL = 20
SPACE_XXL = 28

RADIUS_SECTION = 12
RADIUS_ROW = 8

PAGE_MARGIN = 24
HEADER_HEIGHT = 52
SIDEBAR_WIDTH = 220

# macOS text styles: (point size, weight)
TEXT_STYLES = {
    'largeTitle': (26, QFont.Weight.Bold),
    'title1': (22, QFont.Weight.Bold),
    'title2': (17, QFont.Weight.Bold),
    'title3': (15, QFont.Weight.DemiBold),
    'headline': (13, QFont.Weight.DemiBold),
    'body': (13, QFont.Weight.Normal),
    'callout': (12, QFont.Weight.Normal),
    'subheadline': (11, QFont.Weight.Normal),
    'footnote': (10, QFont.Weight.Normal),
    'monospace': (12, QFont.Weight.Normal),
}


def mix(a: QColor, b: QColor, t: float) -> QColor:
    """Blend colour `a` towards `b` by factor `t` (0 = a, 1 = b)."""
    return QColor.fromRgbF(
        a.redF() + (b.redF() - a.redF()) * t,
        a.greenF() + (b.greenF() - a.greenF()) * t,
        a.blueF() + (b.blueF() - a.blueF()) * t,
        a.alphaF() + (b.alphaF() - a.alphaF()) * t,
    )


def with_alpha(color: QColor, alpha: float) -> QColor:
    c = QColor(color)
    c.setAlphaF(alpha)
    return c


def palette() -> QPalette:
    return QApplication.palette()


def is_dark() -> bool:
    return uses_dark_mode()


def window_color() -> QColor:
    return palette().color(QPalette.ColorRole.Window)


def label_color() -> QColor:
    return palette().color(QPalette.ColorRole.WindowText)


def secondary_label_color() -> QColor:
    return with_alpha(label_color(), 0.55 if is_dark() else 0.5)


def tertiary_label_color() -> QColor:
    return with_alpha(label_color(), 0.3 if is_dark() else 0.26)


def accent_color() -> QColor:
    return palette().color(QPalette.ColorRole.Accent)


def section_color() -> QColor:
    """Background of an inset grouped section."""
    if is_dark():
        return mix(window_color(), QColor('white'), 0.05)
    return mix(window_color(), QColor('white'), 0.75)


def section_border_color() -> QColor:
    return with_alpha(label_color(), 0.07 if is_dark() else 0.06)


def separator_color() -> QColor:
    return with_alpha(label_color(), 0.1 if is_dark() else 0.09)


def selection_fill_color() -> QColor:
    """Sidebar selection capsule, like the macOS 26 source list."""
    return with_alpha(label_color(), 0.11 if is_dark() else 0.09)


def success_color() -> QColor:
    return QColor('#30d158') if is_dark() else QColor('#28a745')


def warning_color() -> QColor:
    return QColor('#ffd60a') if is_dark() else QColor('#c27c00')


def danger_color() -> QColor:
    return QColor('#ff453a') if is_dark() else QColor('#d70015')


def link_color() -> QColor:
    return palette().color(QPalette.ColorRole.Link)


ROLE_COLORS = {
    'secondary': secondary_label_color,
    'tertiary': tertiary_label_color,
    'danger': danger_color,
    'success': success_color,
    'warning': warning_color,
    'accent': accent_color,
}


def font(style: str) -> QFont:
    if style == 'monospace':
        f = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    else:
        f = QFont(QApplication.font())
    size, weight = TEXT_STYLES.get(style, TEXT_STYLES['body'])
    f.setPointSizeF(size)
    f.setWeight(weight)
    return f


def apply_text_style(widget: QWidget, style: str) -> None:
    widget.setProperty('textStyle', style)
    widget.setFont(font(style))


def apply_text_role(widget: QWidget, role: str) -> None:
    widget.setProperty('textRole', role)
    _apply_role(widget, role)


def _apply_role(widget: QWidget, role: str) -> None:
    color_fn = ROLE_COLORS.get(role)
    if color_fn is None:
        return
    color = color_fn()
    pal = QPalette(QApplication.palette())
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        pal.setColor(group, QPalette.ColorRole.WindowText, color)
        pal.setColor(group, QPalette.ColorRole.Text, color)
    widget.setPalette(pal)


class _ThemeFilter(QObject):
    """Applies `textStyle` / `textRole` properties on polish and on theme changes."""

    def eventFilter(self, obj, event):
        etype = event.type()
        if etype == QEvent.Type.Polish and isinstance(obj, QWidget):
            self.apply(obj)
        elif etype == QEvent.Type.ApplicationPaletteChange and obj is QApplication.instance():
            for widget in QApplication.allWidgets():
                if widget.property('textRole'):
                    _apply_role(widget, widget.property('textRole'))
        return False

    @staticmethod
    def apply(widget: QWidget) -> None:
        # Icon-only buttons: let VoiceOver read the tooltip
        if isinstance(widget, QAbstractButton) and not widget.text() and not widget.accessibleName():
            if widget.toolTip():
                widget.setAccessibleName(widget.toolTip())
        style = widget.property('textStyle')
        if style:
            widget.setFont(font(style))
        role = widget.property('textRole')
        if role:
            _apply_role(widget, role)


def apply_theme(app: QApplication) -> None:
    """Install the theme filter once per application."""
    if getattr(app, '_vorta_theme_filter', None) is not None:
        return
    theme_filter = _ThemeFilter(app)
    app.installEventFilter(theme_filter)
    app._vorta_theme_filter = theme_filter
    for widget in QApplication.allWidgets():
        theme_filter.apply(widget)
