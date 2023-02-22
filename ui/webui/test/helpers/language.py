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
from step_logger import log_step


LOCALIZATION_INTERFACE = "org.fedoraproject.Anaconda.Modules.Localization"
LOCALIZATION_OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Localization"

class Language():
    def __init__(self, browser, machine):
        self.browser = browser
        self.machine = machine
        self._step = InstallerSteps.WELCOME
        self._bus_address = self.machine.execute("cat /run/anaconda/bus.address")

    @log_step()
    def select_locale(self, locale):
        if self.browser.val(f"#{self._step}-language-search .pf-c-text-input-group__text-input") != "":
            self.input_locale_search("")
        self.browser.click(f"#{self._step}-option-common-{locale} > button")

    @log_step()
    def get_locale_search(self):
        return self.browser.val(f"#{self._step}-language-search .pf-c-text-input-group__text-input")

    @log_step()
    def input_locale_search(self, text):
        self.browser.set_input_text(f"#{self._step}-language-search .pf-c-text-input-group__text-input", text)

    @log_step()
    def locale_option_visible(self, locale, visible=True):
        if visible:
            self.browser.wait_visible(f"#{self._step}-option-alpha-{locale}")
        else:
            self.browser.wait_not_present(f"#{self._step}-option-alpha-{locale}")

    @log_step()
    def locale_common_option_visible(self, locale, visible=True):
        if visible:
            self.browser.wait_visible(f"#{self._step}-option-common-{locale}")
        else:
            self.browser.wait_not_present(f"#{self._step}-option-common-{locale}")

    @log_step(snapshot_before=True)
    def check_selected_locale(self, locale):
        self.browser.wait_visible(f"#{self._step}-option-alpha-{locale} .pf-m-selected")

    def dbus_set_language(self, value):
        self.machine.execute(f'dbus-send --print-reply --bus="{self._bus_address}" \
            --dest={LOCALIZATION_INTERFACE} \
            {LOCALIZATION_OBJECT_PATH} \
            org.freedesktop.DBus.Properties.Set \
            string:"{LOCALIZATION_INTERFACE}" string:"Language" variant:string:"{value}"')

    def dbus_get_language(self):
        return self.machine.execute(f'dbus-send --print-reply --bus="{self._bus_address}" \
            --dest={LOCALIZATION_INTERFACE} \
            {LOCALIZATION_OBJECT_PATH} \
            org.freedesktop.DBus.Properties.Get \
            string:"{LOCALIZATION_INTERFACE}" string:"Language"')
