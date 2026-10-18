import math
from typing import Optional

from PyQt6.QtCore import QPointF, QSize, Qt, QTimer
from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtWidgets import QLabel, QSizePolicy, QWidget

from vorta.views import theme


class ActivityIndicator(QWidget):
    """A spinning progress indicator like NSProgressIndicator's spinning style."""

    SPOKES = 8

    def __init__(self, parent: Optional[QWidget] = None, size: int = 16):
        super().__init__(parent)
        self._size = size
        self._step = 0
        self._timer = QTimer(self, interval=90)
        self._timer.timeout.connect(self._advance)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setVisible(False)

    def sizeHint(self) -> QSize:
        return QSize(self._size, self._size)

    def start(self):
        self.setVisible(True)
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        self._timer.stop()
        self.setVisible(False)

    def is_running(self) -> bool:
        return self._timer.isActive()

    def _advance(self):
        self._step = (self._step + 1) % self.SPOKES
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = min(self.width(), self.height()) / 2
        inner, outer = radius * 0.45, radius * 0.95
        color = theme.label_color()
        for i in range(self.SPOKES):
            age = (self._step - i) % self.SPOKES
            c = theme.with_alpha(color, max(0.15, 0.85 - age * 0.1))
            pen = QPen(c, max(1.5, radius * 0.22))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            angle = 2 * math.pi * i / self.SPOKES - math.pi / 2
            painter.drawLine(
                center + QPointF(math.cos(angle) * inner, math.sin(angle) * inner),
                center + QPointF(math.cos(angle) * outer, math.sin(angle) * outer),
            )
        painter.end()


class ElidedLabel(QLabel):
    """
    A one-line label that elides long text with "…" instead of growing the layout.

    `text()` still returns the full text; it is also shown as tooltip when elided.
    """

    def __init__(self, text: str = '', parent: Optional[QWidget] = None, mode=Qt.TextElideMode.ElideRight):
        super().__init__(parent)
        self._full_text = ''
        self._mode = mode
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:
        self._full_text = text or ''
        self._refresh()

    def text(self) -> str:
        return self._full_text

    def minimumSizeHint(self) -> QSize:
        return QSize(0, super().minimumSizeHint().height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self):
        single_line = ' '.join(self._full_text.split())
        elided = self.fontMetrics().elidedText(single_line, self._mode, max(0, self.width()))
        super().setText(elided)
        self.setToolTip(self._full_text if elided != single_line else '')
