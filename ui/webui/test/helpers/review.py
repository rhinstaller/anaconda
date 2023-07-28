#!/usr/bin/python3
#
# Copyright (C) 2022 Red Hat, Inc.
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


class Review():
    def __init__(self, browser):
        self.browser = browser
        self._step = InstallerSteps.REVIEW

    @log_step()
    def check_language(self, lang):
        self.browser.wait_in_text(f"#{self._step}-target-system-language > .pf-c-description-list__text", lang)

    @log_step()
    def check_encryption(self, state):
        self.browser.wait_in_text(f"#{self._step}-target-system-encrypt > .pf-c-description-list__text", state)

    @log_step()
    def check_storage_config(self, scenario):
        self.browser.wait_in_text(f"#{self._step}-target-system-mode > .pf-c-description-list__text", scenario)

    def check_disk(self, disk, text):
        self.browser.wait_text(f"#disk-{disk} span", text)

    def check_disk_row(self, disk, row, text):
        self.browser.wait_text(f"#disk-{disk} ul li:nth-child({row})", text)

    def check_in_disk_row(self, disk, row, text):
        self.browser.wait_in_text(f"#disk-{disk} ul li:nth-child({row})", text)
