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
import time

HELPERS_DIR = os.path.dirname(__file__)
sys.path.append(HELPERS_DIR)

from installer import InstallerSteps  # pylint: disable=import-error
from step_logger import log_step


class Progress():
    def __init__(self, browser):
        self.browser = browser
        self.steps = InstallerSteps()
        self._reboot_selector = ".installation-progress-status-success button:contains('Reboot')"

    @log_step(snapshot_after=True)
    def wait_done(self, timeout=1200):
        timeout += time.time()
        while timeout > time.time():
            if self.browser.is_present(self._reboot_selector):
                break
            if self.browser.is_present('.pf-v5-c-alert.pf-m-danger'):
                raise AssertionError('Error during installation')
            time.sleep(30)
        else:
            self.browser.wait_visible(self._reboot_selector)

    @log_step()
    def reboot(self):
        self.browser.click(self._reboot_selector)

