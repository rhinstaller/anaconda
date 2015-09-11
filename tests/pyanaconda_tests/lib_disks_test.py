# -*- coding: utf-8 -*-
#
# Copyright (C) 2015  Red Hat, Inc.
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
# Red Hat Author(s): Brian C. Lane <bcl@redhat.com>
#                    Martin Kolman <mkolman@redhat.com>

from pyanaconda.ui.lib.disks import FakeDisk, getDiskDescription
import unittest

class GetDiskDescriptionTests(unittest.TestCase):
    def setUp(self):
        # pylint: disable=attribute-defined-outside-init
        self.model_disk = FakeDisk(name="Fake Disk 1", model="Only Model")
        self.vendor_disk = FakeDisk(name="Fake Disk 2", vendor="Only Vendor")
        self.normal_disk = FakeDisk(name="Fake Disk 3", model="Plane", vendor="Ice Cream")
        self.virtio_disk = FakeDisk(name="Fake Disk 4", vendor="0x1af4")

    def disk_description_test(self):
        """Disk description should be correct"""

        # Just the model, no vendor
        self.assertEqual(getDiskDescription(self.model_disk), "Only Model")

        # Just the vendor, no model
        self.assertEqual(getDiskDescription(self.vendor_disk), "Only Vendor")

        # Both model and vendor
        self.assertEqual(getDiskDescription(self.normal_disk), "Ice Cream Plane")

        # Virtio translation
        self.assertEqual(getDiskDescription(self.virtio_disk), "Virtio Block Device")
