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


STORAGE_SERVICE = "org.fedoraproject.Anaconda.Modules.Storage"
STORAGE_INTERFACE = STORAGE_SERVICE
DISK_INITIALIZATION_INTERFACE = "org.fedoraproject.Anaconda.Modules.Storage.DiskInitialization"
STORAGE_OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Storage"
DISK_INITIALIZATION_OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Storage/DiskInitialization"


class Storage():
    def __init__(self, browser, machine):
        self.browser = browser
        self.machine = machine
        self._step = InstallerSteps.STORAGE_DEVICES
        self._bus_address = self.machine.execute("cat /run/anaconda/bus.address")

    def get_disks(self):
        output = self.machine.execute('list-harddrives')
        for disk in output.splitlines():
            yield disk.split()[0]

    @log_step()
    def select_disk(self, disk, selected=True):
        self.browser.set_checked(f"#{disk} input", selected)
        self.check_disk_selected(disk, selected)

    @log_step()
    def select_all_disks_and_check(self, disks):
        self.browser.click("#local-disks-bulk-select-toggle")
        self.browser.click("#local-disks-bulk-select-all")
        self.browser.wait_visible("#select-multiple-split-checkbox:checked")
        for disk in disks:
            self.check_disk_selected(disk)

    @log_step()
    def select_none_disks_and_check(self, disks):
        self.browser.click("#local-disks-bulk-select-toggle")
        self.browser.click("#local-disks-bulk-select-none")
        self.browser.wait_visible("#select-multiple-split-checkbox:not(:checked)")
        for disk in disks:
            self.check_disk_selected(disk, False)

    @log_step()
    def click_checkbox_and_check_all_disks(self, disks, selected):
        self.browser.click("#select-multiple-split-checkbox")
        if selected:
            self.browser.wait_visible("#select-multiple-split-checkbox:checked")
        else:
            self.browser.wait_visible("#select-multiple-split-checkbox:not(:checked)")
        for disk in disks:
            self.check_disk_selected(disk, selected)

    @log_step(snapshot_before=True)
    def check_disk_selected(self, disk, selected=True):
        if selected:
            self.browser.wait_visible(f"#{disk} input:checked")
        else:
            self.browser.wait_visible(f"#{disk} input:not(:checked)")


    @log_step()
    def wait_no_disks(self):
        self.browser.wait_in_text("#next-helper-text",
                                  "To continue, select the devices to install to.")

    @log_step()
    def wait_no_disks_detected(self):
        self.browser.wait_in_text("#no-disks-detected-alert",
                                  "No additional disks detected")

    @log_step()
    def wait_no_disks_detected_not_present(self):
        self.browser.wait_not_present("#no-disks-detected-alert")

    def dbus_scan_devices(self):
        task = self.machine.execute(f'busctl --address="{self._bus_address}" \
            call \
            {STORAGE_SERVICE} \
            {STORAGE_OBJECT_PATH} \
            {STORAGE_INTERFACE} ScanDevicesWithTask')
        task = task.splitlines()[-1].split()[-1]

        self.machine.execute(f'busctl --address="{self._bus_address}" \
            call \
            {STORAGE_SERVICE} \
            {task} \
            org.fedoraproject.Anaconda.Task Start')

    def dbus_reset_partitioning(self):
        self.machine.execute(f'busctl --address="{self._bus_address}" \
            call \
            {STORAGE_SERVICE} \
            {STORAGE_OBJECT_PATH} \
            {STORAGE_INTERFACE} ResetPartitioning')

    def dbus_create_partitioning(self, method="MANUAL"):
        return self.machine.execute(f'busctl --address="{self._bus_address}" \
            call \
            {STORAGE_SERVICE} \
            {STORAGE_OBJECT_PATH} \
            {STORAGE_INTERFACE} CreatePartitioning s {method}')

    def dbus_get_applied_partitioning(self):
        ret = self.machine.execute(f'busctl --address="{self._bus_address}" \
            get-property  \
            {STORAGE_SERVICE} \
            {STORAGE_OBJECT_PATH} \
            {STORAGE_INTERFACE} AppliedPartitioning')

        print("ret: ", ret)
        return ret.split('s ')[1].strip()

    def dbus_get_created_partitioning(self):
        ret = self.machine.execute(f'busctl --address="{self._bus_address}" \
            get-property  \
            {STORAGE_SERVICE} \
            {STORAGE_OBJECT_PATH} \
            {STORAGE_INTERFACE} CreatedPartitioning')

        return ret[ret.find("[")+1:ret.rfind("]")].split()

    def dbus_set_initialization_mode(self, value):
        self.machine.execute(f'busctl --address="{self._bus_address}" \
            set-property \
            {STORAGE_SERVICE} \
            {DISK_INITIALIZATION_OBJECT_PATH} \
            {DISK_INITIALIZATION_INTERFACE} InitializationMode i -- {value}')

    @log_step(snapshots=True)
    def rescan_disks(self):
        self.browser.click(f"#{self._step}-rescan-disks")

    @log_step(snapshot_before=True)
    def check_disk_visible(self, disk, visible=True):
        if visible:
            self.browser.wait_text(f"#{disk} > th[data-label=Name]", f"{disk}")
        else:
            self.browser.wait_not_present(f"#{disk}")

    def check_disk_expandable(self, disk, expandable=True):
        if expandable:
            self.browser.wait_visible(f"#{disk} .pf-c-table__toggle button")
        else:
            self.browser.wait_not_present(f"#{disk} .pf-c-table__toggle button")

    @log_step(snapshot_before=True)
    def check_disk_capacity(self, disk, total=None, free=None):
        if total:
            self.browser.wait_text(f"#{disk} > td[data-label=Total]", total)
        if free:
            self.browser.wait_text(f"#{disk} > td[data-label=Free]", free)

    def _partitioning_selector(self, scenario):
        return "#storage-configuration-autopart-scenario-" + scenario

    @log_step(snapshot_before=True)
    def check_partitioning_selected(self, scenario):
        self.browser.wait_visible(self._partitioning_selector(scenario) + ":checked")

    @log_step(snapshot_before=True)
    def set_partitioning(self, scenario):
        self.browser.set_checked(self._partitioning_selector(scenario), True)

    @log_step(snapshot_before=True)
    def check_encryption_selected(self, selected):
        sel = "#disk-encryption-encrypt-devices"
        if selected:
            self.browser.wait_visible(sel + ':checked')
        else:
            self.browser.wait_visible(sel + ':not([checked])')

    @log_step(snapshot_before=True)
    def set_encryption_selected(self, selected):
        sel = "#disk-encryption-encrypt-devices"
        self.browser.set_checked(sel, selected)

    @log_step(snapshot_before=True)
    def check_pw_rule(self, rule, value):
        sel = "#disk-encryption-password-rule-" + rule
        cls_value = "pf-m-" + value
        self.browser.wait_visible(sel)
        self.browser.wait_attr_contains(sel, "class", cls_value)

    @log_step(snapshot_before=True)
    def set_password(self, password, append=False, value_check=True):
        sel = "#disk-encryption-password-field"
        self.browser.set_input_text(sel, password, append=append, value_check=value_check)

    @log_step(snapshot_before=True)
    def check_password(self, password):
        sel = "#disk-encryption-password-field"
        self.browser.wait_val(sel, password)

    @log_step(snapshot_before=True)
    def set_password_confirm(self, password):
        sel = "#disk-encryption-password-confirm-field"
        self.browser.set_input_text(sel, password)

    @log_step(snapshot_before=True)
    def check_password_confirm(self, password):
        sel = "#disk-encryption-password-confirm-field"
        self.browser.wait_val(sel, password)

    @log_step(snapshot_before=True)
    def check_pw_strength(self, strength):
        sel = "#disk-encryption-password-strength-label"

        if strength is None:
            self.browser.wait_not_present(sel)
            return

        variant = ""
        if strength == "weak":
            variant = "error"
        elif strength == "medium":
            variant = "warning"
        elif strength == "strong":
            variant = "success"

        self.browser.wait_attr_contains(sel, "class", "pf-m-" + variant)

    @log_step(docstring=True)
    def unlock_storage_on_boot(self, password):
        """ Add keyfile to unlock luks encrypted storage on boot """
        self.machine.write('/mnt/sysroot/root/keyfile', password, perm='0400')
        self.machine.write('/mnt/sysroot/root/add_keyfile.sh', '''
            awk -v "KEY_FILE=/root/keyfile" '{$3=KEY_FILE; print $0}' /etc/crypttab > crypttab_mod
            mv -Z crypttab_mod /etc/crypttab
            chmod 0600 /etc/crypttab
            kernel_file=`grubby --default-kernel`
            kernel_version=`rpm -qf $kernel_file --qf '%{VERSION}-%{RELEASE}.%{ARCH}'`
            initrd_file="/boot/initramfs-${kernel_version}.img"
            dracut -f -I /root/keyfile $initrd_file $kernel_version
            if [ -x /sbin/zipl ]; then
                /sbin/zipl
            fi
        ''')
        self.machine.execute('chroot /mnt/sysroot bash /root/add_keyfile.sh')

    def open_storage_options_help_drawer(self):
        self.browser.click(".pf-c-wizard__main-body #learn-more-about-storage-options")
        self.browser.wait_visible(".pf-c-drawer__panel-main")

    def set_expand_disk_row(self, disk, expanded=True):
        if not expanded:
            self.browser.wait_visible(f"#{disk} + .pf-c-table__expandable-row.pf-m-expanded")
        else:
            self.browser._wait_present(f"#{disk} + .pf-c-table__expandable-row[hidden]")

        self.browser.click(f"#{disk} > .pf-c-table__toggle button")

        if not expanded:
            self.browser._wait_present(f"#{disk} + .pf-c-table__expandable-row[hidden]")
        else:
            self.browser.wait_visible(f"#{disk} + .pf-c-table__expandable-row.pf-m-expanded")

    def check_disk_partition(self, disk, partition, fs_type=None, size=None):
        self.browser.wait_visible(f"#{disk} + .pf-c-table__expandable-row.pf-m-expanded tr:contains('{partition}')")
        if fs_type:
            self.browser.wait_in_text(f"#{disk} + .pf-c-table__expandable-row.pf-m-expanded tr:contains('{partition}') td[data-label=Type]", fs_type)
        if size:
            self.browser.wait_in_text(f"#{disk} + .pf-c-table__expandable-row.pf-m-expanded tr:contains('{partition}') td[data-label=Size]", size)
