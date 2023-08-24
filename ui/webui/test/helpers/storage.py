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
import re

HELPERS_DIR = os.path.dirname(__file__)
sys.path.append(HELPERS_DIR)

from installer import InstallerSteps  # pylint: disable=import-error
from step_logger import log_step


STORAGE_SERVICE = "org.fedoraproject.Anaconda.Modules.Storage"
STORAGE_INTERFACE = STORAGE_SERVICE
DISK_INITIALIZATION_INTERFACE = "org.fedoraproject.Anaconda.Modules.Storage.DiskInitialization"
STORAGE_OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Storage"
DISK_INITIALIZATION_OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Storage/DiskInitialization"

id_prefix = "installation-method"

class Storage():
    def __init__(self, browser, machine):
        self.browser = browser
        self.machine = machine
        self._step = InstallerSteps.INSTALLATION_METHOD
        self._bus_address = self.machine.execute("cat /run/anaconda/bus.address")

    def get_disks(self):
        output = self.machine.execute('list-harddrives')
        for disk in output.splitlines():
            yield disk.split()[0]

    @log_step()
    def select_disk(self, disk, selected=True, is_single_disk=False):
        if not self.browser.is_present(f".pf-v5-c-menu[aria-labelledby='{id_prefix}-disk-selector-title']"):
            self.browser.click(f"#{id_prefix}-disk-selector-toggle > button")

        if selected:
            self.browser.click(f"#{id_prefix}-disk-selector-option-{disk}:not(.pf-m-selected)")
        else:
            self.browser.click(f"#{id_prefix}-disk-selector-option-{disk}.pf-m-selected")

        if is_single_disk:
            self.check_single_disk_destination(disk)
        else:
            self.check_disk_selected(disk, selected)

    @log_step()
    def select_none_disks_and_check(self, disks):
        self.browser.click(f"#{id_prefix}-disk-selector-clear")
        for disk in disks:
            self.check_disk_selected(disk, False)

    def check_single_disk_destination(self, disk, capacity=None):
        self.browser.wait_in_text(f"#{id_prefix}-target-disk", disk)
        if capacity:
            self.browser.wait_in_text(f"#{id_prefix}-target-disk", capacity)

    @log_step(snapshot_before=True)
    def check_disk_selected(self, disk, selected=True):
        if selected:
            self.browser.wait_visible(f"#{id_prefix}-selector-form li.pf-v5-c-chip-group__list-item:contains('{disk}')")
        else:
            self.browser.wait_not_present(f"#{id_prefix}-selector-form li.pf-v5-c-chip-group__list-item:contains({disk})")

    def get_disk_selected(self, disk):
        return (
            self.browser.is_present(f"#{id_prefix}-selector-form li.pf-v5-c-chip-group__list-item:contains({disk})") or
            (self.browser.is_present(f"#{id_prefix}-target-disk") and
             disk in self.browser.text(f"#{id_prefix}-target-disk"))
        )

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

    def dbus_get_usable_disks(self):
        ret = self.machine.execute(f'busctl --address="{self._bus_address}" \
            call \
            {STORAGE_SERVICE} \
            {STORAGE_OBJECT_PATH}/DiskSelection \
            {STORAGE_INTERFACE}.DiskSelection GetUsableDisks')

        return re.findall('"([^"]*)"', ret)

    def dbus_reset_selected_disks(self):
        self.machine.execute(f'busctl --address="{self._bus_address}" \
            set-property \
            {STORAGE_SERVICE} \
            {STORAGE_OBJECT_PATH}/DiskSelection \
            {STORAGE_INTERFACE}.DiskSelection SelectedDisks as 0')

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
        if not self.browser.is_present(f".pf-v5-c-menu[aria-labelledby='{id_prefix}-disk-selector-title']"):
            self.browser.click(f"#{id_prefix}-disk-selector-toggle > button")

        if visible:
            self.browser.wait_visible(f"#{id_prefix}-disk-selector-option-{disk}")
        else:
            self.browser.wait_not_present(f"#{id_prefix}-disk-selector-option-{disk}")

        self.browser.click(f"#{id_prefix}-disk-selector-toggle > button")
        self.browser.wait_not_present(f".pf-v5-c-menu[aria-labelledby='{id_prefix}-disk-selector-title']")

    def _partitioning_selector(self, scenario):
        return f"#{id_prefix}-scenario-" + scenario

    def wait_scenario_visible(self, scenario, visible=True):
        if visible:
            self.browser.wait_visible(self._partitioning_selector(scenario))
        else:
            self.browser.wait_not_present(self._partitioning_selector(scenario))

    @log_step(snapshot_before=True)
    def check_partitioning_selected(self, scenario):
        self.browser.wait_visible(self._partitioning_selector(scenario) + ":checked")

    @log_step(snapshot_before=True)
    def set_partitioning(self, scenario):
        self.browser.click(self._partitioning_selector(scenario))
        self.browser.wait_visible(self._partitioning_selector(scenario) + ":checked")

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

    def add_basic_partitioning(self, target="vda", size="1GiB"):
        # Add a partition for "Use free space" scenario to be present
        self.machine.execute(f"sgdisk --new=0:0:+{size} /dev/{target}")
        self.rescan_disks()

    # partitions_params expected structure: [("size", "file system" {, "other mkfs.fs flags"})]
    def partition_disk(self, disk, partitions_params):
        command = f"sgdisk --zap-all {disk}"

        for i, params in enumerate(partitions_params):
            sgdisk = ["sgdisk", f"--new=0:0{':+' + params[0] if params[0] != '' else ':0'}"]

            if params[1] == "biosboot":
                sgdisk.append("--typecode=0:ef02")
            if params[1] == "efi":
                sgdisk.append("--typecode=0:ef00")

            sgdisk.append(disk)

            command += f"\n{' '.join(sgdisk)}"

            if params[1] not in ("biosboot", None):
                if params[1] == "lvmpv":
                    mkfs = ["pvcreate"]
                else:
                    if params[1] == "efi":
                        fs = "vfat"
                    else:
                        fs = params[1]
                    mkfs = [f"mkfs.{fs}"]

                # force flag
                if params[1] in ["xfs", "btrfs", "lvmpv"]:
                    mkfs.append("-f")
                elif params[1] in ["ext4", "etx3", "ext2", "ntfs"]:
                    mkfs.append("-F")

                # additional mkfs flags
                if len(params) > 2:
                    mkfs += params[2:]

                mkfs.append(f"{disk}{i + 1}")
                command += f"\n{' '.join(mkfs)}"

        self.machine.execute(command)

    def udevadm_settle(self):
        # Workaround to not have any empty mountpoint labels
        self.machine.execute("""
        udevadm trigger
        udevadm settle --timeout=120
        """)

    def set_partition_uuid(self, disk, partition, uuid):
        self.machine.execute(f"sfdisk --part-uuid {disk} {partition} {uuid}")
