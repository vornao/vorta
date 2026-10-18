from typing import List, Optional

from PyQt6.QtCore import QRect, QRectF, Qt
from PyQt6.QtGui import QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QBoxLayout, QFrame, QGridLayout, QLayout, QSizePolicy, QWidget

from vorta.views import theme


class FormSection(QFrame):
    """
    An inset grouped section, like the ones in macOS System Settings.

    Lay out rows in a QGridLayout (one row per setting: label left, control right)
    or a vertical QBoxLayout. Hairline separators are drawn between visible rows.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._separators = True

    def setSeparators(self, enabled: bool) -> None:
        self._separators = enabled
        self.update()

    @staticmethod
    def configure_layout(layout: QLayout) -> QLayout:
        layout.setContentsMargins(theme.SPACE_L - 2, theme.SPACE_M - 2, theme.SPACE_L - 2, theme.SPACE_M - 2)
        if isinstance(layout, QGridLayout):
            layout.setHorizontalSpacing(theme.SPACE_M)
            layout.setVerticalSpacing(theme.SPACE_L + 2)
        else:
            layout.setSpacing(theme.SPACE_L + 2)
        return layout

    def _row_rects(self) -> List[QRect]:
        layout = self.layout()
        rects: List[QRect] = []
        if isinstance(layout, QGridLayout):
            for row in range(layout.rowCount()):
                rect = QRect()
                for col in range(layout.columnCount()):
                    item = layout.itemAtPosition(row, col)
                    if item is None or item.isEmpty():
                        continue
                    widget = item.widget()
                    if widget is not None and widget.isHidden():
                        continue
                    rect = rect.united(item.geometry())
                if not rect.isNull():
                    rects.append(rect)
        elif isinstance(layout, QBoxLayout):
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item is None or item.isEmpty() or item.spacerItem() is not None:
                    continue
                widget = item.widget()
                if widget is not None and widget.isHidden():
                    continue
                rects.append(item.geometry())
        # rows may span several grid cells in arbitrary order
        rects.sort(key=lambda r: r.top())
        return rects

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(bounds, theme.RADIUS_SECTION, theme.RADIUS_SECTION)
        painter.fillPath(path, theme.section_color())
        painter.setPen(QPen(theme.section_border_color(), 1))
        painter.drawPath(path)

        if self._separators and self.layout() is not None:
            margins = self.layout().contentsMargins()
            pen = QPen(theme.separator_color(), 1)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            rows = self._row_rects()
            for previous, current in zip(rows, rows[1:]):
                if current.top() <= previous.bottom():
                    continue  # same visual row
                y = (previous.bottom() + current.top() + 1) // 2
                painter.drawLine(margins.left(), y, self.width() - margins.right(), y)
        painter.end()


def make_section_title(text: str, parent: Optional[QWidget] = None):
    from PyQt6.QtWidgets import QLabel

    label = QLabel(text, parent)
    theme.apply_text_style(label, 'headline')
    label.setContentsMargins(theme.SPACE_S, 0, 0, 0)
    return label


def add_sheet_header(layout, title: str, message: str = '') -> None:
    """Put a bold title (and an optional secondary message) on top of a dialog's layout."""
    from PyQt6.QtWidgets import QLabel

    labels = []
    title_label = QLabel(title)
    theme.apply_text_style(title_label, 'title3')
    labels.append(title_label)
    if message:
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        theme.apply_text_style(message_label, 'callout')
        theme.apply_text_role(message_label, 'secondary')
        labels.append(message_label)
    for index, label in enumerate(labels):
        layout.insertWidget(index, label)
    layout.insertSpacing(len(labels), theme.SPACE_S)


def make_footnote(text: str, parent: Optional[QWidget] = None):
    from PyQt6.QtWidgets import QLabel

    label = QLabel(text, parent)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.AutoText)
    theme.apply_text_style(label, 'subheadline')
    theme.apply_text_role(label, 'secondary')
    label.setContentsMargins(theme.SPACE_S, 0, theme.SPACE_S, 0)
    return label
