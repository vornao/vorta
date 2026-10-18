from typing import Optional

from PyQt6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QVariantAnimation
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QCheckBox, QSizePolicy, QWidget

from vorta.views import theme


class Switch(QCheckBox):
    """
    A toggle switch drawn like NSSwitch.

    It is a QCheckBox, so existing code (checkState, stateChanged, toggled, text)
    keeps working. The label is drawn on the left, the switch on the right; an
    optional secondary description wraps under the label. The whole row is clickable.
    """

    TRACK_WIDTH = 34
    TRACK_HEIGHT = 20
    GAP = 16

    def __init__(self, text: str = '', parent: Optional[QWidget] = None, description: str = ''):
        super().__init__(text, parent)
        self._description = description
        self._position = 1.0 if self.isChecked() else 0.0
        self._animation = QVariantAnimation(self, duration=140, easingCurve=QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._set_position)
        self.toggled.connect(self._animate)
        self.setTristate(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # --- API -------------------------------------------------------------------------------------------------------
    def setDescription(self, text: str) -> None:
        self._description = text
        self.updateGeometry()
        self.update()

    def description(self) -> str:
        return self._description

    # --- geometry --------------------------------------------------------------------------------------------------
    def _text_width(self, total_width: int) -> int:
        return max(40, total_width - self.TRACK_WIDTH - self.GAP)

    def _description_font(self):
        return theme.font('subheadline')

    def _description_height(self, width: int) -> int:
        if not self._description:
            return 0
        fm = QFontMetrics(self._description_font())
        rect = fm.boundingRect(0, 0, self._text_width(width), 10000, Qt.TextFlag.TextWordWrap, self._description)
        return rect.height() + 2

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        text_width = fm.horizontalAdvance(self.text())
        width = text_width + self.GAP + self.TRACK_WIDTH
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:
        return QSize(self.TRACK_WIDTH + self.GAP + 60, self.TRACK_HEIGHT)

    def hasHeightForWidth(self) -> bool:
        return bool(self._description)

    def heightForWidth(self, width: int) -> int:
        text_height = self.fontMetrics().height() + self._description_height(width)
        return max(self.TRACK_HEIGHT + 2, text_height + 2)

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    # --- painting --------------------------------------------------------------------------------------------------
    def _set_position(self, value):
        self._position = float(value)
        self.update()

    def _animate(self, checked: bool):
        self._animation.stop()
        if not self.isVisible():
            self._set_position(1.0 if checked else 0.0)
            return
        self._animation.setStartValue(self._position)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        enabled = self.isEnabled()
        if not enabled:
            painter.setOpacity(0.45)

        # label + description
        text_width = self._text_width(self.width())
        fm = self.fontMetrics()
        text_height = fm.height() + self._description_height(self.width())
        top = max(0, (self.height() - text_height) // 2)
        painter.setPen(theme.label_color())
        painter.setFont(self.font())
        label = fm.elidedText(self.text(), Qt.TextElideMode.ElideRight, text_width)
        painter.drawText(
            0, top, text_width, fm.height(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label
        )
        if self._description:
            painter.setFont(self._description_font())
            painter.setPen(theme.secondary_label_color())
            painter.drawText(
                QRectF(0, top + fm.height() + 2, text_width, self.height()),
                Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                self._description,
            )

        # track
        track = QRectF(
            self.width() - self.TRACK_WIDTH - 1,
            (self.height() - self.TRACK_HEIGHT) / 2,
            self.TRACK_WIDTH,
            self.TRACK_HEIGHT,
        )
        off = theme.with_alpha(theme.label_color(), 0.16 if theme.is_dark() else 0.1)
        on = theme.accent_color()
        fill = theme.mix(off, on, self._position) if self._position > 0 else off
        path = QPainterPath()
        path.addRoundedRect(track, track.height() / 2, track.height() / 2)
        painter.fillPath(path, fill)
        if self._position < 1:
            painter.setPen(QPen(theme.with_alpha(theme.label_color(), 0.08 * (1 - self._position)), 1))
            painter.drawPath(path)

        # knob
        margin = 2.0
        diameter = track.height() - 2 * margin
        x = track.left() + margin + (track.width() - diameter - 2 * margin) * self._position
        knob = QRectF(x, track.top() + margin, diameter, diameter)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 40))
        painter.drawEllipse(knob.translated(QPointF(0, 0.6)))
        painter.setBrush(QColor('white'))
        painter.drawEllipse(knob)

        if self.hasFocus() and self.focusPolicy() != Qt.FocusPolicy.NoFocus:
            ring = QPainterPath()
            ring_rect = track.adjusted(-2.5, -2.5, 2.5, 2.5)
            ring.addRoundedRect(ring_rect, ring_rect.height() / 2, ring_rect.height() / 2)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(theme.with_alpha(theme.accent_color(), 0.5), 3))
            painter.drawPath(ring)
        painter.end()
