# -*- coding: utf-8 -*-
#
# Copyright (C) 2014  Red Hat, Inc.
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
# Red Hat Author(s): Radek Vykydal <rvykydal@redhat.com>

from pyanaconda import nm
import unittest
import socket

class UtilityFunctionsTests(unittest.TestCase):

    def ipv6_address_convert_test(self):
        addresses = ["::",
                     "ef:ef:eeef:ef:ef:eeef:efff:ef"]
        for address in addresses:
            self.assertEqual(nm.nm_dbus_ay_to_ipv6(nm.nm_ipv6_to_dbus_ay(address)),
                            address)

        self.assertEqual(nm.nm_ipv6_to_dbus_ay("ef:ef:eeef:ef:ef:eeef:efff:ef"),
                         [0, 239, 0, 239, 238, 239, 0, 239, 0, 239, 238, 239, 239, 255, 0, 239])

    def ipv4_address_convert_test(self):
        addresses = ["192.168.102.1"]
        for address in addresses:
            self.assertEqual(nm.nm_dbus_int_to_ipv4(nm.nm_ipv4_to_dbus_int(address)),
                            address)

        # The result will be 23505088 little-endian or 3232261633 big-endian
        self.assertEqual(nm.nm_ipv4_to_dbus_int("192.168.102.1"),
                         socket.ntohl(3232261633))

