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
from pyanaconda.bootloader.base import BootLoaderError, BootLoader
from pyanaconda.bootloader.efi import EFIGRUB, Aarch64EFIGRUB, ArmEFIGRUB, MacEFIGRUB
from pyanaconda.bootloader.extlinux import EXTLINUX
from pyanaconda.bootloader.grub import GRUB
from pyanaconda.bootloader.grub2 import GRUB2, IPSeriesGRUB2
from pyanaconda.bootloader.zipl import ZIPL
from pyanaconda.core.constants import BOOTLOADER_TYPE_EXTLINUX
from pyanaconda.modules.common.constants.objects import BOOTLOADER
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda import platform

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["get_bootloader", "BootLoaderError"]


# every platform that wants a bootloader needs to be in this dict
bootloader_by_platform = {
    platform.X86: GRUB2,
    platform.EFI: EFIGRUB,
    platform.MacEFI: MacEFIGRUB,
    platform.PPC: GRUB2,
    platform.IPSeriesPPC: IPSeriesGRUB2,
    platform.S390: ZIPL,
    platform.Aarch64EFI: Aarch64EFIGRUB,
    platform.ARM: EXTLINUX,
    platform.ArmEFI: ArmEFIGRUB,
}


def get_bootloader():
    bootloader_proxy = STORAGE.get_proxy(BOOTLOADER)
    platform_name = platform.platform.__class__.__name__

    if bootloader_proxy.BootloaderType == BOOTLOADER_TYPE_EXTLINUX:
        cls = EXTLINUX
    else:
        cls = bootloader_by_platform.get(platform.platform.__class__, BootLoader)

    log.info("bootloader %s on %s platform", cls.__name__, platform_name)
    return cls()
