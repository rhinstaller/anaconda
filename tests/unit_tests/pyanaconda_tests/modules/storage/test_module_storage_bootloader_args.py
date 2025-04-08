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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import unittest

from pyanaconda.modules.storage.bootloader.base import BootLoaderArguments


class BootLoaderArgsTestCase(unittest.TestCase):

    def test_add(self):
        """BootLoaderArguments.add reorders things as expected."""
        args = BootLoaderArguments()

        args.add("first")
        args.add("second")
        assert str(args) == "first second"
        assert list(args) == ["first", "second"]

        args.add("first")
        assert str(args) == "second first"
        assert list(args) == ["second", "first"]

    def test_update(self):
        """BootLoaderArguments.update reorders things as expected."""
        args = BootLoaderArguments()

        args.update(["one", "two", "three"])
        args.update("abc")
        assert str(args) == "one two three a b c"
        args.update(["three", "two"])
        assert str(args) == "one a b c three two"

    def test_ip_merge(self):
        """BootLoaderArguments.__str__ reorders ip= as expected."""
        args = BootLoaderArguments()
        args.update(["start", "blah"])
        args.update(["ip=ens0p3:dhcp6", "ip=::::tester::dhcp", "ip=ens0p3:dhcp"])
        args.add("end")
        assert list(args) == \
            ["start", "blah", "ip=ens0p3:dhcp6", "ip=::::tester::dhcp", "ip=ens0p3:dhcp", "end"]
        assert str(args) == \
            "start blah ip=::::tester::dhcp end ip=ens0p3:dhcp,dhcp6"
        assert list(args) == \
            ["start", "blah", "ip=::::tester::dhcp", "end", "ip=ens0p3:dhcp,dhcp6"]
