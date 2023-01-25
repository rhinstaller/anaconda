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

from installer import InstallerSteps  # pylint: disable=import-error


class Review():
    def __init__(self, browser):
        self.browser = browser
        self._step = InstallerSteps.REVIEW

    def check_language(self, lang):
        self.browser.wait_in_text(f"#{self._step}-target-system-language > .pf-c-description-list__text", lang)

    def check_disk_label(self, disk, label):
        self.browser.wait_in_text(f"#{self._step}-disk-label-{disk}", label)

    def check_disk_description(self, disk, description):
        self.browser.wait_in_text(f"#{self._step}-disk-description-{disk}", description)
