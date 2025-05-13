#
# Copyright (C) 2020  Red Hat, Inc.
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
import unittest
from unittest.mock import patch

import pytest
from blivet.devicelibs import raid
from blivet.size import Size

from pyanaconda.modules.storage.partitioning.specification import PartSpec
from pyanaconda.modules.storage.platform import (
    ARM,
    EFI,
    PS3,
    S390,
    X86,
    Aarch64EFI,
    IPSeriesPPC,
    NewWorldPPC,
    PowerNV,
    get_platform,
)


class PlatformTestCase(unittest.TestCase):
    """Test the platform classes."""

    def setUp(self):
        """Set up the test."""
        self.maxDiff = None

    def _reset_arch(self, arch):
        """Reset the arch module."""
        arch.is_ppc.return_value = False
        arch.is_s390.return_value = False
        arch.is_efi.return_value = False
        arch.is_mactel.return_value = False
        arch.is_aarch64.return_value = False
        arch.is_arm.return_value = False
        arch.is_x86.return_value = False
        arch.is_arm.return_value = False

    def _check_platform(self, platform_cls, packages=None, non_linux_format_types=None):
        """Check the detected platform."""
        if packages is None:
            packages = []

        if non_linux_format_types is None:
            non_linux_format_types = []

        platform = get_platform()
        assert platform.__class__ == platform_cls
        assert platform.packages == packages
        assert platform.non_linux_format_types == non_linux_format_types

    def _check_partitions(self, *partitions):
        """Check the platform-specific partitions."""
        platform = get_platform()
        assert platform.partitions == list(partitions)

    def _check_constraints(self, descriptions, constraints, error_message):
        """Check the platform-specific constraints."""
        all_constraints = {
            "device_types": [],
            "format_types": [],
            "mountpoints": [],
            "max_end": None,
            "raid_levels": [],
            "raid_metadata": [],
        }
        all_constraints.update(constraints)

        platform = get_platform()
        assert platform.stage1_descriptions == descriptions
        assert platform.stage1_constraints == all_constraints
        assert platform.stage1_suggestion == error_message

    @patch("pyanaconda.modules.storage.platform.arch")
    def test_x86(self, arch):
        """Test the x86 platform."""
        self._reset_arch(arch)
        arch.is_x86.return_value = True

        self._check_platform(
            platform_cls=X86,
            non_linux_format_types=["vfat", "ntfs", "hpfs"],
        )

        self._check_partitions(
            PartSpec(fstype="biosboot", size=Size("1MiB")),
            PartSpec(mountpoint="/boot", size=Size("1GiB")),
        )

        self._check_constraints(
            constraints={
                "device_types": ["disk"],
            },
            descriptions={
                "disk": "Master Boot Record",
                "partition": "First sector of boot partition",
                "mdarray": "RAID Device"
            },
            error_message=str(
                "You must include at least one MBR- or "
                "GPT-formatted disk as an install target."
            )
        )

    @patch("pyanaconda.modules.storage.platform.arch")
    def test_s390x(self, arch):
        """Test the s390x platform."""
        self._reset_arch(arch)
        arch.is_s390.return_value = True

        self._check_platform(
            platform_cls=S390
        )

        self._check_partitions(
            PartSpec(mountpoint="/boot", size=Size("1GiB"), lv=False),
        )

        self._check_constraints(
            constraints={
                "device_types": ["disk", "partition"],
            },
            descriptions={
                "dasd": "DASD",
                "zfcp": "zFCP",
                "disk": "Master Boot Record",
                "partition": "First sector of boot partition"
            },
            error_message=str(
                "You must include at least one MBR- or "
                "DASD-formatted disk as an install target."
            )
        )

    @patch("pyanaconda.modules.storage.platform.arch")
    def test_arm(self, arch):
        """Test the ARM platform."""
        self._reset_arch(arch)
        arch.is_arm.return_value = True

        self._check_platform(
            platform_cls=ARM
        )

        self._check_partitions(
            PartSpec(mountpoint="/boot", size=Size("1GiB"))
        )

        self._check_constraints(
            constraints={
                "device_types": ["disk"]
            },
            descriptions={
                "disk": "Master Boot Record",
                "partition": "First sector of boot partition",
            },
            error_message=str(
                "You must include at least one MBR-formatted "
                "disk as an install target."
            )
        )

    @patch("pyanaconda.modules.storage.platform.arch")
    def test_efi(self, arch):
        """Test the EFI platform."""
        self._reset_arch(arch)
        arch.is_efi.return_value = True

        self._check_platform(
            platform_cls=EFI,
            non_linux_format_types=["vfat", "ntfs", "hpfs"]
        )

        self._check_partitions(
            PartSpec(mountpoint="/boot/efi", fstype="efi", grow=True,
                     size=Size("500MiB"), max_size=Size("600MiB")),
            PartSpec(mountpoint="/boot", size=Size("1GiB"))
        )

        self._check_constraints(
            constraints={
                "format_types": ["efi"],
                "device_types": ["partition", "mdarray"],
                "mountpoints": ["/boot/efi"],
                "raid_levels": [raid.RAID1],
                "raid_metadata": ["1.0"]
            },
            descriptions={
                "partition": "EFI System Partition",
                "mdarray": "RAID Device"
            },
            error_message=str(
                "For a UEFI installation, you must include "
                "an EFI System Partition on a GPT-formatted "
                "disk, mounted at /boot/efi."
            )
        )

    @patch("pyanaconda.modules.storage.platform.arch")
    def test_aarch64_efi(self, arch):
        """Test the Aarch64 EFI platform."""
        self._reset_arch(arch)
        arch.is_efi.return_value = True
        arch.is_aarch64.return_value = True

        self._check_platform(
            platform_cls=Aarch64EFI,
            non_linux_format_types=["vfat", "ntfs"]
        )

        self._check_partitions(
            PartSpec(mountpoint="/boot/efi", fstype="efi", grow=True,
                     size=Size("500MiB"), max_size=Size("600MiB")),
            PartSpec(mountpoint="/boot", size=Size("1GiB"))
        )

        self._check_constraints(
            constraints={
                "format_types": ["efi"],
                "device_types": ["partition", "mdarray"],
                "mountpoints": ["/boot/efi"],
                "raid_levels": [raid.RAID1],
                "raid_metadata": ["1.0"]
            },
            descriptions={
                "partition": "EFI System Partition",
                "mdarray": "RAID Device"
            },
            error_message=str(
                "For a UEFI installation, you must include "
                "an EFI System Partition on a GPT-formatted "
                "disk, mounted at /boot/efi."
            )
        )

    @patch("pyanaconda.modules.storage.platform.arch")
    def test_arm_efi(self, arch):
        """Test the ARM EFI platform."""
        self._reset_arch(arch)
        arch.is_efi.return_value = True
        arch.is_aarch64.return_value = True

        self._check_platform(
            platform_cls=Aarch64EFI,
            non_linux_format_types=["vfat", "ntfs"]
        )

        self._check_partitions(
            PartSpec(mountpoint="/boot/efi", fstype="efi", grow=True,
                     size=Size("500MiB"), max_size=Size("600MiB")),
            PartSpec(mountpoint="/boot", size=Size("1GiB"))
        )

        self._check_constraints(
            constraints={
                "format_types": ["efi"],
                "device_types": ["partition", "mdarray"],
                "mountpoints": ["/boot/efi"],
                "raid_levels": [raid.RAID1],
                "raid_metadata": ["1.0"]
            },
            descriptions={
                "partition": "EFI System Partition",
                "mdarray": "RAID Device"
            },
            error_message=str(
                "For a UEFI installation, you must include "
                "an EFI System Partition on a GPT-formatted "
                "disk, mounted at /boot/efi."
            )
        )

    @patch("pyanaconda.modules.storage.platform.arch")
    def test_new_world_ppc(self, arch):
        """Test the New World PPC platform."""
        self._reset_arch(arch)
        arch.is_ppc.return_value = True
        arch.get_ppc_machine.return_value = "PMac"
        arch.get_ppc_mac_gen.return_value = "NewWorld"

        self._check_platform(
            platform_cls=NewWorldPPC,
            non_linux_format_types=["hfs", "hfs+"]
        )

        self._check_partitions(
            PartSpec(fstype="appleboot", size=Size("1MiB")),
            PartSpec(mountpoint="/boot", size=Size("1GiB"))
        )

        self._check_constraints(
            constraints={
                "device_types": ["partition"],
                "format_types": ["appleboot"],

            },
            descriptions={
                "partition": "Apple Bootstrap Partition"
            },
            error_message=str(
                "You must include an Apple Bootstrap "
                "Partition on an Apple Partition Map-"
                "formatted disk."
            )
        )

    @patch("pyanaconda.modules.storage.platform.arch")
    def test_iseries_ppc(self, arch):
        """Test the iSeries PPC platform."""
        self._reset_arch(arch)
        arch.is_ppc.return_value = True
        arch.get_ppc_machine.return_value = "iSeries"

        self._check_platform(
            platform_cls=IPSeriesPPC
        )

        self._check_partitions(
            PartSpec(fstype="prepboot", size=Size("4MiB")),
            PartSpec(mountpoint="/boot", size=Size("1GiB"))
        )

        self._check_constraints(
            constraints={
                "device_types": ["partition"],
                "format_types": ["prepboot"],
                "max_end": Size("4 GiB")
            },
            descriptions={
                "partition": "PReP Boot Partition"
            },
            error_message=str(
                "You must include a PReP Boot Partition "
                "within the first 4GiB of an MBR- "
                "or GPT-formatted disk."
            )
        )

    @patch("pyanaconda.modules.storage.platform.arch")
    def test_pseries_ppc(self, arch):
        """Test the pSeries PPC platform."""
        self._reset_arch(arch)
        arch.is_ppc.return_value = True
        arch.get_ppc_machine.return_value = "pSeries"

        self._check_platform(
            platform_cls=IPSeriesPPC
        )

        self._check_partitions(
            PartSpec(fstype="prepboot", size=Size("4MiB")),
            PartSpec(mountpoint="/boot", size=Size("1GiB"))
        )

        self._check_constraints(
            constraints={
                "device_types": ["partition"],
                "format_types": ["prepboot"],
                "max_end": Size("4 GiB")
            },
            descriptions={
                "partition": "PReP Boot Partition"
            },
            error_message=str(
                "You must include a PReP Boot Partition "
                "within the first 4GiB of an MBR- "
                "or GPT-formatted disk."
            )
        )

    @patch("pyanaconda.modules.storage.platform.arch")
    def test_power_nv_ppc(self, arch):
        """Test the Power NV PPC platform."""
        self._reset_arch(arch)
        arch.is_ppc.return_value = True
        arch.get_ppc_machine.return_value = "PowerNV"

        self._check_platform(
            platform_cls=PowerNV
        )

        self._check_partitions(
            PartSpec(mountpoint="/boot", size=Size("1GiB"))
        )

        self._check_constraints(
            constraints={
                "device_types": ["partition"],
            },
            descriptions={
                "partition": "First sector of boot partition"
            },
            error_message=str(
                "You must include at least one disk as an install target."
            )
        )

    @patch("pyanaconda.modules.storage.platform.arch")
    def test_ps3_ppc(self, arch):
        """Test the PS3 PPC platform."""
        self._reset_arch(arch)
        arch.is_ppc.return_value = True
        arch.get_ppc_machine.return_value = "PS3"

        self._check_platform(
            platform_cls=PS3
        )

        self._check_partitions(
            PartSpec(mountpoint="/boot", size=Size("1GiB"))
        )

        self._check_constraints(
            constraints={
                "device_types": ["partition"],
            },
            descriptions={},
            error_message=str(
                "You must include at least one disk as an install target."
            )
        )

    @patch("pyanaconda.modules.storage.platform.arch")
    def test_unsupported_ppc(self, arch):
        """Test an unsupported PPC platform."""
        self._reset_arch(arch)
        arch.is_ppc.return_value = True
        arch.get_ppc_machine.return_value = "INVALID"

        with pytest.raises(SystemError) as cm:
            get_platform()

        assert str(cm.value) == "Unsupported PPC machine type: INVALID"

    @patch("pyanaconda.modules.storage.platform.arch")
    def test_unsupported_platform(self, arch):
        """Test an unsupported platform."""
        self._reset_arch(arch)

        with pytest.raises(SystemError) as cm:
            get_platform()

        assert str(cm.value) == "Could not determine system architecture."
