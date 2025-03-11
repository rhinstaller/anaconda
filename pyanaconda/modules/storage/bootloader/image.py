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

__all__ = ["BootLoaderImage", "LinuxBootLoaderImage"]


class BootLoaderImage:
    """A base class for boot loader images.

    Suitable for non-linux OS images.
    """

    def __init__(self, device=None, label=None):
        """Initialize the image.

        :param device: an instance of StorageDevice
        :param label: a label string
        """
        self.label = label
        self.device = device


class LinuxBootLoaderImage(BootLoaderImage):
    """Linux-OS image."""

    def __init__(self, device=None, label=None, version=None):
        """Initialize the image.

        :param device: an instance of StorageDevice
        :param label: a label string
        :param version: a kernel version string
        """
        super().__init__(device=device, label=label)
        self.label = label
        self.device = device
        self.version = version
        self._kernel = None
        self._initrd = None

    @property
    def kernel(self):
        """Kernel filename.

        :return: a filename string
        """
        filename = self._kernel
        if self.version and not filename:
            filename = "vmlinuz-%s" % self.version
        return filename

    @property
    def initrd(self):
        """Initrd filename.

        :return: a filename string
        """
        filename = self._initrd
        if self.version and not filename:
            filename = "initramfs-%s.img" % self.version
        return filename
