"""
Semantic icons.

On macOS icons are SF Symbols rendered at the exact requested size and tinted
with the live palette, so they follow light/dark mode and look native. Elsewhere
(or if a symbol is missing) the bundled monochrome SVGs are used.
"""

from typing import Callable, Dict, Optional, Tuple

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QIconEngine, QImage, QPainter, QPalette, QPixmap
from PyQt6.QtWidgets import QApplication

from vorta.utils import get_asset, uses_dark_mode
from vorta.views import platform_macos

# icon name -> (SF Symbol, fallback SVG in assets/icons)
SYMBOLS: Dict[str, Tuple[str, str]] = {
    # legacy names used throughout the views
    'angle-down-solid': ('chevron.down', 'angle-down-solid'),
    'angle-up-solid': ('chevron.up', 'angle-up-solid'),
    'broom-solid': ('arrow.down.right.and.arrow.up.left', 'broom-solid'),
    'check-circle': ('checkmark.shield', 'check-circle'),
    'clock-o': ('clock', 'clock-o'),
    'cloud-download': ('arrow.down.doc', 'cloud-download'),
    'copy': ('doc.on.doc', 'copy'),
    'cut': ('scissors', 'cut'),
    'edit': ('pencil', 'edit'),
    'eject': ('eject', 'eject'),
    'ellipsis-v': ('ellipsis', 'ellipsis-v'),
    'exclamation-triangle': ('exclamationmark.triangle.fill', 'exclamation-triangle'),
    'eye': ('eye', 'eye'),
    'eye-slash': ('eye.slash', 'eye-slash'),
    'file': ('doc', 'file'),
    'file-import-solid': ('square.and.arrow.up', 'file-import-solid'),
    'folder': ('folder', 'folder'),
    'folder-on-top': ('folder.badge.plus', 'folder-on-top'),
    'folder-open': ('externaldrive.badge.plus', 'folder-open'),
    'globe': ('globe', 'globe'),
    'help-about': ('info.circle', 'help-about'),
    'home': ('house', 'home'),
    'key': ('key', 'key'),
    'minus': ('minus', 'minus'),
    'plus': ('plus', 'plus'),
    'refresh': ('arrow.clockwise', 'refresh'),
    'server': ('server.rack', 'server'),
    'settings_wheel': ('gearshape', 'settings_wheel'),
    'stream-solid': ('arrow.left.arrow.right', 'stream-solid'),
    'tasks': ('checklist', 'tasks'),
    'terminal': ('apple.terminal', 'terminal'),
    'trash': ('trash', 'trash'),
    'unlink': ('minus.circle', 'unlink'),
    'user': ('person', 'user'),
    'view-list-details': ('list.bullet', 'view-list-details'),
    'view-list-tree': ('list.bullet.indent', 'view-list-tree'),
    'wifi': ('wifi', 'wifi'),
    # sidebar and new surfaces
    'overview': ('gauge.with.dots.needle.67percent', 'home'),
    'sources': ('folder', 'folder'),
    'repository': ('externaldrive.connected.to.line.below', 'server'),
    'schedule': ('calendar.badge.clock', 'clock-o'),
    'archives': ('archivebox', 'tasks'),
    'activity': ('list.bullet.rectangle', 'view-list-details'),
    'backup': ('arrow.clockwise.circle', 'refresh'),
    'stop': ('stop.fill', 'minus'),
    'status-ok': ('checkmark.circle.fill', 'check-circle'),
    'status-warning': ('exclamationmark.triangle.fill', 'exclamation-triangle'),
    'status-running': ('arrow.triangle.2.circlepath', 'refresh'),
    'status-none': ('clock.badge.questionmark', 'clock-o'),
    'info': ('info.circle', 'help-about'),
    'more': ('ellipsis.circle', 'ellipsis-v'),
    'profile': ('person.crop.circle', 'user'),
    'sidebar': ('sidebar.left', 'view-list-details'),
    'shield': ('lock.shield', 'key'),
    'compression': ('archivebox', 'tasks'),
    'network': ('network', 'wifi'),
    'restore': ('arrow.uturn.backward.circle', 'cloud-download'),
}

ColorProvider = Callable[[QIcon.Mode], QColor]


def _default_color(mode: QIcon.Mode) -> QColor:
    pal = QApplication.palette()
    if mode == QIcon.Mode.Disabled:
        return pal.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText)
    if mode == QIcon.Mode.Selected:
        return pal.color(QPalette.ColorRole.HighlightedText)
    color = pal.color(QPalette.ColorRole.WindowText)
    color.setAlphaF(0.85)
    return color


def _accent_color(mode: QIcon.Mode) -> QColor:
    if mode == QIcon.Mode.Disabled:
        return _default_color(mode)
    return QApplication.palette().color(QPalette.ColorRole.Accent)


class SymbolIconEngine(QIconEngine):
    """Renders an SF Symbol on demand, at the requested size, in the current palette colour."""

    def __init__(self, symbol: str, fallback_svg: str, color: Optional[ColorProvider] = None, weight='regular'):
        super().__init__()
        self.symbol = symbol
        self.fallback_svg = fallback_svg
        self.color = color or _default_color
        self.weight = weight
        self._cache: Dict[tuple, QPixmap] = {}

    def clone(self):
        return SymbolIconEngine(self.symbol, self.fallback_svg, self.color, self.weight)

    def _template(self, size: QSize, scale: float) -> Optional[QImage]:
        point_size = max(6.0, min(size.width(), size.height()) * 0.78)
        image = platform_macos.sf_symbol_image(self.symbol, point_size, scale=scale, weight=self.weight)
        if image is None:
            svg = QIcon(get_asset(f'icons/{self.fallback_svg}.svg'))
            device_size = QSize(round(size.width() * scale), round(size.height() * scale))
            image = svg.pixmap(device_size).toImage()
            image.setDevicePixelRatio(scale)
        return image

    def scaledPixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State, scale: float) -> QPixmap:
        scale = max(1.0, scale)
        color = self.color(mode)
        key = (size.width(), size.height(), scale, color.rgba())
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        canvas = QImage(
            round(size.width() * scale), round(size.height() * scale), QImage.Format.Format_ARGB32_Premultiplied
        )
        canvas.fill(Qt.GlobalColor.transparent)
        canvas.setDevicePixelRatio(scale)
        template = self._template(size, scale)
        if template is not None and not template.isNull():
            painter = QPainter(canvas)
            logical = QSize(round(template.width() / scale), round(template.height() / scale))
            if logical.width() > size.width() or logical.height() > size.height():
                logical.scale(size, Qt.AspectRatioMode.KeepAspectRatio)
            top_left = QPoint((size.width() - logical.width()) // 2, (size.height() - logical.height()) // 2)
            painter.drawImage(QRect(top_left, logical), template)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(QRect(QPoint(0, 0), size), color)
            painter.end()
        pixmap = QPixmap.fromImage(canvas)
        if len(self._cache) > 64:
            self._cache.clear()
        self._cache[key] = pixmap
        return pixmap

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        screen = QApplication.primaryScreen()
        return self.scaledPixmap(size, mode, state, screen.devicePixelRatio() if screen else 1.0)

    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State):
        scale = painter.device().devicePixelRatioF() if painter.device() else 1.0
        painter.drawPixmap(rect, self.scaledPixmap(rect.size(), mode, state, scale))

    def actualSize(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QSize:
        return size


def symbol_icon(name: str, accent: bool = False, weight: str = 'regular') -> QIcon:
    """Return the themed icon for a semantic or legacy icon name."""
    symbol, fallback = SYMBOLS.get(name, (name, name))
    return QIcon(SymbolIconEngine(symbol, fallback, _accent_color if accent else None, weight))


def symbol_pixmap(name: str, size: int, color: Optional[QColor] = None) -> QPixmap:
    symbol, fallback = SYMBOLS.get(name, (name, name))
    provider = (lambda _mode: QColor(color)) if color is not None else None
    engine = SymbolIconEngine(symbol, fallback, provider)
    screen = QApplication.primaryScreen()
    scale = screen.devicePixelRatio() if screen else 1.0
    return engine.scaledPixmap(QSize(size, size), QIcon.Mode.Normal, QIcon.State.Off, scale)


def has_symbol(name: str) -> bool:
    return name in SYMBOLS


def legacy_svg_icon(icon_name, scaled_height=128, return_qpixmap=False):
    """The original recoloured-SVG implementation, used for logos and non-symbol assets."""
    with open(get_asset(f"icons/{icon_name}.svg"), 'rb') as svg_file:
        svg_str = svg_file.read()
    if uses_dark_mode():
        svg_str = svg_str.replace(b'#000000', b'#ffffff')
    svg_img = QImage.fromData(svg_str).scaledToHeight(scaled_height)

    if return_qpixmap:
        return QPixmap(svg_img)
    return QIcon(QPixmap(svg_img))
