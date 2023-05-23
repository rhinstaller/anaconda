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
from collections import UserList
from time import sleep
from step_logger import log_step


class InstallerSteps(UserList):
    WELCOME = "installation-language"
    STORAGE_DEVICES = "storage-devices"
    STORAGE_CONFIGURATION = "storage-configuration"
    DISK_ENCRYPTION = "disk-encryption"
    REVIEW = "installation-review"
    PROGRESS = "installation-progress"
    _steps_list = (WELCOME, STORAGE_DEVICES, STORAGE_CONFIGURATION, DISK_ENCRYPTION, REVIEW, PROGRESS)

    def __init__(self, initlist=_steps_list):
        super().__init__(initlist)


class Installer():
    def __init__(self, browser, machine):
        self.browser = browser
        self.machine = machine
        self.steps = InstallerSteps()

    @log_step(snapshot_before=True)
    def begin_installation(self, should_fail=False, confirm_erase=True):
        current_step_id = self.get_current_page_id()
        self.browser.click("button:contains('Erase disks and install')")

        if confirm_erase:
            self.browser.click(f"#{self.steps.REVIEW}-disk-erase-confirm")
        else:
            self.browser.click(".pf-c-modal-box button:contains(Back)")

        if should_fail:
            self.wait_current_page(self.steps[current_step_id])
        else:
            self.wait_current_page(self.steps[current_step_id+1])

    @log_step()
    def next(self, should_fail=False, subpage=False):
        current_step_id = self.get_current_page_id()
        current_page = self.steps[current_step_id]
        next_page = self.steps[current_step_id+1]

        # Wait for a disk to be pre-selected before clicking 'Next'.
        # FIXME: Find a better way.
        if current_page == self.steps.STORAGE_DEVICES:
            sleep(2)

        self.browser.click("button:contains(Next)")
        self.wait_current_page(current_page if should_fail or subpage else next_page)

    @log_step()
    def check_next_disabled(self, disabled=True):
        """Check if the Next button is disabled.

        :param disabled: True if Next button should be disabled, False if not
        :type disabled: bool, optional
        """
        value = "false" if disabled else "true"
        self.browser.wait_visible(f"#installation-next-btn:not([aria-disabled={value}]")

    @log_step(snapshot_before=True)
    def back(self, should_fail=False, subpage=False):
        current_step_id = self.get_current_page_id()
        self.browser.click("button:contains(Back)")

        if should_fail or subpage:
            self.wait_current_page(self.steps[current_step_id])
        else:
            self.wait_current_page(self.steps[current_step_id-1])

    @log_step()
    def open(self, step="installation-language"):
        self.browser.open(f"/cockpit/@localhost/anaconda-webui/index.html#/{step}")
        self.wait_current_page(step)

    def get_current_page_id(self):
        page = self.browser.eval_js('window.location.hash;').replace('#/', '') or self.steps[0]
        return self.steps.index(page)

    @log_step(snapshot_after=True)
    def wait_current_page(self, page):
        self.browser.wait_not_present("#installation-destination-next-spinner")
        self.browser.wait_js_cond(f'window.location.hash === "#/{page}"')

        if page == self.steps.PROGRESS:
            self.browser.wait_visible(".pf-c-progress-stepper")
        else:
            self.browser.wait_visible(f"#{page}.pf-m-current")

    @log_step(snapshot_after=True)
    def check_prerelease_info(self, is_expected=None):
        """ Checks whether the pre-release information is visible or not.

        If is_expected is not set, the expected state is deduced from .buildstamp file.

        :param is_expected: Is it expected that the info is visible or not, defaults to None
        :type is_expected: bool, optional
        """
        if is_expected is not None:
            value = str(is_expected)
        else:
            value = self.machine.execute("grep IsFinal= /.buildstamp").split("=", 1)[1]

        # Check betanag
        if value.lower() == "false":
            self.browser.wait_visible("#betanag-icon")
        else:
            self.browser.wait_not_present("#betang-icon")

    @log_step()
    def quit(self):
        self.browser.click("#installation-quit-btn")
        self.browser.wait_visible("#installation-quit-confirm-dialog")
        self.browser.click("#installation-quit-confirm-btn")

    def is_drawer_open(self):
        return self.browser.is_present(".pf-c-drawer__panel-main")
