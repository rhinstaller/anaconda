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

class Language():
    def __init__(self, browser):
        self.browser = browser

    def clear_language_selector(self):
        # Check that the [x] button clears the input text
        self.browser.click(".pf-c-select__toggle-clear")
        self.browser.wait_val("#language-menu-toggle-select-typeahead", "")

    def select_locale(self, locale):
        if self.browser.val("#language-menu-toggle-select-typeahead") != "":
            self.clear_language_selector()
        self.browser.click("#language-menu-toggle")
        self.browser.click("#" + locale + " > button")
        self.browser.expect_load()
