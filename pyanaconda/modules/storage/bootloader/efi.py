#
# Copyright (C) 2019 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
import re

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.kernel import kernel_arguments
from pyanaconda.modules.storage.bootloader.base import BootLoaderError
from pyanaconda.modules.storage.bootloader.grub2 import GRUB2
from pyanaconda.product import productName

log = get_module_logger(__name__)

__all__ = ["EFIBase", "EFIGRUB", "Aarch64EFIGRUB", "ArmEFIGRUB", "MacEFIGRUB"]


class EFIBase(object):
    """A base class for EFI-based boot loaders."""

    @property
    def efi_config_dir(self):
        return "/boot/" + self._efi_config_dir

    @property
    def _efi_config_dir(self):
        return "efi/EFI/{}".format(conf.bootloader.efi_dir)

    def efibootmgr(self, *args, **kwargs):
        if not conf.target.is_hardware:
            log.info("Skipping efibootmgr for image/directory install.")
            return ""

        if "noefi" in kernel_arguments:
            log.info("Skipping efibootmgr for noefi")
            return ""

        if kwargs.pop("capture", False):
            exec_func = util.execWithCapture
        else:
            exec_func = util.execWithRedirect
        if "root" not in kwargs:
            kwargs["root"] = conf.target.system_root

        return exec_func("efibootmgr", list(args), **kwargs)

    @property
    def efi_dir_as_efifs_dir(self):
        ret = self._efi_config_dir.replace('efi/', '')
        return "\\" + ret.replace('/', '\\')

    def _add_single_efi_boot_target(self, partition):
        boot_disk = partition.disk
        boot_part_num = str(partition.parted_partition.number)

        create_method = "-C" if self.keep_boot_order else "-c" # pylint: disable=no-member

        rc = self.efibootmgr(
            create_method, "-w", "-L", productName.split("-")[0],  # pylint: disable=no-member
            "-d", boot_disk.path, "-p", boot_part_num,
            "-l", self.efi_dir_as_efifs_dir + self._efi_binary,  # pylint: disable=no-member
            root=conf.target.system_root
        )
        if rc != 0:
            raise BootLoaderError("Failed to set new efi boot target. This is most "
                                  "likely a kernel or firmware bug.")

    def add_efi_boot_target(self):
        if self.stage1_device.type == "partition":  # pylint: disable=no-member
            self._add_single_efi_boot_target(self.stage1_device)  # pylint: disable=no-member
        elif self.stage1_device.type == "mdarray":  # pylint: disable=no-member
            for parent in self.stage1_device.parents:  # pylint: disable=no-member
                self._add_single_efi_boot_target(parent)

    def remove_efi_boot_target(self):
        buf = self.efibootmgr(capture=True)
        for line in buf.splitlines():
            try:
                (slot, _product) = line.split(None, 1)
            except ValueError:
                continue

            if _product == productName.split("-")[0]:           # pylint: disable=no-member
                slot_id = slot[4:8]
                # slot_id is hex, we can't use .isint and use this regex:
                if not re.match("^[0-9a-fA-F]+$", slot_id):
                    log.warning("failed to parse efi boot slot (%s)", slot)
                    continue

                rc = self.efibootmgr("-b", slot_id, "-B")
                if rc:
                    raise BootLoaderError("Failed to remove old efi boot entry. This is most "
                                          "likely a kernel or firmware bug.")

    def write(self):
        """ Write the bootloader configuration and install the bootloader. """
        if self.skip_bootloader:  # pylint: disable=no-member
            return

        try:
            os.sync()
            self.stage2_device.format.sync(root=conf.target.physical_root) # pylint: disable=no-member
            self.install()
        finally:
            self.write_config()  # pylint: disable=no-member

    def check(self):
        return True

    def install(self, args=None):
        if not self.keep_boot_order:  # pylint: disable=no-member
            self.remove_efi_boot_target()
        self.add_efi_boot_target()


class EFIGRUB(EFIBase, GRUB2):
    """EFI GRUBv2"""
    _packages32 = [ "grub2-efi-ia32", "shim-ia32" ]
    _packages_common = [ "efibootmgr", "grub2-tools" ]
    stage2_is_valid_stage1 = False
    stage2_bootable = False

    _is_32bit_firmware = False

    def __init__(self):
        super().__init__()
        self._packages64 = [ "grub2-efi-x64", "shim-x64" ]

        try:
            f = open("/sys/firmware/efi/fw_platform_size", "r")
            value = f.readline().strip()
        except IOError:
            log.info("Reading /sys/firmware/efi/fw_platform_size failed, "
                     "defaulting to 64-bit install.")
            value = '64'
        if value == '32':
            self._is_32bit_firmware = True

    @property
    def _efi_binary(self):
        if self._is_32bit_firmware:
            return "\\shimia32.efi"
        return "\\shimx64.efi"

    @property
    def packages(self):
        if self._is_32bit_firmware:
            return self._packages32 + self._packages_common
        return self._packages64 + self._packages_common

    @property
    def efi_config_file(self):
        """ Full path to EFI configuration file. """
        return "%s/%s" % (self.efi_config_dir, self._config_file)

    def write_config(self):
        rc = util.execWithRedirect(
            "gen_grub_cfgstub",
            [self.config_dir, self.efi_config_dir],
            root=conf.target.system_root,
        )

        if rc != 0:
            raise BootLoaderError("gen_grub_cfgstub script failed")

        super().write_config()


class Aarch64EFIGRUB(EFIGRUB):
    _serial_consoles = ["ttyAMA", "ttyS"]
    _efi_binary = "\\shimaa64.efi"

    def __init__(self):
        super().__init__()
        self._packages64 = ["grub2-efi-aa64", "shim-aa64"]


class ArmEFIGRUB(EFIGRUB):
    _serial_consoles = ["ttyAMA", "ttyS"]
    _efi_binary = "\\grubarm.efi"

    def __init__(self):
        super().__init__()
        self._packages32 = ["grub2-efi-arm"]
        self._is_32bit_firmware = True


class MacEFIGRUB(EFIGRUB):
    def __init__(self):
        super().__init__()
        self._packages64.extend(["grub2-tools-efi", "mactel-boot"])

    def mactel_config(self):
        if os.path.exists(conf.target.system_root + "/usr/libexec/mactel-boot-setup"):
            rc = util.execInSysroot("/usr/libexec/mactel-boot-setup", [])
            if rc:
                log.error("failed to configure Mac boot loader")

    def install(self, args=None):
        super().install()
        self.mactel_config()

    def is_valid_stage1_device(self, device, early=False):
        valid = super().is_valid_stage1_device(device, early)

        # Make sure we don't pick the OSX root partition
        if valid and getattr(device.format, "name", "") != "Linux HFS+ ESP":
            valid = False

        if hasattr(device.format, "name"):
            log.debug("device.format.name is '%s'", device.format.name)

        log.debug("MacEFIGRUB.is_valid_stage1_device(%s) returning %s", device.name, valid)
        return valid
