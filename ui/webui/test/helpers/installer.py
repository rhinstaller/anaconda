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
from collections import UserDict
from time import sleep
from step_logger import log_step

from users import create_user


class InstallerSteps(UserDict):
    WELCOME = "installation-language"
    INSTALLATION_METHOD = "installation-method"
    CUSTOM_MOUNT_POINT = "mount-point-mapping"
    DISK_CONFIGURATION = "disk-configuration"
    DISK_ENCRYPTION = "disk-encryption"
    ACCOUNTS = "accounts"
    REVIEW = "installation-review"
    PROGRESS = "installation-progress"

    _steps_jump = {}
    _steps_jump[WELCOME] = INSTALLATION_METHOD
    _steps_jump[INSTALLATION_METHOD] = [DISK_ENCRYPTION, CUSTOM_MOUNT_POINT]
    _steps_jump[DISK_ENCRYPTION] = ACCOUNTS
    _steps_jump[CUSTOM_MOUNT_POINT] = ACCOUNTS
    _steps_jump[ACCOUNTS] = REVIEW
    _steps_jump[REVIEW] = PROGRESS
    _steps_jump[PROGRESS] = []

    _steps_callbacks = {}
    _steps_callbacks[ACCOUNTS] = create_user

class Installer():
    def __init__(self, browser, machine):
        self.browser = browser
        self.machine = machine
        self.steps = InstallerSteps()

    @log_step(snapshot_before=True)
    def begin_installation(self, should_fail=False, confirm_erase=True):
        current_page = self.get_current_page()

        self.browser.click("button:contains('Erase data and install')")

        if confirm_erase:
            self.browser.click(f"#{self.steps.REVIEW}-disk-erase-confirm")
        else:
            self.browser.click(".pf-v5-c-modal-box button:contains(Back)")

        if should_fail:
            self.wait_current_page(current_page)
        else:
            self.wait_current_page(self.steps._steps_jump[current_page])

    def reach(self, target_page, hidden_steps=None):
        hidden_steps = hidden_steps or []
        path = []
        prev_pages = [target_page]
        current_page = self.get_current_page()

        while current_page not in prev_pages:
            page = prev_pages[0]
            path.append(page)
            prev_pages = [k for k, v in self.steps._steps_jump.items() if page in v]

        while self.get_current_page() != target_page:
            next_page = path.pop()
            if next_page not in hidden_steps:
                self.next(next_page=next_page)
                if next_page in self.steps._steps_callbacks:
                    self.steps._steps_callbacks[next_page](self.browser, self.machine)

    @log_step()
    def next(self, should_fail=False, next_page=""):
        current_page = self.get_current_page()
        # If not explicitly specified, get the first item for next page from the steps dict
        if not next_page:
            if isinstance(self.steps._steps_jump[current_page], list):
                next_page = self.steps._steps_jump[current_page][0]
            else:
                next_page = self.steps._steps_jump[current_page]

        # Wait for a disk to be pre-selected before clicking 'Next'.
        # FIXME: Find a better way.
        if current_page == self.steps.INSTALLATION_METHOD:
            sleep(2)

        self.browser.click("button:contains(Next)")
        expected_page = current_page if should_fail else next_page
        self.wait_current_page(expected_page)
        return expected_page

    @log_step()
    def check_next_disabled(self, disabled=True):
        """Check if the Next button is disabled.

        :param disabled: True if Next button should be disabled, False if not
        :type disabled: bool, optional
        """
        value = "false" if disabled else "true"
        self.browser.wait_visible(f"#installation-next-btn:not([aria-disabled={value}]")

    @log_step(snapshot_before=True)
    def back(self, should_fail=False, previous_page=""):
        current_page = self.get_current_page()

        self.browser.click("button:contains(Back)")

        if should_fail:
            self.wait_current_page(current_page)
        else:
            if not previous_page:
                previous_page = [k for k, v in self.steps._steps_jump.items() if current_page in v][0]

            self.wait_current_page(previous_page)

    @log_step()
    def open(self, step="installation-language"):
        self.browser.open(f"/cockpit/@localhost/anaconda-webui/index.html#/{step}")
        self.wait_current_page(step)
        # Ensure that the logo is visible before proceeding as pixel tests get racy otherwise
        self.browser.wait_js_cond("document.querySelector('.logo').complete")

    def click_step_on_sidebar(self, step=None):
        step = step or self.get_current_page()
        self.browser.click(f"#{step}")

    @log_step()
    def reach_on_sidebar(self, target_page, parent_step=None):
        if parent_step:
            self.click_step_on_sidebar(parent_step)
        self.click_step_on_sidebar(target_page)
        self.wait_current_page(target_page)

    def get_current_page(self):
        return self.browser.eval_js('window.location.hash;').replace('#/', '') or self.steps[0]

    @log_step(snapshot_after=True)
    def wait_current_page(self, page):
        self.browser.wait_not_present("#installation-destination-next-spinner")
        self.browser.wait_js_cond(f'window.location.hash === "#/{page}"')

        if page == self.steps.PROGRESS:
            self.browser.wait_visible(".pf-v5-c-progress-stepper")
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
