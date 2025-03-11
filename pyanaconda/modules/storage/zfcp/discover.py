#
# Discovery tasks
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
from blivet import blockdev
from blivet.zfcp import zfcp

from pyanaconda.core.regexes import (
    DASD_DEVICE_NUMBER,
    ZFCP_LUN_NUMBER,
    ZFCP_WWPN_NUMBER,
)
from pyanaconda.modules.common.errors.configuration import StorageDiscoveryError
from pyanaconda.modules.common.task import Task


class ZFCPDiscoverTask(Task):
    """A task for discovering a zFCP device"""

    def __init__(self, device_number, wwpn, lun):
        super().__init__()
        self._device_number = device_number
        self._wwpn = wwpn
        self._lun = lun

    @property
    def name(self):
        return "Discover a zFCP"

    def run(self):
        """Run the discovery."""
        self._check_input()
        self._sanitize_input()
        self._discover_device()

    def _check_input(self):
        """Check the input values."""
        if not DASD_DEVICE_NUMBER.match(self._device_number):
            raise StorageDiscoveryError("Incorrect format of the given device number.")

        if self._wwpn and not ZFCP_WWPN_NUMBER.match(self._wwpn):
            raise StorageDiscoveryError("Incorrect format of the given WWPN number.")

        if self._lun and not ZFCP_LUN_NUMBER.match(self._lun):
            raise StorageDiscoveryError("Incorrect format of the given LUN number.")

        # Zfcp automatic LUN scan requires just the device number to be provided by the user.
        # If zfcp auto LUN scan is not available, the user has to specify the device number, WWPN
        # and LUN.
        if not ((self._device_number and not self._wwpn and not self._lun)
                or (self._device_number and self._wwpn and self._lun)):
            raise StorageDiscoveryError(
                "Only device number or device number with WWPN and LUN are allowed."
            )

    def _sanitize_input(self):
        """Sanitize the input values."""
        try:
            self._device_number = blockdev.s390.sanitize_dev_input(self._device_number)
            if self._wwpn:
                self._wwpn = blockdev.s390.zfcp_sanitize_wwpn_input(self._wwpn)
            if self._lun:
                self._lun = blockdev.s390.zfcp_sanitize_lun_input(self._lun)
        except (blockdev.S390Error, ValueError) as err:
            raise StorageDiscoveryError(str(err)) from err

    def _discover_device(self):
        """Discover the device."""
        try:
            zfcp.add_fcp(self._device_number, self._wwpn, self._lun)
        except ValueError as e:
            raise StorageDiscoveryError(str(e)) from e
