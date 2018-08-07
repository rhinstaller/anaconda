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
from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class MountPoint(object):
    """Specification of a mount point assignment."""

    def __init__(self):
        self._device = ""
        self._mount_point = ""
        self._mount_options = ""
        self._reformat = False
        self._new_format = ""
        self._format_options = ""

    @property
    def device(self):
        """The block device to mount."""
        return self._device

    def set_device(self, device):
        """Set the block device to mount.

        :param device: a device specification
        """
        self._device = device

    @property
    def mount_point(self):
        """Mount point."""
        return self._mount_point

    def set_mount_point(self, mount_point):
        """Set the mount point.

        Set where the device will be mounted.
        For example: '/', '/home', 'none'

        :param mount_point: a path to a mount point or 'none'
        """
        self._mount_point = mount_point

    @property
    def mount_options(self):
        """Mount options for /etc/fstab."""
        return self._mount_options

    def set_mount_options(self, options):
        """Set mount options for /etc/fstab.

        Specifies a free form string of options to be used when
        mounting the filesystem. This string will be copied into
        the /etc/fstab file of the installed system.

        :param options: a string with options
        """
        self._mount_options = options

    @property
    def reformat(self):
        """Should the device be reformatted?"""
        return self._reformat

    def set_reformat(self, reformat):
        """Should the device be reformatted?

        :param reformat: True or False
        """
        self._reformat = reformat

    @property
    def new_format(self):
        """New format of the device."""
        return self._new_format

    def set_new_format(self, new_format):
        """Set a new format of the device.

        For example: 'xfs'

        :param new_format: a specification of the format
        """
        self._new_format = new_format

    @property
    def format_options(self):
        """Additional format options."""
        return self._format_options

    def set_format_options(self, options):
        """Set additional format options.

        Specifies additional parameters to be passed to the mkfs
        program that makes a filesystem on this partition.

        :param options: a string with options
        """
        self._format_options = options

    def __str__(self):
        return self._get_summary()

    def __repr__(self):
        return self._get_summary()

    def _get_summary(self):
        return " ".join(filter(None, (
            self._mount_point_to_str(),
            self._mount_options_to_str(),
            self._format_to_str(),
            self._format_options_to_str(),
        )))

    def _mount_point_to_str(self):
        return "{} on {}".format(self.device, self.mount_point)

    def _mount_options_to_str(self):
        if not self.mount_options:
            return ""

        return "({})".format(self.mount_options)

    def _format_to_str(self):
        if not self.reformat:
            return ""

        return "type {}*".format(self.new_format or '?')

    def _format_options_to_str(self):
        if not self.reformat or not self.format_options:
            return ""

        return "({})".format(self.format_options)
