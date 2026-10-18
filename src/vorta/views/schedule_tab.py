from PyQt6 import uic
from PyQt6.QtWidgets import QWidget

from vorta.utils import get_asset
from vorta.views.base_tab import BaseTab
from vorta.views.jobs_page import JobsPage
from vorta.views.log_page import LogPage
from vorta.views.networks_page import NetworksPage
from vorta.views.schedule_page import SchedulePage
from vorta.views.shell_commands_page import ShellCommandsPage

uifile = get_asset('UI/schedule_tab.ui')
ScheduleUI, ScheduleBase = uic.loadUiType(uifile)


class ScheduleTab(BaseTab, ScheduleBase, ScheduleUI):
    """
    The Schedule page: when backups run and what happens around them.

    It also owns the Log and Jobs pages, which the main window shows on the Activity page.
    """

    def __init__(self, parent=None, profile_provider=None):
        super().__init__(parent=parent, profile_provider=profile_provider)
        self.setupUi(parent)
        self.init_log_page()
        self.init_shell_commands_page()
        self.init_networks_page()
        self.init_schedule_page()
        self.init_jobs_page()
        self.track_backup_finished(self.logPage.populate_logs)

    def init_log_page(self):
        self.logPage = LogPage(self, profile_provider=self.profile)

    def init_shell_commands_page(self):
        self.shellCommandsPage = ShellCommandsPage(self, profile_provider=self.profile)
        self.shellCommandsLayout.addWidget(self.shellCommandsPage)
        self.shellCommandsPage.show()

    def init_networks_page(self):
        self.networksPage = NetworksPage(self, profile_provider=self.profile)
        self.networksLayout.addWidget(self.networksPage)
        self.networksPage.show()

    def init_schedule_page(self):
        self.schedulePage = SchedulePage(self, profile_provider=self.profile)
        self.scheduleLayout.addWidget(self.schedulePage)
        self.schedulePage.show()

    def init_jobs_page(self):
        self.jobsPage = JobsPage(self, profile_provider=self.profile)

    def add_retention_page(self, page: QWidget) -> None:
        """Place the prune and archive naming settings (owned by the archive tab) on this page."""
        self.retentionLayout.addWidget(page)
        page.show()

    def hide_networks(self) -> None:
        for widget in (self.networksTitle, self.networksSection):
            widget.hide()
