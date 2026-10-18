from typing import Callable

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from vorta.views import theme
from vorta.views.partials.segmented_control import SegmentedControl


def tr(text: str) -> str:
    return QCoreApplication.translate('ActivityPage', text)


class ActivityPage:
    """Jobs and the event log, switched with a segmented control."""

    def __init__(self, slot: QWidget, jobs_page: QWidget, log_page: QWidget, open_logs: Callable[[], None]):
        self.slot = slot
        layout = QVBoxLayout(slot)
        layout.setContentsMargins(theme.PAGE_MARGIN, theme.SPACE_S, theme.PAGE_MARGIN, theme.PAGE_MARGIN)
        layout.setSpacing(theme.SPACE_M)

        bar = QHBoxLayout()
        bar.addStretch(1)
        self.segments = SegmentedControl(
            [QCoreApplication.translate('Form', 'Jobs'), QCoreApplication.translate('Form', 'Log')], slot
        )
        bar.addWidget(self.segments)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.stack = QStackedWidget(slot)
        self.stack.addWidget(jobs_page)
        self.stack.addWidget(log_page)
        layout.addWidget(self.stack, 1)
        self.segments.currentChanged.connect(self.stack.setCurrentIndex)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.openLogsButton = QPushButton(tr('Open Log Folder'), slot)
        self.openLogsButton.clicked.connect(open_logs)
        footer.addWidget(self.openLogsButton, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(footer)
