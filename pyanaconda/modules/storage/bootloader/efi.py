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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
import re

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import _
from pyanaconda.core.kernel import kernel_arguments
from pyanaconda.core.path import join_paths
from pyanaconda.core.product import get_product_name
from pyanaconda.modules.storage.bootloader.base import BootLoaderError
from pyanaconda.modules.storage.bootloader.grub2 import GRUB2
from pyanaconda.modules.storage.bootloader.systemd import SystemdBoot

log = get_module_logger(__name__)

__all__ = [
    "EFIGRUB",
    "RISCV64EFIGRUB",
    "Aarch64EFIGRUB",
    "Aarch64EFISystemdBoot",
    "ArmEFIGRUB",
    "EFIBase",
    "EFISystemdBoot",
    "X64EFISystemdBoot"
]


class EFIBase:
    """A base class for EFI-based boot loaders."""

    @property
    def efi_config_dir(self):
        return "/boot/" + self._efi_config_dir

    @property
    def _efi_config_dir(self):
        return "efi/EFI/{}".format(conf.bootloader.efi_dir)

    def get_fw_platform_size(self):
        try:
            with open("/sys/firmware/efi/fw_platform_size", "r") as f:
                value = f.readline().strip()
        except OSError:
            log.info("Reading /sys/firmware/efi/fw_platform_size failed, "
                     "defaulting to 64-bit install.")
            value = '64'
        return value

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

        # Add replace_utf_decode_errors=True to kwargs
        # to avoid decoding errors with non-utf8 characters
        kwargs["replace_utf_decode_errors"] = True

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
            create_method, "-w", "-L", get_product_name().split("-")[0],  # pylint: disable=no-member
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
                # keep only the name, if verbose output is default in this version
                _product = _product.split("\t")[0]
            except ValueError:
                continue

            if _product == get_product_name().split("-")[0]:           # pylint: disable=no-member
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
    _packages_common = ["efibootmgr", "grub2-tools", "grub2-tools-extra", "grubby" ]
    stage2_is_valid_stage1 = False
    stage2_bootable = False

    _is_32bit_firmware = False

    def __init__(self):
        super().__init__()
        self._packages64 = [ "grub2-efi-x64", "shim-x64" ]

        if self.get_fw_platform_size() == '32':
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


class EFISystemdBoot(EFIBase, SystemdBoot):
    """EFI Systemd-boot"""
    _packages_common = ["efibootmgr", "systemd-udev", "systemd-boot", "sdubby"]
    _packages64 = []

    def __init__(self):
        super().__init__()

        if self.get_fw_platform_size() == '32':
            # not supported try a different bootloader
            log.error("efi.py: systemd-boot is not supported on 32-bit platforms")
            raise BootLoaderError(_("Systemd-boot is not supported on this platform"))

    @property
    def packages(self):
        return self._packages64 + self._packages_common

    @property
    def efi_config_file(self):
        """ Full path to EFI configuration file. """
        return join_paths(self.efi_config_dir, self._config_file)

    def check(self):
        """Verify the bootloader configuration."""
        # Force the resolution order to run the systemd-boot check.
        return SystemdBoot.check(self) and EFIBase.check(self)

    def write_config(self):
        """ Write the config settings to config file (ex: grub.cfg) not needed for systemd. """
        config_path = join_paths(conf.target.system_root, self.efi_config_file)

        log.info("efi.py: (systemd) write_config systemd : %s ", config_path)

        super().write_config()

    def install(self, args=None):
        log.info("efi.py: (systemd) install")
        # force the resolution order, we don't want to:
        #   efibootmgr remove old "fedora"
        #   or use efiboot mgr to install a new one
        # lets just use `bootctl install` directly.
        # which will fix the efi boot variables too.
        SystemdBoot.install(self)


class Aarch64EFIGRUB(EFIGRUB):
    _serial_consoles = ["ttyAMA", "ttyS"]
    _efi_binary = "\\shimaa64.efi"

    def __init__(self):
        super().__init__()
        self._packages64 = ["grub2-efi-aa64", "shim-aa64", "grub2-efi-aa64-cdboot"]


class Aarch64EFISystemdBoot(EFISystemdBoot):
    _serial_consoles = ["ttyAMA", "ttyS"]
    _efi_binary = "\\systemd-bootaa64.efi"

    def __init__(self):
        super().__init__()
        self._packages64 = []

class X64EFISystemdBoot(EFISystemdBoot):
    _efi_binary = "\\systemd-bootx64.efi"

    def __init__(self):
        super().__init__()
        self._packages64 = []



class ArmEFIGRUB(EFIGRUB):
    _serial_consoles = ["ttyAMA", "ttyS"]
    _efi_binary = "\\grubarm.efi"

    def __init__(self):
        super().__init__()
        self._packages32 = ["grub2-efi-arm"]
        self._is_32bit_firmware = True


class RISCV64EFIGRUB(EFIGRUB):
    _serial_consoles = ["ttyS"]
    _efi_binary = "\\grubriscv64.efi"

    def __init__(self):
        super().__init__()
        self._packages64 = ["grub2-efi-riscv64"]
