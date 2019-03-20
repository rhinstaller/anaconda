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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.bootloader.base import BootLoaderError
from pyanaconda.core.constants import BOOTLOADER_TYPE_EXTLINUX
from pyanaconda.modules.common.constants.objects import BOOTLOADER
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda import platform

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["get_bootloader", "get_bootloader_class", "BootLoaderError"]


def get_bootloader_class(platform_class=None):
    """Get the bootloader class for the given platform.

    We will use the current platform by default.

    :param platform_class: a type of a platform or None
    :return: a type of a bootloader
    """
    # Get the type of the current platform.
    if not platform_class:
        platform_class = platform.platform.__class__

    # Get the type of the bootloader.
    if platform_class is platform.X86:
        from pyanaconda.bootloader.grub2 import GRUB2
        return GRUB2

    if platform_class is platform.EFI:
        from pyanaconda.bootloader.efi import EFIGRUB
        return EFIGRUB

    if platform_class is platform.MacEFI:
        from pyanaconda.bootloader.efi import MacEFIGRUB
        return MacEFIGRUB

    if platform_class is platform.PPC:
        from pyanaconda.bootloader.grub2 import GRUB2
        return GRUB2

    if platform_class is platform.IPSeriesPPC:
        from pyanaconda.bootloader.grub2 import IPSeriesGRUB2
        return IPSeriesGRUB2

    if platform_class is platform.S390:
        from pyanaconda.bootloader.zipl import ZIPL
        return ZIPL

    if platform_class is platform.Aarch64EFI:
        from pyanaconda.bootloader.efi import Aarch64EFIGRUB
        return Aarch64EFIGRUB

    if platform_class is platform.ARM:
        from pyanaconda.bootloader.extlinux import EXTLINUX
        return EXTLINUX

    if platform_class is platform.ArmEFI:
        from pyanaconda.bootloader.efi import ArmEFIGRUB
        return ArmEFIGRUB

    from pyanaconda.bootloader.base import BootLoader
    return BootLoader


def get_bootloader():
    bootloader_proxy = STORAGE.get_proxy(BOOTLOADER)
    platform_name = platform.platform.__class__.__name__

    if bootloader_proxy.BootloaderType == BOOTLOADER_TYPE_EXTLINUX:
        from pyanaconda.bootloader.extlinux import EXTLINUX
        cls = EXTLINUX
    else:
        cls = get_bootloader_class()

    log.info("bootloader %s on %s platform", cls.__name__, platform_name)
    return cls()
