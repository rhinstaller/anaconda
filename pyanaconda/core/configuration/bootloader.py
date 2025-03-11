#
# Copyright (C) 2018 Red Hat, Inc.
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
#  Author(s):  Vendula Poncova <vponcova@redhat.com>
#
from enum import Enum

from pyanaconda.core.configuration.base import Section


class BootloaderType(Enum):
    """Type of the bootloader."""
    DEFAULT  = "DEFAULT"
    EXTLINUX = "EXTLINUX"
    SDBOOT   = "SDBOOT"


class BootloaderSection(Section):
    """The Bootloader section."""

    @property
    def type(self):
        """Type of the bootloader.

        Supported values:

            DEFAULT   Choose the type by platform.
            EXTLINUX  Use extlinux as the bootloader.
            SDBOOT    Use systemd-boot as the bootloader.

        :return: an instance of BootloaderType
        """
        return self._get_option("type", BootloaderType)

    @property
    def efi_dir(self):
        """Name of the EFI directory."""
        return self._get_option("efi_dir", str)

    @property
    def menu_auto_hide(self):
        """Hide the GRUB menu."""
        return self._get_option("menu_auto_hide", bool)

    @property
    def nonibft_iscsi_boot(self):
        """Are non-iBFT iSCSI disks allowed?

        The option allows to place boot loader on iSCSI devices
        which were not configured in iBFT.
        """
        return self._get_option("nonibft_iscsi_boot", bool)

    @property
    def preserved_arguments(self):
        """Arguments preserved from the installation system.

        :return: a list of kernel arguments
        """
        return self._get_option("preserved_arguments", str).split()
