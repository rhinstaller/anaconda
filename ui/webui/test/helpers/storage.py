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


STORAGE_INTERFACE = "org.fedoraproject.Anaconda.Modules.Storage"
STORAGE_OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Storage"


class Storage():
    def __init__(self, browser, machine):
        self.browser = browser
        self.machine = machine
        self._step = InstallerSteps.STORAGE

    def get_disks(self):
        output = self.machine.execute('list-harddrives')
        for disk in output.splitlines():
            yield disk.split()[0]

    def select_disk(self, disk, selected=True):
        self.browser.set_checked(f"#{disk} input", selected)
        self.check_disk_selected(disk, selected)

    def select_all_disks_and_check(self, disks):
        self.browser.click("#local-disks-bulk-select-toggle")
        self.browser.click("#local-disks-bulk-select-all")
        for disk in disks:
            self.check_disk_selected(disk)

    def select_none_disks_and_check(self, disks):
        self.browser.click("#local-disks-bulk-select-toggle")
        self.browser.click("#local-disks-bulk-select-none")
        for disk in disks:
            self.check_disk_selected(disk, False)

    def click_checkbox_and_check_all_disks(self, disks, selected):
        self.browser.click("#select-multiple-split-checkbox")
        for disk in disks:
            self.check_disk_selected(disk, selected)

    def check_disk_selected(self, disk, selected=True):
        assert self.browser.get_checked(f"#{disk} input") == selected

    def wait_no_disks(self):
        self.browser.wait_in_text("#next-tooltip-ref",
                                  "To continue, select the devices(s) to install to.")

    def wait_no_disks_detected(self):
        self.browser.wait_in_text("#no-disks-detected-alert",
                                  "No additional disks detected")

    def wait_no_disks_detected_not_present(self):
        self.browser.wait_not_present("#no-disks-detected-alert")

    def dbus_reset_partitioning(self):
        bus_address = self.machine.execute("cat /run/anaconda/bus.address")
        self.machine.execute(f'dbus-send --print-reply --bus="{bus_address}" \
            --dest={STORAGE_INTERFACE} \
            {STORAGE_OBJECT_PATH} \
            {STORAGE_INTERFACE}.ResetPartitioning')

    def rescan_disks(self):
        self.browser.click(f"#{self._step}-rescan-disks")

    def check_disk_visible(self, disk, visible=True):
        if visible:
            self.browser.wait_text(f"#{disk} > th[data-label=Name]", f"{disk}")
        else:
            self.browser.wait_not_present(f"#{disk}")

    def check_disk_capacity(self, disk, total=None, free=None):
        if total:
            self.browser.wait_text(f"#{disk} > td[data-label=Total]", total)
        if free:
            self.browser.wait_text(f"#{disk} > td[data-label=Free]", free)
