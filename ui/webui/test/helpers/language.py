#!/usr/bin/python3
#
# Copyright (C) 2021 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; If not, see <http://www.gnu.org/licenses/>.

import os
import sys

HELPERS_DIR = os.path.dirname(__file__)
sys.path.append(HELPERS_DIR)

from installer import InstallerSteps  # pylint: disable=import-error

LOCALIZATION_INTERFACE = "org.fedoraproject.Anaconda.Modules.Localization"
LOCALIZATION_OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Localization"

class Language():
    def __init__(self, browser, machine):
        self.browser = browser
        self.machine = machine
        self._step = InstallerSteps.WELCOME

    def clear_language_selector(self):
        # Check that the [x] button clears the input text
        self.browser.click(".pf-c-select__toggle-clear")
        self.browser.wait_val(f"#{self._step}-menu-toggle-select-typeahead", "")

    def select_locale(self, locale):
        if self.browser.val(f"#{self._step}-menu-toggle-select-typeahead") != "":
            self.clear_language_selector()
        if not self.browser.is_present(".pf-c-select__menu"):
            self.browser.click(f"#{self._step}-menu-toggle")
        self.browser.click(f"#{self._step}-option-{locale} > button")

    def input_locale_select(self, text):
        self.browser.set_input_text(f"#{self._step}-menu-toggle-select-typeahead", text)

    def locale_option_visible(self, locale, visible=True):
        if visible:
            self.browser.wait_visible(f"#{self._step}-option-{locale}")
        else:
            self.browser.wait_not_present(f"#{self._step}-option-{locale}")

    def open_locale_options(self):
        self.browser.click(f"#{self._step}-menu-toggle")

    def check_selected_locale(self, locale):
        self.browser.wait_val(f"#{self._step}-menu-toggle-select-typeahead", locale)

    def dbus_set_language_cmd(self, value, bus_address):
        return f'dbus-send --print-reply --bus="{bus_address}" \
            --dest={LOCALIZATION_INTERFACE} \
            {LOCALIZATION_OBJECT_PATH} \
            org.freedesktop.DBus.Properties.Set \
            string:"{LOCALIZATION_INTERFACE}" string:"Language" variant:string:"{value}"'

    def dbus_get_language_cmd(self, bus_address):
        return f'dbus-send --print-reply --bus="{bus_address}" \
            --dest={LOCALIZATION_INTERFACE} \
            {LOCALIZATION_OBJECT_PATH} \
            org.freedesktop.DBus.Properties.Get \
            string:"{LOCALIZATION_INTERFACE}" string:"Language"'
