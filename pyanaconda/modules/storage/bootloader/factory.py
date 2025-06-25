#
# Copyright (C) 2011 Red Hat, Inc.
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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.storage import platform

log = get_module_logger(__name__)

__all__ = ["BootLoaderFactory"]


class BootLoaderFactory:
    """The boot loader factory."""

    # The default boot loader class.
    _default_class = None

    @classmethod
    def create_boot_loader(cls):
        """Create a boot loader.

        :return: an instance of a boot loader class
        """
        boot_loader_class = cls.get_class()
        boot_loader_instance = boot_loader_class()

        log.info("Created the boot loader %s.", boot_loader_class.__name__)
        return boot_loader_instance

    @classmethod
    def get_class(cls):
        """Get the boot loader class.

        :return: a boot loader class
        """
        return cls.get_default_class() \
            or cls.get_class_by_platform() \
            or cls.get_generic_class()

    @classmethod
    def set_default_class(cls, default_class):
        """Set the default boot loader class.

        :param default_class: a boot loader class or None
        """
        cls._default_class = default_class

    @classmethod
    def get_default_class(cls):
        """Get the default boot loader class.

        :return: a boot loader class or None
        """
        return cls._default_class

    @classmethod
    def get_generic_class(cls):
        """Get the generic boot loader class.

        :return: a boot loader class
        """
        from pyanaconda.modules.storage.bootloader.base import BootLoader
        return BootLoader

    @classmethod
    def get_class_by_name(cls, name):
        """Get the boot loader class for the given name.

        Supported values:
            EXTLINUX
            SDBOOT

        :param name: a boot loader name or None
        :return: a boot loader class or None
        """
        if name == "EXTLINUX":
            from pyanaconda.modules.storage.bootloader.extlinux import EXTLINUX
            return EXTLINUX

        if name == "SDBOOT":
            platform_class = platform.platform.__class__
            if platform_class is platform.Aarch64EFI:
                from pyanaconda.modules.storage.bootloader.efi import (
                    Aarch64EFISystemdBoot,
                )
                return Aarch64EFISystemdBoot
            if platform_class is platform.EFI:
                from pyanaconda.modules.storage.bootloader.efi import X64EFISystemdBoot
                return X64EFISystemdBoot

        return None

    @classmethod
    def get_class_by_platform(cls, platform_class=None):
        """Get the boot loader class for the given platform.

        We will use the current platform by default.

        :param platform_class: a type of a platform or None
        :return: a boot loader class or None
        """
        # Get the type of the current platform.
        if not platform_class:
            platform_class = platform.platform.__class__

        # Get the type of the bootloader.
        if platform_class is platform.X86:
            from pyanaconda.modules.storage.bootloader.grub2 import GRUB2
            return GRUB2

        if platform_class is platform.EFI or platform_class is platform.X86EFI:
            from pyanaconda.modules.storage.bootloader.efi import EFIGRUB
            return EFIGRUB

        if platform_class is platform.PPC:
            from pyanaconda.modules.storage.bootloader.grub2 import GRUB2
            return GRUB2

        if platform_class is platform.IPSeriesPPC:
            from pyanaconda.modules.storage.bootloader.grub2 import IPSeriesGRUB2
            return IPSeriesGRUB2

        if platform_class is platform.PowerNV:
            from pyanaconda.modules.storage.bootloader.grub2 import PowerNVGRUB2
            return PowerNVGRUB2

        if platform_class is platform.S390:
            from pyanaconda.modules.storage.bootloader.zipl import ZIPL
            return ZIPL

        if platform_class is platform.Aarch64EFI:
            from pyanaconda.modules.storage.bootloader.efi import Aarch64EFIGRUB
            return Aarch64EFIGRUB

        if platform_class is platform.ARM:
            from pyanaconda.modules.storage.bootloader.extlinux import EXTLINUX
            return EXTLINUX

        if platform_class is platform.ArmEFI:
            from pyanaconda.modules.storage.bootloader.efi import ArmEFIGRUB
            return ArmEFIGRUB

        if platform_class is platform.RISCV64:
            from pyanaconda.modules.storage.bootloader.extlinux import EXTLINUX
            return EXTLINUX

        if platform_class is platform.RISCV64EFI:
            from pyanaconda.modules.storage.bootloader.efi import RISCV64EFIGRUB
            return RISCV64EFIGRUB

        return None
