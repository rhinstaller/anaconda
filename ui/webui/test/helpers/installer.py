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


class Installer():
    welcome_id = "installation-language"
    storage_id = "installation-destination"
    review_id = "installation-review"
    progress_id = "installation-progress"
    steps = [welcome_id, storage_id, review_id, progress_id]

    def __init__(self, browser):
        self.browser = browser

    def begin_installation(self, should_fail=False, confirm_erase=True):
        current_step_id = self.get_current_page_id()
        self.browser.click("button:contains('Begin installation')")

        if confirm_erase:
            self.browser.click(f"#{self.review_id}-disk-erase-confirm")
        else:
            self.browser.click(".pf-c-modal-box button:contains(Back)")

        if should_fail:
            self.wait_current_page(self.steps[current_step_id])
        else:
            self.wait_current_page(self.steps[current_step_id+1])

    def next(self, should_fail=False):
        current_step_id = self.get_current_page_id()
        self.browser.click("button:contains(Next)")

        if should_fail:
            self.wait_current_page(self.steps[current_step_id])
        else:
            self.wait_current_page(self.steps[current_step_id+1])

    def open(self, step="installation-language"):
        self.browser.open(f"/cockpit/@localhost/anaconda-webui/index.html#/{step}")
        self.wait_current_page(step)

    def get_current_page_id(self):
        page = self.browser.eval_js('window.location.hash;').replace('#/', '') or self.steps[0]
        return self.steps.index(page)

    def wait_current_page(self, page):
        self.browser.wait_js_cond(f'window.location.hash === "#/{page}"')
        if page == self.progress_id:
            self.browser.wait_visible(".pf-c-progress-stepper")
        else:
            self.browser.wait_visible(f"#{page}.pf-m-current")
