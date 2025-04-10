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
from unittest.case import TestCase

from pyanaconda.modules.payloads.base.utils import sort_kernel_version_list


class PayloadBaseUtilsTest(TestCase):
    def test_sort_kernel_version_list(self):
        """Test the sort_kernel_version_list function."""
        # Test fake versions.
        kernel_version_list = [
            '9.1.1-100.f1',
            '10.1.1-100.f1',
            '1.9.1-100.f1',
            '1.10.1-100.f1',
            '1.1.9-100.f1',
            '1.1.10-100.f1',
            '1.1.1-999.f1',
            '1.1.1-1000.f1',
            '1.1.1-100.f1',
            '1.1.1-100.f2',
        ]

        sort_kernel_version_list(kernel_version_list)
        assert kernel_version_list == [
            '1.1.1-100.f1',
            '1.1.1-100.f2',
            '1.1.1-999.f1',
            '1.1.1-1000.f1',
            '1.1.9-100.f1',
            '1.1.10-100.f1',
            '1.9.1-100.f1',
            '1.10.1-100.f1',
            '9.1.1-100.f1',
            '10.1.1-100.f1'
        ]

        # Test real versions.
        kernel_version_list = [
            '5.8.16-200.fc32.x86_64',
            '5.8.18-200.fc32.x86_64',
            '5.10.0-0.rc4.78.fc34.x86_64',
            '5.9.8-100.fc33.x86_64',
            '5.8.18-300.fc33.x86_64',
            '5.8.15-201.fc32.x86_64',
            '5.9.8-200.fc33.x86_64',
        ]

        sort_kernel_version_list(kernel_version_list)
        assert kernel_version_list == [
            '5.8.15-201.fc32.x86_64',
            '5.8.16-200.fc32.x86_64',
            '5.8.18-200.fc32.x86_64',
            '5.8.18-300.fc33.x86_64',
            '5.9.8-100.fc33.x86_64',
            '5.9.8-200.fc33.x86_64',
            '5.10.0-0.rc4.78.fc34.x86_64'
        ]
