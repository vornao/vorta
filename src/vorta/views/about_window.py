from PyQt6.QtCore import QCoreApplication

from vorta.views.aux_window import AuxWindow


class AboutWindow(AuxWindow):
    """The About window. Content is provided by `AboutTab`."""

    def __init__(self, main_window):
        super().__init__(
            main_window, QCoreApplication.translate('MainWindow', 'About Vorta'), 460, 520, scrollable=False
        )
        self.setFixedSize(460, 520)
