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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
#  Author(s):  Vendula Poncova <vponcova@redhat.com>
#
from enum import Enum

from pyanaconda.core.configuration.base import Section


class PartitioningType(Enum):
    """Type of the default partitioning."""
    SERVER = "SERVER"
    WORKSTATION = "WORKSTATION"
    QUBESOS = "QUBESOS"


class StorageSection(Section):
    """The Storage section."""

    @property
    def dmraid(self):
        """Enable dmraid usage during the installation."""
        return self._get_option("dmraid", bool)

    @property
    def ibft(self):
        """Enable iBFT usage during the installation."""
        return self._get_option("ibft", bool)

    @property
    def gpt(self):
        """Do you prefer creation of GPT disk labels?"""
        return self._get_option("gpt", bool)

    @property
    def multipath_friendly_names(self):
        """Use user friendly names for multipath devices.

        Tell multipathd to use user friendly names when naming devices
        during the installation.
        """
        return self._get_option("multipath_friendly_names", bool)

    @property
    def allow_imperfect_devices(self):
        """Do you want to allow imperfect devices?

        Imperfect devices are for example degraded mdraid arrays.
        This option should be enabled only in the rescue mode.
        """
        return self._get_option("allow_imperfect_devices", bool)

    @property
    def file_system_type(self):
        """Default file system type.

        If no type is specified, we will use whatever Blivet uses by default.

        For example: xfs
        """
        return self._get_option("file_system_type", str)

    @property
    def default_partitioning(self):
        """Default partitioning.

        Valid values:

          SERVER       Choose partitioning for servers.
          WORKSTATION  Choose partitioning for workstations.
          QUBESOS      Choose partitioning for QubesOS.

        :return: an instance of PartitioningType
        """
        return self._get_option("default_partitioning", PartitioningType)

    @property
    def luks_version(self):
        """Default version of LUKS.

        Valid values:

          luks1  Use version 1 by default.
          luks2  Use version 2 by default.

        """
        value = self._get_option("luks_version", str)

        if value not in ("luks1", "luks2"):
            raise ValueError("Invalid value: {}".format(value))

        return value
