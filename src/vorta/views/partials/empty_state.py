from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from vorta.views import theme
from vorta.views.icons import symbol_pixmap


class EmptyState(QWidget):
    """Centred placeholder for an empty page: large symbol, title, message and actions."""

    def __init__(self, icon_name: str, title: str, message: str = '', parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._icon_name = icon_name
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_XXL, theme.SPACE_XXL, theme.SPACE_XXL, theme.SPACE_XXL)
        layout.setSpacing(theme.SPACE_S)
        layout.addStretch(1)

        self.iconLabel = QLabel(self)
        self.iconLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.iconLabel)
        layout.addSpacing(theme.SPACE_S)

        self.titleLabel = QLabel(title, self)
        self.titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        theme.apply_text_style(self.titleLabel, 'title2')
        layout.addWidget(self.titleLabel)

        self.messageLabel = QLabel(message, self)
        self.messageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.messageLabel.setWordWrap(True)
        self.messageLabel.setOpenExternalLinks(True)
        self.messageLabel.setVisible(bool(message))
        theme.apply_text_role(self.messageLabel, 'secondary')
        layout.addWidget(self.messageLabel)

        layout.addSpacing(theme.SPACE_M)
        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.setSpacing(theme.SPACE_S)
        self.buttonLayout.addStretch(1)
        self.buttonLayout.addStretch(1)
        layout.addLayout(self.buttonLayout)
        layout.addStretch(2)
        self._update_icon()

    def add_button(self, text: str, default: bool = False) -> QPushButton:
        button = QPushButton(text, self)
        button.setDefault(default)
        button.setAutoDefault(default)
        self.buttonLayout.insertWidget(self.buttonLayout.count() - 1, button)
        return button

    def _update_icon(self):
        self.iconLabel.setPixmap(symbol_pixmap(self._icon_name, 56, theme.tertiary_label_color()))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.PaletteChange:
            self._update_icon()
