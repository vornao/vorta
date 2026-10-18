import logging
import sys
from pathlib import Path

from PyQt6 import QtCore, uic
from PyQt6.QtCore import QEvent, QPoint, Qt, QTimer, QUrl
from PyQt6.QtCore import pyqtSignal as Signal
from PyQt6.QtGui import QAction, QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QMenu,
    QMessageBox,
    QToolTip,
)

from vorta import config
from vorta.profile_export import ImportFailedException, ProfileExport
from vorta.store.models import BackupProfileModel, SettingsModel
from vorta.utils import (
    borg_compat,
    get_asset,
    get_network_status_monitor,
    is_system_tray_available,
)
from vorta.views import platform_macos, theme
from vorta.views.about_window import AboutWindow
from vorta.views.activity_page import ActivityPage
from vorta.views.dialogs.profile.export_window import ExportWindow
from vorta.views.dialogs.profile.import_window import ImportWindow
from vorta.views.dialogs.profile.profile_add_edit import AddProfileWindow, EditProfileWindow
from vorta.views.overview_page import OverviewPage
from vorta.views.partials.loading_button import LoadingButton
from vorta.views.partials.sidebar import PAGE_ROLE
from vorta.views.settings_window import SettingsWindow
from vorta.views.utils import get_colored_icon, popup_menu

from .about_tab import AboutTab
from .archive_tab import ArchiveTab
from .misc_tab import MiscTab
from .repo_tab import RepoTab
from .schedule_tab import ScheduleTab
from .source_tab import SourceTab

uifile = get_asset('UI/main_window.ui')
MainWindowUI, MainWindowBase = uic.loadUiType(uifile)

logger = logging.getLogger(__name__)

__all__ = ['MainWindow', 'ArchiveTab']


class MainWindow(MainWindowBase, MainWindowUI):
    loaded = Signal()

    # page key -> index in pageStack
    PAGES = ['overview', 'sources', 'repository', 'schedule', 'archives', 'activity']

    def __init__(self, parent=None):
        super().__init__()
        self.app = parent
        theme.apply_theme(QApplication.instance())
        platform_macos.install_click_count_guard()  # Qt tray crash on macOS 27, see the function

        self._native_chrome = platform_macos.native_windows_available()
        if self._native_chrome:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea, False)
        self.setupUi(self)
        self.setWindowTitle('Vorta for Borg Backup')
        self.setWindowIcon(get_colored_icon("icon"))
        if sys.platform.startswith('linux'):
            self.app.setDesktopFileName('com.borgbase.Vorta')
        flags = (
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinMaxButtonsHint
        )
        if self._native_chrome:
            flags |= Qt.WindowType.NoTitleBarBackgroundHint | Qt.WindowType.WindowFullscreenButtonHint
        self.setWindowFlags(flags)
        self.chrome = platform_macos.WindowChrome(self)
        # Header: title and subtitle vertically centred in the toolbar area, next to the traffic lights
        self.titleLayout.insertStretch(0, 1)
        self.titleLayout.addStretch(1)
        self.headerLayout.setStretchFactor(self.titleLayout, 1)
        self.pageTitle.setMinimumWidth(120)
        for area in (self.repoScrollArea, self.scheduleScrollArea):
            area.viewport().setAutoFillBackground(False)

        self.createStartBtn = LoadingButton(self.tr("Back Up Now"))
        self.createStartBtn.setDefault(True)
        self.createStartBtn.setAutoDefault(False)
        self.createStartBtn.setToolTip(self.tr("Start a backup of the current profile now"))
        self.gridLayout.addWidget(self.createStartBtn, 0, 0, 1, 1)
        self.cancelButton.setToolTip(self.tr("Cancel the running task"))
        self.cancelButton.hide()

        # Use previous window state
        previous_window_width = SettingsModel.get(key='previous_window_width')
        previous_window_height = SettingsModel.get(key='previous_window_height')
        self.resize(
            max(int(previous_window_width.str_value), self.minimumWidth()),
            max(int(previous_window_height.str_value), self.minimumHeight()),
        )

        # Select previously used profile, if available
        prev_profile_id = SettingsModel.get(key='previous_profile_id')
        self.current_profile = BackupProfileModel.get_or_none(id=prev_profile_id.str_value)
        if self.current_profile is None:
            profiles = BackupProfileModel.select()
            self.current_profile = min(profiles, key=lambda p: (p.name.casefold(), p.name))

        # Secondary windows host the global settings and the about page
        self.settingsWindow = SettingsWindow(self)
        self.aboutWindow = AboutWindow(self)

        # Load tab models
        self.repoTab = RepoTab(self.repoTabSlot, profile_provider=self.get_current_profile)
        self.sourceTab = SourceTab(self.sourceTabSlot, profile_provider=self.get_current_profile)
        self.archiveTab = ArchiveTab(self.archiveTabSlot, app=self.app, profile_provider=self.get_current_profile)
        self.scheduleTab = ScheduleTab(self.scheduleTabSlot, profile_provider=self.get_current_profile)
        self.miscTab = MiscTab(self.settingsWindow.contentSlot, profile_provider=self.get_current_profile)
        self.aboutTab = AboutTab(self.aboutWindow.contentSlot, profile_provider=self.get_current_profile)
        self.aboutTab.set_borg_details(borg_compat.version, borg_compat.path)
        self.scheduleTab.add_retention_page(self.archiveTab.retentionPage)
        self.activityPage = ActivityPage(
            self.activityTabSlot, self.scheduleTab.jobsPage, self.scheduleTab.logPage, open_logs=self.open_log_folder
        )
        self.overviewPage = OverviewPage(
            self.overviewTabSlot,
            app=self.app,
            profile_provider=self.get_current_profile,
            navigate=self.show_page,
            start_backup=lambda: self.createStartBtn.click(),
        )

        self.repoTab.repo_changed.connect(self.archiveTab.populate_from_profile)
        self.repoTab.repo_changed.connect(self.scheduleTab.schedulePage.populate_from_profile)
        self.repoTab.repo_changed.connect(self.overviewPage.populate_from_profile)
        self.repoTab.repo_changed.connect(self.update_header)
        self.repoTab.repo_added.connect(self.archiveTab.refresh_archive_list)
        self.miscTab.refresh_archive.connect(self.archiveTab.populate_from_profile)

        self.createStartBtn.clicked.connect(self.app.create_backup_action)
        self.cancelButton.clicked.connect(self.app.backup_cancelled_event.emit)

        self.app.backup_started_event.connect(self.backup_started_event)
        self.app.backup_finished_event.connect(self.backup_finished_event)
        self.app.backup_log_event.connect(self.set_log)
        self.app.backup_progress_event.connect(self.set_progress)
        self.app.backup_cancelled_event.connect(self.backup_cancelled_event)
        self.app.profile_changed_event.connect(self.update_header)

        # Sidebar navigation
        self.sidebar.add_page('overview', self.tr('Overview'), 'overview')
        self.sidebar.add_header(self.tr('Backup'))
        self.sidebar.add_page('sources', self.tr('Sources'), 'sources')
        self.sidebar.add_page('repository', self.tr('Repository'), 'repository')
        self.sidebar.add_page('schedule', self.tr('Schedule'), 'schedule')
        self.sidebar.add_header(self.tr('History'))
        self.sidebar.add_page('archives', self.tr('Archives'), 'archives')
        self.sidebar.add_page('activity', self.tr('Activity'), 'activity')
        self.sidebar.page_selected.connect(self.show_page)
        self.headerActionsLayout.addWidget(self.archiveTab.bList)
        self._header_actions = {'archives': [self.archiveTab.bList]}

        # Actions shared by the menu bar and the profile menu
        self._create_actions()
        self.profileMenuButton.clicked.connect(lambda: popup_menu(self.profileMenuButton, self.profileMenu))
        self.miscButton.clicked.connect(self.show_settings)
        if platform_macos.IS_MACOS:
            self.miscButton.hide()  # Settings lives in the app menu (⌘,)
        self._create_menu_bar()

        # Init profile list
        self.populate_profile_selector()
        self.profileSelector.currentIndexChanged.connect(self.profile_selection_changed_action)

        # OS-specific startup options:
        if not get_network_status_monitor().is_network_status_available():
            # Hide Wifi-rule section in schedule tab.
            self.scheduleTab.networksPage.wifiListLabel.hide()
            self.scheduleTab.networksPage.wifiListWidget.hide()
            self.scheduleTab.hide_networks()

        # Connect to existing thread.
        if self.app.jobs_manager.is_worker_running():
            self._toggle_buttons(create_enabled=False)

        # Connect to palette change
        self._palette_connection = QApplication.instance().paletteChanged.connect(lambda p: self.set_icons())
        self.destroyed.connect(self._on_destroyed)

        self.show_page('overview')
        self.set_icons()
        self.loaded.emit()

    # --- actions & menus -------------------------------------------------------------------------------------------
    def _action(self, text, slot, shortcut=None, role=None, icon=None):
        action = QAction(text, self)
        action.triggered.connect(slot)
        if shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
        if role is not None:
            action.setMenuRole(role)
        if icon is not None:
            action.setIcon(get_colored_icon(icon))
            action.setIconVisibleInMenu(False)
        return action

    def _create_actions(self):
        self.backupAction = self._action(self.tr('Back Up Now'), lambda: self.createStartBtn.click(), 'Ctrl+B')
        self.cancelAction = self._action(
            self.tr('Cancel'), lambda: self.cancelButton.click(), QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Period)
        )
        self.cancelAction.setEnabled(False)
        self.profileAddAction = self._action(
            self.tr("Create new profile"), self.profile_add_action, 'Ctrl+N', icon='plus'
        )
        self.profileImportAction = self._action(self.tr("Import from file…"), self.profile_import_action)
        self.profileRenameAction = self._action(self.tr('Rename Profile…'), self.profile_rename_action, icon='edit')
        self.profileExportAction = self._action(self.tr('Export Profile…'), self.profile_export_action)
        self.profileDeleteAction = self._action(self.tr('Delete Profile…'), self.profile_delete_action, icon='trash')
        self.settingsAction = self._action(
            self.tr('Settings…'),
            self.show_settings,
            QKeySequence.StandardKey.Preferences,
            QAction.MenuRole.PreferencesRole,
        )
        self.aboutAction = self._action(self.tr('About Vorta'), self.show_about, role=QAction.MenuRole.AboutRole)
        self.closeAction = self._action(self.tr('Close Window'), self.on_close_window, QKeySequence.StandardKey.Close)
        self.pageActions = []
        for number, key in enumerate(self.PAGES, start=1):
            item = self._sidebar_item(key)
            text = item.text() if item is not None else key.title()
            self.pageActions.append(self._action(text, lambda _=False, k=key: self.show_page(k), f'Ctrl+{number}'))

        self.profileMenu = QMenu(self)
        for action in (self.profileAddAction, self.profileImportAction):
            self.profileMenu.addAction(action)
        self.profileMenu.addSeparator()
        for action in (self.profileRenameAction, self.profileExportAction, self.profileDeleteAction):
            self.profileMenu.addAction(action)

    def _create_menu_bar(self):
        if not platform_macos.IS_MACOS:
            # No menu bar on Linux; keep the keyboard shortcuts on the window.
            for action in (self.backupAction, self.cancelAction, self.profileAddAction, self.settingsAction):
                self.addAction(action)
            self.addActions(self.pageActions)
            QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(self.on_close_window)
            QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.on_close_window)
            return

        menu_bar = self.menuBar()
        quit_action = self._action(self.tr('Quit Vorta'), self.app.quit, QKeySequence.StandardKey.Quit)
        quit_action.setMenuRole(QAction.MenuRole.QuitRole)

        file_menu = menu_bar.addMenu(self.tr('File'))
        file_menu.addAction(self.backupAction)
        file_menu.addAction(self.cancelAction)
        file_menu.addSeparator()
        file_menu.addAction(self.profileAddAction)
        file_menu.addAction(self.profileImportAction)
        file_menu.addAction(self.profileExportAction)
        file_menu.addSeparator()
        file_menu.addAction(self.closeAction)
        file_menu.addAction(self.settingsAction)
        file_menu.addAction(self.aboutAction)
        file_menu.addAction(quit_action)

        view_menu = menu_bar.addMenu(self.tr('View'))
        view_menu.addActions(self.pageActions)

        help_menu = menu_bar.addMenu(self.tr('Help'))
        help_menu.addAction(
            self._action(self.tr('Vorta Help'), lambda: QDesktopServices.openUrl(QUrl('https://vorta.borgbase.com/')))
        )
        help_menu.addAction(
            self._action(
                self.tr('Report a Bug…'),
                lambda: QDesktopServices.openUrl(QUrl('https://github.com/borgbase/vorta/issues/new/choose')),
            )
        )
        help_menu.addAction(self._action(self.tr('View the logs'), self.open_log_folder))

    def _sidebar_item(self, key):
        for row in range(self.sidebar.count()):
            item = self.sidebar.item(row)
            if item.data(PAGE_ROLE) == key:
                return item
        return None

    # --- navigation ------------------------------------------------------------------------------------------------
    def show_page(self, key: str) -> None:
        index = self.PAGES.index(key)
        if self.pageStack.currentIndex() != index:
            self.pageStack.setCurrentIndex(index)
        if self.sidebar.current_page() != key:
            self.sidebar.select_page(key)
        for page, widgets in self._header_actions.items():
            for widget in widgets:
                widget.setVisible(page == key)
        self.update_header()

    def current_page(self) -> str:
        return self.PAGES[self.pageStack.currentIndex()]

    def update_header(self, *_args) -> None:
        key = self.current_page()
        item = self._sidebar_item(key)
        self.pageTitle.setText(item.text() if item is not None else '')
        profile = self.current_profile
        subtitle = profile.name if profile is not None else ''
        if key in ('repository', 'archives'):
            repo = BackupProfileModel.get(id=profile.id).repo
            if repo is not None:
                subtitle = repo.name or repo.url
        self.pageSubtitle.setText(subtitle)

    def show_settings(self):
        self.settingsWindow.present()

    def show_about(self):
        self.aboutWindow.present()

    def open_log_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(config.LOG_DIR)))

    # Kept for compatibility: Settings and About used to replace the tabs in place.
    def toggle_misc_visibility(self):
        self.show_settings()

    def on_close_window(self):
        self.close()

    def get_current_profile(self):
        return BackupProfileModel.get(id=self.current_profile.id)

    def set_icons(self):
        self.profileMenuButton.setIcon(get_colored_icon('more'))
        self.miscButton.setIcon(get_colored_icon('settings_wheel'))
        self.chrome.set_background(theme.window_color())
        self.sidebar.viewport().update()

    def _on_destroyed(self):
        try:
            QApplication.instance().paletteChanged.disconnect(self._palette_connection)
        except (TypeError, RuntimeError):
            pass

    # --- status ----------------------------------------------------------------------------------------------------
    def set_progress(self, text=''):
        self.progressText.setText(text)
        self.progressText.repaint()

    def set_log(self, text='', context=None):
        # Truncate very long messages to keep the status area readable
        if text and len(text) > 300:
            text = text[:300] + '...'
        self.logText.setText(text)
        self.logText.repaint()

    def _toggle_buttons(self, create_enabled=True):
        if create_enabled:
            self.createStartBtn.stop()
            self.activityIndicator.stop()
        else:
            self.createStartBtn.start()
            self.activityIndicator.start()
        self.createStartBtn.setEnabled(create_enabled)
        self.createStartBtn.setVisible(create_enabled)
        self.cancelButton.setEnabled(not create_enabled)
        self.cancelButton.setVisible(not create_enabled)
        self.backupAction.setEnabled(create_enabled)
        self.cancelAction.setEnabled(not create_enabled)
        self.overviewPage.set_running(not create_enabled)

    # --- profiles --------------------------------------------------------------------------------------------------
    def populate_profile_selector(self):
        self.profileSelector.blockSignals(True)
        try:
            self.profileSelector.clear()
            profiles = BackupProfileModel.select()
            for profile in sorted(profiles, key=lambda p: (p.name.casefold(), p.name)):
                self.profileSelector.addItem(get_colored_icon('profile'), profile.name, profile.id)
            index = self.profileSelector.findData(self.current_profile.id)
            if index >= 0:
                self.profileSelector.setCurrentIndex(index)
        finally:
            self.profileSelector.blockSignals(False)
        self.profileDeleteAction.setEnabled(self.profileSelector.count() > 1)

    def profile_selection_changed_action(self, index=None):
        backup_profile_id = self.profileSelector.currentData()
        if not backup_profile_id:
            return

        self.current_profile = BackupProfileModel.get(id=backup_profile_id)
        SettingsModel.update({SettingsModel.str_value: self.current_profile.id}).where(
            SettingsModel.key == 'previous_profile_id'
        ).execute()

        self.app.profile_changed_event.emit()

    def profile_rename_action(self):
        backup_profile_id = self.profileSelector.currentData()
        window = EditProfileWindow(rename_existing_id=backup_profile_id)
        self.window = window  # For tests
        window.setParent(self, QtCore.Qt.WindowType.Sheet)
        window.open()
        window.profile_changed.connect(self.profile_add_edit_result)

    def profile_delete_action(self):
        if self.profileSelector.count() > 1:
            to_delete_id = self.profileSelector.currentData()
            to_delete = BackupProfileModel.get(id=to_delete_id)

            msg = self.tr("Are you sure you want to delete profile '{}'?").format(to_delete.name)
            reply = QMessageBox.question(
                self,
                self.tr("Confirm deletion"),
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.app.scheduler.clear_pause(to_delete_id)  # Drop a pause the deleted id could outlive
                to_delete.delete_instance(recursive=True)
                self.app.scheduler.remove_job(to_delete_id)  # Remove pending jobs
                self.profileSelector.blockSignals(True)
                self.profileSelector.removeItem(self.profileSelector.currentIndex())
                self.profileSelector.blockSignals(False)
                self.profileDeleteAction.setEnabled(self.profileSelector.count() > 1)
                self.profile_selection_changed_action()

        else:
            warn = self.tr("Cannot delete the last profile.")
            point = QPoint(0, int(self.profileMenuButton.size().height() / 2))
            QToolTip.showText(self.profileMenuButton.mapToGlobal(point), warn)

    def profile_add_action(self):
        window = AddProfileWindow()
        self.window = window  # For tests
        window.setParent(self, QtCore.Qt.WindowType.Sheet)
        window.open()
        window.profile_changed.connect(self.profile_add_edit_result)

    def profile_export_action(self):
        """
        React to pressing "Export Profile" button and save current
        profile as .json file.
        """
        window = ExportWindow(profile=self.current_profile.refresh())
        self.window = window
        window.setParent(self, QtCore.Qt.WindowType.Sheet)
        window.show()

    def profile_import_action(self):
        """
        React to "Import Profile". Ask to select a .json file and import it as
        new profile.
        """

        def profile_imported_event(profile):
            QMessageBox.information(
                None,
                self.tr('Profile import successful!'),
                self.tr('Profile {} imported.').format(profile.name),
            )
            self.populate_profile_selector()
            self.app.profile_changed_event.emit()

        filename = QFileDialog.getOpenFileName(
            self,
            self.tr("Load profile"),
            str(Path.home()),
            self.tr("JSON (*.json);;All files (*)"),
        )[0]
        if filename:
            try:
                profile_export = ProfileExport.from_json(filename)
            except ImportFailedException as exception:
                QMessageBox.critical(None, self.tr('Failed to import profile'), str(exception))
                return
            window = ImportWindow(profile_export=profile_export)
            self.window = window
            window.setParent(self, QtCore.Qt.WindowType.Sheet)
            window.profile_imported.connect(profile_imported_event)
            window.show()

    def profile_add_edit_result(self, profile_name, profile_id):
        changed = profile_id != self.current_profile.id
        self.current_profile = BackupProfileModel.get(id=profile_id)
        self.populate_profile_selector()
        if changed:
            self.profile_selection_changed_action()
        else:
            self.update_header()

    # --- backup events ---------------------------------------------------------------------------------------------
    def backup_started_event(self):
        self._toggle_buttons(create_enabled=False)
        self.archiveTab._toggle_all_buttons(enabled=False)
        self.set_log('')

    def backup_finished_event(self):
        if not self.app.jobs_manager.is_worker_running() and (
            self.archiveTab.remaining_refresh_archives == 0 or self.archiveTab.remaining_refresh_archives == 1
        ):  # Either the refresh is done or this is the last archive to refresh.
            self._toggle_buttons(create_enabled=True)
            self.archiveTab._toggle_all_buttons(enabled=True)

    def backup_cancelled_event(self):
        self._toggle_buttons(create_enabled=True)
        self.set_log(self.tr('Task cancelled'))

    # --- window lifecycle ------------------------------------------------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        platform_macos.update_app_presence()
        if self._native_chrome and not self.chrome.installed:
            QTimer.singleShot(0, self._install_chrome)

    def _install_chrome(self):
        installed = self.chrome.install()
        self.sidebarPane.set_native_backdrop(installed)
        if installed:
            self.chrome.set_background(theme.window_color())
            self._sync_sidebar_backdrop()

    def _sync_sidebar_backdrop(self):
        if self.chrome.installed:
            rect = self.sidebarPane.geometry() if self.sidebarPane.isVisible() else None
            self.chrome.set_sidebar_rect(rect)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.chrome.ensure()
        self._sync_sidebar_backdrop()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.WindowStateChange, QEvent.Type.ActivationChange):
            self.chrome.ensure()

    def closeEvent(self, event):
        # Save window state in SettingsModel
        SettingsModel.update({SettingsModel.str_value: str(self.width())}).where(
            SettingsModel.key == 'previous_window_width'
        ).execute()
        SettingsModel.update({SettingsModel.str_value: str(self.height())}).where(
            SettingsModel.key == 'previous_window_height'
        ).execute()

        if not is_system_tray_available():
            if SettingsModel.get(key="enable_background_question").value:
                msg = QMessageBox()
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.setParent(self, QtCore.Qt.WindowType.Sheet)
                msg.setText(self.tr("Should Vorta continue to run in the background?"))
                msg.button(QMessageBox.StandardButton.Yes).clicked.connect(
                    lambda: self.miscTab.save_setting("disable_background_state", True)
                )
                msg.button(QMessageBox.StandardButton.No).clicked.connect(
                    lambda: (
                        self.miscTab.save_setting("disable_background_state", False),
                        self.app.quit(),
                    )
                )
                msg.setWindowTitle(self.tr("Quit"))
                dont_show_box = QCheckBox(self.tr("Don't show this again"))
                dont_show_box.clicked.connect(lambda x: self.miscTab.save_setting("enable_background_question", not x))
                dont_show_box.setTristate(False)
                msg.setCheckBox(dont_show_box)
                msg.exec()
            elif not SettingsModel.get(key="disable_background_state").value:
                self.app.quit()
        event.accept()
        # Closing only hides the window: Qt keeps the native window and its backing store
        # (~28 MB on a Retina display) alive while Vorta sits in the tray. Release them once
        # the close has gone through (Qt hides the widget after this handler returns).
        QTimer.singleShot(0, self._release_native_window)

    def _release_native_window(self):
        if not self.isVisible():
            platform_macos.update_app_presence()
            self.chrome.remove()
            self.sidebarPane.set_native_backdrop(False)
            self.destroy()  # show() creates the native window again
