from typing import Optional

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from vorta.views import theme
from vorta.views.icons import symbol_icon

PAGE_ROLE = Qt.ItemDataRole.UserRole + 1
HEADER_ROLE = Qt.ItemDataRole.UserRole + 2


class SidebarDelegate(QStyledItemDelegate):
    ROW_HEIGHT = 32
    HEADER_HEIGHT = 28
    ICON_SIZE = 18

    def sizeHint(self, option, index):
        if index.data(HEADER_ROLE):
            return QSize(option.rect.width(), self.HEADER_HEIGHT)
        return QSize(option.rect.width(), self.ROW_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(theme.SPACE_S + 2, 1, -(theme.SPACE_S + 2), -1)
        if index.data(HEADER_ROLE):
            painter.setFont(theme.font('subheadline'))
            f = painter.font()
            f.setWeight(f.Weight.DemiBold)
            painter.setFont(f)
            painter.setPen(theme.tertiary_label_color())
            painter.drawText(
                rect.adjusted(theme.SPACE_S, 0, 0, -4),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                index.data(Qt.ItemDataRole.DisplayRole),
            )
            painter.restore()
            return

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:
            path = QPainterPath()
            path.addRoundedRect(QRectF(rect), theme.RADIUS_ROW, theme.RADIUS_ROW)
            painter.fillPath(path, theme.selection_fill_color())

        icon = index.data(Qt.ItemDataRole.DecorationRole)
        x = rect.left() + theme.SPACE_S
        if icon is not None:
            icon_rect = rect.adjusted(0, 0, 0, 0)
            icon_rect.setLeft(x)
            icon_rect.setWidth(self.ICON_SIZE)
            icon_rect.setTop(rect.center().y() - self.ICON_SIZE // 2 + 1)
            icon_rect.setHeight(self.ICON_SIZE)
            icon.paint(painter, icon_rect)
            x += self.ICON_SIZE + theme.SPACE_S

        painter.setFont(theme.font('body'))
        painter.setPen(theme.label_color())
        text_rect = rect.adjusted(x - rect.left(), 0, -theme.SPACE_S, 0)
        text = painter.fontMetrics().elidedText(
            index.data(Qt.ItemDataRole.DisplayRole), Qt.TextElideMode.ElideRight, text_rect.width()
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        painter.restore()


class SidebarPane(QWidget):
    """
    Container of the sidebar column.

    On macOS a native Liquid Glass view sits behind it and the pane stays transparent.
    Otherwise it paints its own floating, rounded panel so the layout looks the same.
    """

    INSET = 8

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._native_backdrop = False

    def set_native_backdrop(self, enabled: bool) -> None:
        self._native_backdrop = enabled
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if not self._native_backdrop:
            painter.fillRect(self.rect(), theme.window_color())
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            panel = QRectF(self.rect()).adjusted(self.INSET, self.INSET, -self.INSET, -self.INSET)
            path = QPainterPath()
            path.addRoundedRect(panel, 16, 16)
            painter.fillPath(path, theme.section_color())
            painter.setPen(theme.section_border_color())
            painter.drawPath(path)
        painter.end()


class Sidebar(QListWidget):
    """Source-list navigation: rounded selection capsules, accent-coloured SF Symbols, section headers."""

    page_selected = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setItemDelegate(SidebarDelegate(self))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.viewport().setAutoFillBackground(False)
        self.setAutoFillBackground(False)
        self.setStyleSheet('QListWidget { background: transparent; }')
        self.currentItemChanged.connect(self._on_current_changed)

    def add_header(self, text: str) -> QListWidgetItem:
        item = QListWidgetItem(text)
        item.setData(HEADER_ROLE, True)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.addItem(item)
        return item

    def add_page(self, key: str, text: str, icon_name: str) -> QListWidgetItem:
        item = QListWidgetItem(symbol_icon(icon_name, accent=True), text)
        item.setData(PAGE_ROLE, key)
        item.setToolTip(text)
        self.addItem(item)
        return item

    def select_page(self, key: str) -> None:
        for row in range(self.count()):
            item = self.item(row)
            if item.data(PAGE_ROLE) == key:
                self.setCurrentItem(item)
                return

    def current_page(self) -> Optional[str]:
        item = self.currentItem()
        return item.data(PAGE_ROLE) if item else None

    def _on_current_changed(self, current, _previous):
        if current is not None and current.data(PAGE_ROLE):
            self.page_selected.emit(current.data(PAGE_ROLE))
