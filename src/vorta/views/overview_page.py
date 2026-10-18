from typing import Callable, Optional

from peewee import fn
from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from vorta.store.models import ArchiveModel, EventLogModel, SettingsModel, SourceFileModel
from vorta.utils import pretty_bytes
from vorta.views import theme
from vorta.views.base_tab import BaseTab
from vorta.views.formatting import next_backup_text, next_backup_tooltip, plural, relative_time
from vorta.views.icons import symbol_pixmap
from vorta.views.partials.activity_indicator import ElidedLabel
from vorta.views.partials.form_section import FormSection, make_section_title


def tr(text: str) -> str:
    return QCoreApplication.translate('OverviewPage', text)


class NavigationRow(QWidget):
    """A summary row: title on the left, value and chevron on the right; click to navigate."""

    def __init__(self, title: str, on_click: Optional[Callable[[], None]] = None, parent=None):
        super().__init__(parent)
        self._on_click = on_click
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SPACE_S)
        self.titleLabel = QLabel(title, self)
        self.valueLabel = ElidedLabel('', self, Qt.TextElideMode.ElideMiddle)
        self.valueLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        theme.apply_text_role(self.valueLabel, 'secondary')
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.valueLabel, 1)
        if on_click is not None:
            self.chevron = QLabel('›', self)
            theme.apply_text_role(self.chevron, 'tertiary')
            theme.apply_text_style(self.chevron, 'title3')
            layout.addWidget(self.chevron)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setValue(self, text: str) -> None:
        self.valueLabel.setText(text)

    def mouseReleaseEvent(self, event):
        if self._on_click is not None and event.button() == Qt.MouseButton.LeftButton:
            self._on_click()
        super().mouseReleaseEvent(event)


class OverviewPage(BaseTab, QWidget):
    """
    The landing page: is the profile protected, when was the last and when is the next
    backup, plus a summary of the repository, sources and latest archives.
    """

    def __init__(self, slot: QWidget, app=None, profile_provider=None, navigate=None, start_backup=None):
        super().__init__(parent=slot, profile_provider=profile_provider)
        self.app = app or self.app
        self._navigate = navigate or (lambda key: None)
        self._start_backup = start_backup
        self._running = False
        self._primary_action: Optional[Callable[[], None]] = None

        outer = QVBoxLayout(slot)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(slot)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.viewport().setAutoFillBackground(False)
        outer.addWidget(scroll)
        body = QWidget()
        body.setAutoFillBackground(False)
        scroll.setWidget(body)

        layout = QVBoxLayout(body)
        layout.setContentsMargins(theme.PAGE_MARGIN, theme.SPACE_S, theme.PAGE_MARGIN, theme.PAGE_MARGIN)
        layout.setSpacing(theme.SPACE_S)

        # --- status hero
        self.hero = FormSection(body)
        self.hero.setSeparators(False)
        hero_layout = QHBoxLayout(self.hero)
        hero_layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        hero_layout.setSpacing(theme.SPACE_L + 2)
        self.statusIcon = QLabel(self.hero)
        self.statusIcon.setFixedSize(52, 52)
        self.statusIcon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(self.statusIcon, 0, Qt.AlignmentFlag.AlignTop)
        text_column = QVBoxLayout()
        text_column.setSpacing(2)
        self.statusTitle = QLabel(self.hero)
        self.statusTitle.setWordWrap(True)
        theme.apply_text_style(self.statusTitle, 'title2')
        self.statusDetail = QLabel(self.hero)
        self.statusDetail.setWordWrap(True)
        theme.apply_text_role(self.statusDetail, 'secondary')
        self.nextBackupLabel = QLabel(self.hero)
        self.nextBackupLabel.setWordWrap(True)
        theme.apply_text_role(self.nextBackupLabel, 'secondary')
        text_column.addWidget(self.statusTitle)
        text_column.addWidget(self.statusDetail)
        text_column.addWidget(self.nextBackupLabel)
        text_column.addStretch(1)
        hero_layout.addLayout(text_column, 1)
        self.actionButton = QPushButton(self.hero)
        self.actionButton.clicked.connect(self._run_primary_action)
        hero_layout.addWidget(self.actionButton, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.hero)
        layout.addSpacing(theme.SPACE_M)

        # --- summary
        layout.addWidget(make_section_title(tr('Summary'), body))
        summary = FormSection(body)
        summary_layout = FormSection.configure_layout(QVBoxLayout(summary))
        self.repoRow = NavigationRow(tr('Repository'), lambda: self._navigate('repository'), summary)
        self.sourcesRow = NavigationRow(tr('Sources'), lambda: self._navigate('sources'), summary)
        self.scheduleRow = NavigationRow(tr('Schedule'), lambda: self._navigate('schedule'), summary)
        self.archivesRow = NavigationRow(tr('Archives'), lambda: self._navigate('archives'), summary)
        for row in (self.repoRow, self.sourcesRow, self.scheduleRow, self.archivesRow):
            summary_layout.addWidget(row)
        layout.addWidget(summary)
        layout.addSpacing(theme.SPACE_M)

        # --- repository statistics
        self.statsTitle = make_section_title(tr('Repository Size'), body)
        layout.addWidget(self.statsTitle)
        self.stats = FormSection(body)
        stats_layout = FormSection.configure_layout(QGridLayout(self.stats))
        self.statLabels = {}
        stats = [
            ('original', tr('Original Size')),
            ('deduplicated', tr('Deduplicated Size')),
            ('compressed', tr('Compressed Size')),
            ('encryption', tr('Encryption')),
        ]
        for row, (key, title) in enumerate(stats):
            stats_layout.addWidget(QLabel(title, self.stats), row, 0)
            value = QLabel(self.stats)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            theme.apply_text_role(value, 'secondary')
            stats_layout.addWidget(value, row, 1)
            self.statLabels[key] = value
        layout.addWidget(self.stats)
        layout.addSpacing(theme.SPACE_M)

        # --- latest archives
        latest_header = QHBoxLayout()
        self.latestTitle = make_section_title(tr('Latest Archives'), body)
        latest_header.addWidget(self.latestTitle)
        latest_header.addStretch(1)
        self.showAllButton = QPushButton(tr('Show All'), body)
        self.showAllButton.setFlat(True)
        self.showAllButton.setCursor(Qt.CursorShape.PointingHandCursor)
        theme.apply_text_role(self.showAllButton, 'accent')
        self.showAllButton.clicked.connect(lambda: self._navigate('archives'))
        latest_header.addWidget(self.showAllButton)
        layout.addLayout(latest_header)
        self.latest = FormSection(body)
        self.latestLayout = FormSection.configure_layout(QGridLayout(self.latest))
        self.latestLayout.setColumnStretch(0, 1)
        layout.addWidget(self.latest)
        layout.addStretch(1)

        for widget in (self.hero, summary, self.stats, self.latest):
            widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        self.track_profile_change(call_now=True)
        self.track_backup_finished()
        self.track_signal(self.app.scheduler.schedule_changed, lambda *_: self.populate_from_profile())
        self.track_signal(self.app.backup_progress_event, self._on_progress)
        self.track_palette_change(self.populate_from_profile)

    # --- state ------------------------------------------------------------------------------------------------------
    def set_running(self, running: bool) -> None:
        self._running = running
        self.populate_from_profile()

    def _on_progress(self, text: str) -> None:
        if self._running and text:
            self.statusDetail.setText(text)

    def _run_primary_action(self):
        if self._primary_action is not None:
            self._primary_action()

    def _set_status(self, icon: str, color, title: str, detail: str, action: str = '', callback=None):
        self.statusIcon.setPixmap(symbol_pixmap(icon, 44, color))
        self.statusTitle.setText(title)
        self.statusDetail.setText(detail)
        self.statusDetail.setVisible(bool(detail))
        self._primary_action = callback
        self.actionButton.setText(action)
        self.actionButton.setVisible(bool(action) and callback is not None)

    def _backup(self):
        if self._start_backup is not None:
            self._start_backup()
        else:
            self.app.create_backup_action()

    def populate_from_profile(self, *_args) -> None:
        profile = self.current_profile()
        if profile is None:
            return
        repo = profile.repo
        sources = SourceFileModel.select().where(SourceFileModel.profile == profile)
        source_count = sources.count()
        archives = list(repo.archives.select().order_by(ArchiveModel.time.desc()).limit(3)) if repo else []
        archive_count = repo.archives.count() if repo else 0
        last_event = (
            EventLogModel.select()
            .where((EventLogModel.profile == str(profile.id)) & (EventLogModel.subcommand == 'create'))
            .order_by(EventLogModel.start_time.desc())
            .first()
        )

        # --- hero
        next_text = next_backup_text(self.app.scheduler, profile.id)
        self.nextBackupLabel.setText(tr('Next backup: %1').replace('%1', next_text))
        self.nextBackupLabel.setToolTip(next_backup_tooltip(self.app.scheduler, profile.id))
        self.nextBackupLabel.setVisible(repo is not None and not self._running)
        if self._running:
            self._set_status(
                'status-running', theme.accent_color(), tr('Backing up…'), self.statusDetail.text() or profile.name
            )
        elif repo is None:
            self._set_status(
                'repository',
                theme.secondary_label_color(),
                tr('Set up a repository'),
                tr('Choose where your backups are stored: a folder, a disk or a server.'),
                tr('Set Up Repository…'),
                lambda: self._navigate('repository'),
            )
        elif source_count == 0:
            self._set_status(
                'sources',
                theme.secondary_label_color(),
                tr('Choose what to back up'),
                tr('Add the folders and files you want to keep safe.'),
                tr('Add Folders…'),
                lambda: self._navigate('sources'),
            )
        elif last_event is not None and last_event.returncode not in (0, 1, -1):
            self._set_status(
                'status-warning',
                theme.danger_color(),
                tr('The last backup failed'),
                relative_time(last_event.end_time or last_event.start_time).capitalize(),
                tr('Show Activity'),
                lambda: self._navigate('activity'),
            )
        elif archives:
            latest = archives[0]
            if last_event is not None and last_event.returncode == 1:
                icon, color, detail = 'status-warning', theme.warning_color(), tr('Finished with warnings')
            else:
                icon, color, detail = 'status-ok', theme.success_color(), ''
            self._set_status(
                icon,
                color,
                tr('Last backup %1').replace('%1', relative_time(latest.time)),
                detail,
            )
        else:
            self._set_status(
                'status-none',
                theme.secondary_label_color(),
                tr('No backups yet'),
                tr('Your first backup may take a while. Later backups only store what changed.'),
                tr('Back Up Now'),
                self._backup,
            )

        # --- summary
        self.repoRow.setValue((repo.name or repo.url) if repo else tr('Not set up'))
        total_size = sources.select(fn.SUM(SourceFileModel.dir_size)).scalar() or 0
        if source_count:
            self.sourcesRow.setValue(
                plural('%n item', '%n items', source_count) + (f' · {pretty_bytes(total_size)}' if total_size else '')
            )
        else:
            self.sourcesRow.setValue(tr('None'))
        self.scheduleRow.setValue(self._schedule_summary(profile))
        self.archivesRow.setValue(plural('%n archive', '%n archives', archive_count) if repo else '—')

        # --- statistics
        has_stats = repo is not None and repo.total_size is not None
        self.statsTitle.setVisible(has_stats)
        self.stats.setVisible(has_stats)
        if has_stats:
            na = QCoreApplication.translate('RepoTab', 'N/A', 'Not available.')
            self.statLabels['original'].setText(pretty_bytes(repo.total_size) if repo.total_size is not None else na)
            self.statLabels['deduplicated'].setText(
                pretty_bytes(repo.unique_size) if repo.unique_size is not None else na
            )
            self.statLabels['compressed'].setText(
                pretty_bytes(repo.unique_csize) if repo.unique_csize is not None else na
            )
            self.statLabels['encryption'].setText(str(repo.encryption or na))

        # --- latest archives
        while self.latestLayout.count():
            item = self.latestLayout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.latestTitle.setVisible(bool(archives))
        self.showAllButton.setVisible(bool(archives))
        self.latest.setVisible(bool(archives))
        use_fixed_units = bool(SettingsModel.get(key='enable_fixed_units').value)
        for row, archive in enumerate(archives):
            name = ElidedLabel(archive.name, self.latest, Qt.TextElideMode.ElideMiddle)
            when = QLabel(relative_time(archive.time), self.latest)
            theme.apply_text_role(when, 'secondary')
            size = QLabel(pretty_bytes(archive.size) if archive.size else '', self.latest)
            size.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            size.setMinimumWidth(70 if use_fixed_units else 60)
            theme.apply_text_role(size, 'secondary')
            self.latestLayout.addWidget(name, row, 0)
            self.latestLayout.addWidget(when, row, 1)
            self.latestLayout.addWidget(size, row, 2)
        self.latest.update()

    @staticmethod
    def _schedule_summary(profile) -> str:
        if profile.schedule_mode == 'interval':
            units = {
                'minutes': QCoreApplication.translate('SchedulePage', 'Minutes'),
                'hours': QCoreApplication.translate('SchedulePage', 'Hours'),
                'days': QCoreApplication.translate('SchedulePage', 'Days'),
                'weeks': QCoreApplication.translate('SchedulePage', 'Weeks'),
            }
            unit = units.get(profile.schedule_interval_unit, profile.schedule_interval_unit).lower()
            return tr('Every %1 %2').replace('%1', str(profile.schedule_interval_count)).replace('%2', unit)
        if profile.schedule_mode == 'fixed':
            return tr('Daily at %1').replace(
                '%1', f'{profile.schedule_fixed_hour:02d}:{profile.schedule_fixed_minute:02d}'
            )
        return QCoreApplication.translate('Form', 'Manual only')
