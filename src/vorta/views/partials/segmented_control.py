from typing import List, Optional

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPainterPath
from PyQt6.QtWidgets import QSizePolicy, QWidget

from vorta.views import theme


class SegmentedControl(QWidget):
    """
    A segmented control like NSSegmentedControl (select one).

    QTabBar would draw similarly, but on macOS it reconfigures the window's titlebar
    (content border area), which breaks the full-size content window chrome.
    """

    currentChanged = pyqtSignal(int)

    PADDING = 14
    HEIGHT = 24

    def __init__(self, labels: Optional[List[str]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._labels: List[str] = list(labels or [])
        self._current = 0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def addSegment(self, label: str) -> int:
        self._labels.append(label)
        self.updateGeometry()
        self.update()
        return len(self._labels) - 1

    def count(self) -> int:
        return len(self._labels)

    def currentIndex(self) -> int:
        return self._current

    def setCurrentIndex(self, index: int) -> None:
        if 0 <= index < len(self._labels) and index != self._current:
            self._current = index
            self.update()
            self.currentChanged.emit(index)

    def _segment_width(self) -> int:
        fm = self.fontMetrics()
        widest = max((fm.horizontalAdvance(label) for label in self._labels), default=40)
        return widest + 2 * self.PADDING

    def sizeHint(self) -> QSize:
        return QSize(self._segment_width() * max(1, len(self._labels)) + 4, self.HEIGHT)

    def _segment_at(self, x: float) -> int:
        width = self.width() / max(1, len(self._labels))
        return min(len(self._labels) - 1, max(0, int(x // width)))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCurrentIndex(self._segment_at(event.position().x()))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Left:
            self.setCurrentIndex(self._current - 1)
        elif event.key() == Qt.Key.Key_Right:
            self.setCurrentIndex(self._current + 1)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = bounds.height() / 2
        track = QPainterPath()
        track.addRoundedRect(bounds, radius, radius)
        painter.fillPath(track, theme.with_alpha(theme.label_color(), 0.08 if theme.is_dark() else 0.06))

        count = max(1, len(self._labels))
        width = bounds.width() / count
        thumb = QRectF(bounds.left() + width * self._current, bounds.top(), width, bounds.height()).adjusted(
            2, 2, -2, -2
        )
        thumb_path = QPainterPath()
        thumb_path.addRoundedRect(thumb, thumb.height() / 2, thumb.height() / 2)
        thumb_color = (
            theme.mix(theme.window_color(), theme.label_color(), 0.22) if theme.is_dark() else theme.section_color()
        )
        painter.fillPath(thumb_path, thumb_color)
        if not theme.is_dark():
            painter.setPen(theme.section_border_color())
            painter.drawPath(thumb_path)

        for index, label in enumerate(self._labels):
            rect = QRectF(bounds.left() + width * index, bounds.top(), width, bounds.height())
            font = theme.font('callout')
            if index == self._current:
                font.setWeight(font.Weight.DemiBold)
            painter.setFont(font)
            painter.setPen(theme.label_color() if index == self._current else theme.secondary_label_color())
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

        if self.hasFocus():
            ring = QPainterPath()
            ring.addRoundedRect(bounds.adjusted(-1, -1, 1, 1), radius + 1, radius + 1)
            painter.setPen(theme.with_alpha(theme.accent_color(), 0.6))
            painter.drawPath(ring)
        painter.end()
