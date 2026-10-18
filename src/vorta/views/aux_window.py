from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

from vorta.views import platform_macos, theme


class AuxWindow(QWidget):
    """
    A secondary top-level window (Settings, About) hosting a content slot.

    The window has no Qt parent so that releasing the main window's native window
    doesn't take it down; it follows the main window's lifetime instead.
    """

    def __init__(self, main_window: QWidget, title: str, width: int, height: int, scrollable: bool = True):
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle(title)
        self.setWindowIcon(main_window.windowIcon())
        self.resize(width, height)
        self.setMinimumWidth(width)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.contentSlot = QWidget()
        if scrollable:
            scroll = QScrollArea(self)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.viewport().setAutoFillBackground(False)
            scroll.setWidget(self.contentSlot)
            layout.addWidget(scroll)
        else:
            layout.addWidget(self.contentSlot)
        self.contentSlot.setContentsMargins(theme.SPACE_XL, theme.SPACE_L, theme.SPACE_XL, theme.SPACE_XL)

        QShortcut(QKeySequence.StandardKey.Close, self).activated.connect(self.close)
        main_window.destroyed.connect(self.deleteLater)

    def showEvent(self, event):
        super().showEvent(event)
        platform_macos.update_app_presence()

    def hideEvent(self, event):
        super().hideEvent(event)
        QTimer.singleShot(0, platform_macos.update_app_presence)

    def present(self):
        self.show()
        self.raise_()
        self.activateWindow()
