#
# Manual partitioning data.
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

from pyanaconda.dbus.structure import DBusData
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import

__all__ = ["MountPoint"]


class MountPoint(DBusData):
    """Mount point assignment data."""

    def __init__(self):
        self._device_spec = ""
        self._mount_point = ""
        self._mount_options = ""
        self._reformat = False
        self._format_type = ""
        self._format_options = ""

    @property
    def device_spec(self) -> Str:
        """The block device to mount.

        :return: a device specification
        """
        return self._device_spec

    @device_spec.setter
    def device_spec(self, spec: Str):
        """Set the block device to mount."""
        self._device_spec = spec

    @property
    def mount_point(self) -> Str:
        """Mount point.

        Set where the device will be mounted.
        For example: '/', '/home', 'none'

        :return: a path to a mount point or 'none'
        """
        return self._mount_point

    @mount_point.setter
    def mount_point(self, mount_point: Str):
        self._mount_point = mount_point

    @property
    def mount_options(self) -> Str:
        """Mount options for /etc/fstab.

        Specifies a free form string of options to be used when
        mounting the filesystem. This string will be copied into
        the /etc/fstab file of the installed system.

        :return: a string with options
        """
        return self._mount_options

    @mount_options.setter
    def mount_options(self, options: Str):
        self._mount_options = options

    @property
    def reformat(self) -> Bool:
        """Should the device be reformatted?

        :return: True or False
        """
        return self._reformat

    @reformat.setter
    def reformat(self, reformat: Bool):
        self._reformat = reformat

    @property
    def format_type(self) -> Str:
        """New format of the device.

        For example: 'xfs'

        :return: a specification of the format
        """
        return self._format_type

    @format_type.setter
    def format_type(self, format_type: Str):
        self._format_type = format_type

    @property
    def format_options(self) -> Str:
        """Additional format options.

        Specifies additional parameters to be passed to the mkfs
        program that makes a filesystem on this partition.

        :return: a string with options
        """
        return self._format_options

    @format_options.setter
    def format_options(self, options: Str):
        self._format_options = options
