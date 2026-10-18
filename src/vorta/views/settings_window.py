from PyQt6.QtCore import QCoreApplication

from vorta.views.aux_window import AuxWindow


class SettingsWindow(AuxWindow):
    """Global application settings (⌘,). Content is provided by `MiscTab`."""

    def __init__(self, main_window):
        super().__init__(main_window, QCoreApplication.translate('MainWindow', 'Settings'), 560, 620)
