#
# Copyright (C) 2018  Red Hat, Inc.
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

from mock import Mock, patch

from pyanaconda.platform import Platform
from pyanaconda.storage.partspec import PartSpec
from pyanaconda.storage.partitioning import _get_platform_specific_partitioning, \
    _complete_partitioning_requests, _filter_default_partitions


class PartitioningTestCase(unittest.TestCase):

    def get_platform_specific_partitioning_test(self):
        requests = _get_platform_specific_partitioning(Platform(), [PartSpec("/")])
        self.assertEqual(["/boot", "/"], [spec.mountpoint for spec in requests])

    def complete_partitioning_requests_test(self):

        def get_fstype(mountpoint):
            if mountpoint == "/boot":
                return "ext4"

            return "xfs"

        storage = Mock()
        storage.get_fstype = get_fstype

        requests = _complete_partitioning_requests(storage, [PartSpec("/boot"), PartSpec("/")])
        self.assertEqual(["ext4", "xfs"], [spec.fstype for spec in requests])

    @patch("pyanaconda.dbus.DBus.get_proxy")
    def filter_all_default_partitioning_test(self, proxy_getter):
        proxy = Mock()
        proxy_getter.return_value = proxy

        proxy.NoHome = True
        proxy.NoBoot = True
        proxy.NoSwap = True

        requests = _filter_default_partitions(
            [PartSpec("/boot"), PartSpec("/"), PartSpec("/home"), PartSpec(fstype="swap")]
        )

        self.assertEqual(["/"], [spec.mountpoint for spec in requests])

    @patch("pyanaconda.dbus.DBus.get_proxy")
    def filter_none_default_partitioning_test(self, proxy_getter):
        proxy = Mock()
        proxy_getter.return_value = proxy

        proxy.NoHome = False
        proxy.NoBoot = False
        proxy.NoSwap = False

        requests = _filter_default_partitions(
            [PartSpec("/boot"), PartSpec("/"), PartSpec("/home"), PartSpec(fstype="swap")]
        )

        self.assertEqual(
            ["/boot", "/", "/home", "swap"], [spec.mountpoint or spec.fstype for spec in requests]
        )
