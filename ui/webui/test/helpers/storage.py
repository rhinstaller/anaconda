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

STORAGE_INTERFACE = "org.fedoraproject.Anaconda.Modules.Storage"
STORAGE_OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Storage"

class Storage():
    def __init__(self, browser, machine):
        self.browser = browser
        self.machine = machine

    def select_disk(self, disk, selected=True):
        self.browser.set_checked("#" + disk + " input", selected)

    def wait_no_disks(self):
        self.browser.wait_in_text(".pf-c-alert.pf-m-danger.pf-m-inline", "No usable disks")

    def dbus_reset_partitioning(self):
        bus_address = self.machine.execute("cat /run/anaconda/bus.address")
        self.machine.execute(f'dbus-send --print-reply --bus="{bus_address}" \
            --dest={STORAGE_INTERFACE} \
            {STORAGE_OBJECT_PATH} \
            {STORAGE_INTERFACE}.ResetPartitioning')
