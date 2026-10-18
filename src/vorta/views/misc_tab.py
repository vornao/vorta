from PyQt6 import QtCore, uic
from PyQt6.QtWidgets import QVBoxLayout

from vorta.i18n import translate
from vorta.store.models import SettingsModel
from vorta.store.settings import get_grouped_checkbox_settings
from vorta.utils import get_asset
from vorta.views import theme
from vorta.views.base_tab import BaseTab
from vorta.views.partials.form_section import FormSection, make_section_title
from vorta.views.partials.switch import Switch

uifile = get_asset('UI/misc_tab.ui')
MiscTabUI, MiscTabBase = uic.loadUiType(uifile)


class MiscTab(BaseTab, MiscTabBase, MiscTabUI):
    refresh_archive = QtCore.pyqtSignal()

    def __init__(self, parent=None, profile_provider=None):
        """Init."""
        super().__init__(parent=parent, profile_provider=profile_provider)
        self.setupUi(parent)

        self.checkboxLayout = QVBoxLayout(self.frameSettings)
        self.checkboxLayout.setSpacing(theme.SPACE_S)
        self.checkboxLayout.setContentsMargins(0, 0, 0, 0)
        self.switches = []

        self.populate()

    def populate(self):
        """
        Populate the settings view with one grouped section per settings group.

        Groups and per-group settings come from `get_grouped_checkbox_settings()`,
        which already filters out platform-irrelevant groups and legacy DB rows.
        """
        # clear layout
        while self.checkboxLayout.count():
            child = self.checkboxLayout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.switches = []

        for index, (group_name, settings) in enumerate(get_grouped_checkbox_settings()):
            if index > 0:
                self.checkboxLayout.addSpacing(theme.SPACE_M)
            self.checkboxLayout.addWidget(make_section_title(translate('settings', group_name), self.frameSettings))

            section = FormSection(self.frameSettings)
            rows = FormSection.configure_layout(QVBoxLayout(section))
            for setting in settings:
                description = translate('settings', setting.tooltip) if setting.tooltip else ''
                switch = Switch(translate('settings', setting.label), section, description=description)
                switch.setChecked(bool(setting.value))
                switch.stateChanged.connect(lambda v, key=setting.key: self.save_setting(key, v))
                if setting.key == 'enable_fixed_units':
                    switch.stateChanged.connect(self.refresh_archive.emit)
                rows.addWidget(switch)
                self.switches.append(switch)
            self.checkboxLayout.addWidget(section)

    def save_setting(self, key, new_value):
        setting = SettingsModel.get(key=key)
        setting.value = bool(new_value)
        setting.save()
